/* ═══════════════════════════════════════════════
   NeuralTrade Dashboard — JS Engine
   ═══════════════════════════════════════════════ */

const REFRESH_MS = 8000;
let equityChart, dailyPnlChart, hourlyChart, winLossChart, pnlDistChart, marketPnlChart;

// ─── Chart Theme ────────────────────────────────
const CHART_COLORS = {
    accent: '#00F0FF', purple: '#8B5CF6', green: '#22c55e',
    red: '#ef4444', yellow: '#f59e0b', grid: 'rgba(255,255,255,0.04)',
    text: '#8b8fa3',
};
const CHART_DEFAULTS = {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
        x: { grid: { color: CHART_COLORS.grid }, ticks: { color: CHART_COLORS.text, font: { family: 'JetBrains Mono', size: 10 } } },
        y: { grid: { color: CHART_COLORS.grid }, ticks: { color: CHART_COLORS.text, font: { family: 'JetBrains Mono', size: 10 } } },
    },
};

// ─── Tabs ────────────────────────────────────────
document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.addEventListener('click', () => switchTab(tab.dataset.tab));
});
function switchTab(name) {
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === name));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.toggle('active', c.id === 'tab-' + name));
    if (name === 'trades') loadTrades();
    if (name === 'analytics') loadAnalytics();
}

// ─── Time ────────────────────────────────────────
function updateTime() {
    const now = new Date();
    const el = document.getElementById('navTime');
    if (!el) return;
    const local = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true, timeZoneName: 'short' });
    const utc = now.toISOString().slice(11, 19) + ' UTC';
    el.textContent = local + ' · ' + utc;
}
setInterval(updateTime, 1000);
updateTime();

// ─── Helpers ────────────────────────────────────
function $(id) { return document.getElementById(id); }
function fmt(n, d=2) { return n !== null && n !== undefined ? '$' + Number(n).toFixed(d) : '—'; }
function fmtPnl(n) {
    if (n === null || n === undefined) return '—';
    const v = Number(n);
    const s = (v >= 0 ? '+' : '') + '$' + v.toFixed(2);
    return `<span class="${v >= 0 ? 'green' : 'red'}">${s}</span>`;
}
function outcomeHtml(o) {
    if (o === 'WIN') return '<span class="outcome-win">WIN</span>';
    if (o === 'LOSS') return '<span class="outcome-loss">LOSS</span>';
    return '<span class="outcome-open">OPEN</span>';
}
function sideHtml(s) {
    if (s === 'BUY' || s === 'SELL') return `<span class="side-${s.toLowerCase()}">${s === 'BUY' ? 'LONG' : 'SHORT'}</span>`;
    return s;
}

// ═══ DATA LOADERS ════════════════════════════════

async function loadSummary() {
    try {
        const d = await (await fetch('/api/summary')).json();
        $('mBalance').textContent = fmt(d.balance);
        $('navBalance').textContent = fmt(d.balance);
        const pnl = d.total_pnl || 0;
        const roi = d.roi || 0;
        $('mBalanceChange').innerHTML = `<span class="${pnl >= 0 ? 'green' : 'red'}">${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)} (${roi >= 0 ? '+' : ''}${roi.toFixed(1)}%)</span>`;
        $('mPnl').innerHTML = `<span class="${pnl >= 0 ? 'green' : 'red'}">${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}</span>`;
        $('mPnlSub').textContent = `${d.resolved} resolved`;
        $('mWinRate').textContent = d.win_rate.toFixed(1) + '%';
        $('mWinRate').className = 'metric-value ' + (d.win_rate >= 50 ? 'green' : d.win_rate > 0 ? 'red' : '');
        $('mWinLoss').textContent = `${d.wins}W / ${d.losses}L`;
        $('mProfitFactor').textContent = d.profit_factor === '∞' ? '∞' : Number(d.profit_factor).toFixed(2);
        $('mBest').textContent = fmt(d.best_trade);
        $('mDrawdown').textContent = d.max_drawdown.toFixed(1) + '%';
        $('footerStartBal').textContent = d.starting_balance;
        $('footerLastUpdate').textContent = new Date().toLocaleTimeString();
    } catch (e) { console.error('Summary:', e); }
}

async function loadStatus() {
    try {
        const d = await (await fetch('/api/status')).json();
        const pill = $('botStatus');
        const dot = pill.querySelector('.status-dot');
        const text = pill.querySelector('.status-text');
        if (d.running) { dot.classList.add('active'); text.textContent = 'Bot Running'; }
        else { dot.classList.remove('active'); text.textContent = 'Bot Offline'; }
    } catch (e) {
        console.error('Status:', e);
        const pill = $('botStatus');
        if (pill) {
            pill.querySelector('.status-dot').classList.remove('active');
            pill.querySelector('.status-text').textContent = 'Bot Offline';
        }
    }
}

async function loadEquity() {
    try {
        const data = await (await fetch('/api/equity')).json();
        const labels = data.map(d => d.time.slice(5, 16));
        const values = data.map(d => d.value);
        const ctx = $('equityChart');
        if (equityChart) equityChart.destroy();
        const gradient = ctx.getContext('2d').createLinearGradient(0, 0, 0, 320);
        gradient.addColorStop(0, 'rgba(0,240,255,0.15)');
        gradient.addColorStop(1, 'rgba(0,240,255,0.0)');
        equityChart = new Chart(ctx, {
            type: 'line',
            data: { labels, datasets: [{ data: values, borderColor: CHART_COLORS.accent, backgroundColor: gradient, borderWidth: 2.5, fill: true, tension: 0.3, pointRadius: 0, pointHoverRadius: 5, pointHoverBackgroundColor: CHART_COLORS.accent }] },
            options: { ...CHART_DEFAULTS, scales: { ...CHART_DEFAULTS.scales, y: { ...CHART_DEFAULTS.scales.y, ticks: { ...CHART_DEFAULTS.scales.y.ticks, callback: v => '$' + v } } } },
        });
    } catch (e) { console.error('Equity:', e); }
}

async function loadDaily() {
    try {
        const data = await (await fetch('/api/daily')).json();
        const labels = data.map(d => d.date.slice(5));
        const values = data.map(d => d.pnl);
        const colors = values.map(v => v >= 0 ? CHART_COLORS.green : CHART_COLORS.red);
        const ctx = $('dailyPnlChart');
        if (dailyPnlChart) dailyPnlChart.destroy();
        dailyPnlChart = new Chart(ctx, {
            type: 'bar',
            data: { labels, datasets: [{ data: values, backgroundColor: colors, borderRadius: 4, barThickness: 20 }] },
            options: { ...CHART_DEFAULTS, scales: { ...CHART_DEFAULTS.scales, y: { ...CHART_DEFAULTS.scales.y, ticks: { ...CHART_DEFAULTS.scales.y.ticks, callback: v => '$' + v } } } },
        });
    } catch (e) { console.error('Daily:', e); }
}

async function loadMarkets() {
    try {
        const data = await (await fetch('/api/markets')).json();
        const tb = document.querySelector('#marketsTable tbody');
        tb.innerHTML = data.map(m => {
            const statusBadge = m.open > 0 ? `<span class="outcome-open">${m.open} open</span>` : '';
            return `<tr>
                <td class="sym">${m.symbol} ${statusBadge}</td>
                <td>${m.trades}</td>
                <td>${m.wins + m.losses > 0 ? m.win_rate.toFixed(0) + '%' : '—'}</td>
                <td class="right">${fmtPnl(m.pnl)}</td>
            </tr>`;
        }).join('');
    } catch (e) { console.error('Markets:', e); }
}

async function loadRecentTrades() {
    try {
        const d = await (await fetch('/api/trades?per_page=8')).json();
        const tb = document.querySelector('#recentTradesTable tbody');
        tb.innerHTML = d.trades.map(t => `<tr>
            <td>${t.timestamp.slice(5,16)}</td>
            <td class="sym">${t.symbol}</td>
            <td>${sideHtml(t.side)}</td>
            <td style="font-family:var(--mono)">${Number(t.entry_price).toFixed(t.entry_price >= 100 ? 2 : 4)}</td>
            <td>${outcomeHtml(t.outcome)}</td>
            <td class="right">${t.pnl !== null ? fmtPnl(t.pnl) : '—'}</td>
        </tr>`).join('');
    } catch (e) { console.error('Recent:', e); }
}

// ─── Trades Tab ──────────────────────────────────
let currentPage = 1;
async function loadTrades(page) {
    if (page) currentPage = page;
    try {
        const side = $('filterSide').value;
        const outcome = $('filterOutcome').value;
        let url = `/api/trades?page=${currentPage}&per_page=30`;
        const d = await (await fetch(url)).json();
        let trades = d.trades;
        if (side) trades = trades.filter(t => t.side === side);
        if (outcome) trades = trades.filter(t => t.outcome === outcome);

        const tb = document.querySelector('#allTradesTable tbody');
        tb.innerHTML = trades.map(t => `<tr>
            <td>${t.timestamp}</td>
            <td class="sym">${t.symbol}</td>
            <td>${sideHtml(t.side)}</td>
            <td class="right">${Number(t.entry_price).toFixed(t.entry_price >= 100 ? 2 : 4)}</td>
            <td class="right">${t.exit_price ? Number(t.exit_price).toFixed(t.exit_price >= 100 ? 2 : 4) : '—'}</td>
            <td class="right">${Number(t.stop_loss).toFixed(t.stop_loss >= 100 ? 2 : 4)}</td>
            <td class="right">${Number(t.take_profit).toFixed(t.take_profit >= 100 ? 2 : 4)}</td>
            <td class="right">${Number(t.amount).toFixed(4)}</td>
            <td>${outcomeHtml(t.outcome)}</td>
            <td class="right">${t.pnl !== null ? fmtPnl(t.pnl) : '—'}</td>
        </tr>`).join('');

        const pg = $('pagination');
        pg.innerHTML = '';
        for (let i = 1; i <= d.pages; i++) {
            const btn = document.createElement('button');
            btn.textContent = i;
            btn.className = i === d.page ? 'active' : '';
            btn.onclick = () => loadTrades(i);
            pg.appendChild(btn);
        }
    } catch (e) { console.error('Trades:', e); }
}

// ─── Analytics Tab ───────────────────────────────
async function loadAnalytics() {
    try {
        const [summary, hourly, pnlDist, markets, daily] = await Promise.all([
            fetch('/api/summary').then(r => r.json()),
            fetch('/api/hourly').then(r => r.json()),
            fetch('/api/pnl-distribution').then(r => r.json()),
            fetch('/api/markets').then(r => r.json()),
            fetch('/api/daily').then(r => r.json()),
        ]);

        // Stats
        $('sTotalTrades').textContent = summary.total_trades;
        $('sResolved').textContent = summary.resolved;
        $('sPending').textContent = summary.pending;
        $('sAvgPnl').textContent = fmt(summary.avg_pnl);
        $('sWorstTrade').textContent = fmt(summary.worst_trade);
        $('sGrossProfit').textContent = fmt(summary.gross_profit);
        $('sGrossLoss').textContent = fmt(summary.gross_loss);
        $('sConsecWins').textContent = summary.max_consec_wins;
        $('sConsecLosses').textContent = summary.max_consec_losses;

        // Hourly chart
        if (hourlyChart) hourlyChart.destroy();
        hourlyChart = new Chart($('hourlyChart'), {
            type: 'bar',
            data: { labels: hourly.map(h => h.hour), datasets: [{ data: hourly.map(h => h.pnl), backgroundColor: hourly.map(h => h.pnl >= 0 ? CHART_COLORS.green : CHART_COLORS.red), borderRadius: 3 }] },
            options: { ...CHART_DEFAULTS, scales: { ...CHART_DEFAULTS.scales, y: { ...CHART_DEFAULTS.scales.y, ticks: { ...CHART_DEFAULTS.scales.y.ticks, callback: v => '$' + v } } } },
        });

        // Win/Loss pie
        if (winLossChart) winLossChart.destroy();
        winLossChart = new Chart($('winLossChart'), {
            type: 'doughnut',
            data: { labels: ['Wins', 'Losses'], datasets: [{ data: [summary.wins, summary.losses], backgroundColor: [CHART_COLORS.green, CHART_COLORS.red], borderWidth: 0, spacing: 2 }] },
            options: { responsive: true, maintainAspectRatio: false, cutout: '65%', plugins: { legend: { position: 'bottom', labels: { color: CHART_COLORS.text, font: { family: 'Outfit', size: 12 }, padding: 16 } } } },
        });

        // P&L distribution
        if (pnlDistChart) pnlDistChart.destroy();
        if (pnlDist.buckets.length > 0) {
            pnlDistChart = new Chart($('pnlDistChart'), {
                type: 'bar',
                data: { labels: pnlDist.buckets, datasets: [{ data: pnlDist.counts, backgroundColor: pnlDist.colors || pnlDist.counts.map(() => CHART_COLORS.purple), borderRadius: 3 }] },
                options: CHART_DEFAULTS,
            });
        }

        // Market P&L bar
        if (marketPnlChart) marketPnlChart.destroy();
        const mColors = ['#00F0FF','#8B5CF6','#22c55e','#f59e0b','#ec4899','#06b6d4','#f97316','#a855f7'];
        marketPnlChart = new Chart($('marketPnlChart'), {
            type: 'bar',
            data: { labels: markets.map(m => m.symbol), datasets: [{ data: markets.map(m => m.pnl), backgroundColor: markets.map((m,i) => m.pnl >= 0 ? CHART_COLORS.green : CHART_COLORS.red), borderRadius: 4 }] },
            options: { ...CHART_DEFAULTS, indexAxis: 'y', scales: { x: { ...CHART_DEFAULTS.scales.x, ticks: { ...CHART_DEFAULTS.scales.x.ticks, callback: v => '$' + v } }, y: CHART_DEFAULTS.scales.y } },
        });

        // Daily table
        const dtb = document.querySelector('#dailyTable tbody');
        dtb.innerHTML = daily.map(d => {
            const barW = Math.min(Math.abs(d.pnl) * 5, 100);
            const barColor = d.pnl >= 0 ? CHART_COLORS.green : CHART_COLORS.red;
            return `<tr>
                <td>${d.date}</td><td>${d.trades}</td><td class="green">${d.wins}</td><td class="red">${d.losses}</td>
                <td>${d.win_rate.toFixed(0)}%</td><td class="right">${fmtPnl(d.pnl)}</td>
                <td><div style="width:${barW}%;height:6px;background:${barColor};border-radius:3px;min-width:4px"></div></td>
            </tr>`;
        }).join('');

    } catch (e) { console.error('Analytics:', e); }
}

// ─── Live Positions ──────────────────────────────
async function loadLivePositions() {
    try {
        const d = await (await fetch('/api/live-positions')).json();
        const grid = $('positionsGrid');
        const countEl = $('liveCount');
        const totalEl = $('liveTotalPnl');

        const scalps = d.positions.filter(p => p.strategy !== 'SWING').length;
        const swings = d.positions.filter(p => p.strategy === 'SWING').length;
        countEl.textContent = swings > 0 ? `${scalps} scalp + ${swings} swing` : d.count;
        const tp = d.total_unrealized;
        totalEl.innerHTML = `uPnL: <span class="${tp >= 0 ? 'green' : 'red'}">${tp >= 0 ? '+' : ''}$${tp.toFixed(2)}</span>`;

        if (d.positions.length === 0) {
            grid.innerHTML = '<div class="no-positions">No open positions — waiting for signals...</div>';
            return;
        }

        grid.innerHTML = d.positions.map(p => {
            const isBull = p.direction === 'BULL';
            const cardClass = isBull ? 'bull' : 'bear';
            const winClass = p.winning ? 'winning' : 'losing';
            const dirTag = isBull ? 'bull-tag' : 'bear-tag';
            const dirIcon = isBull ? '🟢 LONG' : '🔴 SHORT';
            const pnlClass = p.unrealized_pnl >= 0 ? 'positive' : 'negative';
            const pnlStr = (p.unrealized_pnl >= 0 ? '+' : '') + '$' + p.unrealized_pnl.toFixed(2);
            const pctStr = (p.pct_move >= 0 ? '+' : '') + p.pct_move.toFixed(3) + '%';

            // Progress bar: how close to TP vs SL
            const ep = p.entry_price;
            const cp = p.current_price;
            const slDist = Math.abs(ep - p.stop_loss);
            const tpDist = Math.abs(ep - p.take_profit);
            const totalRange = slDist + tpDist;
            let progress = 50;
            if (totalRange > 0) {
                if (isBull) {
                    progress = Math.min(100, Math.max(0, ((cp - p.stop_loss) / totalRange) * 100));
                } else {
                    progress = Math.min(100, Math.max(0, ((p.stop_loss - cp) / totalRange) * 100));
                }
            }
            const barColor = progress > 50 ? 'green' : 'red';

            const priceDP = ep >= 100 ? 2 : ep >= 1 ? 4 : 6;

            const stratBadge = p.strategy === 'SWING'
                ? '<span class="strat-badge swing-badge">SWING</span>'
                : '<span class="strat-badge scalp-badge">SCALP</span>';

            return `<div class="pos-card ${cardClass} ${winClass}">
                <div class="pos-header">
                    <span class="pos-symbol">${p.symbol} ${stratBadge}</span>
                    <span class="pos-direction ${dirTag}">${dirIcon}</span>
                </div>
                <div class="pos-pnl ${pnlClass}">${pnlStr}</div>
                <div class="pos-details">
                    <span class="pos-entry">${cp.toFixed(priceDP)} (${pctStr})</span>
                    <span class="pos-age">${p.age_minutes}m</span>
                </div>
                <div class="pos-bar"><div class="pos-bar-fill ${barColor}" style="width:${progress}%"></div></div>
            </div>`;
        }).join('');
    } catch (e) { console.error('LivePos:', e); }
}

// ═══ REFRESH LOOP ════════════════════════════════
async function refreshAll() {
    await Promise.all([loadSummary(), loadStatus(), loadEquity(), loadDaily(), loadMarkets(), loadRecentTrades(), loadLivePositions()]);
}
refreshAll();
setInterval(refreshAll, REFRESH_MS);
