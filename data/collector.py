"""
Data Collector — Automatic OHLCV data collection and local storage.
====================================================================
Fetches 5-minute candles from Bybit for all configured symbols.
Stores historical data locally as CSV files with incremental updates.
Designed to run in a background thread alongside the trading bot.
"""

from __future__ import annotations
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from config.settings import (
    SYMBOLS, ENTRY_TF, DATA_RAW, DATA_LOOKBACK_BARS,
    DATA_COLLECTION_INTERVAL,
)
from data.pipeline import fetch_ohlcv, save_raw, _get_public_exchange

log = logging.getLogger("data.collector")


def collect_all(exchange=None) -> dict[str, int]:
    """
    Fetch latest OHLCV data for all symbols and save to local CSV.
    
    Returns dict of {symbol: rows_saved}.
    """
    if exchange is None:
        exchange = _get_public_exchange()

    results = {}
    for sym in SYMBOLS:
        try:
            df = fetch_ohlcv(sym, ENTRY_TF, limit=DATA_LOOKBACK_BARS, exchange=exchange)
            if df.empty:
                log.warning("No data returned for %s", sym)
                continue

            # Merge with existing local data (no duplicates)
            local_df = _load_local(sym)
            if local_df is not None and not local_df.empty:
                combined = pd.concat([local_df, df])
                combined = combined[~combined.index.duplicated(keep="last")]
                combined.sort_index(inplace=True)
                # Keep last 5000 bars max to avoid unbounded growth
                if len(combined) > 5000:
                    combined = combined.iloc[-5000:]
                df = combined

            save_raw(df, sym, ENTRY_TF)
            results[sym] = len(df)
            time.sleep(0.3)  # rate limit

        except Exception as e:
            log.error("Collection failed for %s: %s", sym, e)
            results[sym] = 0

    log.info("Data collection complete: %d symbols, %d total bars",
             len(results), sum(results.values()))
    return results


def _load_local(symbol: str) -> pd.DataFrame | None:
    """Load existing local CSV data for a symbol."""
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    fname = f"{symbol.replace('/', '').replace(':', '_')}_{ENTRY_TF}.csv"
    path = DATA_RAW / fname
    if path.exists():
        try:
            df = pd.read_csv(path, index_col="timestamp", parse_dates=True)
            return df
        except Exception:
            return None
    return None


def get_latest_data(symbol: str) -> pd.DataFrame | None:
    """Get the most recent local data for a symbol (for model/scanner use)."""
    return _load_local(symbol)


def run_collector_loop(exchange=None):
    """
    Continuous data collection loop — designed to run in a background thread.
    Fetches data every DATA_COLLECTION_INTERVAL seconds.
    """
    if exchange is None:
        exchange = _get_public_exchange()

    log.info("Data collector started (interval=%ds)", DATA_COLLECTION_INTERVAL)

    while True:
        try:
            collect_all(exchange)
        except Exception as e:
            log.error("Collector loop error: %s", e)

        time.sleep(DATA_COLLECTION_INTERVAL)
