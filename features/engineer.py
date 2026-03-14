"""
Feature Engineering — Compute predictive indicators.
=====================================================
Includes proven quantitative techniques:
  • VWAP (Volume-Weighted Average Price) — institutional standard
  • Bollinger Bands (%B + bandwidth) — statistical mean reversion (John Bollinger)
  • Hurst Exponent — fractal analysis, trending vs mean-reverting (H.E. Hurst, 1951)
  • OBV (On-Balance Volume) — Larry Williams / Joe Granville, volume-confirms-price
  • RSI Divergence — momentum reversal detection
  • Market Regime — volatility regime classification
"""

from __future__ import annotations
import numpy as np
import pandas as pd

from config.settings import (
    EMA_PERIODS, RSI_PERIOD, MACD_FAST, MACD_SLOW, MACD_SIGNAL,
    ATR_PERIOD, VOLUME_LOOKBACK, MOMENTUM_PERIOD,
    TARGET_THRESHOLD, PREDICTION_HORIZON, FEATURE_COLS,
)


# ── Indicator helpers ────────────────────────────────────────────────────────

def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0.0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / (loss + 1e-10)
    return 100 - (100 / (1 + rs))


def macd(series: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    fast = ema(series, MACD_FAST)
    slow = ema(series, MACD_SLOW)
    macd_line = fast - slow
    signal_line = ema(macd_line, MACD_SIGNAL)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = ATR_PERIOD) -> pd.Series:
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


# ── VWAP (Volume-Weighted Average Price) ─────────────────────────────────────
# Institutional benchmark: price above VWAP = buyers in control, below = sellers
# Resets each session (rolling window since crypto trades 24/7)

def vwap(high: pd.Series, low: pd.Series, close: pd.Series,
         volume: pd.Series, period: int = 50) -> pd.Series:
    """Rolling VWAP over `period` bars (no session reset for 24/7 crypto)."""
    typical_price = (high + low + close) / 3.0
    tp_vol = typical_price * volume
    cum_tp_vol = tp_vol.rolling(window=period, min_periods=1).sum()
    cum_vol = volume.rolling(window=period, min_periods=1).sum()
    return cum_tp_vol / (cum_vol + 1e-10)


# ── Bollinger Bands (John Bollinger, 1983) ───────────────────────────────────
# %B = position within bands (0 = lower, 1 = upper, >1 = above upper)
# Bandwidth = band width relative to middle → measures volatility expansion/squeeze

def bollinger_bands(close: pd.Series, period: int = 20, num_std: float = 2.0):
    """Returns (percent_b, bandwidth) — both normalized features."""
    sma = close.rolling(window=period, min_periods=1).mean()
    std = close.rolling(window=period, min_periods=1).std()
    upper = sma + num_std * std
    lower = sma - num_std * std
    # %B: where price sits within the bands (0–1 = inside, <0 or >1 = outside)
    percent_b = (close - lower) / (upper - lower + 1e-10)
    # Bandwidth: normalized volatility measure
    bandwidth = (upper - lower) / (sma + 1e-10)
    return percent_b, bandwidth


# ── Hurst Exponent (H.E. Hurst, 1951) ──────────────────────────────────────
# H > 0.5 → trending (persistent)
# H = 0.5 → random walk (no edge)
# H < 0.5 → mean-reverting (anti-persistent)
# Uses Rescaled Range (R/S) analysis — the original method from hydrology

def hurst_exponent(series: pd.Series, max_lag: int = 20) -> pd.Series:
    """
    Rolling Hurst exponent using correct R/S analysis on LOG RETURNS.

    The proper R/S method (Hurst, 1951):
      For each chunk size n, split the segment into non-overlapping chunks
      of length n. For each chunk, compute rescaled range R/S. Average R/S
      across all chunks for that n. Then regress log(mean R/S) on log(n)
      across multiple chunk sizes — the slope is the Hurst exponent.

    Previous implementation was broken: it used segment[:lag] (a growing
    prefix from the same start point) instead of non-overlapping sub-periods,
    which always produced H ≈ 0.95–1.0 regardless of market conditions.

    Returns a Series of H values (0 to 1).
    """
    result = pd.Series(np.nan, index=series.index)
    # Must use log returns, not raw prices (prices have unit root → H≈1.0)
    log_returns = np.log(series / series.shift(1)).values
    window = max_lag * 5  # need enough data for the largest chunk size

    for i in range(window + 1, len(log_returns)):
        segment = log_returns[i - window:i]
        if not np.all(np.isfinite(segment)):
            continue

        # Test chunk sizes from 8 up to window//2
        # (need at least 2 non-overlapping chunks per size)
        min_chunk = 8
        max_chunk = len(segment) // 2
        if max_chunk < min_chunk:
            continue

        chunk_sizes = []
        mean_rs = []

        n = min_chunk
        while n <= max_chunk:
            # Split segment into non-overlapping chunks of size n
            num_chunks = len(segment) // n
            if num_chunks < 2:
                break

            rs_for_this_n = []
            for c in range(num_chunks):
                chunk = segment[c * n:(c + 1) * n]
                mean_val = np.mean(chunk)
                deviations = chunk - mean_val
                cumulative = np.cumsum(deviations)
                r = np.max(cumulative) - np.min(cumulative)
                s = np.std(chunk, ddof=1)
                if s > 1e-10:
                    rs_for_this_n.append(r / s)

            if len(rs_for_this_n) >= 2:
                chunk_sizes.append(n)
                mean_rs.append(np.mean(rs_for_this_n))

            # Increase chunk size (use ~1.4x steps for good log spacing)
            n = max(n + 1, int(n * 1.4))

        if len(chunk_sizes) >= 3:
            log_n = np.log(np.array(chunk_sizes, dtype=float))
            log_rs = np.log(np.array(mean_rs, dtype=float))
            n_pts = len(log_n)
            slope = (n_pts * np.sum(log_n * log_rs) - np.sum(log_n) * np.sum(log_rs)) / \
                    (n_pts * np.sum(log_n ** 2) - np.sum(log_n) ** 2 + 1e-10)
            result.iloc[i] = np.clip(slope, 0.0, 1.0)

    return result


# ── OBV (On-Balance Volume) — Joe Granville ──────────────────────────────────
# Volume confirms price: rising OBV + rising price = strong trend
# Divergence between OBV and price signals potential reversal

def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On-Balance Volume — cumulative volume flow indicator."""
    direction = np.sign(close.diff())
    return (volume * direction).cumsum()


def obv_slope(close: pd.Series, volume: pd.Series, period: int = 10) -> pd.Series:
    """Normalized OBV slope — rate of change of OBV over `period` bars."""
    obv_vals = obv(close, volume)
    return obv_vals.pct_change(period)


# ── RSI Divergence Detection ────────────────────────────────────────────────
# Bearish divergence: price makes higher high but RSI makes lower high → reversal
# Bullish divergence: price makes lower low but RSI makes higher low → reversal
# Uses rolling window to detect divergence over recent bars

def rsi_divergence(close: pd.Series, rsi_series: pd.Series,
                   lookback: int = 14) -> pd.Series:
    """
    Detect RSI divergence: +1 = bullish divergence, -1 = bearish, 0 = none.
    """
    result = pd.Series(0.0, index=close.index)

    for i in range(lookback, len(close)):
        window_close = close.iloc[i - lookback:i + 1]
        window_rsi = rsi_series.iloc[i - lookback:i + 1]

        price_now = window_close.iloc[-1]
        price_prev_high = window_close.iloc[:-1].max()
        price_prev_low = window_close.iloc[:-1].min()

        rsi_now = window_rsi.iloc[-1]
        rsi_at_prev_high = window_rsi.iloc[window_close.iloc[:-1].argmax()]
        rsi_at_prev_low = window_rsi.iloc[window_close.iloc[:-1].argmin()]

        # Bearish divergence: price higher high, RSI lower high
        if price_now >= price_prev_high and rsi_now < rsi_at_prev_high - 2:
            result.iloc[i] = -1.0

        # Bullish divergence: price lower low, RSI higher low
        elif price_now <= price_prev_low and rsi_now > rsi_at_prev_low + 2:
            result.iloc[i] = 1.0

    return result


# ── Market Regime Detection ─────────────────────────────────────────────────
# Classifies market into regimes using ATR ratio + volatility
# 1 = trending, 0 = ranging, -1 = volatile/chaotic

def market_regime(atr_series: pd.Series, close: pd.Series,
                  short_window: int = 10, long_window: int = 50) -> pd.Series:
    """
    Volatility regime: compare short ATR to long ATR.
    High ratio = breakout/trending, low ratio = ranging, very high = chaotic.
    """
    atr_short = atr_series.rolling(window=short_window, min_periods=1).mean()
    atr_long = atr_series.rolling(window=long_window, min_periods=1).mean()
    atr_ratio = atr_short / (atr_long + 1e-10)

    # Classify: trending if ratio > 1.2, ranging if < 0.8, normal otherwise
    regime = pd.Series(0.0, index=close.index)
    regime = np.where(atr_ratio > 1.2, 1.0, np.where(atr_ratio < 0.8, -1.0, 0.0))
    return pd.Series(regime, index=close.index)


# ── Main Feature Builder ────────────────────────────────────────────────────

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add all predictive features to an OHLCV DataFrame.

    Expects columns: open, high, low, close, volume.
    Returns the same DataFrame with feature columns appended.

    Mathematical techniques included:
      — VWAP: institutional fair-value benchmark
      — Bollinger %B: statistical band position (mean reversion)
      — Bollinger Bandwidth: volatility expansion/squeeze
      — Hurst Exponent: trending vs mean-reverting (R/S analysis)
      — OBV Slope: volume-confirms-price momentum
      — RSI Divergence: momentum reversal detection
      — Market Regime: volatility regime classification
    """
    df = df.copy()
    c = df["close"]

    # EMAs
    df["ema20"] = ema(c, 20)
    df["ema50"] = ema(c, 50)
    df["ema200"] = ema(c, 200)

    # EMA slope (rate of change over 5 bars)
    df["ema20_slope"] = df["ema20"].pct_change(5)

    # Price relative to EMA200
    df["price_vs_ema200"] = (c - df["ema200"]) / (df["ema200"] + 1e-10)

    # RSI
    df["rsi14"] = rsi(c, RSI_PERIOD)

    # MACD
    macd_line, signal_line, _ = macd(c)
    df["macd"] = macd_line
    df["macd_signal"] = signal_line

    # ATR
    df["atr14"] = atr(df["high"], df["low"], c, ATR_PERIOD)

    # Volume z-score
    vol_mean = df["volume"].rolling(VOLUME_LOOKBACK).mean()
    vol_std = df["volume"].rolling(VOLUME_LOOKBACK).std()
    df["vol_zscore"] = (df["volume"] - vol_mean) / (vol_std + 1e-10)

    # Momentum
    df["momentum"] = c.pct_change(MOMENTUM_PERIOD)

    # Candle body ratio
    candle_range = df["high"] - df["low"]
    df["candle_body"] = (c - df["open"]).abs() / (candle_range + 1e-10)

    # Trend direction: +1 bullish stack, -1 bearish, 0 neutral
    df["trend_dir"] = np.where(
        (df["ema20"] > df["ema50"]) & (df["ema50"] > df["ema200"]), 1,
        np.where(
            (df["ema20"] < df["ema50"]) & (df["ema50"] < df["ema200"]), -1, 0
        )
    )

    # Time features — cyclical encoding to prevent memorizing specific hours/days
    if hasattr(df.index, "hour"):
        h = df.index.hour
        dow = df.index.dayofweek
    else:
        h = 0
        dow = 0
    df["hour_sin"] = np.sin(2 * np.pi * h / 24)
    df["hour_cos"] = np.cos(2 * np.pi * h / 24)
    df["dow_sin"] = np.sin(2 * np.pi * dow / 7)
    df["dow_cos"] = np.cos(2 * np.pi * dow / 7)

    # ── NEW: VWAP — Volume-Weighted Average Price ────────────────────────
    df["vwap"] = vwap(df["high"], df["low"], c, df["volume"])
    # Price position relative to VWAP: positive = above (bullish), negative = below
    df["price_vs_vwap"] = (c - df["vwap"]) / (df["vwap"] + 1e-10)

    # ── NEW: Bollinger Bands — %B and Bandwidth ─────────────────────────
    df["bb_percent_b"], df["bb_bandwidth"] = bollinger_bands(c, period=20, num_std=2.0)

    # ── NEW: Hurst Exponent — trending vs mean-reverting ─────────────────
    df["hurst"] = hurst_exponent(c, max_lag=20)
    df["hurst"] = df["hurst"].fillna(0.5)  # default to random walk

    # ── NEW: OBV Slope — volume confirms price ──────────────────────────
    df["obv_slope"] = obv_slope(c, df["volume"], period=10)

    # ── NEW: RSI Divergence — reversal signal ────────────────────────────
    df["rsi_divergence"] = rsi_divergence(c, df["rsi14"], lookback=14)

    # ── NEW: Market Regime — volatility classification ───────────────────
    df["market_regime"] = market_regime(df["atr14"], c)

    return df


# ── Target Label Builder ────────────────────────────────────────────────────

def build_target(df: pd.DataFrame, threshold: float = TARGET_THRESHOLD,
                 horizon: int = PREDICTION_HORIZON) -> pd.Series:
    """
    Symmetric binary target for balanced LONG/SHORT learning.

    Returns:
      1   if price rises >= threshold within horizon bars  (LONG opportunity)
      0   if price drops >= threshold within horizon bars  (SHORT opportunity)
      NaN if price stays flat (within threshold both ways) — excluded from training

    This prevents the class imbalance that causes all-SHORT bias.
    The model learns BOTH upside AND downside patterns equally.
    """
    close = df["close"]
    future_max = close.shift(-1).rolling(window=horizon, min_periods=1).max().shift(-(horizon - 1))
    future_min = close.shift(-1).rolling(window=horizon, min_periods=1).min().shift(-(horizon - 1))

    goes_up = future_max >= close * (1 + threshold)
    goes_down = future_min <= close * (1 - threshold)

    # Priority: if both triggered, pick the one that happened first (use max/min)
    # If only up → 1, if only down → 0, if both → check magnitude, if neither → NaN
    target = pd.Series(np.nan, index=df.index)
    target[goes_up & ~goes_down] = 1.0   # clear upside
    target[goes_down & ~goes_up] = 0.0   # clear downside
    target[goes_up & goes_down] = np.where(
        (future_max[goes_up & goes_down] / close[goes_up & goes_down] - 1) >=
        (1 - future_min[goes_up & goes_down] / close[goes_up & goes_down]),
        1.0, 0.0
    )  # both triggered → pick larger move
    # Neither triggered → stays NaN → dropped in prepare_dataset

    return target


def prepare_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """Build features + target, drop NaNs, return clean dataset."""
    df = build_features(df)
    df["target"] = build_target(df)
    df.dropna(inplace=True)
    return df
