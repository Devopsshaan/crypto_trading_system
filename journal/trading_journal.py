"""
Trading Journal Manager
=======================
CSV-based trading journal for the AI Crypto Trading System.

Usage
-----
    python trading_journal.py            # interactive mode
    python trading_journal.py summary    # print weekly summary

Stores all trades in  journal/trades.csv
"""

from __future__ import annotations
import csv
import os
import sys
from datetime import datetime, date
from pathlib import Path

JOURNAL_DIR = Path(__file__).parent
TRADES_FILE = JOURNAL_DIR / "trades.csv"

FIELDS = [
    "date", "time_utc", "asset", "direction", "setup_type",
    "ml_probability", "entry_price", "stop_loss", "take_profit",
    "position_size", "leverage", "risk_usd", "risk_pct",
    "exit_price", "pnl_usd", "pnl_pct", "r_multiple",
    "fees", "duration_min", "result", "mistakes", "lessons",
    "discipline_grade", "emotional_state",
]


def _ensure_file():
    """Create the CSV file with headers if it doesn't exist."""
    if not TRADES_FILE.exists():
        with open(TRADES_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()


def add_trade(trade: dict):
    """Append a single trade row to the journal."""
    _ensure_file()
    with open(TRADES_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writerow(trade)


def load_trades() -> list[dict]:
    """Load all trades from the CSV."""
    _ensure_file()
    with open(TRADES_FILE, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def weekly_summary(week_start: str | None = None) -> dict:
    """
    Compute summary statistics for a given week (or the current week).

    Parameters
    ----------
    week_start : ISO date string (Monday) or None for current week.
    """
    trades = load_trades()
    if not trades:
        return {"total_trades": 0, "message": "No trades recorded yet."}

    if week_start:
        ws = datetime.strptime(week_start, "%Y-%m-%d").date()
    else:
        today = date.today()
        ws = today - __import__("datetime").timedelta(days=today.weekday())

    we = ws + __import__("datetime").timedelta(days=6)

    week_trades = []
    for t in trades:
        try:
            td = datetime.strptime(t["date"], "%Y-%m-%d").date()
        except (ValueError, KeyError):
            continue
        if ws <= td <= we:
            week_trades.append(t)

    if not week_trades:
        return {"total_trades": 0, "week": str(ws), "message": "No trades this week."}

    wins = [t for t in week_trades if t.get("result", "").upper() == "WIN"]
    losses = [t for t in week_trades if t.get("result", "").upper() == "LOSS"]

    def safe_float(val, default=0.0):
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    gross_profit = sum(safe_float(t["pnl_usd"]) for t in wins)
    gross_loss = abs(sum(safe_float(t["pnl_usd"]) for t in losses))
    total_pnl = sum(safe_float(t["pnl_usd"]) for t in week_trades)
    r_multiples = [safe_float(t.get("r_multiple", 0)) for t in week_trades]

    return {
        "week": str(ws),
        "total_trades": len(week_trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(week_trades) * 100, 1) if week_trades else 0,
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "total_pnl": round(total_pnl, 2),
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else float("inf"),
        "avg_r": round(sum(r_multiples) / len(r_multiples), 2) if r_multiples else 0,
        "best_r": round(max(r_multiples), 2) if r_multiples else 0,
        "worst_r": round(min(r_multiples), 2) if r_multiples else 0,
    }


# ── Interactive CLI ──────────────────────────────────────────────────────────

def _prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    val = input(f"  {label}{suffix}: ").strip()
    return val if val else default


def interactive_add():
    """Guided trade entry."""
    print()
    print("─" * 50)
    print("  NEW TRADE ENTRY")
    print("─" * 50)

    trade = {}
    trade["date"] = _prompt("Date (YYYY-MM-DD)", datetime.utcnow().strftime("%Y-%m-%d"))
    trade["time_utc"] = _prompt("Time UTC (HH:MM)", datetime.utcnow().strftime("%H:%M"))
    trade["asset"] = _prompt("Asset (e.g. BTCUSDT)").upper()
    trade["direction"] = _prompt("Direction (LONG/SHORT)").upper()
    trade["setup_type"] = _prompt("Setup (Pullback/Sweep/Breakout)")
    trade["ml_probability"] = _prompt("ML Probability (0.00-1.00)")
    trade["entry_price"] = _prompt("Entry Price")
    trade["stop_loss"] = _prompt("Stop-Loss Price")
    trade["take_profit"] = _prompt("Take-Profit Price")
    trade["position_size"] = _prompt("Position Size (units)")
    trade["leverage"] = _prompt("Leverage", "3")
    trade["risk_usd"] = _prompt("Risk Amount ($)")
    trade["risk_pct"] = _prompt("Risk (%)", "1.0")
    trade["exit_price"] = _prompt("Exit Price (leave blank if open)", "")
    trade["pnl_usd"] = _prompt("P&L ($)", "0")
    trade["pnl_pct"] = _prompt("P&L (%)", "0")
    trade["r_multiple"] = _prompt("R-Multiple", "0")
    trade["fees"] = _prompt("Fees ($)", "0")
    trade["duration_min"] = _prompt("Duration (minutes)", "0")
    trade["result"] = _prompt("Result (WIN/LOSS/OPEN)", "OPEN").upper()
    trade["mistakes"] = _prompt("Mistakes", "None")
    trade["lessons"] = _prompt("Lessons Learned", "")
    trade["discipline_grade"] = _prompt("Discipline Grade (A/B/C)", "A").upper()
    trade["emotional_state"] = _prompt("Emotional State (Green/Yellow/Red)", "Green")

    add_trade(trade)
    print(f"\n  ✅  Trade saved to {TRADES_FILE}")


def print_summary():
    """Print the current week's summary."""
    s = weekly_summary()
    print()
    print("─" * 50)
    print("  WEEKLY SUMMARY")
    print("─" * 50)
    for k, v in s.items():
        print(f"  {k:<18} {v}")


def interactive():
    """Main interactive loop."""
    print()
    print("═" * 50)
    print("  AI TRADING SYSTEM — TRADING JOURNAL")
    print("═" * 50)

    while True:
        print()
        print("  [1] Add new trade")
        print("  [2] View weekly summary")
        print("  [3] View all trades")
        print("  [Q] Quit")
        print()
        choice = input("  Select option: ").strip().upper()

        if choice == "1":
            interactive_add()
        elif choice == "2":
            print_summary()
        elif choice == "3":
            trades = load_trades()
            if not trades:
                print("  No trades recorded yet.")
            else:
                print()
                for i, t in enumerate(trades, 1):
                    result_icon = "✅" if t.get("result") == "WIN" else ("❌" if t.get("result") == "LOSS" else "⏳")
                    print(f"  #{i} {t.get('date','')} {t.get('asset',''):8s} "
                          f"{t.get('direction',''):5s} {t.get('setup_type',''):12s} "
                          f"P&L: ${t.get('pnl_usd','0'):>7s}  {result_icon}")
        elif choice == "Q":
            print("  Goodbye. Review your journal regularly.")
            break
        else:
            print("  Invalid option.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "summary":
        print_summary()
    else:
        interactive()
