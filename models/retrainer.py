"""
Auto Retrainer — Scheduled model retraining with fresh market data.
====================================================================
Periodically retrains the LightGBM model using the latest collected data.
Saves versioned models and automatically loads the newest one.
Designed to run in a background thread.
"""

from __future__ import annotations
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from config.settings import (
    SYMBOLS, ENTRY_TF, DATA_RAW, MODELS_DIR,
    RETRAIN_INTERVAL_HOURS, RETRAIN_MIN_ROWS,
)
from features.engineer import prepare_dataset
from models.trainer import train_model, load_model

log = logging.getLogger("retrainer")

# Track last retrain time
_last_retrain: datetime | None = None


def retrain_model() -> bool:
    """
    Retrain the ML model using all locally stored data.
    
    Returns True if retraining was successful.
    """
    global _last_retrain
    
    log.info("═══ AUTO RETRAIN STARTING ═══")
    
    frames = []
    for sym in SYMBOLS:
        df = _load_local_data(sym)
        if df is not None and len(df) > 50:
            try:
                dataset = prepare_dataset(df)
                dataset["symbol"] = sym
                frames.append(dataset)
                log.info("  %s: %d usable rows", sym.replace("/USDT:USDT", ""), len(dataset))
            except Exception as e:
                log.error("  %s: feature prep failed: %s", sym, e)
    
    if not frames:
        log.warning("No data available for retraining.")
        return False
    
    combined = pd.concat(frames, ignore_index=True)
    log.info("Combined dataset: %d rows from %d symbols", len(combined), len(frames))
    
    if len(combined) < RETRAIN_MIN_ROWS:
        log.warning("Not enough data (%d < %d min). Skipping retrain.",
                     len(combined), RETRAIN_MIN_ROWS)
        return False
    
    # Save versioned model (keep last 3)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    versioned_path = MODELS_DIR / f"lgbm_model_{timestamp}.txt"
    
    try:
        model = train_model(combined, save_path=versioned_path)
        
        # Also save as the main model file (overwrite)
        main_path = MODELS_DIR / "lgbm_model.txt"
        model.save_model(str(main_path))
        log.info("Model saved → %s (and %s)", main_path, versioned_path)
        
        # Cleanup old versioned models (keep last 3)
        _cleanup_old_models(keep=3)
        
        _last_retrain = datetime.now(timezone.utc)
        log.info("═══ AUTO RETRAIN COMPLETE ═══")
        return True
        
    except Exception as e:
        log.error("Retrain failed: %s", e)
        return False


def _load_local_data(symbol: str) -> pd.DataFrame | None:
    """Load locally stored CSV data for a symbol."""
    fname = f"{symbol.replace('/', '').replace(':', '_')}_{ENTRY_TF}.csv"
    path = DATA_RAW / fname
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path, index_col="timestamp", parse_dates=True)
        return df
    except Exception:
        return None


def _cleanup_old_models(keep: int = 3):
    """Remove old versioned model files, keeping the most recent N."""
    model_files = sorted(MODELS_DIR.glob("lgbm_model_*.txt"), reverse=True)
    for old_file in model_files[keep:]:
        try:
            old_file.unlink()
            log.info("Removed old model: %s", old_file.name)
        except Exception:
            pass


def should_retrain() -> bool:
    """Check if it's time to retrain based on the interval."""
    global _last_retrain
    
    if _last_retrain is None:
        # Check model file modification time
        main_model = MODELS_DIR / "lgbm_model.txt"
        if main_model.exists():
            mtime = datetime.fromtimestamp(main_model.stat().st_mtime, tz=timezone.utc)
            _last_retrain = mtime
        else:
            return True  # no model exists — retrain immediately
    
    hours_since = (datetime.now(timezone.utc) - _last_retrain).total_seconds() / 3600
    return hours_since >= RETRAIN_INTERVAL_HOURS


def run_retrainer_loop():
    """
    Continuous retraining loop — designed to run in a background thread.
    Checks every 30 minutes if retraining is needed.
    """
    log.info("Auto-retrainer started (interval=%dh)", RETRAIN_INTERVAL_HOURS)
    
    while True:
        try:
            if should_retrain():
                log.info("Retrain interval reached. Starting retrain...")
                retrain_model()
            else:
                hours_left = RETRAIN_INTERVAL_HOURS
                if _last_retrain:
                    elapsed = (datetime.now(timezone.utc) - _last_retrain).total_seconds() / 3600
                    hours_left = max(0, RETRAIN_INTERVAL_HOURS - elapsed)
                log.info("Next retrain in ~%.1f hours", hours_left)
        except Exception as e:
            log.error("Retrainer loop error: %s", e)
        
        # Check every 30 minutes
        time.sleep(1800)
