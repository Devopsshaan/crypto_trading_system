"""
Configuration — Money printer settings.
=========================================
Simple. Fast. All markets. Trust the ML.
"""

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT_DIR / "data" / "raw"
DATA_PROCESSED = ROOT_DIR / "data" / "processed"
MODELS_DIR = ROOT_DIR / "models"
LOGS_DIR = ROOT_DIR / "logs"
JOURNAL_DIR = ROOT_DIR / "journal"

BYBIT_API_KEY = os.environ.get("BYBIT_API_KEY", "")
BYBIT_API_SECRET = os.environ.get("BYBIT_API_SECRET", "")
BYBIT_TESTNET = False
PAPER_TRADE = True

# ── All 8 markets ────────────────────────────────────────────────────────────
SYMBOLS = [
    "BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT", "BNB/USDT:USDT",
    "XRP/USDT:USDT", "DOGE/USDT:USDT", "ADA/USDT:USDT", "AVAX/USDT:USDT",
]
BYBIT_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT",
    "XRPUSDT", "DOGEUSDT", "ADAUSDT", "AVAXUSDT",
]

# ── Timeframes ───────────────────────────────────────────────────────────────
TREND_TF = "1h"
SETUP_TF = "15m"
ENTRY_TF = "5m"
PREDICTION_HORIZON = 5

# ── Feature Engineering ──────────────────────────────────────────────────────
EMA_PERIODS = [20, 50, 200]
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
ATR_PERIOD = 14
VOLUME_LOOKBACK = 50
MOMENTUM_PERIOD = 3

# ── ML Model — high-conviction entries only ──────────────────────────────────
TARGET_THRESHOLD = 0.004
PROB_LONG_THRESHOLD = 0.60   # Only strong LONG signals
PROB_SHORT_THRESHOLD = 0.40  # Only strong SHORT signals
TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
TEST_RATIO = 0.15
MODEL_FILE = MODELS_DIR / "lgbm_model.txt"

FEATURE_COLS = [
    "ema20", "ema50", "ema200",
    "rsi14", "macd", "macd_signal",
    "atr14", "vol_zscore", "momentum",
    "candle_body", "trend_dir",
    "ema20_slope", "price_vs_ema200",
    "hour_sin", "hour_cos", "dow_sin", "dow_cos",
    "price_vs_vwap", "bb_percent_b", "bb_bandwidth",
    "hurst", "obv_slope", "rsi_divergence", "market_regime",
]

# ── Risk — aggressive but protected ─────────────────────────────────────────
STARTING_BALANCE = 200.0
RISK_PER_TRADE = 0.02       # 2% = $4 per trade
MAX_RISK_PER_TRADE = 0.03
MAX_TRADES_PER_DAY = 999
MAX_DAILY_LOSS_PCT = 0.20   # 20% daily cap — room to recover from early losses
MAX_WEEKLY_LOSS_PCT = 0.30
DEFAULT_LEVERAGE = 20        # 20x for margin efficiency
MAX_LEVERAGE = 20
MIN_MARGIN_BUFFER = 0.05

# ── Drawdown Gears ──────────────────────────────────────────────────────────
DRAWDOWN_GEARS = {
    "NORMAL":   {"threshold": 0.00, "risk": 0.020, "max_trades": 999},
    "CAUTION":  {"threshold": 0.08, "risk": 0.015, "max_trades": 999},
    "RECOVERY": {"threshold": 0.15, "risk": 0.010, "max_trades": 999},
    "PAUSE":    {"threshold": 0.25, "risk": 0.000, "max_trades": 0},
}

# ── Signal Filters — quality over quantity ────────────────────────────────────
VOLUME_SPIKE_THRESHOLD = 0.0  # NO volume filter
MIN_ATR_FILTER = 0.0
MIN_TRADE_GRADE = "B"         # only trend-aligned or confirmed setups
MARKET_MIN_GRADE = {}
COUNTER_TREND_PROB_FLOOR = 0.0  # NO counter-trend filter
MAX_SAME_DIRECTION = 3         # max 3 trades in same direction
MAX_OPEN_TRADES = 3            # max 3 concurrent trades
LOSS_COOLDOWN_MINUTES = 15     # 15 min cooldown per symbol after SL hit

# ── Fees — maker rate for limit orders ───────────────────────────────────────
SIMULATE_FEES = True
TAKER_FEE_RATE = 0.0002       # 0.02% maker fee

# ── Smart Exit — close at profit, don't wait for TP ──────────────────────────
RESOLVE_TIMEOUT_MINUTES = 30   # 30 min max hold — more time for profits to develop
MIN_ATR_PCT = 0.0005           # 0.05% — only skip truly dead markets
EARLY_PROFIT_USD = 1.00        # close if raw profit covers fees + nets $1.00
TIME_DECAY_PROFIT_USD = 0.10   # after 10 min, close if raw profit covers fees + $0.10
EARLY_LOSS_USD = -2.50         # close if raw loss ≥ $2.50 (before fees, ~0.25% move)

# ── Trailing Stop ────────────────────────────────────────────────────────────
TRAILING_STOP_ENABLED = False  # OFF — simple SL/TP, no complications
TRAILING_TP_BOOST = 1.0
TRAILING_BOOST_ASSETS = []

# ── Bot Timing — fast scanning ───────────────────────────────────────────────
SCAN_INTERVAL_SECONDS = 60     # 60 sec — faster resolution cycles
DATA_LOOKBACK_BARS = 300

# ── Auto Systems ─────────────────────────────────────────────────────────────
DATA_COLLECTION_INTERVAL = 300
RETRAIN_INTERVAL_HOURS = 6
RETRAIN_MIN_ROWS = 500

# ── Swing Trading Strategy ───────────────────────────────────────────────────
SWING_ENABLED = True
SWING_TF = "4h"                    # 4-hour candles for swing
SWING_LOOKBACK_BARS = 500          # more history for 4h
SWING_MODEL_FILE = MODELS_DIR / "lgbm_swing_model.txt"
SWING_LEVERAGE = 5                 # conservative leverage
SWING_RISK_PER_TRADE = 0.03       # 3% risk per swing trade ($6 on $200)
SWING_SL_ATR_MULT = 2.0           # 2x ATR stop (wider)
SWING_TP_ATR_MULT = 6.0           # 6x ATR target → 1:3 R:R
SWING_MIN_SL_PCT = 0.015          # 1.5% minimum stop distance
SWING_RESOLVE_TIMEOUT_HOURS = 48  # 2 days to let trades work
SWING_SCAN_INTERVAL_SECONDS = 900 # scan every 15 min (4h candles don't change fast)
SWING_MAX_OPEN = 3                # max 3 swing trades at once
SWING_MAX_SAME_DIR = 2            # max 2 same direction
SWING_COOLDOWN_HOURS = 4          # 4h cooldown after SL hit
SWING_PROB_LONG = 0.55            # higher threshold for swing (more selective)
SWING_PROB_SHORT = 0.45
SWING_TARGET_THRESHOLD = 0.015    # 1.5% move target for swing labels
SWING_TRADES_LOG = LOGS_DIR / "paper_trades_swing.jsonl"
SWING_PNL_LOG = LOGS_DIR / "paper_pnl_swing.jsonl"
