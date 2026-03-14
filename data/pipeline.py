"""
Data Pipeline — Fetch and cache OHLCV data via CCXT.
=====================================================
"""

from __future__ import annotations
import time
import logging
from pathlib import Path

import ccxt
import pandas as pd

from config.settings import (
    BYBIT_API_KEY, BYBIT_API_SECRET, BYBIT_TESTNET,
    DATA_RAW, DATA_LOOKBACK_BARS,
)

log = logging.getLogger(__name__)


def _get_public_exchange() -> ccxt.bybit:
    """Create an unauthenticated CCXT Bybit instance for public data."""
    exchange = ccxt.bybit({
        "enableRateLimit": True,
        "options": {"defaultType": "swap"},
    })
    if BYBIT_TESTNET:
        exchange.set_sandbox_mode(True)
    return exchange


def _get_exchange() -> ccxt.bybit:
    """Create an authenticated CCXT Bybit instance for private calls."""
    exchange = ccxt.bybit({
        "apiKey": BYBIT_API_KEY,
        "secret": BYBIT_API_SECRET,
        "enableRateLimit": True,
        "options": {"defaultType": "swap"},
    })
    if BYBIT_TESTNET:
        exchange.set_sandbox_mode(True)
    return exchange


def fetch_ohlcv(
    symbol: str,
    timeframe: str = "5m",
    limit: int = DATA_LOOKBACK_BARS,
    exchange: ccxt.bybit | None = None,
) -> pd.DataFrame:
    """
    Fetch OHLCV candles from Bybit.

    Parameters
    ----------
    symbol    : e.g. "BTC/USDT:USDT"
    timeframe : "5m", "15m", "1h"
    limit     : number of bars
    exchange  : optional pre-created exchange instance

    Returns
    -------
    DataFrame with columns: timestamp, open, high, low, close, volume
    """
    if exchange is None:
        exchange = _get_public_exchange()

    log.info("Fetching %d bars of %s %s …", limit, symbol, timeframe)
    bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

    df = pd.DataFrame(bars, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df.set_index("timestamp", inplace=True)
    df = df.astype(float)
    return df


def fetch_all_symbols(
    symbols: list[str],
    timeframe: str = "5m",
    limit: int = DATA_LOOKBACK_BARS,
) -> dict[str, pd.DataFrame]:
    """Fetch OHLCV for multiple symbols, return dict of DataFrames."""
    exchange = _get_exchange()
    result = {}
    for sym in symbols:
        try:
            result[sym] = fetch_ohlcv(sym, timeframe, limit, exchange)
            time.sleep(0.3)  # rate limit courtesy
        except Exception as e:
            log.error("Failed to fetch %s: %s", sym, e)
    return result


def save_raw(df: pd.DataFrame, symbol: str, timeframe: str):
    """Save raw OHLCV to CSV."""
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    fname = f"{symbol.replace('/', '').replace(':', '_')}_{timeframe}.csv"
    path = DATA_RAW / fname
    df.to_csv(path)
    log.info("Saved %d bars → %s", len(df), path)


def load_raw(symbol: str, timeframe: str) -> pd.DataFrame | None:
    """Load raw OHLCV from CSV if available."""
    fname = f"{symbol.replace('/', '').replace(':', '_')}_{timeframe}.csv"
    path = DATA_RAW / fname
    if path.exists():
        df = pd.read_csv(path, index_col="timestamp", parse_dates=True)
        return df
    return None
