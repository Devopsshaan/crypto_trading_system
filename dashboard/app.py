"""
SaaS Trading Dashboard — TradingView-style
============================================
Professional paper-trading dashboard with REST API, real-time charts,
and AWS-ready deployment.

Usage (local):
    py dashboard/app.py

Usage (production):
    gunicorn -c dashboard/gunicorn_conf.py dashboard.app:app
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template, request

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PAPER_LOG = ROOT / "logs" / "paper_trades.jsonl"
PNL_LOG = ROOT / "logs" / "paper_pnl.jsonl"
SWING_TRADES_LOG = ROOT / "logs" / "paper_trades_swing.jsonl"
SWING_PNL_LOG = ROOT / "logs" / "paper_pnl_swing.jsonl"
BOT_LOG_DIR = ROOT / "logs"

STARTING_BALANCE = float(os.environ.get("STARTING_BALANCE", "200"))

# ── Flask App ────────────────────────────────────────────────────────────────
app = Flask(
    __name__,
    template_folder=str(Path(__file__).parent / "templates"),
    static_folder=str(Path(__file__).parent / "static"),
)
app.config["JSON_SORT_KEYS"] = False


# ── Data helpers ─────────────────────────────────────────────────────────────

def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def _bot_status() -> dict:
    # Find today's log file (try both UTC and local date)
    import os, time
    today_utc = datetime.now(timezone.utc).strftime("%Y%m%d")
    today_local = datetime.now().strftime("%Y%m%d")

    log_file = None
    for d in [today_utc, today_local]:
        candidate = BOT_LOG_DIR / f"bot_{d}.log"
        if candidate.exists():
            log_file = candidate
            break

    if log_file is None:
        return {"running": False, "message": "No log file found"}
    try:
        # Simple check: was the file modified in the last 5 minutes?
        mtime = os.path.getmtime(str(log_file))
        age_seconds = time.time() - mtime
        is_recent = age_seconds < 300

        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        last = lines[-1].strip() if lines else ""

        return {"running": is_recent, "message": last[:200], "lines": len(lines)}
    except Exception as e:
        return {"running": False, "message": str(e)}


# ── API Endpoints ────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/summary")
def api_summary():
    """Overall trading metrics (scalper + swing combined)."""
    trades = _load_jsonl(PAPER_LOG)
    pnl_records = _load_jsonl(PNL_LOG)

    # Include swing trades in totals
    swing_trades = _load_jsonl(SWING_TRADES_LOG)
    swing_pnl = _load_jsonl(SWING_PNL_LOG)
    trades = trades + swing_trades
    pnl_records = pnl_records + swing_pnl

    total = len(trades)
    resolved = len(pnl_records)
    pending = total - resolved

    wins = sum(1 for r in pnl_records if r.get("outcome") == "WIN")
    losses = sum(1 for r in pnl_records if r.get("outcome") == "LOSS")
    skips = sum(1 for r in pnl_records if r.get("outcome") == "SKIP")

    total_pnl = sum(r.get("pnl_usd", 0) for r in pnl_records)
    balance = STARTING_BALANCE + total_pnl
    roi = (total_pnl / STARTING_BALANCE) * 100 if STARTING_BALANCE > 0 else 0
    win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
    avg_pnl = total_pnl / resolved if resolved > 0 else 0

    # Best / worst trade
    pnl_values = [r.get("pnl_usd", 0) for r in pnl_records if r.get("outcome") in ("WIN", "LOSS")]
    best_trade = max(pnl_values) if pnl_values else 0
    worst_trade = min(pnl_values) if pnl_values else 0

    # Profit factor
    gross_profit = sum(p for p in pnl_values if p > 0)
    gross_loss = abs(sum(p for p in pnl_values if p < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0

    # Max drawdown
    equity = STARTING_BALANCE
    peak = equity
    max_dd = 0
    for r in pnl_records:
        equity += r.get("pnl_usd", 0)
        peak = max(peak, equity)
        dd = (peak - equity) / peak * 100 if peak > 0 else 0
        max_dd = max(max_dd, dd)

    # Consecutive wins/losses
    max_consec_wins = 0
    max_consec_losses = 0
    cur_w = 0
    cur_l = 0
    for r in pnl_records:
        if r.get("outcome") == "WIN":
            cur_w += 1
            cur_l = 0
            max_consec_wins = max(max_consec_wins, cur_w)
        elif r.get("outcome") == "LOSS":
            cur_l += 1
            cur_w = 0
            max_consec_losses = max(max_consec_losses, cur_l)
        else:
            cur_w = 0
            cur_l = 0

    return jsonify({
        "balance": round(balance, 2),
        "starting_balance": STARTING_BALANCE,
        "total_pnl": round(total_pnl, 2),
        "roi": round(roi, 2),
        "win_rate": round(win_rate, 1),
        "wins": wins,
        "losses": losses,
        "skips": skips,
        "total_trades": total,
        "resolved": resolved,
        "pending": pending,
        "avg_pnl": round(avg_pnl, 2),
        "best_trade": round(best_trade, 2),
        "worst_trade": round(worst_trade, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else "∞",
        "max_drawdown": round(max_dd, 2),
        "max_consec_wins": max_consec_wins,
        "max_consec_losses": max_consec_losses,
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
    })


@app.route("/api/equity")
def api_equity():
    """Equity curve data for the chart."""
    pnl_records = _load_jsonl(PNL_LOG)
    trades = _load_jsonl(PAPER_LOG)
    equity = STARTING_BALANCE

    # Use earliest trade timestamp as starting point, or current time
    if trades:
        start_ts = trades[0].get("timestamp", "")[:19].replace("T", " ")
    else:
        start_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    curve = [{"time": start_ts, "value": equity}]

    for r in pnl_records:
        equity += r.get("pnl_usd", 0)
        ts = r.get("resolved_at", r.get("timestamp", ""))[:19].replace("T", " ")
        curve.append({"time": ts, "value": round(equity, 2)})

    # Always add a "now" point so chart renders with at least 2 points
    now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    if now_ts != curve[-1]["time"]:
        curve.append({"time": now_ts, "value": round(equity, 2)})

    return jsonify(curve)


@app.route("/api/daily")
def api_daily():
    """Daily P&L breakdown."""
    pnl_records = _load_jsonl(PNL_LOG)
    daily = defaultdict(lambda: {"pnl": 0, "wins": 0, "losses": 0, "trades": 0})

    for r in pnl_records:
        day = r.get("timestamp", "")[:10]
        if not day:
            continue
        daily[day]["pnl"] += r.get("pnl_usd", 0)
        daily[day]["trades"] += 1
        if r.get("outcome") == "WIN":
            daily[day]["wins"] += 1
        elif r.get("outcome") == "LOSS":
            daily[day]["losses"] += 1

    result = []
    for day in sorted(daily.keys()):
        d = daily[day]
        wr = (d["wins"] / (d["wins"] + d["losses"]) * 100) if (d["wins"] + d["losses"]) > 0 else 0
        result.append({
            "date": day,
            "pnl": round(d["pnl"], 2),
            "wins": d["wins"],
            "losses": d["losses"],
            "trades": d["trades"],
            "win_rate": round(wr, 1),
        })

    return jsonify(result)


@app.route("/api/trades")
def api_trades():
    """Recent trade history with pagination."""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    per_page = min(per_page, 200)

    trades = _load_jsonl(PAPER_LOG)
    trades.reverse()  # newest first

    total = len(trades)
    start = (page - 1) * per_page
    end = start + per_page
    page_trades = trades[start:end]

    # Enrich with P&L data
    pnl_records = _load_jsonl(PNL_LOG)
    pnl_map = {}
    for r in pnl_records:
        pnl_map[r.get("trade_id", "")] = r

    enriched = []
    for i, t in enumerate(page_trades):
        real_idx = total - 1 - (start + i)
        trade_id = f"{t['timestamp']}_{t['symbol']}_{real_idx}"
        pnl_info = pnl_map.get(trade_id, {})

        enriched.append({
            "timestamp": t["timestamp"][:19].replace("T", " "),
            "symbol": t["symbol"].replace("/USDT:USDT", ""),
            "side": t["side"],
            "amount": t["amount"],
            "entry_price": t.get("entry_price", 0),
            "stop_loss": t.get("stop_loss", 0),
            "take_profit": t.get("take_profit", 0),
            "outcome": pnl_info.get("outcome", "OPEN"),
            "pnl": pnl_info.get("pnl_usd", None),
            "exit_price": pnl_info.get("current_price", None),
        })

    return jsonify({
        "trades": enriched,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    })


@app.route("/api/pnl")
def api_pnl():
    """All resolved P&L records."""
    records = _load_jsonl(PNL_LOG)
    for r in records:
        r["symbol"] = r.get("symbol", "").replace("/USDT:USDT", "")
    records.reverse()
    return jsonify(records)


@app.route("/api/markets")
def api_markets():
    """Per-market performance breakdown (includes open trades)."""
    pnl_records = _load_jsonl(PNL_LOG)
    trades = _load_jsonl(PAPER_LOG)
    markets = defaultdict(lambda: {"pnl": 0, "wins": 0, "losses": 0, "trades": 0, "open": 0})

    # Count open trades per market
    resolved_ids = set()
    for r in pnl_records:
        resolved_ids.add(r.get("trade_id", ""))
    for i, t in enumerate(trades):
        sym = t.get("symbol", "").replace("/USDT:USDT", "")
        trade_id = f"{t['timestamp']}_{t['symbol']}_{i}"
        if trade_id not in resolved_ids:
            markets[sym]["open"] += 1
            markets[sym]["trades"] += 1

    for r in pnl_records:
        sym = r.get("symbol", "").replace("/USDT:USDT", "")
        if not sym:
            continue
        markets[sym]["pnl"] += r.get("pnl_usd", 0)
        markets[sym]["trades"] += 1
        if r.get("outcome") == "WIN":
            markets[sym]["wins"] += 1
        elif r.get("outcome") == "LOSS":
            markets[sym]["losses"] += 1

    result = []
    for sym in sorted(markets.keys()):
        m = markets[sym]
        resolved = m["wins"] + m["losses"]
        wr = (m["wins"] / resolved * 100) if resolved > 0 else 0
        result.append({
            "symbol": sym,
            "pnl": round(m["pnl"], 2),
            "wins": m["wins"],
            "losses": m["losses"],
            "trades": m["trades"],
            "open": m["open"],
            "win_rate": round(wr, 1),
        })

    return jsonify(result)


@app.route("/api/live-positions")
def api_live_positions():
    """Live open positions with unrealized P&L (scalper + swing)."""
    trades = _load_jsonl(PAPER_LOG)
    pnl_records = _load_jsonl(PNL_LOG)

    # Include swing trades
    swing_trades = _load_jsonl(SWING_TRADES_LOG)
    swing_pnl = _load_jsonl(SWING_PNL_LOG)
    # Tag swing trades
    for t in swing_trades:
        t["_strategy"] = "SWING"
    trades = trades + swing_trades
    pnl_records = pnl_records + swing_pnl
    resolved_ids = set(r.get("trade_id", "") for r in pnl_records)

    # Get live prices
    prices = {}
    try:
        import ccxt
        exchange = ccxt.bybit({"enableRateLimit": True, "options": {"defaultType": "swap"}})
        symbols = set()
        for i, t in enumerate(trades):
            tid = f"{t['timestamp']}_{t['symbol']}_{i}"
            if tid not in resolved_ids:
                symbols.add(t["symbol"])
        for sym in symbols:
            try:
                ticker = exchange.fetch_ticker(sym)
                prices[sym] = float(ticker["last"])
            except Exception:
                pass
    except Exception:
        pass

    positions = []
    for i, t in enumerate(trades):
        tid = f"{t['timestamp']}_{t['symbol']}_{i}"
        if tid in resolved_ids:
            continue

        sym = t["symbol"]
        ep = t.get("entry_price", 0)
        cp = prices.get(sym, ep)
        side = t["side"].upper()
        amt = t["amount"]
        sl = t.get("stop_loss", 0)
        tp = t.get("take_profit", 0)

        if side == "BUY":
            unrealized = (cp - ep) * amt
        else:
            unrealized = (ep - cp) * amt

        # Calculate % move from entry
        pct_move = ((cp - ep) / ep * 100) if ep > 0 else 0
        if side == "SELL":
            pct_move = -pct_move  # flip for shorts

        # Time open
        try:
            trade_time = datetime.fromisoformat(t["timestamp"])
            age_sec = (datetime.now(timezone.utc) - trade_time).total_seconds()
            age_min = int(age_sec / 60)
        except Exception:
            age_min = 0

        positions.append({
            "symbol": sym.replace("/USDT:USDT", ""),
            "side": side,
            "direction": "BULL" if side == "BUY" else "BEAR",
            "entry_price": ep,
            "current_price": cp,
            "stop_loss": sl,
            "take_profit": tp,
            "size": amt,
            "unrealized_pnl": round(unrealized, 2),
            "pct_move": round(pct_move, 3),
            "age_minutes": age_min,
            "winning": unrealized > 0,
            "strategy": t.get("_strategy", "SCALP"),
        })

    # Sort: winning first, then by unrealized P&L
    positions.sort(key=lambda p: p["unrealized_pnl"], reverse=True)

    return jsonify({
        "positions": positions,
        "total_unrealized": round(sum(p["unrealized_pnl"] for p in positions), 2),
        "count": len(positions),
    })


@app.route("/api/status")
def api_status():
    """Bot health status with system info."""
    status = _bot_status()
    # Add system info
    import os
    model_path = ROOT / "models" / "lgbm_model.txt"
    if model_path.exists():
        mtime = datetime.fromtimestamp(model_path.stat().st_mtime, tz=timezone.utc)
        status["model_updated"] = mtime.strftime("%Y-%m-%d %H:%M UTC")
    else:
        status["model_updated"] = "No model"

    # Count data files
    data_dir = ROOT / "data" / "raw"
    data_files = list(data_dir.glob("*.csv")) if data_dir.exists() else []
    status["data_files"] = len(data_files)

    # Open positions count
    trades = _load_jsonl(PAPER_LOG)
    pnl_records = _load_jsonl(PNL_LOG)
    resolved_ids = set(r.get("trade_id", "") for r in pnl_records)
    open_count = 0
    for i, t in enumerate(trades):
        trade_id = f"{t['timestamp']}_{t['symbol']}_{i}"
        if trade_id not in resolved_ids:
            open_count += 1
    status["open_positions"] = open_count

    return jsonify(status)


@app.route("/api/pnl-distribution")
def api_pnl_distribution():
    """P&L distribution histogram data."""
    pnl_records = _load_jsonl(PNL_LOG)
    pnl_values = [r.get("pnl_usd", 0) for r in pnl_records if r.get("outcome") in ("WIN", "LOSS")]

    if not pnl_values:
        return jsonify({"buckets": [], "counts": []})

    # Create buckets
    min_pnl = min(pnl_values)
    max_pnl = max(pnl_values)
    n_buckets = 15
    if max_pnl == min_pnl:
        return jsonify({"buckets": [f"${min_pnl:.1f}"], "counts": [len(pnl_values)]})

    step = (max_pnl - min_pnl) / n_buckets
    buckets = []
    counts = []
    colors = []
    for i in range(n_buckets):
        low = min_pnl + i * step
        high = low + step
        label = f"${low:.1f}"
        count = sum(1 for v in pnl_values if low <= v < high or (i == n_buckets - 1 and v == high))
        buckets.append(label)
        counts.append(count)
        colors.append("#089981" if low >= 0 else "#f23645")

    return jsonify({"buckets": buckets, "counts": counts, "colors": colors})


@app.route("/api/hourly")
def api_hourly():
    """Hourly trade performance."""
    pnl_records = _load_jsonl(PNL_LOG)
    hours = defaultdict(lambda: {"pnl": 0, "count": 0})

    for r in pnl_records:
        ts = r.get("timestamp", "")
        if len(ts) >= 13:
            try:
                h = int(ts[11:13])
                hours[h]["pnl"] += r.get("pnl_usd", 0)
                hours[h]["count"] += 1
            except ValueError:
                pass

    result = []
    for h in range(24):
        result.append({
            "hour": f"{h:02d}:00",
            "pnl": round(hours[h]["pnl"], 2),
            "count": hours[h]["count"],
        })

    return jsonify(result)


@app.route("/api/swing")
def api_swing():
    """Swing trading specific metrics."""
    swing_trades = _load_jsonl(SWING_TRADES_LOG)
    swing_pnl = _load_jsonl(SWING_PNL_LOG)

    resolved = len(swing_pnl)
    total = len(swing_trades)
    wins = sum(1 for r in swing_pnl if r.get("outcome") == "WIN")
    losses = sum(1 for r in swing_pnl if r.get("outcome") == "LOSS")
    total_pnl = sum(r.get("pnl_usd", 0) for r in swing_pnl)
    win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0

    return jsonify({
        "strategy": "SWING",
        "timeframe": "4h",
        "total_trades": total,
        "resolved": resolved,
        "open": total - resolved,
        "wins": wins,
        "losses": losses,
        "pnl": round(total_pnl, 2),
        "win_rate": round(win_rate, 1),
    })


# ── Auto-resolve background thread ──────────────────────────────────────────
def _start_resolver():
    """Dashboard resolver DISABLED — main bot handles all trade resolution.
    Having two resolvers caused trades to be killed prematurely.
    The dashboard now only reads from the PnL file written by the bot."""
    pass


# ── Run ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    _start_resolver()
    port = int(os.environ.get("PORT", 8080))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    print(f"\n  {'='*52}")
    print(f"  |  AI Crypto Trading Dashboard                   |")
    print(f"  |  http://localhost:{port}                          |")
    print(f"  |  Auto-resolves trades every 60s                |")
    print(f"  {'='*52}\n")
    app.run(host="0.0.0.0", port=port, debug=debug)
