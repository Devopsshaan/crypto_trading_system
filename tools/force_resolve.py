"""Force-resolve all pending trades at current market price."""
import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.paper_pnl import load_trades, load_pnl_records, save_pnl_record, get_live_prices
from config.settings import SIMULATE_FEES, TAKER_FEE_RATE

trades = load_trades()
already_resolved = {r["trade_id"] for r in load_pnl_records()}
unresolved = []
for i, t in enumerate(trades):
    tid = f"{t['timestamp']}_{t['symbol']}_{i}"
    if tid not in already_resolved:
        t["_trade_id"] = tid
        unresolved.append(t)

if not unresolved:
    print("Nothing to resolve")
    sys.exit(0)

symbols = list(set(t["symbol"] for t in unresolved))
prices = get_live_prices(symbols)
print(f"Resolving {len(unresolved)} trades...")

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

    if side == "BUY":
        if cp <= sl:
            outcome, pnl = "LOSS", (sl - ep) * amt
        elif cp >= tp:
            outcome, pnl = "WIN", (tp - ep) * amt
        else:
            pnl = (cp - ep) * amt
            outcome = "WIN" if pnl > 0 else "LOSS"
    else:
        if cp >= sl:
            outcome, pnl = "LOSS", (ep - sl) * amt
        elif cp <= tp:
            outcome, pnl = "WIN", (ep - tp) * amt
        else:
            pnl = (ep - cp) * amt
            outcome = "WIN" if pnl > 0 else "LOSS"

    fee = 0.0
    if SIMULATE_FEES:
        fee = ep * amt * TAKER_FEE_RATE * 2
        pnl -= fee

    record = {
        "trade_id": t["_trade_id"],
        "timestamp": t["timestamp"],
        "resolved_at": datetime.now(timezone.utc).isoformat(),
        "symbol": sym,
        "side": side,
        "amount": amt,
        "entry_price": ep,
        "stop_loss": sl,
        "take_profit": tp,
        "current_price": cp,
        "outcome": outcome,
        "pnl_usd": round(pnl, 2),
        "fee_usd": round(fee, 2),
    }
    save_pnl_record(record)
    icon = "WIN" if outcome == "WIN" else "LOSS"
    print(f"  {icon} {sym}: {outcome} Entry={ep} Now={cp} PnL=${pnl:+.2f} fee=${fee:.2f}")

print("Done!")
