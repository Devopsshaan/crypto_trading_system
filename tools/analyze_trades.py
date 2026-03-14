"""Analyze all paper trade backups to find loss patterns."""
import json
from pathlib import Path

logs = Path("logs")

for f in sorted(logs.glob("paper_pnl_backup*_20260314.jsonl")):
    print(f"\n{'='*70}")
    print(f"  {f.name}")
    print(f"{'='*70}")
    lines = [json.loads(l) for l in open(f) if l.strip()]
    if not lines:
        print("  (empty)")
        continue
    
    wins = sum(1 for l in lines if l["outcome"] == "WIN")
    losses = sum(1 for l in lines if l["outcome"] == "LOSS")
    total_pnl = sum(l["pnl_usd"] for l in lines)
    
    tp_hits = 0
    sl_hits = 0
    timeouts = 0
    
    for l in lines:
        sym = l["symbol"].replace("/USDT:USDT", "")
        side = l["side"]
        ep = l["entry_price"]
        xp = l["exit_price"]
        sl = l["stop_loss"]
        tp = l["take_profit"]
        sl_dist_pct = abs(sl - ep) / ep * 100
        tp_dist_pct = abs(tp - ep) / ep * 100
        actual_move_pct = abs(xp - ep) / ep * 100
        
        # Determine exit type
        if side == "BUY":
            if xp <= sl * 1.001:
                exit_type = "SL"
                sl_hits += 1
            elif xp >= tp * 0.999:
                exit_type = "TP"
                tp_hits += 1
            else:
                exit_type = "TIMEOUT"
                timeouts += 1
        else:
            if xp >= sl * 0.999:
                exit_type = "SL"
                sl_hits += 1
            elif xp <= tp * 1.001:
                exit_type = "TP"
                tp_hits += 1
            else:
                exit_type = "TIMEOUT"
                timeouts += 1
        
        print(f"  {l['outcome']:4s} {exit_type:7s} {side:4s} {sym:5s}  "
              f"SL%={sl_dist_pct:.3f}  TP%={tp_dist_pct:.3f}  "
              f"moved={actual_move_pct:.3f}%  PnL={l['pnl_usd']:+.2f}")
    
    print(f"\n  SUMMARY: {wins}W/{losses}L = ${total_pnl:.2f}")
    print(f"  Exit types: TP={tp_hits} SL={sl_hits} TIMEOUT={timeouts}")
    if lines:
        avg_sl = sum(abs(l["stop_loss"]-l["entry_price"])/l["entry_price"]*100 for l in lines) / len(lines)
        avg_tp = sum(abs(l["take_profit"]-l["entry_price"])/l["entry_price"]*100 for l in lines) / len(lines)
        print(f"  Avg SL distance: {avg_sl:.3f}%  Avg TP distance: {avg_tp:.3f}%")
