"""
Signal Generator — Convert ML predictions + filters into trade signals.
=======================================================================
Uses a confidence-based system: higher ML confidence = more permissive.
Counter-trend trades are ALLOWED when ML confidence is strong enough.

Quantitative confirmations:
  • VWAP confluence — institutional fair-value filter
  • Bollinger Band extremes — mean reversion at ±2σ
  • Hurst Exponent — skip signals in random-walk markets (H ≈ 0.5)
  • RSI Divergence — upgrade/downgrade on momentum divergence
  • Market Regime — adapt behavior to trending vs ranging conditions
"""

from __future__ import annotations
import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from config.settings import (
    PROB_LONG_THRESHOLD, PROB_SHORT_THRESHOLD,
    VOLUME_SPIKE_THRESHOLD, MIN_TRADE_GRADE,
)

log = logging.getLogger(__name__)


@dataclass
class Signal:
    symbol: str
    direction: str  # "LONG", "SHORT", "NONE"
    probability: float
    grade: str       # "A+", "A", "SKIP"
    trend_ok: bool
    volume_ok: bool
    sweep_detected: bool
    entry_price: float
    atr: float
    reason: str
    confidence: float = 0.0  # ML confidence strength (how far from 0.50)


def detect_liquidity_sweep(df: pd.DataFrame, lookback: int = 20) -> bool:
    if len(df) < lookback + 1:
        return False
    recent_low = df["low"].iloc[-(lookback + 1):-1].min()
    last = df.iloc[-1]
    swept_below = last["low"] < recent_low and last["close"] > recent_low
    recent_high = df["high"].iloc[-(lookback + 1):-1].max()
    swept_above = last["high"] > recent_high and last["close"] < recent_high
    return swept_below or swept_above


def generate_signal(
    symbol: str,
    df: pd.DataFrame,
    probability: float,
) -> Signal:
    """
    Generate a trade signal from ML probability and filter conditions.

    Key change: counter-trend trades are now ALLOWED when ML confidence
    is strong enough. This prevents the bot from sitting idle when
    the model sees opportunity the EMAs haven't caught up with yet.
    """
    last = df.iloc[-1]
    entry_price = last["close"]
    atr_val = last.get("atr14", 0.0)
    trend = int(last.get("trend_dir", 0))
    vol_z = last.get("vol_zscore", 0.0)

    # ── ML confidence = distance from 0.50 ──────────────────────────────
    confidence = abs(probability - 0.50) * 2  # 0.0 = no edge, 1.0 = max edge

    # ── Direction from probability ───────────────────────────────────────
    if probability >= PROB_LONG_THRESHOLD:
        direction = "LONG"
    elif probability <= PROB_SHORT_THRESHOLD:
        direction = "SHORT"
    else:
        return Signal(symbol, "NONE", probability, "SKIP",
                      False, False, False, entry_price, atr_val,
                      f"Probability {probability:.2f} in dead zone",
                      confidence)

    # ── Trend alignment ──────────────────────────────────────────────────
    ema20_slope = last.get("ema20_slope", 0.0)

    if trend != 0:
        trend_ok = (direction == "LONG" and trend == 1) or \
                   (direction == "SHORT" and trend == -1)
        counter_trend = not trend_ok
    else:
        # Neutral: use short-term slope as tiebreaker
        if direction == "LONG":
            trend_ok = ema20_slope > 0
        else:
            trend_ok = ema20_slope < 0
        counter_trend = not trend_ok

    # ── Volume confirmation ──────────────────────────────────────────────
    volume_ok = vol_z >= VOLUME_SPIKE_THRESHOLD

    # ── Liquidity sweep ──────────────────────────────────────────────────
    sweep = detect_liquidity_sweep(df)

    # ── Grade the setup ──────────────────────────────────────────────────
    # IMPORTANT: Counter-trend trades now get base grade C (not D)
    # They can be upgraded by quant confirmations below
    if trend_ok and volume_ok and sweep:
        grade = "A+"
    elif trend_ok and volume_ok:
        grade = "A"
    elif trend_ok and sweep:
        grade = "B+"
    elif trend_ok:
        grade = "B"
    elif counter_trend and (volume_ok or sweep):
        # Counter-trend with volume/sweep confirmation = tradeable
        grade = "C"
    elif counter_trend and confidence >= 0.30:
        # Strong ML confidence counter-trend = give it C grade (tradeable)
        grade = "C"
    else:
        grade = "D"

    # ══════════════════════════════════════════════════════════════════════
    # QUANTITATIVE CONFIRMATIONS — upgrade/downgrade grades
    # ══════════════════════════════════════════════════════════════════════

    # ── VWAP Confluence ──────────────────────────────────────────────────
    price_vs_vwap = last.get("price_vs_vwap", 0.0)
    vwap_confirms = (direction == "LONG" and price_vs_vwap > 0) or \
                    (direction == "SHORT" and price_vs_vwap < 0)
    if vwap_confirms and grade in ("B", "B+", "C"):
        grade = {"B": "B+", "B+": "A", "C": "B"}[grade]

    # ── Bollinger Band Mean Reversion ────────────────────────────────────
    bb_pct_b = last.get("bb_percent_b", 0.5)
    bb_extreme_long = bb_pct_b < 0.10    # oversold (was 0.05 — too strict)
    bb_extreme_short = bb_pct_b > 0.90   # overbought (was 0.95 — too strict)

    if direction == "LONG" and bb_extreme_long and grade in ("B", "B+", "C", "D"):
        grade = "B+"  # oversold + LONG = mean reversion setup
    if direction == "SHORT" and bb_extreme_short and grade in ("B", "B+", "C", "D"):
        grade = "B+"  # overbought + SHORT = mean reversion setup
    if direction == "LONG" and bb_extreme_short and grade in ("A", "A+"):
        grade = "B+"
    if direction == "SHORT" and bb_extreme_long and grade in ("A", "A+"):
        grade = "B+"

    # ── Hurst Exponent ───────────────────────────────────────────────────
    hurst_val = last.get("hurst", 0.5)
    is_random_walk = 0.45 <= hurst_val <= 0.55
    is_trending = hurst_val > 0.55
    is_mean_reverting = hurst_val < 0.45

    # Only downgrade on random walk if confidence is weak
    if is_random_walk and grade in ("C", "D") and confidence < 0.20:
        grade = "D"

    if is_trending and trend_ok and grade in ("B+", "B"):
        grade = "A"

    # ── RSI Divergence ───────────────────────────────────────────────────
    rsi_div = last.get("rsi_divergence", 0.0)

    if rsi_div > 0 and direction == "LONG" and grade in ("B", "B+", "C"):
        grade = "A"  # bullish divergence confirms LONG
    if rsi_div < 0 and direction == "SHORT" and grade in ("B", "B+", "C"):
        grade = "A"  # bearish divergence confirms SHORT
    if rsi_div < 0 and direction == "LONG" and grade in ("A", "A+"):
        grade = "B+"
    if rsi_div > 0 and direction == "SHORT" and grade in ("A", "A+"):
        grade = "B+"

    # ── Market Regime Adaptation ─────────────────────────────────────────
    regime = last.get("market_regime", 0.0)

    if regime == 1.0 and not trend_ok and grade in ("B",) and confidence < 0.30:
        grade = "C"  # trending regime against us, weak confidence → downgrade
    if regime == -1.0 and trend_ok and not is_trending:
        if grade in ("A", "A+"):
            grade = "B+"

    # ── Momentum cross-check (LAST — applies to ALL grades) ─────────────
    momentum_val = last.get("momentum", 0.0)
    momentum_opposes = (direction == "SHORT" and momentum_val > 0.002) or \
                       (direction == "LONG" and momentum_val < -0.002)
    # Only downgrade if momentum opposition is strong AND confidence is weak
    if momentum_opposes and confidence < 0.30:
        downgrade = {"A+": "A", "A": "B+", "B+": "B", "B": "C", "C": "D"}
        if grade in downgrade:
            grade = downgrade[grade]

    # ── Apply MIN_TRADE_GRADE filter ─────────────────────────────────────
    grade_rank = {"A+": 6, "A": 5, "B+": 4, "B": 3, "C": 2, "D": 1, "SKIP": 0}
    min_rank = grade_rank.get(MIN_TRADE_GRADE, 2)
    if grade_rank.get(grade, 0) < min_rank:
        direction = "NONE"
        grade = "SKIP"

    reason_parts = []
    if trend_ok:
        reason_parts.append("trend-aligned")
    else:
        reason_parts.append("counter-trend")
    reason_parts.append(f"conf={confidence:.0%}")
    if volume_ok:
        reason_parts.append(f"vol-spike({vol_z:.1f}σ)")
    if sweep:
        reason_parts.append("sweep")
    if vwap_confirms:
        reason_parts.append("VWAP✓")
    if bb_extreme_long:
        reason_parts.append("BB-oversold")
    elif bb_extreme_short:
        reason_parts.append("BB-overbought")
    if is_trending:
        reason_parts.append(f"Hurst={hurst_val:.2f}↑")
    elif is_mean_reverting:
        reason_parts.append(f"Hurst={hurst_val:.2f}↓")
    if rsi_div != 0:
        reason_parts.append(f"RSI-div={'bull' if rsi_div > 0 else 'bear'}")
    if regime == 1.0:
        reason_parts.append("regime:trend")
    elif regime == -1.0:
        reason_parts.append("regime:range")
    reason = f"Prob={probability:.2f} | {' + '.join(reason_parts)} → {grade}"

    return Signal(
        symbol=symbol,
        direction=direction,
        probability=probability,
        grade=grade,
        trend_ok=trend_ok,
        volume_ok=volume_ok,
        sweep_detected=sweep,
        entry_price=entry_price,
        atr=atr_val,
        confidence=confidence,
        reason=reason,
    )
