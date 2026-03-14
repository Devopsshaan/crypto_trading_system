"""
Web Dashboard — Paper Trading P&L viewer in the browser.
=========================================================
Usage:  py tools/web_dashboard.py
Then open:  http://localhost:5555
"""
from __future__ import annotations
import json
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from collections import defaultdict
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
PAPER_LOG = ROOT / "logs" / "paper_trades.jsonl"
PNL_LOG = ROOT / "logs" / "paper_pnl.jsonl"
BOT_LOG_DIR = ROOT / "logs"

PORT = 5555

# ── Auto-resolve in background ──────────────────────────────────────────
def _auto_resolve_loop():
    """Background thread: resolve pending trades every 60s."""
    time.sleep(10)  # let server start first
    while True:
        try:
            from tools.paper_pnl import resolve_trades
            resolve_trades()
        except Exception as e:
            print(f"[auto-resolve] error: {e}")
        time.sleep(60)


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def get_bot_status() -> str:
    today = datetime.now().strftime("%Y%m%d")
    log_file = BOT_LOG_DIR / f"bot_{today}.log"
    if not log_file.exists():
        return "No log file found"
    with open(log_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    if not lines:
        return "Log empty"
    last = lines[-1].strip()
    return last[:120]


def build_html() -> str:
    trades = load_jsonl(PAPER_LOG)
    pnl_records = load_jsonl(PNL_LOG)

    total = len(trades)
    resolved = len(pnl_records)
    pending = total - resolved

    wins = sum(1 for r in pnl_records if r.get("outcome") == "WIN")
    losses = sum(1 for r in pnl_records if r.get("outcome") == "LOSS")
    skips = sum(1 for r in pnl_records if r.get("outcome") == "SKIP")
    total_pnl = sum(r.get("pnl_usd", 0) for r in pnl_records)
    win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
    avg_pnl = total_pnl / resolved if resolved > 0 else 0
    balance = 200.0 + total_pnl
    roi = (total_pnl / 200.0) * 100

    # Daily breakdown
    daily = defaultdict(lambda: {"pnl": 0, "wins": 0, "losses": 0})
    for r in pnl_records:
        day = r["timestamp"][:10]
        daily[day]["pnl"] += r.get("pnl_usd", 0)
        if r.get("outcome") == "WIN":
            daily[day]["wins"] += 1
        elif r.get("outcome") == "LOSS":
            daily[day]["losses"] += 1

    # Trade rows
    trade_rows = ""
    for t in reversed(trades[-50:]):
        ts = t["timestamp"][:19].replace("T", " ")
        sym = t["symbol"].replace("/USDT:USDT", "")
        side = t["side"]
        side_cls = "buy" if side == "BUY" else "sell"
        amt = t["amount"]
        entry = t.get("entry_price", "—")
        sl = t.get("stop_loss", "—")
        tp = t.get("take_profit", "—")
        trade_rows += f"""<tr>
            <td>{ts}</td>
            <td class="{side_cls}">{side}</td>
            <td><b>{sym}</b></td>
            <td>{entry}</td>
            <td>{sl}</td>
            <td>{tp}</td>
            <td>{amt:.4f}</td>
        </tr>"""

    # P&L rows
    pnl_rows = ""
    for r in reversed(pnl_records[-50:]):
        ts = r["timestamp"][:19].replace("T", " ")
        sym = r["symbol"].replace("/USDT:USDT", "")
        side = r["side"]
        side_cls = "buy" if side == "BUY" else "sell"
        outcome = r.get("outcome", "—")
        outcome_cls = "win" if outcome == "WIN" else ("loss" if outcome == "LOSS" else "")
        pnl = r.get("pnl_usd", 0)
        pnl_cls = "profit" if pnl >= 0 else "loss-val"
        entry = r.get("entry_price", "—")
        current = r.get("current_price", "—")
        pnl_rows += f"""<tr>
            <td>{ts}</td>
            <td class="{side_cls}">{side}</td>
            <td><b>{sym}</b></td>
            <td>{entry}</td>
            <td>{current}</td>
            <td class="{outcome_cls}">{outcome}</td>
            <td class="{pnl_cls}">${pnl:+.2f}</td>
        </tr>"""

    # Daily rows
    daily_rows = ""
    for day in sorted(daily.keys(), reverse=True):
        d = daily[day]
        pnl_val = d["pnl"]
        pnl_cls = "profit" if pnl_val >= 0 else "loss-val"
        bar_w = min(int(abs(pnl_val) * 8), 300)
        bar_color = "#00c853" if pnl_val >= 0 else "#ff1744"
        daily_rows += f"""<tr>
            <td>{day}</td>
            <td>{d['wins']}</td>
            <td>{d['losses']}</td>
            <td class="{pnl_cls}">${pnl_val:+.2f}</td>
            <td><div style="width:{bar_w}px;height:18px;background:{bar_color};border-radius:3px"></div></td>
        </tr>"""

    pnl_color = "#00c853" if total_pnl >= 0 else "#ff1744"
    bot_status = get_bot_status()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="30">
<title>Crypto Bot — Paper Trading Dashboard</title>
<style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ font-family:'Segoe UI',system-ui,sans-serif; background:#0d1117; color:#e6edf3; padding:20px; }}
    .header {{ text-align:center; padding:20px 0 30px; }}
    .header h1 {{ font-size:28px; color:#58a6ff; }}
    .header .sub {{ color:#8b949e; font-size:14px; margin-top:5px; }}
    .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:16px; margin-bottom:30px; }}
    .card {{ background:#161b22; border:1px solid #30363d; border-radius:12px; padding:20px; text-align:center; }}
    .card .label {{ font-size:12px; color:#8b949e; text-transform:uppercase; letter-spacing:1px; }}
    .card .value {{ font-size:32px; font-weight:700; margin-top:8px; }}
    .card .value.green {{ color:#00c853; }}
    .card .value.red {{ color:#ff1744; }}
    .card .value.blue {{ color:#58a6ff; }}
    .card .value.yellow {{ color:#ffc107; }}
    .section {{ background:#161b22; border:1px solid #30363d; border-radius:12px; padding:20px; margin-bottom:24px; }}
    .section h2 {{ font-size:18px; color:#58a6ff; margin-bottom:16px; border-bottom:1px solid #30363d; padding-bottom:10px; }}
    table {{ width:100%; border-collapse:collapse; font-size:13px; }}
    th {{ text-align:left; color:#8b949e; font-weight:600; padding:8px 12px; border-bottom:1px solid #30363d; }}
    td {{ padding:8px 12px; border-bottom:1px solid #21262d; }}
    .buy {{ color:#00c853; font-weight:700; }}
    .sell {{ color:#ff1744; font-weight:700; }}
    .win {{ color:#00c853; font-weight:700; }}
    .loss {{ color:#ff1744; font-weight:700; }}
    .profit {{ color:#00c853; font-weight:600; }}
    .loss-val {{ color:#ff1744; font-weight:600; }}
    .status {{ background:#161b22; border:1px solid #30363d; border-radius:8px; padding:12px 16px;
               font-size:12px; color:#8b949e; margin-bottom:20px; font-family:monospace; overflow:hidden;
               text-overflow:ellipsis; white-space:nowrap; }}
    .status .dot {{ display:inline-block; width:8px; height:8px; border-radius:50%; background:#00c853;
                    margin-right:8px; animation:pulse 2s infinite; }}
    @keyframes pulse {{ 0%,100%{{opacity:1}} 50%{{opacity:0.3}} }}
    .refresh {{ text-align:center; color:#484f58; font-size:12px; margin-top:20px; }}
</style>
</head>
<body>
    <div class="header">
        <h1>&#128202; AI Crypto Trading Bot</h1>
        <div class="sub">Paper Trading Dashboard &mdash; Auto-refreshes every 30s</div>
    </div>

    <div class="status">
        <span class="dot"></span>
        Bot: {bot_status}
    </div>

    <div class="cards">
        <div class="card">
            <div class="label">Paper Balance</div>
            <div class="value {'green' if balance >= 200 else 'red'}">${balance:.2f}</div>
        </div>
        <div class="card">
            <div class="label">Total P&amp;L</div>
            <div class="value {'green' if total_pnl >= 0 else 'red'}">${total_pnl:+.2f}</div>
        </div>
        <div class="card">
            <div class="label">Win Rate</div>
            <div class="value {'green' if win_rate >= 50 else 'red'}">{win_rate:.1f}%</div>
        </div>
        <div class="card">
            <div class="label">Wins / Losses</div>
            <div class="value blue">{wins}W / {losses}L</div>
        </div>
        <div class="card">
            <div class="label">Total Trades</div>
            <div class="value blue">{total}</div>
        </div>
        <div class="card">
            <div class="label">Pending</div>
            <div class="value yellow">{pending}</div>
        </div>
        <div class="card">
            <div class="label">ROI</div>
            <div class="value {'green' if roi >= 0 else 'red'}">{roi:+.1f}%</div>
        </div>
        <div class="card">
            <div class="label">Avg / Trade</div>
            <div class="value {'green' if avg_pnl >= 0 else 'red'}">${avg_pnl:+.2f}</div>
        </div>
    </div>

    <div class="section">
        <h2>&#128197; Daily P&amp;L</h2>
        <table>
            <tr><th>Date</th><th>Wins</th><th>Losses</th><th>P&amp;L</th><th></th></tr>
            {daily_rows if daily_rows else '<tr><td colspan="5" style="color:#484f58">No resolved trades yet</td></tr>'}
        </table>
    </div>

    <div class="section">
        <h2>&#9989; Resolved Trades</h2>
        <table>
            <tr><th>Time</th><th>Side</th><th>Symbol</th><th>Entry</th><th>Exit</th><th>Result</th><th>P&amp;L</th></tr>
            {pnl_rows if pnl_rows else '<tr><td colspan="7" style="color:#484f58">No resolved trades yet. Run: py tools/paper_pnl.py --resolve</td></tr>'}
        </table>
    </div>

    <div class="section">
        <h2>&#128203; Open Paper Trades</h2>
        <table>
            <tr><th>Time</th><th>Side</th><th>Symbol</th><th>Entry</th><th>SL</th><th>TP</th><th>Qty</th></tr>
            {trade_rows if trade_rows else '<tr><td colspan="7" style="color:#484f58">No trades yet</td></tr>'}
        </table>
    </div>

    <div class="refresh">Auto-refreshes every 30 seconds &bull; Started $200 &bull; {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
</body>
</html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(build_html().encode("utf-8"))

    def log_message(self, fmt, *args):
        pass  # suppress console noise


def main():
    # Start auto-resolve background thread
    resolver = threading.Thread(target=_auto_resolve_loop, daemon=True)
    resolver.start()

    server = HTTPServer(("127.0.0.1", PORT), DashboardHandler)
    print(f"\n  ╔══════════════════════════════════════════════╗")
    print(f"  ║  📊 Paper Trading Dashboard                  ║")
    print(f"  ║  Open: http://localhost:{PORT}               ║")
    print(f"  ║  Auto-resolves trades every 60s              ║")
    print(f"  ║  Press Ctrl+C to stop                        ║")
    print(f"  ╚══════════════════════════════════════════════╝\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
