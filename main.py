"""
AI Crypto Trading Bot — Self-Updating Main Orchestrator
=========================================================
Automatically collects data, retrains ML model, scans markets,
generates signals, and executes paper trades.

Usage
-----
    # First time: train the model
    py main.py --train

    # Run the full self-updating bot
    py main.py

    # Single scan (no loop)
    py main.py --once

    # Force retrain only
    py main.py --retrain

    # Manual data collection only
    py main.py --collect
"""

from __future__ import annotations
import argparse
import logging
import sys
import threading
import time
from datetime import date, datetime, timezone
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from config.settings import (
    SYMBOLS, ENTRY_TF, SCAN_INTERVAL_SECONDS,
    BYBIT_TESTNET, MODEL_FILE, PAPER_TRADE,
    PROB_LONG_THRESHOLD, PROB_SHORT_THRESHOLD,
    DEFAULT_LEVERAGE, RISK_PER_TRADE, MAX_TRADES_PER_DAY,
    STARTING_BALANCE, MIN_TRADE_GRADE,
    MARKET_MIN_GRADE, TRAILING_STOP_ENABLED,
    TRAILING_TP_BOOST, TRAILING_BOOST_ASSETS,
    COUNTER_TREND_PROB_FLOOR, MAX_SAME_DIRECTION,
    SIMULATE_FEES, TAKER_FEE_RATE,
    RETRAIN_INTERVAL_HOURS, RESOLVE_TIMEOUT_MINUTES,
    MAX_OPEN_TRADES, LOSS_COOLDOWN_MINUTES,
    MIN_ATR_PCT, EARLY_PROFIT_USD, TIME_DECAY_PROFIT_USD, EARLY_LOSS_USD,
)
from data.pipeline import fetch_ohlcv, save_raw, _get_exchange, _get_public_exchange
from data.collector import collect_all, run_collector_loop
from features.engineer import build_features, prepare_dataset
from models.trainer import train_model, load_model, predict
from models.retrainer import retrain_model, should_retrain, run_retrainer_loop
from scanner.engine import scan_markets, print_scan_table
from signals.generator import generate_signal, Signal
from risk_management.manager import RiskManager, RiskState
from execution.engine import Executor

# ── Logging Setup ────────────────────────────────────────────────────────────

LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
log_file = LOG_DIR / f"bot_{datetime.now(timezone.utc).strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding="utf-8"),
    ],
)
log = logging.getLogger("bot")


# ── Banner ───────────────────────────────────────────────────────────────────

BANNER = r"""
╔══════════════════════════════════════════════════════════════╗
║       AI CRYPTO TRADING BOT v4.0 — SELF-UPDATING ENGINE     ║
║       Bybit Perpetual Futures — {mode:<8s}                   ║
║       Paper Trade: {paper:<4s}                                  ║
║                                                              ║
║  Markets : BTC  ETH  SOL  BNB  XRP  DOGE  ADA  AVAX         ║
║  Strategy: ML + VWAP + Bollinger + Hurst + Kelly Criterion   ║
║  Auto    : Data Collection + Model Retraining + Scanner      ║
║  Risk    : Kelly Criterion (fractional) | 10x lev            ║
╚══════════════════════════════════════════════════════════════╝
"""


# ── Training Mode ────────────────────────────────────────────────────────────

def do_train():
    """Download data for all symbols, build features, train model."""
    log.info("═══ TRAINING MODE ═══")
    import pandas as pd

    pub_exchange = _get_public_exchange()
    frames = []

    for sym in SYMBOLS:
        log.info("Fetching training data for %s …", sym)
        try:
            df = fetch_ohlcv(sym, ENTRY_TF, limit=1000, exchange=pub_exchange)
            save_raw(df, sym, ENTRY_TF)
            dataset = prepare_dataset(df)
            dataset["symbol"] = sym
            frames.append(dataset)
            log.info("  → %d usable rows", len(dataset))
        except Exception as e:
            log.error("  ✗ Failed for %s: %s", sym, e)
        time.sleep(0.5)

    if not frames:
        log.error("No data fetched. Check API keys and network.")
        return

    combined = pd.concat(frames, ignore_index=True)
    log.info("Combined dataset: %d rows", len(combined))

    model = train_model(combined)
    log.info("═══ TRAINING COMPLETE ═══")


# ── Data Collection Mode ────────────────────────────────────────────────────

def do_collect():
    """One-shot data collection for all symbols."""
    log.info("═══ DATA COLLECTION ═══")
    pub_exchange = _get_public_exchange()
    results = collect_all(pub_exchange)
    for sym, count in results.items():
        log.info("  %s: %d bars saved", sym.replace("/USDT:USDT", ""), count)
    log.info("═══ COLLECTION COMPLETE ═══")


# ── Auto-Resolve Paper Trades ────────────────────────────────────────────────

def _auto_resolve(exchange) -> int:
    """
    Smart exit resolution — closes trades based on P&L thresholds, not just SL/TP.
    
    Exit priority (smart exits FIRST, then disaster SL/TP):
      1. PROFIT TAKE: close if raw P&L ≥ $1.00 + fees
      2. EARLY STOP: close if raw P&L ≤ -$2.50
      3. TIME TAKE: after 10 min, close if raw P&L ≥ $0.10 + fees
      4. HARD SL/TP: disaster stops only (0.40%+ SL)
      5. TIMEOUT: after 30 min, force close at market
    """
    import json
    trades_file = ROOT / "logs" / "paper_trades.jsonl"
    pnl_file = ROOT / "logs" / "paper_pnl.jsonl"
    if not trades_file.exists():
        return 0

    trades = []
    with open(trades_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                trades.append(json.loads(line))

    resolved_ids = set()
    if pnl_file.exists():
        with open(pnl_file, "r", encoding="utf-8") as f:
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

    # Fetch live prices AND recent candle data
    symbols = list(set(t["symbol"] for t in unresolved))
    prices = {}
    candle_data = {}
    for sym in symbols:
        try:
            ticker = exchange.fetch_ticker(sym)
            prices[sym] = float(ticker["last"])
        except Exception as e:
            log.warning("  ⚠ fetch_ticker(%s) failed: %s", sym.replace('/USDT:USDT', ''), e)
        try:
            from data.pipeline import fetch_ohlcv
            from config.settings import ENTRY_TF
            df = fetch_ohlcv(sym, ENTRY_TF, limit=10, exchange=exchange)
            candle_data[sym] = df
        except Exception:
            pass

    resolved_count = 0
    now = datetime.now(timezone.utc)

    for t in unresolved:
        sym = t["symbol"]
        if sym not in prices:
            continue
        cp = prices[sym]
        ep = t.get("entry_price", cp)
        sl = t.get("stop_loss")
        tp = t.get("take_profit")
        side = t["side"].upper()
        amt = t["amount"]
        if sl is None or tp is None:
            continue

        trade_time = datetime.fromisoformat(t["timestamp"])
        age_minutes = (now - trade_time).total_seconds() / 60

        # Calculate unrealized P&L (raw, before fees)
        if side == "BUY":
            raw_pnl = (cp - ep) * amt
        else:
            raw_pnl = (ep - cp) * amt

        # Calculate fee
        fee = ep * amt * TAKER_FEE_RATE * 2 if SIMULATE_FEES else 0.0
        unrealized_net = raw_pnl - fee

        # Check candle data for hard SL/TP hits
        sl_hit = False
        tp_hit = False
        if sym in candle_data:
            df = candle_data[sym]
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

        # ────── SMART EXIT LOGIC ──────
        # Smart exits control everything. Hard SL/TP is disaster-only backup.
        outcome = None
        exit_price = cp
        exit_type = "TIMEOUT"

        # Priority 1: Early profit take — raw P&L covers fees + nets $2.00
        if raw_pnl >= (EARLY_PROFIT_USD + fee):
            outcome = "WIN"
            exit_type = "PROFIT_TAKE"

        # Priority 2: Early loss cut — raw P&L loss exceeds $2.50
        elif raw_pnl <= EARLY_LOSS_USD:
            outcome = "LOSS"
            exit_type = "EARLY_STOP"

        # Priority 3: Time decay — after 10 min, take any profit ≥ $0.75 net
        elif age_minutes >= 10 and raw_pnl >= (TIME_DECAY_PROFIT_USD + fee):
            outcome = "WIN"
            exit_type = "TIME_TAKE"

        # Priority 4: Hard SL/TP — disaster stops only (SL at 0.40%+)
        elif tp_hit and not sl_hit:
            outcome = "WIN"
            exit_price = tp
            exit_type = "TP"
        elif sl_hit:
            outcome = "LOSS"
            exit_price = sl
            exit_type = "SL"

        # Priority 5: Timeout — after 20 min, force close
        elif age_minutes >= RESOLVE_TIMEOUT_MINUTES:
            outcome = "WIN" if raw_pnl > 0 else "LOSS"
            exit_type = "TIMEOUT"

        if outcome is None:
            # Still open — log unrealized P&L
            short_sym = sym.replace('/USDT:USDT', '')
            log.info("  📊 OPEN %s %s: entry=%.2f now=%.2f uPnL=$%+.2f net=$%+.2f (%.0fm)",
                     side, short_sym, ep, cp, raw_pnl, unrealized_net, age_minutes)
            continue

        # Calculate final P&L
        if exit_type in ("TP", "SL"):
            if side == "BUY":
                pnl = (exit_price - ep) * amt
            else:
                pnl = (ep - exit_price) * amt
        else:
            pnl = raw_pnl

        if SIMULATE_FEES:
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
            "exit_type": exit_type,
        }
        pnl_file.parent.mkdir(parents=True, exist_ok=True)
        with open(pnl_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

        icon = "✅" if outcome == "WIN" else "❌"
        short_sym = sym.replace('/USDT:USDT', '')
        log.info("  %s RESOLVED %s %s: %s @ %.2f → %.2f  PnL=$%+.2f  [%s]",
                 icon, side, short_sym, outcome, ep, exit_price, pnl, exit_type)

        # Cooldown after real SL hit
        if exit_type == "SL":
            from datetime import timedelta
            _loss_cooldowns[sym] = now + timedelta(minutes=LOSS_COOLDOWN_MINUTES)
            log.info("  ⏳ %s cooldown for %dm after SL", short_sym, LOSS_COOLDOWN_MINUTES)

        resolved_count += 1

    return resolved_count


# ── Scan Cycle ───────────────────────────────────────────────────────────────

# Track open (unresolved) paper positions
_open_positions: set[str] = set()
# Global model reference (can be hot-reloaded)
_current_model = None
_model_lock = threading.Lock()

_open_margin_total: float = 0.0  # total margin across all open positions

# Cooldown tracking: symbol → earliest re-entry time (UTC)
_loss_cooldowns: dict[str, datetime] = {}

# Consecutive loss cooldown: track when it started so we can auto-reset
_consec_cooldown_start: datetime | None = None


def _load_open_positions():
    """Rebuild set of symbols with unresolved paper trades and calc total margin."""
    import json
    global _open_positions, _open_margin_total
    trades_file = ROOT / "logs" / "paper_trades.jsonl"
    pnl_file = ROOT / "logs" / "paper_pnl.jsonl"
    if not trades_file.exists():
        _open_positions = set()
        _open_margin_total = 0.0
        return
    trades = []
    with open(trades_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                trades.append(json.loads(line))
    resolved_ids = set()
    if pnl_file.exists():
        with open(pnl_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    resolved_ids.add(r.get("trade_id", ""))
    _open_positions = set()
    _open_margin_total = 0.0
    for i, t in enumerate(trades):
        trade_id = f"{t['timestamp']}_{t['symbol']}_{i}"
        if trade_id not in resolved_ids:
            _open_positions.add(t["symbol"])
            # Calculate margin for this open position
            ep = t.get("entry_price", 0)
            amt = t.get("amount", 0)
            notional = ep * amt
            _open_margin_total += notional / DEFAULT_LEVERAGE


def _count_open_directions() -> dict:
    """Count how many unresolved trades are LONG vs SHORT."""
    import json
    counts = {"LONG": 0, "SHORT": 0}
    trades_file = ROOT / "logs" / "paper_trades.jsonl"
    pnl_file = ROOT / "logs" / "paper_pnl.jsonl"
    if not trades_file.exists():
        return counts
    trades = []
    with open(trades_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                trades.append(json.loads(line))
    resolved_ids = set()
    if pnl_file.exists():
        with open(pnl_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    resolved_ids.add(r.get("trade_id", ""))
    for i, t in enumerate(trades):
        trade_id = f"{t['timestamp']}_{t['symbol']}_{i}"
        if trade_id not in resolved_ids:
            side = t.get("side", "").lower()
            if side == "buy":
                counts["LONG"] += 1
            elif side == "sell":
                counts["SHORT"] += 1
    return counts


def scan_once(
    executor: Executor,
    risk_mgr: RiskManager,
    model,
    exchange,
) -> list[Signal]:
    """Scan all markets with position limits, direction caps, and cooldowns."""
    signals: list[Signal] = []

    _load_open_positions()

    scan_results = scan_markets(model, exchange, SYMBOLS)
    print_scan_table(scan_results)

    # Count current open directions
    dir_counts = _count_open_directions()
    num_open = len(_open_positions)
    now = datetime.now(timezone.utc)

    for result in scan_results:
        signal = result.signal
        signals.append(signal)

        if signal.direction == "NONE":
            continue

        if signal.symbol in _open_positions:
            continue

        # Gate 1: Max open trades
        if num_open >= MAX_OPEN_TRADES:
            log.info("  ⛔ SKIP %s: max %d open trades reached",
                     signal.symbol.replace('/USDT:USDT', ''), MAX_OPEN_TRADES)
            continue

        # Gate 2: Max same direction
        if dir_counts.get(signal.direction, 0) >= MAX_SAME_DIRECTION:
            log.info("  ⛔ SKIP %s: max %d %s trades reached",
                     signal.symbol.replace('/USDT:USDT', ''), MAX_SAME_DIRECTION, signal.direction)
            continue

        # Gate 3: Loss cooldown per symbol
        cooldown_until = _loss_cooldowns.get(signal.symbol)
        if cooldown_until and now < cooldown_until:
            remaining = (cooldown_until - now).total_seconds() / 60
            log.info("  ⏳ COOLDOWN %s: %.0fm remaining after SL hit",
                     signal.symbol.replace('/USDT:USDT', ''), remaining)
            continue

        placed = _execute_signal(executor, risk_mgr, signal)
        if placed:
            _open_positions.add(signal.symbol)
            dir_counts[signal.direction] = dir_counts.get(signal.direction, 0) + 1
            num_open += 1

    return signals


def _execute_signal(executor: Executor, risk_mgr: RiskManager, signal: Signal) -> bool:
    """Place a trade with ATR-based SL and wider-but-achievable TP."""
    atr = signal.atr if signal.atr > 0 else signal.entry_price * 0.002

    # SL = 1.5x ATR, TP = 2.0x ATR — wide enough to survive 5m noise
    # Smart exits (EARLY_STOP/PROFIT_TAKE) manage exits before SL/TP
    sl_dist = atr * 1.5
    tp_dist = atr * 2.0

    # Floor: SL must be at least 0.40% — 5m noise is 0.05-0.15%, need room
    min_sl_dist = signal.entry_price * 0.004
    if sl_dist < min_sl_dist:
        sl_dist = min_sl_dist
        tp_dist = sl_dist * 2.0  # keep 1:2 ratio

    if signal.direction == "LONG":
        stop_price = signal.entry_price - sl_dist
        tp_price = signal.entry_price + tp_dist
        side = "buy"
    else:
        stop_price = signal.entry_price + sl_dist
        tp_price = signal.entry_price - tp_dist
        side = "sell"

    plan = risk_mgr.size_position(signal.entry_price, stop_price)

    if not plan.allow:
        log.info("  ⛔ BLOCKED: %s", plan.reason)
        return False

    # FULL SIZE — no grade scaling, no min-profit filter
    trade_size = plan.size

    log.info(
        "  📋 TRADE: %s %s  size=%.6f  risk=$%.2f  SL=%.2f  TP=%.2f",
        signal.direction, signal.symbol.replace('/USDT:USDT', ''),
        trade_size, plan.risk_usd, stop_price, tp_price,
    )

    try:
        executor.set_leverage(signal.symbol, plan.leverage)

        if signal.entry_price >= 100:
            dp = 2
        elif signal.entry_price >= 1:
            dp = 4
        else:
            dp = 6

        order = executor.market_order(
            symbol=signal.symbol,
            side=side,
            amount=trade_size,
            stop_loss=round(stop_price, dp),
            take_profit=round(tp_price, dp),
            entry_price=round(signal.entry_price, dp),
        )
        log.info("  ✅ ORDER: %s %s @ %.4f",
                 signal.direction, signal.symbol.replace('/USDT:USDT', ''),
                 signal.entry_price)
        risk_mgr.state.trades_today += 1
        notional = signal.entry_price * trade_size
        risk_mgr.state.open_margin += notional / plan.leverage
        return True
    except Exception as e:
        log.error("  ✗ ORDER FAILED: %s", e)
        return False


# ── Kelly Criterion History Loader ────────────────────────────────────────

def _load_kelly_history(risk_mgr: RiskManager):
    """Load past P&L results from paper_pnl.jsonl for Kelly Criterion."""
    import json
    pnl_file = ROOT / "logs" / "paper_pnl.jsonl"
    if not pnl_file.exists():
        log.info("No trade history for Kelly Criterion — using default risk.")
        return
    count = 0
    with open(pnl_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                r = json.loads(line)
                pnl = r.get("pnl_usd", 0.0)
                risk_mgr.record_result(pnl)
                count += 1
    if count > 0:
        kelly = risk_mgr.kelly_fraction()
        log.info("Kelly Criterion: loaded %d trades → optimal risk = %.2f%%", count, kelly * 100)


def _load_kelly_history_incremental(risk_mgr: RiskManager):
    """Reload resolved P&L into risk manager and sync balance + consecutive losses."""
    import json
    pnl_file = ROOT / "logs" / "paper_pnl.jsonl"
    if not pnl_file.exists():
        return
    risk_mgr._trade_results = []
    total_pnl = 0.0
    consecutive_losses = 0
    daily_pnl = 0.0
    today_str = date.today().isoformat()
    with open(pnl_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                r = json.loads(line)
                pnl = r.get("pnl_usd", 0.0)
                risk_mgr.record_result(pnl)
                total_pnl += pnl
                # Track consecutive losses
                if pnl < 0:
                    consecutive_losses += 1
                else:
                    consecutive_losses = 0
                # Track daily P&L
                resolved_at = r.get("resolved_at", "")
                if resolved_at.startswith(today_str):
                    daily_pnl += pnl
    # Sync balance with actual P&L
    risk_mgr.state.balance = STARTING_BALANCE + total_pnl
    if risk_mgr.state.balance > risk_mgr.state.peak_balance:
        risk_mgr.state.peak_balance = risk_mgr.state.balance
    # Sync consecutive losses so cooldown works correctly
    risk_mgr.state.consecutive_losses = consecutive_losses
    # Sync daily P&L for daily loss cap
    risk_mgr.state.daily_pnl = daily_pnl


# ── Background Threads ──────────────────────────────────────────────────────

def _start_background_threads(exchange):
    """Start background threads for data collection, model retraining, swing trading, and dashboard."""
    # Data collector thread
    collector_thread = threading.Thread(
        target=run_collector_loop,
        args=(exchange,),
        daemon=True,
        name="DataCollector",
    )
    collector_thread.start()
    log.info("📡 Data collector thread started")

    # Model retrainer thread
    retrainer_thread = threading.Thread(
        target=run_retrainer_loop,
        daemon=True,
        name="ModelRetrainer",
    )
    retrainer_thread.start()
    log.info("🔄 Auto-retrainer thread started (every %dh)", RETRAIN_INTERVAL_HOURS)

    # Swing trader thread
    from config.settings import SWING_ENABLED
    swing_thread = None
    if SWING_ENABLED:
        from swing.trader import run_swing_loop
        swing_thread = threading.Thread(
            target=run_swing_loop,
            args=(exchange,),
            daemon=True,
            name="SwingTrader",
        )
        swing_thread.start()
        log.info("📈 Swing trader thread started (4h timeframe)")

    # Dashboard thread — auto-launch on bot start
    def _run_dashboard():
        try:
            from dashboard.app import app, _start_resolver
            _start_resolver()
            import logging as _log
            _log.getLogger("werkzeug").setLevel(_log.WARNING)  # quiet Flask logs
            app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)
        except Exception as e:
            log.warning("Dashboard failed to start: %s", e)

    dashboard_thread = threading.Thread(
        target=_run_dashboard,
        daemon=True,
        name="Dashboard",
    )
    dashboard_thread.start()
    log.info("🌐 Dashboard started → http://localhost:8080")

    return collector_thread, retrainer_thread, dashboard_thread


def _try_reload_model(model):
    """Check if a newer model exists and reload it."""
    try:
        mtime = MODEL_FILE.stat().st_mtime if MODEL_FILE.exists() else 0
        if not hasattr(_try_reload_model, '_last_mtime'):
            _try_reload_model._last_mtime = mtime
            return model
        
        if mtime > _try_reload_model._last_mtime:
            new_model = load_model()
            if new_model is not None:
                _try_reload_model._last_mtime = mtime
                log.info("🔄 Hot-reloaded updated model")
                return new_model
    except Exception as e:
        log.warning("Model reload check failed: %s", e)
    
    return model


# ── Main Loop ────────────────────────────────────────────────────────────────

def run_bot(once: bool = False):
    """Main bot loop with auto data collection and model retraining."""
    mode = "TESTNET" if BYBIT_TESTNET else "LIVE"
    paper = "ON" if PAPER_TRADE else "OFF"
    print(BANNER.format(mode=mode, paper=paper))
    log.info("Starting bot in %s mode (paper_trade=%s) …", mode, paper)

    # Load model
    model = load_model()
    if model is None:
        log.warning("No trained model found. Running initial training...")
        do_train()
        model = load_model()
        if model is None:
            log.error("Training failed. Cannot start bot.")
            sys.exit(1)

    # Init executor & risk state
    executor = Executor()
    try:
        balance = executor.fetch_balance()
        if balance <= 0 and PAPER_TRADE:
            log.info("Balance is $0 — using $%.0f paper balance.", STARTING_BALANCE)
            balance = STARTING_BALANCE
    except Exception as e:
        log.warning("Could not fetch balance (%s). Using default $%.0f.", e, STARTING_BALANCE)
        balance = STARTING_BALANCE

    risk_state = RiskState(balance=balance, peak_balance=balance)
    risk_mgr = RiskManager(risk_state)

    _load_kelly_history(risk_mgr)

    pub_exchange = _get_public_exchange()

    gear = risk_mgr.current_gear()
    log.info("Balance: $%.2f | Gear: %s | Drawdown: %.1f%%",
             balance, gear.get("name", "NORMAL"), risk_mgr._drawdown_pct() * 100)
    log.info("Thresholds: LONG > %.2f | SHORT < %.2f | Min Grade: %s",
             PROB_LONG_THRESHOLD, PROB_SHORT_THRESHOLD, MIN_TRADE_GRADE)
    log.info("Risk: %.0f%% per trade | Max %d trades/day | Max %.0f%% daily loss",
             RISK_PER_TRADE * 100, MAX_TRADES_PER_DAY,
             float(STARTING_BALANCE) * 0.05)

    if once:
        scan_once(executor, risk_mgr, model, pub_exchange)
        log.info("Single scan complete.")
        return

    # Start background threads for auto data collection + retraining + dashboard
    _start_background_threads(pub_exchange)

    # Auto-open dashboard in browser
    import webbrowser
    time.sleep(1.5)  # give Flask a moment to start
    try:
        webbrowser.open("http://localhost:8080")
    except Exception:
        pass

    # Continuous scan loop
    log.info("Entering scan loop (every %ds) …  Press Ctrl+C to stop.", SCAN_INTERVAL_SECONDS)
    scan_count = 0

    try:
        while True:
            today = date.today()
            if today != risk_state.today:
                risk_state.new_day(risk_state.balance)
                log.info("── New day: %s  Balance: $%.2f ──", today, risk_state.balance)
            if today.weekday() == 0 and today != risk_state.week_start:
                risk_state.new_week(risk_state.balance)
                log.info("── New week ──")

            # Hot-reload model if retrainer updated it
            model = _try_reload_model(model)

            # Auto-resolve open paper trades first
            if PAPER_TRADE:
                resolved = _auto_resolve(pub_exchange)
                if resolved > 0:
                    log.info("🔄 Auto-resolved %d trade(s)", resolved)
                # Always sync state (dashboard resolver may have resolved trades)
                _load_open_positions()
                _load_kelly_history_incremental(risk_mgr)
                # Sync trades_today and open_margin with actual open positions
                risk_mgr.state.trades_today = len(_open_positions)
                risk_mgr.state.open_margin = _open_margin_total

            allowed, reason = risk_mgr.can_trade()
            # Fix death spiral: auto-reset consecutive loss cooldown after 30 min
            if not allowed and "Consecutive loss" in reason:
                global _consec_cooldown_start
                now_check = datetime.now(timezone.utc)
                if _consec_cooldown_start is None:
                    _consec_cooldown_start = now_check
                elif (now_check - _consec_cooldown_start).total_seconds() > 1800:  # 30 min
                    risk_mgr.state.consecutive_losses = 0
                    _consec_cooldown_start = None
                    log.info("🔄 Consecutive loss cooldown auto-reset after 30 min")
                    allowed, reason = risk_mgr.can_trade()  # re-check
            elif allowed:
                _consec_cooldown_start = None  # reset timer when trading is allowed

            if not allowed:
                log.info("⛔ Trading paused: %s", reason)
            else:
                signals = scan_once(executor, risk_mgr, model, pub_exchange)
                tradeable = [s for s in signals if s.direction != "NONE" and s.grade != "SKIP"]
                log.info("Scan #%d done. %d signals, %d actionable.",
                         scan_count + 1, len(signals), len(tradeable))

            scan_count += 1
            log.info("Next scan in %ds …", SCAN_INTERVAL_SECONDS)
            time.sleep(SCAN_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        log.info("Bot stopped by user. %d scans completed.", scan_count)


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AI Crypto Trading Bot — Self-Updating Engine")
    parser.add_argument("--train", action="store_true", help="Train the ML model")
    parser.add_argument("--once", action="store_true", help="Run a single scan then exit")
    parser.add_argument("--retrain", action="store_true", help="Force model retrain")
    parser.add_argument("--collect", action="store_true", help="Collect data for all symbols")
    args = parser.parse_args()

    if args.collect:
        do_collect()
    elif args.retrain:
        retrain_model()
    elif args.train:
        do_train()
    else:
        run_bot(once=args.once)


if __name__ == "__main__":
    main()
