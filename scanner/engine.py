"""
Market Scanner — Evaluate and rank trade opportunities across all coins.
=========================================================================
Scans all configured symbols, runs ML predictions, and ranks by signal quality.
Uses locally cached data (from the collector thread) to avoid duplicate API calls.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from config.settings import SYMBOLS, ENTRY_TF, DATA_LOOKBACK_BARS, DATA_RAW
from data.pipeline import fetch_ohlcv
from features.engineer import build_features
from models.trainer import predict
from signals.generator import generate_signal, Signal

log = logging.getLogger("scanner")


@dataclass
class ScanResult:
    """One scanned symbol with its signal and ranking score."""
    symbol: str
    signal: Signal
    score: float = 0.0
    rank: int = 0
    _df: object = None  # DataFrame for momentum check in scan_once


GRADE_SCORE = {"A+": 100, "A": 85, "B+": 70, "B": 55, "C": 40, "D": 20, "SKIP": 0}


def _load_local_data(symbol: str) -> pd.DataFrame | None:
    """Load locally cached CSV data for a symbol (written by collector thread)."""
    fname = f"{symbol.replace('/', '').replace(':', '_')}_{ENTRY_TF}.csv"
    path = DATA_RAW / fname
    if path.exists():
        try:
            df = pd.read_csv(path, index_col="timestamp", parse_dates=True)
            # Return only last DATA_LOOKBACK_BARS rows
            if len(df) > DATA_LOOKBACK_BARS:
                df = df.iloc[-DATA_LOOKBACK_BARS:]
            return df
        except Exception:
            return None
    return None


def scan_markets(model, exchange=None, symbols: list[str] | None = None) -> list[ScanResult]:
    """
    Scan all markets and rank trade opportunities.
    
    Prefers locally cached data from the collector thread to avoid
    duplicate API calls. Falls back to live fetch if no local data exists.
    
    Returns list of ScanResult sorted by score (best first).
    """
    if symbols is None:
        symbols = list(SYMBOLS)
    
    results: list[ScanResult] = []
    
    for sym in symbols:
        try:
            # Try local cache first (written by collector thread)
            df = _load_local_data(sym)
            if df is None or len(df) < 50:
                # Fallback: fetch live if no local data
                df = fetch_ohlcv(sym, ENTRY_TF, limit=DATA_LOOKBACK_BARS, exchange=exchange)
            
            df = build_features(df)
            df.dropna(inplace=True)
            
            if len(df) < 10:
                log.warning("Not enough data for %s, skipping.", sym)
                continue
            
            probs = predict(model, df)
            prob = float(probs[-1])
            
            signal = generate_signal(sym, df, prob)
            
            # Compute ranking score
            score = _compute_score(signal, prob, df)
            
            results.append(ScanResult(symbol=sym, signal=signal, score=score, _df=df))
            
        except Exception as e:
            log.error("Scan error for %s: %s", sym, e)
    
    # Sort by score descending (best opportunities first)
    results.sort(key=lambda r: r.score, reverse=True)
    
    # Assign ranks
    for i, r in enumerate(results):
        r.rank = i + 1
    
    return results


def _compute_score(signal: Signal, probability: float, df: pd.DataFrame) -> float:
    """
    Compute a ranking score for a signal based on multiple factors.
    Higher score = better trade opportunity.
    """
    if signal.direction == "NONE" or signal.grade == "SKIP":
        return 0.0
    
    last = df.iloc[-1]
    score = 0.0
    
    # 1. Grade score (0-100)
    score += GRADE_SCORE.get(signal.grade, 0)
    
    # 2. ML confidence bonus (0-50) — further from 0.50 = stronger signal
    confidence = abs(probability - 0.50) * 100
    score += confidence
    
    # 3. Trend alignment bonus (0-30)
    if signal.trend_ok:
        score += 30
    
    # 4. Volume confirmation bonus (0-20)
    if signal.volume_ok:
        vol_z = last.get("vol_zscore", 0.0)
        score += min(vol_z * 10, 20)
    
    # 5. Liquidity sweep bonus (0-15)
    if signal.sweep_detected:
        score += 15
    
    # 6. VWAP alignment bonus (0-10)
    price_vs_vwap = last.get("price_vs_vwap", 0.0)
    vwap_aligned = (signal.direction == "LONG" and price_vs_vwap > 0) or \
                   (signal.direction == "SHORT" and price_vs_vwap < 0)
    if vwap_aligned:
        score += 10
    
    # 7. Hurst trending bonus (0-10)
    hurst_val = last.get("hurst", 0.5)
    if hurst_val > 0.55 and signal.trend_ok:
        score += 10
    
    return round(score, 1)


def print_scan_table(results: list[ScanResult]):
    """Print a formatted scan results table to logs."""
    log.info("=" * 72)
    log.info("  MARKET SCANNER — %d symbols scanned", len(results))
    log.info("=" * 72)
    log.info("  %-4s  %-6s  %-5s  %-5s  %-5s  %-5s  %s",
             "RANK", "SYM", "PROB", "DIR", "GRADE", "SCORE", "REASON")
    log.info("-" * 72)
    
    for r in results:
        s = r.signal
        sym_short = s.symbol.replace("/USDT:USDT", "")
        icon = {"LONG": "🟢", "SHORT": "🔴", "NONE": "⚪"}.get(s.direction, "⚪")
        log.info("  #%-3d  %s%-4s  %.2f  %-5s  %-5s  %5.1f  %s",
                 r.rank, icon, sym_short, s.probability, s.direction,
                 s.grade, r.score, s.reason[:50])
    
    actionable = [r for r in results if r.signal.direction != "NONE" and r.signal.grade != "SKIP"]
    log.info("-" * 72)
    log.info("  Actionable: %d / %d signals", len(actionable), len(results))
    log.info("=" * 72)
