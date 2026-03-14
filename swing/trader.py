"""
Swing Trading Module — 4h timeframe strategy running alongside the scalper.
=============================================================================
Uses the same ML pipeline (LightGBM) but trained on 4h candles with:
  - Wider SL/TP (2x ATR stop, 6x ATR target)
  - Lower leverage (5x)
  - Longer holding period (up to 48h)
  - More selective entry (prob > 0.55 for LONG, < 0.45 for SHORT)

Runs as a background thread, scanning every 15 minutes.
Separate trade logs to keep scalper and swing P&L distinct.
"""

from __future__ import annotations
import json
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import lightgbm as lgb
import pandas as pd

from config.settings import (
    SYMBOLS, FEATURE_COLS,
    SWING_ENABLED, SWING_TF, SWING_LOOKBACK_BARS,
    SWING_MODEL_FILE, SWING_LEVERAGE,
    SWING_RISK_PER_TRADE, SWING_SL_ATR_MULT, SWING_TP_ATR_MULT,
    SWING_MIN_SL_PCT, SWING_RESOLVE_TIMEOUT_HOURS,
    SWING_SCAN_INTERVAL_SECONDS, SWING_MAX_OPEN, SWING_MAX_SAME_DIR,
    SWING_COOLDOWN_HOURS, SWING_PROB_LONG, SWING_PROB_SHORT,
    SWING_TARGET_THRESHOLD, SWING_TRADES_LOG, SWING_PNL_LOG,
    STARTING_BALANCE, SIMULATE_FEES, TAKER_FEE_RATE,
)
from data.pipeline import fetch_ohlcv
from features.engineer import build_features

log = logging.getLogger("swing")

# ── State ────────────────────────────────────────────────────────────────────
_open_positions: set[str] = set()
_cooldowns: dict[str, datetime] = {}


def _load_open_positions():
    """Rebuild set of symbols with unresolved swing trades."""
    global _open_positions
    if not SWING_TRADES_LOG.exists():
        _open_positions = set()
        return

    trades = []
    with open(SWING_TRADES_LOG, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                trades.append(json.loads(line))

    resolved_ids = set()
    if SWING_PNL_LOG.exists():
        with open(SWING_PNL_LOG, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    resolved_ids.add(r.get("trade_id", ""))

    _open_positions = set()
    for i, t in enumerate(trades):
        tid = f"{t['timestamp']}_{t['symbol']}_{i}"
        if tid not in resolved_ids:
            _open_positions.add(t["symbol"])


def _count_directions() -> dict:
    """Count open LONG vs SHORT swing trades."""
    counts = {"LONG": 0, "SHORT": 0}
    if not SWING_TRADES_LOG.exists():
        return counts

    trades = []
    with open(SWING_TRADES_LOG, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                trades.append(json.loads(line))

    resolved_ids = set()
    if SWING_PNL_LOG.exists():
        with open(SWING_PNL_LOG, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    resolved_ids.add(r.get("trade_id", ""))

    for i, t in enumerate(trades):
        tid = f"{t['timestamp']}_{t['symbol']}_{i}"
        if tid not in resolved_ids:
            side = t.get("side", "").upper()
            if side == "BUY":
                counts["LONG"] += 1
            elif side == "SELL":
                counts["SHORT"] += 1
    return counts


# ── Model ────────────────────────────────────────────────────────────────────

def train_swing_model(exchange=None):
    """Train a swing-specific model on 4h candle data."""
    log.info("═══ SWING MODEL TRAINING ═══")

    frames = []
    for sym in SYMBOLS:
        try:
            df = fetch_ohlcv(sym, SWING_TF, limit=SWING_LOOKBACK_BARS, exchange=exchange)
            feat = build_features(df)
            if feat is None or feat.empty:
                continue

            # Build swing target: 1.5% move within next 5 candles (20h)
            future_high = df["high"].shift(-1).rolling(5).max().shift(-4)
            future_low = df["low"].shift(-1).rolling(5).min().shift(-4)
            up_move = (future_high - df["close"]) / df["close"]
            down_move = (df["close"] - future_low) / df["close"]
            feat["target"] = ((up_move > SWING_TARGET_THRESHOLD) &
                              (up_move > down_move)).astype(int)

            feat = feat.dropna(subset=["target"] + [c for c in FEATURE_COLS if c in feat.columns])
            feat["symbol"] = sym
            frames.append(feat)
            log.info("  %s: %d rows", sym.replace("/USDT:USDT", ""), len(feat))
        except Exception as e:
            log.error("  %s failed: %s", sym, e)

    if not frames:
        log.error("No data for swing model training")
        return None

    combined = pd.concat(frames, ignore_index=True)
    log.info("Combined: %d rows", len(combined))

    available = [c for c in FEATURE_COLS if c in combined.columns]
    if not available:
        log.error("No feature columns available")
        return None

    # Time-ordered split
    n = len(combined)
    train_end = int(n * 0.70)
    val_end = int(n * 0.85)

    train = combined.iloc[:train_end]
    val = combined.iloc[train_end:val_end]
    test = combined.iloc[val_end:]

    X_train, y_train = train[available], train["target"]
    X_val, y_val = val[available], val["target"]
    X_test, y_test = test[available], test["target"]

    n_pos = int(y_train.sum())
    n_neg = len(y_train) - n_pos
    pos_weight = n_neg / max(n_pos, 1)

    dtrain = lgb.Dataset(X_train, label=y_train)
    dval = lgb.Dataset(X_val, label=y_val, reference=dtrain)

    params = {
        "objective": "binary",
        "metric": "auc",
        "verbosity": -1,
        "learning_rate": 0.02,
        "num_leaves": 16,
        "max_depth": 4,
        "min_child_samples": 30,
        "feature_fraction": 0.6,
        "bagging_fraction": 0.6,
        "bagging_freq": 5,
        "lambda_l1": 0.5,
        "lambda_l2": 5.0,
        "min_gain_to_split": 0.05,
        "max_bin": 127,
        "scale_pos_weight": pos_weight,
    }

    model = lgb.train(
        params, dtrain,
        valid_sets=[dval],
        num_boost_round=500,
        callbacks=[lgb.early_stopping(stopping_rounds=30, verbose=False)],
    )

    # Evaluate
    from sklearn.metrics import roc_auc_score, accuracy_score
    y_prob = model.predict(X_test)
    try:
        auc = roc_auc_score(y_test, y_prob)
        acc = accuracy_score(y_test, (y_prob > 0.5).astype(int))
        log.info("Swing model — Test AUC: %.4f  Acc: %.4f  (test=%d rows)", auc, acc, len(test))
    except ValueError:
        log.warning("Could not compute AUC")

    SWING_MODEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(SWING_MODEL_FILE))
    log.info("Swing model saved → %s", SWING_MODEL_FILE)
    return model


def load_swing_model():
    """Load swing model from disk."""
    if not SWING_MODEL_FILE.exists():
        return None
    return lgb.Booster(model_file=str(SWING_MODEL_FILE))


# ── Trade Execution ──────────────────────────────────────────────────────────

def _place_swing_trade(symbol: str, direction: str, entry_price: float, atr: float) -> bool:
    """Place a swing paper trade with wider SL/TP."""
    sl_dist = max(atr * SWING_SL_ATR_MULT, entry_price * SWING_MIN_SL_PCT)
    tp_dist = sl_dist * (SWING_TP_ATR_MULT / SWING_SL_ATR_MULT)  # maintain R:R ratio

    if direction == "LONG":
        sl = entry_price - sl_dist
        tp = entry_price + tp_dist
        side = "BUY"
    else:
        sl = entry_price + sl_dist
        tp = entry_price - tp_dist
        side = "SELL"

    # Position sizing from risk
    risk_usd = STARTING_BALANCE * SWING_RISK_PER_TRADE
    size = (risk_usd / sl_dist) if sl_dist > 0 else 0
    if size <= 0:
        return False

    # Decimal precision
    if entry_price >= 100:
        dp = 2
    elif entry_price >= 1:
        dp = 4
    else:
        dp = 6

    trade = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "SWING_PAPER",
        "symbol": symbol,
        "side": side,
        "amount": round(size, 8),
        "entry_price": round(entry_price, dp),
        "stop_loss": round(sl, dp),
        "take_profit": round(tp, dp),
        "leverage": SWING_LEVERAGE,
        "status": "PAPER_FILLED",
    }

    SWING_TRADES_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(SWING_TRADES_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(trade) + "\n")

    sl_pct = abs(sl - entry_price) / entry_price * 100
    tp_pct = abs(tp - entry_price) / entry_price * 100
    log.info("  📋 SWING %s %s @ %.4f  SL=%.4f (%.1f%%)  TP=%.4f (%.1f%%)  size=%.6f  risk=$%.2f",
             direction, symbol.replace("/USDT:USDT", ""), entry_price,
             sl, sl_pct, tp, tp_pct, size, risk_usd)
    return True


# ── Resolution ───────────────────────────────────────────────────────────────

def resolve_swing_trades(exchange) -> int:
    """Check open swing trades against candle data for SL/TP hits."""
    if not SWING_TRADES_LOG.exists():
        return 0

    trades = []
    with open(SWING_TRADES_LOG, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                trades.append(json.loads(line))

    resolved_ids = set()
    if SWING_PNL_LOG.exists():
        with open(SWING_PNL_LOG, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    resolved_ids.add(r.get("trade_id", ""))

    unresolved = []
    for i, t in enumerate(trades):
        tid = f"{t['timestamp']}_{t['symbol']}_{i}"
        if tid not in resolved_ids:
            t["_trade_id"] = tid
            unresolved.append(t)

    if not unresolved:
        return 0

    now = datetime.now(timezone.utc)
    resolved_count = 0

    for t in unresolved:
        sym = t["symbol"]
        ep = t.get("entry_price", 0)
        sl = t.get("stop_loss")
        tp = t.get("take_profit")
        side = t["side"].upper()
        amt = t["amount"]
        if sl is None or tp is None:
            continue

        trade_time = datetime.fromisoformat(t["timestamp"])
        age_hours = (now - trade_time).total_seconds() / 3600

        # Fetch recent 4h candles to check SL/TP via high/low
        try:
            df = fetch_ohlcv(sym, SWING_TF, limit=20, exchange=exchange)
        except Exception:
            continue

        cp = float(df["close"].iloc[-1]) if not df.empty else None
        if cp is None:
            continue

        # Check candle high/low for SL/TP hits
        sl_hit = False
        tp_hit = False
        if hasattr(df.index, 'tz') and df.index.tz is not None:
            recent = df[df.index >= trade_time]
        else:
            recent = df[df.index >= trade_time.replace(tzinfo=None)]

        if not recent.empty:
            period_high = recent["high"].max()
            period_low = recent["low"].min()
            if side == "BUY":
                sl_hit = period_low <= sl
                tp_hit = period_high >= tp
            else:
                sl_hit = period_high >= sl
                tp_hit = period_low <= tp

        # Resolution logic
        outcome = None
        pnl = 0.0
        exit_price = cp

        if side == "BUY":
            if sl_hit and tp_hit:
                outcome, pnl, exit_price = "LOSS", (sl - ep) * amt, sl
            elif sl_hit or cp <= sl:
                outcome, pnl, exit_price = "LOSS", (sl - ep) * amt, sl
            elif tp_hit or cp >= tp:
                outcome, pnl, exit_price = "WIN", (tp - ep) * amt, tp
            elif age_hours >= SWING_RESOLVE_TIMEOUT_HOURS:
                pnl = (cp - ep) * amt
                outcome = "WIN" if pnl > 0 else "LOSS"
        else:
            if sl_hit and tp_hit:
                outcome, pnl, exit_price = "LOSS", (ep - sl) * amt, sl
            elif sl_hit or cp >= sl:
                outcome, pnl, exit_price = "LOSS", (ep - sl) * amt, sl
            elif tp_hit or cp <= tp:
                outcome, pnl, exit_price = "WIN", (ep - tp) * amt, tp
            elif age_hours >= SWING_RESOLVE_TIMEOUT_HOURS:
                pnl = (ep - cp) * amt
                outcome = "WIN" if pnl > 0 else "LOSS"

        if outcome is None:
            # Still open
            if side == "BUY":
                unrealized = (cp - ep) * amt
            else:
                unrealized = (ep - cp) * amt
            short_sym = sym.replace("/USDT:USDT", "")
            log.info("  📊 SWING OPEN %s %s: entry=%.4f now=%.4f uPnL=$%+.2f (%.1fh)",
                     side, short_sym, ep, cp, unrealized, age_hours)
            continue

        # Apply fees
        fee = 0.0
        if SIMULATE_FEES:
            fee = ep * amt * TAKER_FEE_RATE * 2
            pnl -= fee

        record = {
            "trade_id": t["_trade_id"],
            "timestamp": t["timestamp"],
            "resolved_at": now.isoformat(),
            "symbol": sym,
            "side": side,
            "amount": amt,
            "entry_price": ep,
            "stop_loss": sl,
            "take_profit": tp,
            "exit_price": round(exit_price, 6),
            "current_price": cp,
            "outcome": outcome,
            "pnl_usd": round(pnl, 2),
            "fee_usd": round(fee, 2),
            "strategy": "SWING",
        }

        SWING_PNL_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(SWING_PNL_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

        icon = "✅" if outcome == "WIN" else "❌"
        short_sym = sym.replace("/USDT:USDT", "")

        if sl_hit or ((side == "BUY" and cp <= sl) or (side == "SELL" and cp >= sl)):
            exit_type = "SL"
            _cooldowns[sym] = now + timedelta(hours=SWING_COOLDOWN_HOURS)
            log.info("  ⏳ %s swing cooldown %dh after SL", short_sym, SWING_COOLDOWN_HOURS)
        elif tp_hit or ((side == "BUY" and cp >= tp) or (side == "SELL" and cp <= tp)):
            exit_type = "TP"
        else:
            exit_type = "TIMEOUT"

        log.info("  %s SWING RESOLVED %s %s: %s @ %.4f → %.4f  PnL=$%+.2f  [%s]",
                 icon, side, short_sym, outcome, ep, exit_price, pnl, exit_type)
        resolved_count += 1

    return resolved_count


# ── Scan Loop ────────────────────────────────────────────────────────────────

def swing_scan(model, exchange) -> int:
    """Scan all markets for swing trade opportunities."""
    _load_open_positions()
    dir_counts = _count_directions()
    num_open = len(_open_positions)
    now = datetime.now(timezone.utc)
    placed = 0

    for sym in SYMBOLS:
        if sym in _open_positions:
            continue
        if num_open >= SWING_MAX_OPEN:
            break

        # Cooldown check
        cd = _cooldowns.get(sym)
        if cd and now < cd:
            continue

        try:
            df = fetch_ohlcv(sym, SWING_TF, limit=SWING_LOOKBACK_BARS, exchange=exchange)
            feat = build_features(df)
            if feat is None or feat.empty:
                continue

            available = [c for c in FEATURE_COLS if c in feat.columns]
            X = feat[available].iloc[-1:]
            prob = model.predict(X)[0]

            if prob >= SWING_PROB_LONG:
                direction = "LONG"
            elif prob <= SWING_PROB_SHORT:
                direction = "SHORT"
            else:
                continue

            # Direction cap
            if dir_counts.get(direction, 0) >= SWING_MAX_SAME_DIR:
                log.info("  ⛔ SWING SKIP %s: max %d %s",
                         sym.replace("/USDT:USDT", ""), SWING_MAX_SAME_DIR, direction)
                continue

            entry_price = float(df["close"].iloc[-1])
            atr = float(feat["atr14"].iloc[-1]) if "atr14" in feat.columns else entry_price * 0.02
            short_sym = sym.replace("/USDT:USDT", "")

            ok = _place_swing_trade(sym, direction, entry_price, atr)
            if ok:
                _open_positions.add(sym)
                dir_counts[direction] = dir_counts.get(direction, 0) + 1
                num_open += 1
                placed += 1
                log.info("  ✅ SWING %s %s (prob=%.3f)", direction, short_sym, prob)

        except Exception as e:
            log.error("  Swing scan error %s: %s", sym, e)

    return placed


# ── Background Thread ────────────────────────────────────────────────────────

def run_swing_loop(exchange):
    """Background thread: train model if needed, then scan/resolve in a loop."""
    if not SWING_ENABLED:
        return

    log.info("═══ SWING TRADER STARTING ═══")
    log.info("  Timeframe: %s | Leverage: %dx | SL: %.1fx ATR | TP: %.1fx ATR",
             SWING_TF, SWING_LEVERAGE, SWING_SL_ATR_MULT, SWING_TP_ATR_MULT)
    log.info("  Max open: %d | Max same dir: %d | Timeout: %dh",
             SWING_MAX_OPEN, SWING_MAX_SAME_DIR, SWING_RESOLVE_TIMEOUT_HOURS)

    # Load or train model
    model = load_swing_model()
    if model is None:
        log.info("No swing model found — training...")
        model = train_swing_model(exchange)
        if model is None:
            log.error("Swing model training failed. Disabling swing trader.")
            return

    scan_count = 0
    while True:
        try:
            # Resolve existing trades first
            resolved = resolve_swing_trades(exchange)
            if resolved > 0:
                log.info("🔄 Swing resolved %d trade(s)", resolved)

            # Scan for new opportunities
            placed = swing_scan(model, exchange)
            scan_count += 1

            if placed > 0 or scan_count % 4 == 0:  # log every 4th scan or when trades placed
                _load_open_positions()
                log.info("Swing scan #%d: %d new trades, %d open positions",
                         scan_count, placed, len(_open_positions))

        except Exception as e:
            log.error("Swing loop error: %s", e)

        time.sleep(SWING_SCAN_INTERVAL_SECONDS)
