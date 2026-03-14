"""
Paper Trade P&L Tracker & Dashboard
====================================
Reads paper_trades.jsonl, simulates outcomes using live prices,
and shows daily P&L summary.

Usage:
    py tools/paper_pnl.py               # Dashboard
    py tools/paper_pnl.py --resolve     # Check live prices & resolve open trades
    py tools/paper_pnl.py --reset       # Reset all paper trades
"""
from __future__ import annotations
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import SIMULATE_FEES, TAKER_FEE_RATE, RESOLVE_TIMEOUT_MINUTES

_resolve_timeout = RESOLVE_TIMEOUT_MINUTES

PAPER_LOG = ROOT / "logs" / "paper_trades.jsonl"
PNL_LOG = ROOT / "logs" / "paper_pnl.jsonl"


def load_trades() -> list[dict]:
    """Load all paper trades from JSONL."""
    trades = []
    if not PAPER_LOG.exists():
        return trades
    with open(PAPER_LOG, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                trades.append(json.loads(line))
    return trades


def load_pnl_records() -> list[dict]:
    """Load resolved P&L records."""
    records = []
    if not PNL_LOG.exists():
        return records
    with open(PNL_LOG, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def save_pnl_record(record: dict):
    """Append a resolved trade record."""
    PNL_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(PNL_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def get_live_prices(symbols: list[str]) -> dict[str, float]:
    """Fetch current prices for given symbols from Bybit."""
    import ccxt
    exchange = ccxt.bybit({"enableRateLimit": True, "options": {"defaultType": "swap"}})
    prices = {}
    for sym in symbols:
        try:
            ticker = exchange.fetch_ticker(sym)
            prices[sym] = float(ticker["last"])
        except Exception as e:
            print(f"  ⚠ Could not fetch price for {sym}: {e}")
    return prices


def resolve_trades():
    """
    Check open paper trades against live prices.
    Uses actual entry price, SL, and TP to determine outcome.
    """
    trades = load_trades()
    already_resolved = {r["trade_id"] for r in load_pnl_records()}

    unresolved = []
    for i, t in enumerate(trades):
        trade_id = f"{t['timestamp']}_{t['symbol']}_{i}"
        if trade_id not in already_resolved:
            t["_trade_id"] = trade_id
            t["_index"] = i
            unresolved.append(t)

    if not unresolved:
        print("No unresolved trades.")
        return

    symbols = list(set(t["symbol"] for t in unresolved))
    print(f"Checking {len(unresolved)} unresolved trades across {len(symbols)} symbols...")
    prices = get_live_prices(symbols)

    resolved_count = 0
    for t in unresolved:
        sym = t["symbol"]
        if sym not in prices:
            continue

        current_price = prices[sym]
        entry_price = t.get("entry_price") or current_price
        sl = t.get("stop_loss")
        tp = t.get("take_profit")
        side = t["side"].upper()
        amount = t["amount"]

        if sl is None or tp is None:
            continue

        # Skip if SL == TP (rounding issue on low-price assets)
        if abs(sl - tp) < 1e-8:
            record = {
                "trade_id": t["_trade_id"],
                "timestamp": t["timestamp"],
                "resolved_at": datetime.now(timezone.utc).isoformat(),
                "symbol": sym,
                "side": side,
                "amount": amount,
                "entry_price": entry_price,
                "stop_loss": sl,
                "take_profit": tp,
                "current_price": current_price,
                "outcome": "SKIP",
                "pnl_usd": 0.0,
            }
            save_pnl_record(record)
            resolved_count += 1
            print(f"  ⚠️ {sym}: SKIPPED (SL=TP rounding issue)")
            continue

        # Determine outcome based on price move from entry
        outcome = None
        pnl = 0.0

        if side == "BUY":
            # Long trade
            if current_price <= sl:
                outcome = "LOSS"
                pnl = (sl - entry_price) * amount
            elif current_price >= tp:
                outcome = "WIN"
                pnl = (tp - entry_price) * amount
            else:
                # Check age — resolve at market price after timeout
                trade_time = datetime.fromisoformat(t["timestamp"])
                age_minutes = (datetime.now(timezone.utc) - trade_time).total_seconds() / 60
                if age_minutes > _resolve_timeout:
                    pnl = (current_price - entry_price) * amount
                    outcome = "WIN" if pnl > 0 else "LOSS"
                else:
                    continue  # Still open
        else:
            # Short trade
            if current_price >= sl:
                outcome = "LOSS"
                pnl = (entry_price - sl) * amount
            elif current_price <= tp:
                outcome = "WIN"
                pnl = (entry_price - tp) * amount
            else:
                trade_time = datetime.fromisoformat(t["timestamp"])
                age_minutes = (datetime.now(timezone.utc) - trade_time).total_seconds() / 60
                if age_minutes > _resolve_timeout:
                    pnl = (entry_price - current_price) * amount
                    outcome = "WIN" if pnl > 0 else "LOSS"
                else:
                    continue

        if outcome:
            # Deduct round-trip fees if enabled
            fee = 0.0
            if SIMULATE_FEES:
                notional = entry_price * amount
                fee = notional * TAKER_FEE_RATE * 2  # entry + exit
                pnl -= fee

            record = {
                "trade_id": t["_trade_id"],
                "timestamp": t["timestamp"],
                "resolved_at": datetime.now(timezone.utc).isoformat(),
                "symbol": sym,
                "side": side,
                "amount": amount,
                "entry_price": entry_price,
                "stop_loss": sl,
                "take_profit": tp,
                "current_price": current_price,
                "outcome": outcome,
                "pnl_usd": round(pnl, 2),
                "fee_usd": round(fee, 2),
            }
            save_pnl_record(record)
            resolved_count += 1
            icon = "✅" if outcome == "WIN" else "❌"
            fee_str = f"  fee=${fee:.2f}" if fee > 0 else ""
            print(f"  {icon} {sym}: {outcome}  Entry={entry_price}  Now={current_price}  P&L: ${pnl:+.2f}{fee_str}")

    print(f"\nResolved {resolved_count} trades.")


def dashboard():
    """Show paper trading P&L dashboard."""
    trades = load_trades()
    pnl_records = load_pnl_records()

    print("\n" + "=" * 60)
    print("     📊  PAPER TRADING P&L DASHBOARD")
    print("=" * 60)

    if not trades:
        print("\n  No paper trades recorded yet.")
        print("  Bot is scanning every 120s — trades will appear here.")
        print("=" * 60)
        return

    # Summary
    total_trades = len(trades)
    resolved = len(pnl_records)
    pending = total_trades - resolved

    print(f"\n  Total Trades : {total_trades}")
    print(f"  Resolved     : {resolved}")
    print(f"  Pending      : {pending}")

    if pnl_records:
        # Daily P&L breakdown
        daily_pnl: dict[str, float] = defaultdict(float)
        daily_wins: dict[str, int] = defaultdict(int)
        daily_losses: dict[str, int] = defaultdict(int)

        total_pnl = 0.0
        wins = 0
        losses = 0

        for r in pnl_records:
            day = r["timestamp"][:10]  # YYYY-MM-DD
            daily_pnl[day] += r["pnl_usd"]
            if r["outcome"] == "WIN":
                wins += 1
                daily_wins[day] += 1
            else:
                losses += 1
                daily_losses[day] += 1
            total_pnl += r["pnl_usd"]

        win_rate = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0

        print(f"\n  {'─' * 50}")
        print(f"  Win Rate     : {win_rate:.1f}%  ({wins}W / {losses}L)")
        print(f"  Total P&L    : ${total_pnl:+.2f}")
        print(f"  Avg per trade: ${total_pnl / resolved:+.2f}" if resolved else "")

        balance = 200.0 + total_pnl
        print(f"  Paper Balance: ${balance:.2f}  (started: $200)")

        print(f"\n  {'─' * 50}")
        print(f"  {'Date':<14} {'W':>3} {'L':>3} {'P&L':>10}")
        print(f"  {'─' * 50}")

        for day in sorted(daily_pnl.keys()):
            pnl = daily_pnl[day]
            w = daily_wins[day]
            l = daily_losses[day]
            bar = "█" * min(int(abs(pnl)), 30)
            color_pnl = f"${pnl:+.2f}"
            print(f"  {day:<14} {w:>3} {l:>3} {color_pnl:>10}  {bar}")

    # Recent trades
    print(f"\n  {'─' * 50}")
    print(f"  Recent Paper Trades:")
    print(f"  {'─' * 50}")

    for t in trades[-10:]:
        ts = t["timestamp"][:19].replace("T", " ")
        sym = t["symbol"].replace("/USDT:USDT", "")
        side = t["side"]
        amt = t["amount"]
        sl = t.get("stop_loss", "—")
        tp = t.get("take_profit", "—")
        print(f"  {ts}  {side:<5} {sym:<5}  qty={amt:.4f}  SL={sl}  TP={tp}")

    print("\n" + "=" * 60)
    print("  Run:  py tools/paper_pnl.py --resolve   to check outcomes")
    print("=" * 60 + "\n")


def reset_paper():
    """Clear all paper trade and P&L logs."""
    confirm = input("⚠ Delete all paper trades and P&L records? (yes/no): ")
    if confirm.strip().lower() == "yes":
        if PAPER_LOG.exists():
            PAPER_LOG.unlink()
        if PNL_LOG.exists():
            PNL_LOG.unlink()
        print("✅ Paper trading data cleared.")
    else:
        print("Cancelled.")


if __name__ == "__main__":
    if "--resolve" in sys.argv:
        resolve_trades()
        dashboard()
    elif "--reset" in sys.argv:
        reset_paper()
    else:
        dashboard()
