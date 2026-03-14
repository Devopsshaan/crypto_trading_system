"""
Position Sizing Calculator & Growth Projector
=============================================
Companion tool for the AI Crypto Trading System Account Growth Plan.

Usage
-----
    python position_sizer.py

Provides:
  1. Position size calculation for any trade
  2. Account growth projection with compounding
  3. Drawdown gear recommendations
"""

from __future__ import annotations
import math


# ── Position Sizing ──────────────────────────────────────────────────────────

def calc_position_size(
    balance: float,
    risk_pct: float,
    entry_price: float,
    stop_price: float,
    leverage: float = 3.0,
) -> dict:
    """
    Calculate position size, notional, and margin for a USDT-margined
    perpetual futures trade.

    Parameters
    ----------
    balance     : Current account balance in USDT.
    risk_pct    : Risk as a decimal (0.01 = 1%).
    entry_price : Planned entry price.
    stop_price  : Planned stop-loss price.
    leverage    : Leverage multiplier (e.g. 3.0).

    Returns
    -------
    dict with keys: risk_usd, stop_dist, size, notional, margin, fits.
    """
    risk_usd = balance * risk_pct
    stop_dist = abs(entry_price - stop_price)
    if stop_dist == 0:
        raise ValueError("Stop distance cannot be zero.")
    size = risk_usd / stop_dist
    notional = size * entry_price
    margin = notional / leverage
    return {
        "risk_usd": round(risk_usd, 2),
        "stop_dist": round(stop_dist, 2),
        "size": round(size, 6),
        "notional": round(notional, 2),
        "margin": round(margin, 2),
        "fits": margin <= balance,
    }


# ── Drawdown Gear ────────────────────────────────────────────────────────────

def drawdown_gear(balance: float, peak_balance: float) -> dict:
    """
    Determine the current drawdown gear and recommended risk parameters.

    Returns dict with: drawdown_pct, gear, risk_pct, max_trades_per_day.
    """
    dd = (peak_balance - balance) / peak_balance if peak_balance > 0 else 0.0
    if dd >= 0.15:
        gear, risk, trades = "PAUSE", 0.0, 0
    elif dd >= 0.10:
        gear, risk, trades = "RECOVERY", 0.005, 1
    elif dd >= 0.05:
        gear, risk, trades = "CAUTION", 0.0075, 2
    else:
        gear, risk, trades = "NORMAL", 0.01, 3
    return {
        "drawdown_pct": round(dd * 100, 2),
        "gear": gear,
        "risk_pct": risk,
        "max_trades_per_day": trades,
    }


# ── Growth Projection ───────────────────────────────────────────────────────

def project_growth(
    start_balance: float,
    weekly_return_pct: float,
    target_balance: float,
    max_weeks: int = 200,
) -> list[dict]:
    """
    Project weekly account growth with compounding.

    Returns list of dicts with: week, balance, risk_per_trade (at 1%).
    """
    rows = []
    bal = start_balance
    for w in range(max_weeks + 1):
        rows.append({
            "week": w,
            "balance": round(bal, 2),
            "risk_per_trade": round(bal * 0.01, 2),
        })
        if bal >= target_balance:
            break
        bal *= 1 + weekly_return_pct / 100
    return rows


# ── Milestone Check ─────────────────────────────────────────────────────────

MILESTONES = [
    (200, {"risk": "1%", "leverage": "2-3x", "concurrent": 1, "daily_trades": 2, "phase": "Foundation"}),
    (400, {"risk": "1-1.5%", "leverage": "3-4x", "concurrent": 2, "daily_trades": 3, "phase": "Validation"}),
    (600, {"risk": "1.5%", "leverage": "3-5x", "concurrent": 2, "daily_trades": 3, "phase": "Growth"}),
    (1000, {"risk": "1-1.5%", "leverage": "3-5x", "concurrent": 3, "daily_trades": 3, "phase": "Target"}),
]


def current_milestone(balance: float) -> dict:
    """Return the scaling parameters for the current account milestone."""
    for threshold, params in reversed(MILESTONES):
        if balance >= threshold:
            return {"milestone": f"${threshold}", **params}
    return {"milestone": "<$200", "risk": "0.5%", "leverage": "1-2x",
            "concurrent": 1, "daily_trades": 1, "phase": "Sub-minimum"}


# ── Interactive CLI ──────────────────────────────────────────────────────────

def _print_separator():
    print("─" * 60)


def interactive():
    """Run an interactive CLI session."""
    print()
    print("═" * 60)
    print("  AI CRYPTO TRADING SYSTEM — POSITION SIZER & GROWTH TOOL")
    print("═" * 60)

    while True:
        print()
        print("  [1] Calculate position size for a trade")
        print("  [2] Project account growth")
        print("  [3] Check drawdown gear")
        print("  [4] Show milestone parameters")
        print("  [5] Quick reference table")
        print("  [Q] Quit")
        print()
        choice = input("  Select option: ").strip().upper()

        if choice == "1":
            _print_separator()
            try:
                balance = float(input("  Account balance ($): "))
                risk_pct = float(input("  Risk per trade (%, e.g. 1): ")) / 100
                entry = float(input("  Entry price ($): "))
                stop = float(input("  Stop-loss price ($): "))
                lev = float(input("  Leverage (e.g. 3): "))
                r = calc_position_size(balance, risk_pct, entry, stop, lev)
                print()
                print(f"  Risk amount:   ${r['risk_usd']}")
                print(f"  Stop distance: ${r['stop_dist']}")
                print(f"  Position size: {r['size']} units")
                print(f"  Notional:      ${r['notional']}")
                print(f"  Margin needed: ${r['margin']}")
                print(f"  Fits balance:  {'✅ YES' if r['fits'] else '❌ NO — widen stop or reduce risk'}")
            except ValueError as e:
                print(f"  Error: {e}")

        elif choice == "2":
            _print_separator()
            try:
                start = float(input("  Starting balance ($): "))
                weekly = float(input("  Weekly return (%): "))
                target = float(input("  Target balance ($): "))
                rows = project_growth(start, weekly, target)
                print()
                print(f"  {'Week':>5}  {'Balance':>12}  {'Risk/Trade':>12}")
                print(f"  {'─'*5}  {'─'*12}  {'─'*12}")
                # print every 4 weeks + last row
                for r in rows:
                    if r["week"] % 4 == 0 or r == rows[-1]:
                        print(f"  {r['week']:>5}  ${r['balance']:>10,.2f}  ${r['risk_per_trade']:>10,.2f}")
                print(f"\n  Reached ${rows[-1]['balance']:,.2f} at week {rows[-1]['week']}")
            except ValueError as e:
                print(f"  Error: {e}")

        elif choice == "3":
            _print_separator()
            try:
                bal = float(input("  Current balance ($): "))
                peak = float(input("  Peak balance ($): "))
                g = drawdown_gear(bal, peak)
                print()
                print(f"  Drawdown:         {g['drawdown_pct']}%")
                print(f"  Gear:             {g['gear']}")
                print(f"  Risk per trade:   {g['risk_pct']*100:.1f}%")
                print(f"  Max trades/day:   {g['max_trades_per_day']}")
                if g["gear"] == "PAUSE":
                    print("  ⚠️  STOP all trading for 48 hours. Review system.")
            except ValueError as e:
                print(f"  Error: {e}")

        elif choice == "4":
            _print_separator()
            try:
                bal = float(input("  Current balance ($): "))
                m = current_milestone(bal)
                print()
                for k, v in m.items():
                    print(f"  {k:<16} {v}")
            except ValueError as e:
                print(f"  Error: {e}")

        elif choice == "5":
            _print_separator()
            print()
            print("  Quick-Reference Position Sizes ($200 account, 1% risk = $2)")
            print()
            examples = [
                ("BTCUSDT", 65000, 400, 200),
                ("ETHUSDT", 3400, 60, 200),
                ("SOLUSDT", 145, 3, 200),
                ("BNBUSDT", 620, 12, 200),
            ]
            print(f"  {'Asset':<10} {'Entry':>10} {'Stop Dist':>10} {'Size':>10} {'Notional':>10} {'Margin@3x':>10}")
            for asset, entry, sd, bal in examples:
                r = calc_position_size(bal, 0.01, entry, entry - sd, 3.0)
                print(f"  {asset:<10} ${entry:>8,} ${sd:>8} {r['size']:>10.4f} ${r['notional']:>8,.2f} ${r['margin']:>8,.2f}")
            print()

        elif choice == "Q":
            print("  Goodbye. Trade with discipline.")
            break
        else:
            print("  Invalid option.")


if __name__ == "__main__":
    interactive()
