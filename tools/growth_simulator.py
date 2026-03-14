"""
Account Growth & Example-Week Simulator
========================================
Simulates realistic trading weeks to illustrate the growth plan.

Usage
-----
    python growth_simulator.py              # run example week + growth projection
    python growth_simulator.py --weeks 52   # project 52 weeks
"""

from __future__ import annotations
import argparse
import random

# ── Simulation Parameters ───────────────────────────────────────────────────

DEFAULT_PARAMS = {
    "start_balance": 200.0,
    "risk_pct": 0.01,        # 1% risk per trade
    "win_rate": 0.58,         # 58% win rate
    "avg_rr": 1.6,            # average reward-to-risk ratio on wins
    "trades_per_week": 12,    # ~2-3 trades per day, 5 days
    "max_daily_loss_pct": 0.05,
    "max_weekly_loss_pct": 0.10,
}


# ── Single Trade Simulator ──────────────────────────────────────────────────

SETUPS = ["Trend Pullback", "Sweep Reversal", "Momentum Breakout"]
ASSETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


def simulate_trade(balance: float, risk_pct: float, win_rate: float, avg_rr: float) -> dict:
    """Simulate a single trade outcome."""
    risk_usd = balance * risk_pct
    is_win = random.random() < win_rate
    if is_win:
        # wins vary: 0.8× to 2.5× of avg R:R
        rr = avg_rr * random.uniform(0.6, 1.4)
        pnl = risk_usd * rr
        result = "WIN"
    else:
        # losses are at most 1R (stopped out)
        pnl = -risk_usd
        rr = -1.0
        result = "LOSS"

    return {
        "asset": random.choice(ASSETS),
        "setup": random.choice(SETUPS),
        "risk_usd": round(risk_usd, 2),
        "pnl": round(pnl, 2),
        "r_multiple": round(rr, 2),
        "result": result,
    }


# ── Week Simulator ──────────────────────────────────────────────────────────

def simulate_week(
    balance: float,
    params: dict | None = None,
    week_num: int = 1,
) -> dict:
    """
    Simulate a full trading week with loss controls.

    Returns dict with week details and ending balance.
    """
    p = params or DEFAULT_PARAMS
    start_balance = balance
    daily_max_loss = balance * p["max_daily_loss_pct"]
    weekly_max_loss = balance * p["max_weekly_loss_pct"]
    trades_remaining = p["trades_per_week"]

    week_trades = []
    week_pnl = 0.0
    daily_trades_per_day = max(1, trades_remaining // 5)

    for day_idx, day_name in enumerate(DAYS):
        if trades_remaining <= 0:
            break
        if week_pnl <= -weekly_max_loss:
            break  # weekly loss cap hit

        daily_pnl = 0.0
        daily_count = 0

        for _ in range(min(3, daily_trades_per_day + random.randint(0, 1))):
            if trades_remaining <= 0:
                break
            if daily_pnl <= -daily_max_loss:
                break  # daily loss cap
            if daily_count >= 3:
                break  # max 3 trades/day

            trade = simulate_trade(balance, p["risk_pct"], p["win_rate"], p["avg_rr"])
            trade["day"] = day_name
            trade["trade_num"] = len(week_trades) + 1

            balance += trade["pnl"]
            daily_pnl += trade["pnl"]
            week_pnl += trade["pnl"]
            daily_count += 1
            trades_remaining -= 1
            week_trades.append(trade)

            # Update risk limits based on new balance
            daily_max_loss = start_balance * p["max_daily_loss_pct"]

    wins = sum(1 for t in week_trades if t["result"] == "WIN")
    losses = sum(1 for t in week_trades if t["result"] == "LOSS")
    gross_profit = sum(t["pnl"] for t in week_trades if t["pnl"] > 0)
    gross_loss = abs(sum(t["pnl"] for t in week_trades if t["pnl"] < 0))

    return {
        "week": week_num,
        "start_balance": round(start_balance, 2),
        "end_balance": round(balance, 2),
        "pnl": round(week_pnl, 2),
        "pnl_pct": round(week_pnl / start_balance * 100, 2),
        "total_trades": len(week_trades),
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / len(week_trades) * 100, 1) if week_trades else 0,
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else float("inf"),
        "trades": week_trades,
    }


# ── Multi-Week Growth ───────────────────────────────────────────────────────

def simulate_growth(
    start_balance: float = 200.0,
    target: float = 1000.0,
    max_weeks: int = 100,
    params: dict | None = None,
) -> list[dict]:
    """Simulate multiple weeks of trading."""
    p = params or DEFAULT_PARAMS
    balance = start_balance
    peak = balance
    results = []

    for w in range(1, max_weeks + 1):
        week = simulate_week(balance, p, week_num=w)
        balance = week["end_balance"]
        peak = max(peak, balance)

        # Drawdown gear adjustment
        dd = (peak - balance) / peak if peak > 0 else 0
        adjusted_params = dict(p)
        if dd >= 0.15:
            adjusted_params["risk_pct"] = 0.0  # pause
        elif dd >= 0.10:
            adjusted_params["risk_pct"] = 0.005
            adjusted_params["trades_per_week"] = 5
        elif dd >= 0.05:
            adjusted_params["risk_pct"] = 0.0075
            adjusted_params["trades_per_week"] = 10
        else:
            adjusted_params = dict(p)  # normal

        week["peak"] = round(peak, 2)
        week["drawdown_pct"] = round(dd * 100, 2)
        results.append(week)

        if balance >= target:
            break
        if balance < 50:  # ruin threshold
            break

    return results


# ── Display ──────────────────────────────────────────────────────────────────

def print_example_week(week: dict):
    """Pretty-print a simulated week."""
    print()
    print("═" * 72)
    print(f"  EXAMPLE TRADING WEEK #{week['week']}")
    print(f"  Starting Balance: ${week['start_balance']:,.2f}")
    print("═" * 72)
    print()
    print(f"  {'#':<3} {'Day':<11} {'Asset':<10} {'Setup':<20} {'Risk$':>6} {'P&L':>8} {'Result':>6}")
    print(f"  {'─'*3} {'─'*11} {'─'*10} {'─'*20} {'─'*6} {'─'*8} {'─'*6}")

    running = week["start_balance"]
    for t in week["trades"]:
        running += t["pnl"]
        icon = "✅" if t["result"] == "WIN" else "❌"
        print(f"  {t['trade_num']:<3} {t['day']:<11} {t['asset']:<10} "
              f"{t['setup']:<20} ${t['risk_usd']:>5.2f} "
              f"{'$' + str(t['pnl']):>7s}  {icon}")

    print()
    print("─" * 72)
    print(f"  Ending Balance:  ${week['end_balance']:,.2f}")
    print(f"  Weekly P&L:      ${week['pnl']:+,.2f} ({week['pnl_pct']:+.1f}%)")
    print(f"  Win Rate:        {week['win_rate']:.0f}%  ({week['wins']}W / {week['losses']}L)")
    print(f"  Profit Factor:   {week['profit_factor']:.2f}")
    print("─" * 72)


def print_growth_summary(results: list[dict]):
    """Print growth simulation results."""
    print()
    print("═" * 72)
    print("  ACCOUNT GROWTH SIMULATION")
    print("═" * 72)
    print()
    print(f"  {'Week':>5} {'Balance':>12} {'P&L':>10} {'Win%':>6} {'Peak':>12} {'DD%':>6}")
    print(f"  {'─'*5} {'─'*12} {'─'*10} {'─'*6} {'─'*12} {'─'*6}")

    for r in results:
        flag = ""
        if r["end_balance"] >= 400 and (not results[results.index(r)-1:results.index(r)] or
           results[max(0,results.index(r)-1)]["end_balance"] < 400):
            flag = " ← $400 milestone"
        elif r["end_balance"] >= 600 and (not results[results.index(r)-1:results.index(r)] or
            results[max(0,results.index(r)-1)]["end_balance"] < 600):
            flag = " ← $600 milestone"
        elif r["end_balance"] >= 1000:
            flag = " ★ TARGET REACHED"

        print(f"  {r['week']:>5} ${r['end_balance']:>10,.2f} "
              f"${r['pnl']:>+8,.2f} {r['win_rate']:>5.0f}% "
              f"${r['peak']:>10,.2f} {r['drawdown_pct']:>5.1f}%{flag}")

    final = results[-1]
    print()
    if final["end_balance"] >= 1000:
        print(f"  🎯 Target of $1,000 reached in {final['week']} weeks!")
    elif final["end_balance"] < 50:
        print(f"  ⚠️  Account depleted at week {final['week']}. Review risk parameters.")
    else:
        print(f"  ⏳ Simulation ended at week {final['week']}. Balance: ${final['end_balance']:,.2f}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Account Growth Simulator")
    parser.add_argument("--weeks", type=int, default=60, help="Max weeks to simulate")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    parser.add_argument("--start", type=float, default=200.0, help="Starting balance")
    parser.add_argument("--target", type=float, default=1000.0, help="Target balance")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)
    else:
        random.seed(42)  # reproducible default

    print()
    print("  Running with: start=${:,.0f}, target=${:,.0f}, max_weeks={}".format(
        args.start, args.target, args.weeks))

    # Simulate one example week first
    random.seed(42)
    example = simulate_week(args.start, week_num=1)
    print_example_week(example)

    # Simulate full growth path
    random.seed(42)
    results = simulate_growth(args.start, args.target, args.weeks)
    print_growth_summary(results)


if __name__ == "__main__":
    main()
