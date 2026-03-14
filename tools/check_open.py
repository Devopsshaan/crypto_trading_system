"""Check open positions across scalper + swing."""
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent

def check():
    now = datetime.now(timezone.utc)
    
    # Scalper
    trades_file = ROOT / "logs" / "paper_trades.jsonl"
    pnl_file = ROOT / "logs" / "paper_pnl.jsonl"
    
    trades = [json.loads(l) for l in open(trades_file) if l.strip()] if trades_file.exists() else []
    pnl = [json.loads(l) for l in open(pnl_file) if l.strip()] if pnl_file.exists() else []
    resolved_ids = set(r.get("trade_id", "") for r in pnl)
    
    print("=== SCALPER OPEN ===")
    scalper_open = 0
    for i, t in enumerate(trades):
        tid = f"{t['timestamp']}_{t['symbol']}_{i}"
        if tid not in resolved_ids:
            scalper_open += 1
            age = (now - datetime.fromisoformat(t['timestamp'])).total_seconds() / 60
            print(f"  {t['side']:>4} {t['symbol'].replace('/USDT:USDT',''):>5} @ {t['entry_price']}  age={age:.0f}m")
    print(f"  Total open: {scalper_open}")
    
    # Swing
    swing_trades_file = ROOT / "logs" / "paper_trades_swing.jsonl"
    swing_pnl_file = ROOT / "logs" / "paper_pnl_swing.jsonl"
    
    swing_trades = [json.loads(l) for l in open(swing_trades_file) if l.strip()] if swing_trades_file.exists() else []
    swing_pnl = [json.loads(l) for l in open(swing_pnl_file) if l.strip()] if swing_pnl_file.exists() else []
    swing_resolved = set(r.get("trade_id", "") for r in swing_pnl)
    
    print("\n=== SWING OPEN ===")
    swing_open = 0
    for i, t in enumerate(swing_trades):
        tid = f"{t['timestamp']}_{t['symbol']}_{i}"
        if tid not in swing_resolved:
            swing_open += 1
            age = (now - datetime.fromisoformat(t['timestamp'])).total_seconds() / 60
            print(f"  {t['side']:>4} {t['symbol'].replace('/USDT:USDT',''):>5} @ {t['entry_price']}  age={age:.0f}m")
    print(f"  Total open: {swing_open}")
    
    # PnL summary
    wins = sum(1 for r in pnl if r['outcome'] == 'WIN')
    losses = sum(1 for r in pnl if r['outcome'] == 'LOSS')
    total = sum(r['pnl_usd'] for r in pnl)
    print(f"\n=== SCALPER PNL: {wins}W/{losses}L = ${total:+.2f} ===")
    for r in pnl:
        sym = r['symbol'].replace('/USDT:USDT','')
        print(f"  {r['side']:>4} {sym:>5} -> {r['outcome']:>4} ${r['pnl_usd']:+.2f} [{r['exit_type']}]")

if __name__ == "__main__":
    check()
