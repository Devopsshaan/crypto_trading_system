# AI CRYPTO TRADING SYSTEM — STRUCTURED ACCOUNT GROWTH PLAN
## $200 → $1,000 Disciplined Growth Framework

> **Purpose:** Grow a $200 Bybit Testnet (then live) futures account to $1,000
> using strict risk management, ML-filtered signals, and compounding.
> Demo-test every rule before risking real capital.

---

## SECTION 1 — ACCOUNT STRUCTURE

### Starting Parameters

| Parameter              | Value           |
|------------------------|-----------------|
| Starting capital       | $200            |
| Risk per trade         | 1–2% of equity  |
| Max trades per day     | 3               |
| Max daily loss         | 5% of equity    |
| Max weekly loss        | 10% of equity   |
| Target account         | $1,000          |

### Why Strict Risk Control Is Non-Negotiable for Small Accounts

1. **Survivability is the priority.**
   A $200 account can absorb very few losses before it becomes too small to trade.
   Three consecutive 5% losses shrink $200 to $171 (−14.5%).
   Without a cap, a single bad day can erase weeks of progress.

2. **Recovery math is asymmetric.**
   A 10% loss needs an 11.1% gain to recover.
   A 50% loss needs a 100% gain.
   Keeping each loss to 1–2% ($2–$4) means recovery is trivial — one good trade.

3. **Emotional stability.**
   Large losses trigger revenge trading, over-leveraging, and tilt.
   When the max pain per trade is $2–$4, the emotional impact is manageable —
   the trader can stay objective and follow the system.

4. **Statistical edge needs volume.**
   A 55% win-rate system needs hundreds of trades to converge to its true edge.
   Blowing up the account on trade #12 means you never reach statistical convergence.
   Small risk per trade keeps you in the game long enough for the edge to compound.

5. **Position sizing drives compounding.**
   If risk stays proportional to equity (percentage-based), winning streaks naturally
   compound while losing streaks automatically reduce exposure — a self-correcting mechanism
   that only works if the percentage stays small.

**Rule of Thumb:** If a single trade outcome changes your mood, your risk is too large.

---

## SECTION 2 — POSITION SIZING

### The Core Formula

```
Position Size (in base currency) = Risk Amount / Stop-Loss Distance

Where:
  Risk Amount     = Account Balance × Risk Percentage
  Stop-Loss Dist  = |Entry Price − Stop-Loss Price|
```

For **USDT-margined perpetual futures** on Bybit, position size is in the base asset
(BTC, ETH, etc.) and the margin required depends on leverage:

```
Margin Required = (Position Size × Entry Price) / Leverage
```

**Always verify:** Margin Required ≤ Available Balance.

### Example 1 — BTCUSDT Long

| Field              | Value       |
|--------------------|-------------|
| Account balance    | $200        |
| Risk per trade     | 1% = $2     |
| Entry price        | $65,000     |
| Stop-loss price    | $64,600     |
| Stop-loss distance | $400        |

```
Position Size = $2 / $400 = 0.005 BTC
Notional      = 0.005 × $65,000 = $325

Leverage 3×  → Margin = $325 / 3 = $108.33  ✅ fits in $200
Leverage 2×  → Margin = $325 / 2 = $162.50  ✅ fits in $200
Leverage 1×  → Margin = $325 / 1 = $325.00  ❌ exceeds $200
```

Recommended: **use 3× leverage** here. The stop-loss controls risk, not the leverage.
Leverage merely determines margin requirement.

### Example 2 — ETHUSDT Short

| Field              | Value       |
|--------------------|-------------|
| Account balance    | $200        |
| Risk per trade     | 2% = $4     |
| Entry price        | $3,400      |
| Stop-loss price    | $3,460      |
| Stop-loss distance | $60         |

```
Position Size = $4 / $60 = 0.0667 ETH
Notional      = 0.0667 × $3,400 = $226.67

Leverage 3×  → Margin = $226.67 / 3 = $75.56  ✅
Leverage 2×  → Margin = $226.67 / 2 = $113.33 ✅
```

### Example 3 — SOLUSDT Long (larger account stage, $400)

| Field              | Value       |
|--------------------|-------------|
| Account balance    | $400        |
| Risk per trade     | 1.5% = $6   |
| Entry price        | $145.00     |
| Stop-loss price    | $142.00     |
| Stop-loss distance | $3.00       |

```
Position Size = $6 / $3 = 2.0 SOL
Notional      = 2.0 × $145 = $290

Leverage 3×  → Margin = $290 / 3 = $96.67  ✅
```

### Quick-Reference Position Sizing Table ($200 account, 1% risk = $2)

| Asset    | Entry     | Stop Dist | Size     | Notional | Margin @3× |
|----------|-----------|-----------|----------|----------|-------------|
| BTCUSDT  | $65,000   | $400      | 0.005    | $325     | $108        |
| BTCUSDT  | $65,000   | $200      | 0.010    | $650     | $217 ⚠️     |
| ETHUSDT  | $3,400    | $60       | 0.033    | $113     | $38         |
| ETHUSDT  | $3,400    | $30       | 0.067    | $227     | $76         |
| SOLUSDT  | $145      | $3        | 0.667    | $97      | $32         |
| BNBUSDT  | $620      | $12       | 0.167    | $103     | $34         |

> ⚠️ If margin exceeds ~60% of balance, **widen the stop or skip the trade**.

---

## SECTION 3 — PROFIT TARGET MODEL

### Realistic Expectations

Crypto futures offer high opportunity but also high noise.
A well-filtered ML system targeting 55–60% win rate with 1:1.5–1:2 R:R can produce
consistent but modest weekly gains.

**Do NOT target huge monthly returns.** Target consistency and let compounding do the work.

### Weekly & Monthly Targets

| Metric                  | Conservative | Moderate  | Aggressive |
|-------------------------|-------------|-----------|------------|
| Win rate                | 55%         | 58%       | 62%        |
| Avg R:R                 | 1:1.5       | 1:1.8     | 1:2        |
| Trades per week         | 10–15       | 10–15     | 10–15      |
| **Weekly net return**   | **2–3%**    | **3–5%**  | **5–8%**   |
| **Monthly net return**  | **8–12%**   | **12–20%**| **20–30%** |

> These targets assume live-equivalent execution with fees and slippage.
> Demo results are often optimistic — discount by ~20–30% for live.

### Compounding Growth Scenarios ($200 Start)

#### Scenario A — Conservative (3% Weekly)

| Week | Balance  | Risk/Trade | Risk $ |
|------|----------|------------|--------|
| 0    | $200.00  | 1%         | $2.00  |
| 4    | $225.10  | 1%         | $2.25  |
| 8    | $253.47  | 1%         | $2.53  |
| 12   | $285.40  | 1%         | $2.85  |
| 16   | $321.35  | 1%         | $3.21  |
| 20   | $361.86  | 1%         | $3.62  |
| 26   | $428.81  | 1%         | $4.29  |
| 34   | $536.59  | 1%         | $5.37  |
| 44   | $710.68  | 1%         | $7.11  |
| 52   | $888.27  | 1%         | $8.88  |
| 55   | $970.35  | 1%         | $9.70  |
| **56** | **$999.46** | 1%     | $9.99  |

**~56 weeks (13 months) to reach $1,000 at 3%/week compounding.**

#### Scenario B — Moderate (5% Weekly)

| Week | Balance   |
|------|-----------|
| 0    | $200.00   |
| 4    | $243.10   |
| 8    | $295.49   |
| 12   | $359.17   |
| 16   | $436.56   |
| 20   | $530.66   |
| 24   | $644.98   |
| 28   | $784.01   |
| 30   | $865.17   |
| 32   | $954.71   |
| **34** | **$1,053.60** |

**~33 weeks (8 months) to reach $1,000 at 5%/week compounding.**

#### Scenario C — Aggressive (8% Weekly)

| Week | Balance   |
|------|-----------|
| 0    | $200.00   |
| 4    | $272.10   |
| 8    | $370.01   |
| 12   | $503.23   |
| 16   | $684.35   |
| 20   | $930.55   |
| **21** | **$1,005.00** |

**~21 weeks (5 months) to reach $1,000 at 8%/week compounding.**

### The Power of Compounding Visualized

```
Week 0   ████ $200
Week 13  ████████ $400           (capital doubled)
Week 26  ████████████████ $800   (doubled again)
Week 33  ████████████████████ $1,000  (target reached)
```
(Based on ~5% weekly growth)

### Key Insight

The difference between 3%, 5%, and 8% weekly is **massive** over time due to compounding.
But chasing higher returns **increases risk of drawdown and ruin**.
Start conservative (2–3%), prove consistency, then gradually increase selectivity and
confidence — which naturally improves returns without increasing risk per trade.

---

## SECTION 4 — TRADE FILTERING

### The Problem with Over-Trading

Taking every signal from the ML model creates noise trades that erode edge.
A single high-quality trade per day beats five mediocre ones.

**Filtering rule:** Only trade setups that pass ALL four filters below.

### Filter 1 — Trend Alignment (Required)

```
CHECK: 1H timeframe EMA structure
  LONG  → EMA20 > EMA50 > EMA200 (bullish stack)
  SHORT → EMA20 < EMA50 < EMA200 (bearish stack)

SKIP if EMAs are flat/tangled (choppy/range-bound market).
```

**Why:** Trading with the higher-timeframe trend dramatically increases win rate.
Counter-trend trades require exceptional setups.

### Filter 2 — Volume Confirmation (Required)

```
CHECK: Volume on the setup candle (5m entry bar)
  PASS  → Volume > 1.5× rolling 20-bar average volume
  FAIL  → Volume is average or below average

Volume spike AT the setup level confirms institutional participation.
```

**Why:** Price moves without volume are unreliable. Volume validates that the move
has real money behind it, not just retail noise.

### Filter 3 — Liquidity Sweep Detection (Situational)

```
CHECK: Recent price action around key support/resistance levels
  SWEEP DETECTED → Price wicked below support (or above resistance)
                    and immediately recovered within 1–3 bars
  
  For REVERSAL setups: sweep confirmation is REQUIRED
  For BREAKOUT setups: NO recent sweep (clean break preferred)
  For PULLBACK setups: sweep can enhance signal quality
```

**Why:** Liquidity sweeps (stop hunts) trigger cascading liquidations and often
mark the turning point where smart money absorbs retail stops. Trading the reversal
after a sweep is one of the highest-probability setups in crypto.

### Filter 4 — ML Prediction Confidence (Required)

```
CHECK: Model output probability

  STRONG LONG   → Probability > 0.65   ✅ Trade with full size
  MODERATE LONG → Probability 0.60–0.65 ✅ Trade with 75% size
  NO TRADE      → Probability 0.40–0.60 ❌ Skip
  MODERATE SHORT→ Probability 0.35–0.40 ✅ Trade with 75% size
  STRONG SHORT  → Probability < 0.35   ✅ Trade with full size
```

**Why:** The model quantifies edge. Below threshold, the edge is statistical noise.
Higher probability = higher confidence = justified full position.

### Combined Filter Decision Matrix

| Trend | Volume | Liquidity | ML Prob | Decision        |
|-------|--------|-----------|---------|-----------------|
| ✅    | ✅     | ✅        | > 0.65  | **A+ TRADE**    |
| ✅    | ✅     | —         | > 0.60  | **A TRADE**     |
| ✅    | ✅     | —         | 0.55–0.60| SKIP           |
| ✅    | ❌     | ✅        | > 0.65  | Wait for volume |
| ❌    | ✅     | ✅        | > 0.65  | Counter-trend ⚠️|
| ❌    | ❌     | —         | any     | **NO TRADE**    |

**Target: Only take A+ and A trades. Skip everything else.**

---

## SECTION 5 — DAILY TRADING ROUTINE

### The 5-Step Daily Workflow

```
┌─────────────────────────────────────────────────────────┐
│  06:00–06:30  MARKET SCAN                               │
│  ↓                                                      │
│  06:30–07:00  SIGNAL DETECTION (ML + Filters)           │
│  ↓                                                      │
│  07:00–12:00  TRADE EXECUTION WINDOW (Active)           │
│  ↓                                                      │
│  After each trade  JOURNAL ENTRY                        │
│  ↓                                                      │
│  End of day   PERFORMANCE REVIEW                        │
└─────────────────────────────────────────────────────────┘
```

> Adjust times to your timezone. The key is consistency, not specific hours.
> Best crypto volatility windows: 08:00–12:00 UTC and 14:00–18:00 UTC.

---

### Step 1 — Market Scan (15–20 min)

**Objective:** Identify which assets have tradable conditions today.

Checklist:
- [ ] Check 1H charts for BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT
- [ ] Identify trend direction (EMA stack) for each asset
- [ ] Note key support/resistance levels from 1H and 4H
- [ ] Check for upcoming high-impact events (FOMC, CPI, ETF decisions)
- [ ] Mark assets as TRADABLE or AVOID for the day

```
Daily Scan Notes:
  BTC: Bullish trend, EMA stack aligned. Key support $64,500. TRADABLE.
  ETH: Choppy, EMAs tangled. AVOID today.
  SOL: Bearish trend, clean structure. TRADABLE (short bias).
  BNB: Range-bound. AVOID unless breakout with volume.
```

---

### Step 2 — Signal Detection (10–15 min)

**Objective:** Run ML model and apply all four filters.

Checklist:
- [ ] Run ML model inference on latest 5m bars for TRADABLE assets
- [ ] Record model probability for each asset
- [ ] Check volume conditions (rolling z-score)
- [ ] Check for liquidity sweep near key levels
- [ ] Apply filter matrix (Section 4) — rate setup as A+, A, or SKIP
- [ ] If A+ or A setup found, calculate position size (Section 2 formula)

```
Signal Log:
  BTC 08:15 UTC → Prob 0.68, Trend ✅, Volume ✅, Sweep ✅ → A+ LONG
  SOL 09:30 UTC → Prob 0.34, Trend ✅, Volume ✅, No sweep → A SHORT
```

---

### Step 3 — Trade Execution (Active Window)

**Objective:** Execute planned trades with discipline.

Pre-Trade Checklist (BEFORE placing order):
- [ ] Position size calculated and within limits
- [ ] Stop-loss price determined (ATR-based or structure)
- [ ] Take-profit price determined (1.5–2× risk)
- [ ] Risk amount confirmed ≤ 2% of current equity
- [ ] Daily trade count confirmed < 3
- [ ] Daily P&L confirmed above −5% threshold

Execution Rules:
- Use **limit orders** when possible (lower fees on Bybit: maker vs taker)
- Set stop-loss immediately — NEVER move it further away
- Set take-profit at planned level
- If trade is not triggered within 30 min, re-evaluate and cancel if conditions changed

---

### Step 4 — Trade Journaling (2–3 min per trade)

**Objective:** Record every trade immediately after execution.

Record in journal spreadsheet/CSV (see Section 8):
- Date and time
- Asset and direction
- Setup type (pullback / sweep reversal / breakout)
- ML probability
- Entry and stop-loss prices
- Position size and leverage
- Result when closed
- Screenshot of chart at entry (optional but valuable)

---

### Step 5 — Performance Review (10 min, end of day)

**Objective:** Learn from today's actions.

End-of-Day Checklist:
- [ ] Review all trades taken today (wins + losses)
- [ ] Calculate daily P&L ($ and %)
- [ ] For losses: was the setup valid? Was execution correct?
- [ ] For wins: was the exit optimal or left money on the table?
- [ ] Update equity curve
- [ ] Note any rule violations and commit to fixing them
- [ ] Rate the trading day: A (perfect discipline), B (minor slip), C (rules broken)

```
Daily Summary:
  Trades: 2/3
  Wins: 1, Losses: 1
  P&L: +$1.20 (+0.6%)
  Discipline Grade: A
  Notes: Followed all rules. Missed SOL SHORT due to hesitation — review entry timing.
```

---

## SECTION 6 — SCALING PLAN

### The Milestone System

As the account grows, risk per trade adjusts **automatically** because it's a percentage.
But maximum leverage, number of positions, and aggressiveness should also scale consciously.

### Milestone 1 — $200 Account (Foundation Phase)

| Parameter              | Setting        |
|------------------------|----------------|
| Risk per trade         | 1% ($2)        |
| Max leverage           | 2–3×           |
| Max concurrent trades  | 1              |
| Max trades per day     | 2–3            |
| Max daily loss         | 5% ($10)       |
| Focus                  | Demo trading    |
| Goal                   | Prove edge      |

**Mindset:** This is the learning phase. Protect capital above all.
Prove the system works for 4+ weeks of demo before any live trading.

---

### Milestone 2 — $400 Account (Validation Phase)

| Parameter              | Setting        |
|------------------------|----------------|
| Risk per trade         | 1–1.5% ($4–$6) |
| Max leverage           | 3–4×           |
| Max concurrent trades  | 2              |
| Max trades per day     | 3              |
| Max daily loss         | 5% ($20)       |
| Focus                  | Consistency     |
| Goal                   | 4+ green weeks  |

**Unlocked:**
- Can now hold 2 positions simultaneously (different assets)
- Slightly wider stop-losses possible (more margin available)
- Begin tracking Sharpe ratio and max drawdown formally

---

### Milestone 3 — $600 Account (Growth Phase)

| Parameter              | Setting         |
|------------------------|-----------------|
| Risk per trade         | 1.5% ($9)       |
| Max leverage           | 3–5×            |
| Max concurrent trades  | 2               |
| Max trades per day     | 3               |
| Max daily loss         | 4% ($24)        |
| Focus                  | Optimization    |
| Goal                   | Refine edge     |

**Unlocked:**
- Review ML model performance and retrain with recent data
- Begin A/B testing new features or alternative setups
- *Reduce* max daily loss percentage as account grows (4% not 5%)

---

### Milestone 4 — $1,000 Account (Target Achieved)

| Parameter              | Setting          |
|------------------------|------------------|
| Risk per trade         | 1–1.5% ($10–$15) |
| Max leverage           | 3–5×             |
| Max concurrent trades  | 2–3              |
| Max trades per day     | 3                |
| Max daily loss         | 3% ($30)         |
| Focus                  | Compounding      |
| Goal                   | Sustain growth   |

**At $1,000:**
- Drawdown tolerance tightens (3% daily cap)
- Begin withdrawing profits periodically (e.g., 10% monthly)
- Consider diversifying across more pairs
- Document the system formally as your "trading playbook"

### Scaling Visualization

```
$200  ─── Risk $2/trade  ─── Foundation  ─── PROVE IT WORKS
  │
  ├── +100% growth ───────────────────────────────────────
  ▼
$400  ─── Risk $4–$6     ─── Validation  ─── CONSISTENCY
  │
  ├── +50% growth ────────────────────────────────────────
  ▼
$600  ─── Risk $9         ─── Growth     ─── OPTIMIZE
  │
  ├── +67% growth ────────────────────────────────────────
  ▼
$1000 ─── Risk $10–$15   ─── Target     ─── COMPOUND & WITHDRAW
```

---

## SECTION 7 — LOSS CONTROL

### Why Loss Control Decides Survival

> *"In trading, you don't get rich by winning big — you get rich by not losing big."*

A 20% drawdown needs a 25% gain to recover.
A 50% drawdown needs a 100% gain — nearly impossible for most systems.
**The entire growth plan fails if a single bad week wipes 30%+ off the account.**

### Loss Control Rules

#### Rule 1 — Daily Loss Circuit Breaker

```
IF daily P&L reaches −5% of starting-day equity → STOP TRADING FOR THE DAY.

Example ($200 account):
  Starting equity today: $200
  Loss limit: $200 × 5% = $10
  After 2 losing trades (−$4 each = −$8), you have 1 trade left but
  if it loses $2 you hit −$10 → day is over regardless.
```

**No exceptions.** Close the charts. Walk away. Review tomorrow.

#### Rule 2 — Reduce Size During Drawdowns

```
IF account drops 5% below recent peak → reduce risk per trade to 0.5%
IF account drops 10% below recent peak → reduce risk per trade to 0.5% AND max 1 trade/day

"Drawdown Gear System":
  Normal mode:   Risk = 1–2%, Max 3 trades/day
  Caution mode:  Risk = 0.5–1%, Max 2 trades/day  (triggered at −5% from peak)
  Recovery mode: Risk = 0.5%, Max 1 trade/day      (triggered at −10% from peak)
  Pause mode:    No trading for 48 hours            (triggered at −15% from peak)
```

#### Rule 3 — Consecutive Loss Cooldown

```
After 3 consecutive losing trades (same day or across days):
  → Stop trading for the rest of the day
  → Next day: trade with 50% position size on first trade
  → Only return to full size after 2 consecutive winners

After 5 consecutive losing trades:
  → Pause all trading for 48 hours
  → Review every losing trade in journal
  → Check if market regime changed (trending → choppy)
  → Re-run model evaluation on recent data
  → If model metrics degraded significantly → retrain before resuming
```

#### Rule 4 — Weekly Loss Cap

```
IF weekly P&L reaches −10% → no more trading until next Monday.

$200 account → weekly loss cap = $20
$400 account → weekly loss cap = $40
```

#### Rule 5 — Never Average Into Losers

```
NEVER add to a losing position.
NEVER remove a stop-loss.
NEVER "hope" a trade recovers.

If stop is hit → accept the loss → move to next setup.
```

### Drawdown Recovery Table

| Drawdown | Recovery Needed | Difficulty | Action                    |
|----------|----------------|------------|---------------------------|
| −2%      | +2.04%         | Easy       | Normal trading            |
| −5%      | +5.26%         | Easy       | Caution mode              |
| −10%     | +11.11%        | Moderate   | Recovery mode             |
| −15%     | +17.65%        | Hard       | Pause 48h, review system  |
| −20%     | +25.00%        | Very Hard  | Full system audit         |
| −30%     | +42.86%        | Extreme    | Stop live, return to demo |

---

## SECTION 8 — PERFORMANCE TRACKING

### Trading Journal Structure

Every trade gets a row in the journal. Use CSV, spreadsheet, or the Python tool provided.

#### Journal Fields

| # | Field             | Example                         | Purpose                        |
|---|-------------------|---------------------------------|--------------------------------|
| 1 | Date              | 2026-03-13                      | When                           |
| 2 | Time (UTC)        | 08:15                           | When (precise)                 |
| 3 | Asset             | BTCUSDT                         | What                           |
| 4 | Direction         | LONG                            | Which way                      |
| 5 | Setup Type        | Trend Pullback                  | Why (strategy)                 |
| 6 | ML Probability    | 0.68                            | Model confidence               |
| 7 | Entry Price       | $65,000                         | Execution details              |
| 8 | Stop-Loss Price   | $64,600                         | Risk control                   |
| 9 | Take-Profit Price | $65,800                         | Target                         |
| 10| Position Size     | 0.005 BTC                       | Exposure                       |
| 11| Leverage          | 3×                              | Margin usage                   |
| 12| Risk Amount ($)   | $2.00                           | Dollar risk                    |
| 13| Risk (%)          | 1.0%                            | Percentage risk                |
| 14| Exit Price        | $65,750                         | Actual exit                    |
| 15| P&L ($)           | +$3.75                          | Dollar result                  |
| 16| P&L (%)           | +1.88%                          | Percentage result              |
| 17| R-Multiple        | +1.88R                          | Risk-adjusted return           |
| 18| Fees              | $0.15                           | Trading cost                   |
| 19| Duration          | 45 min                          | Time in trade                  |
| 20| Result            | WIN                             | Outcome category               |
| 21| Mistakes          | None                            | Self-assessment                |
| 22| Lessons           | Volume confirmed well           | Continuous improvement         |
| 23| Discipline Grade  | A                               | A/B/C self-rating              |

#### Weekly Summary Fields

| Field                   | Calculation                  |
|-------------------------|------------------------------|
| Total Trades            | Count of trades              |
| Win Rate                | Wins / Total                 |
| Average R               | Mean R-Multiple              |
| Profit Factor           | Gross Profit / Gross Loss    |
| Total P&L ($)           | Sum of all P&L              |
| Total P&L (%)           | P&L / Start-of-week equity   |
| Max Drawdown            | Largest peak-to-trough      |
| Best Trade              | Highest R                    |
| Worst Trade             | Lowest R                     |
| # Rule Violations       | Count of discipline breaks   |

---

## SECTION 9 — EXAMPLE WEEK

### Week 1 — Starting Account: $200.00

---

**Monday — 2026-03-16**

*Market Scan:* BTC bullish (EMA stack aligned on 1H). ETH choppy. SOL bearish.

| # | Asset   | Dir   | Setup         | ML Prob | Entry    | SL       | TP       | Size       | Result | P&L     | Balance  |
|---|---------|-------|---------------|---------|----------|----------|----------|------------|--------|---------|----------|
| 1 | BTCUSDT | LONG  | Trend Pullback| 0.67    | $65,000  | $64,600  | $65,800  | 0.005 BTC  | WIN    | +$3.50  | $203.50  |

Notes: Clean pullback to EMA20 on 15m. 5m reversal candle with 2× volume. Exited at $65,700 (partial TP hit, trailed stop for rest). Grade: A.

---

**Tuesday — 2026-03-17**

*Market Scan:* BTC consolidating. SOL strong downtrend continuing.

| # | Asset   | Dir   | Setup          | ML Prob | Entry   | SL      | TP      | Size      | Result | P&L     | Balance  |
|---|---------|-------|----------------|---------|---------|---------|---------|-----------|--------|---------|----------|
| 2 | SOLUSDT | SHORT | Momentum Break | 0.32    | $145.00 | $148.00 | $140.00 | 0.68 SOL  | WIN    | +$2.72  | $206.22  |
| 3 | BTCUSDT | LONG  | Pullback       | 0.62    | $65,200 | $64,800 | $65,800 | 0.005 BTC | LOSS   | −$2.00  | $204.22  |

Notes: SOL short triggered nicely — breakdown below $145 support with volume. BTC trade was marginal (prob only 0.62) and stopped out. Lesson: stick to prob > 0.65 for stronger signals. Grade: B.

---

**Wednesday — 2026-03-18**

*Market Scan:* BTC back in uptrend. No signals meeting A+ criteria early session.

| # | Asset   | Dir  | Setup          | ML Prob | Entry   | SL      | TP      | Size       | Result | P&L     | Balance  |
|---|---------|------|----------------|---------|---------|---------|---------|------------|--------|---------|----------|
| 4 | BTCUSDT | LONG | Sweep Reversal | 0.71    | $64,900 | $64,500 | $65,700 | 0.005 BTC  | WIN    | +$3.25  | $207.47  |

Notes: BTC swept below $64,800 support (wick to $64,650), immediately reclaimed. ML probability spiked to 0.71. Perfect A+ setup. Only 1 trade today — quality over quantity. Grade: A.

---

**Thursday — 2026-03-19**

*Market Scan:* BTC range-bound. SOL bounce. No clear setups.

| # | Asset | Dir | Setup | ML Prob | Entry | SL | TP | Size | Result | P&L | Balance |
|---|-------|-----|-------|---------|-------|----|----|------|--------|-----|---------|
| — | —     | —   | —     | —       | —     | —  | —  | —    | —      | $0  | $207.47 |

Notes: No trades taken. All probabilities in 0.45–0.55 range. Choppy conditions. Sitting out is a valid decision. Grade: A.

---

**Friday — 2026-03-20**

*Market Scan:* BTC breaks new local high. ETH following. Volume increasing.

| # | Asset   | Dir  | Setup          | ML Prob | Entry   | SL      | TP      | Size       | Result | P&L     | Balance  |
|---|---------|------|----------------|---------|---------|---------|---------|------------|--------|---------|----------|
| 5 | BTCUSDT | LONG | Momentum Break | 0.69    | $66,200 | $65,700 | $67,200 | 0.004 BTC  | WIN    | +$2.80  | $210.27  |
| 6 | ETHUSDT | LONG | Trend Pullback | 0.64    | $3,450  | $3,400  | $3,540  | 0.04 ETH   | LOSS   | −$2.00  | $208.27  |

Notes: BTC breakout was clean with high volume confirmation. ETH stopped out — setup was okay but entry timing was late (5m candle already extended). Lesson: if entry candle body is > 70% of ATR, wait for pullback. Grade: B.

---

### Week 1 Summary

| Metric               | Value           |
|----------------------|-----------------|
| Starting Balance     | $200.00         |
| Ending Balance       | $208.27         |
| Weekly P&L ($)       | **+$8.27**      |
| Weekly P&L (%)       | **+4.14%**      |
| Total Trades         | 6               |
| Wins                 | 4               |
| Losses               | 2               |
| Win Rate             | 66.7%           |
| Avg Win              | +$3.07          |
| Avg Loss             | −$2.00          |
| Profit Factor        | 6.14            |
| Largest Win          | +$3.50          |
| Largest Loss         | −$2.00          |
| Days with No Trades  | 1 (Thursday)    |
| Rule Violations      | 0               |
| Avg Discipline Grade | A−              |

**Assessment:** Solid week. Win rate above target. Losses were contained at exactly 1% risk.
Two B-grade days due to marginal setups — tighten filter to prob > 0.65 next week.
Thursday showed discipline in skipping low-quality conditions.

---

## SECTION 10 — TRADER DISCIPLINE

### The 12 Rules of Discipline

These rules protect you from your own emotions — the #1 account killer.

---

**Rule 1 — Follow the System, Not Your Feelings**
```
The system generates signals. You execute them.
You do NOT override the system because you "feel" the market will go up/down.
If the system says NO TRADE, you do not trade.
```

**Rule 2 — Pre-Define Every Trade**
```
Before placing ANY order, write down:
  Entry, Stop-Loss, Take-Profit, Position Size, Risk Amount
If you can't define all five → do not trade.
```

**Rule 3 — Accept Losses as Business Expenses**
```
A 1% loss is the cost of doing business.
It is not a failure. It is not personal.
The best traders in the world lose 40–45% of their trades.
```

**Rule 4 — Never Revenge Trade**
```
After a loss, you will feel the urge to "make it back quickly."
This urge leads to:
  → larger positions
  → lower-quality setups
  → more losses
  → account destruction

After a loss: take a 15-minute break. Walk away from the screen.
Your next trade must pass ALL filters as if the loss never happened.
```

**Rule 5 — Never Move Your Stop-Loss Further Away**
```
If price is approaching your stop → let it hit.
Moving the stop means increasing risk AFTER the trade is on.
This is the single fastest way to blow up an account.
```

**Rule 6 — Respect Daily Limits**
```
3 trades maximum per day.
5% maximum daily loss.
These are hard ceilings, not suggestions.
```

**Rule 7 — Quality Over Quantity**
```
Zero trades in a day = perfect discipline if no A/A+ setups existed.
Overtrading is more dangerous than undertrading.
The best trading days are often the ones where you don't trade.
```

**Rule 8 — Journal Every Trade**
```
No shortcuts. Write it down.
Unreviewed trades are wasted learning opportunities.
```

**Rule 9 — Review Weekly**
```
Every Sunday: review the week's journal.
  → What worked?
  → What didn't?
  → Any patterns in losses?
  → Any rule violations?
  → What will you improve next week?
```

**Rule 10 — Demo First**
```
ANY strategy change → demo test for 2+ weeks first.
Any new asset → demo test for 1+ week first.
Model retrained → demo test for 1+ week first.
```

**Rule 11 — Separate Trading from Entertainment**
```
Trading is not exciting. If it feels exciting, you're gambling.
Professional trading is repetitive, methodical, and often boring.
Embrace the boredom.
```

**Rule 12 — Track Your Emotional State**
```
Before each session, rate your state:
  🟢 Green  = calm, focused, rested → trade normally
  🟡 Yellow = tired, stressed, distracted → reduce to 1 trade max
  🟠 Red    = angry, anxious, euphoric, sick → do NOT trade today

Add this to your daily routine. It takes 5 seconds and prevents catastrophic decisions.
```

---

### Discipline Scorecard

Rate yourself weekly (out of 12 — one point per rule followed perfectly):

| Score  | Rating       | Action                                   |
|--------|-------------|------------------------------------------|
| 12/12  | Perfect     | Keep doing what you're doing             |
| 10–11  | Good        | Note which rules slipped, recommit       |
| 8–9    | Needs work  | Reduce trade frequency until discipline improves |
| < 8    | Danger      | Return to demo trading until score > 10  |

---

## QUICK REFERENCE CARD

```
╔══════════════════════════════════════════════════════════╗
║  TRADING SYSTEM QUICK REFERENCE                         ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  POSITION SIZE = Risk$ / Stop Distance                   ║
║  Risk$ = Balance × 0.01 (or 0.02)                        ║
║                                                          ║
║  SIGNAL: ML Prob > 0.60 + Trend ✅ + Volume ✅           ║
║                                                          ║
║  MAX: 3 trades/day, 5% daily loss, 10% weekly loss       ║
║                                                          ║
║  LEVERAGE: 2–3× (beginner) | 3–5× (experienced)         ║
║                                                          ║
║  AFTER LOSS: 15-min break. Next trade MUST pass filters. ║
║                                                          ║
║  DRAWDOWN GEARS:                                         ║
║    Normal  (-0 to -5%)  → 1–2% risk, 3 trades/day       ║
║    Caution (-5 to -10%) → 0.5–1% risk, 2 trades/day     ║
║    Recovery(-10 to -15%)→ 0.5% risk, 1 trade/day         ║
║    Pause   (> -15%)     → NO TRADING for 48 hours        ║
║                                                          ║
║  GROWTH TARGET: 3–5% per week (compounding)              ║
║  $200 → $1000 in ~6–8 months at 5%/week                 ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
```

---

*Document version: 1.0 — Generated for Bybit Testnet demo trading practice.*
*Always test on demo before using real funds.*
