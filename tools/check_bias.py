"""Check ML model probability bias across all symbols."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
from data.pipeline import fetch_ohlcv, _get_public_exchange
from features.engineer import build_features
from models.trainer import load_model, predict
from config.settings import SYMBOLS, ENTRY_TF, PROB_LONG_THRESHOLD, PROB_SHORT_THRESHOLD

model = load_model()
ex = _get_public_exchange()
print(f"Thresholds: LONG > {PROB_LONG_THRESHOLD}, SHORT < {PROB_SHORT_THRESHOLD}")
print(f"{'SYM':6s} {'LAST':>8s} {'MEAN5':>8s} {'MIN':>8s} {'MAX':>8s} {'TREND':>6s} {'SIGNAL':>8s}")
print("-" * 60)

for sym in SYMBOLS:
    df = fetch_ohlcv(sym, ENTRY_TF, limit=300, exchange=ex)
    df = build_features(df)
    df.dropna(inplace=True)
    probs = predict(model, df)
    last = float(probs[-1])
    mean5 = float(np.mean(probs[-5:]))
    mn = float(np.min(probs))
    mx = float(np.max(probs))
    trend = int(df.iloc[-1].get("trend_dir", 0))
    if last > PROB_LONG_THRESHOLD:
        sig = "LONG"
    elif last < PROB_SHORT_THRESHOLD:
        sig = "SHORT"
    else:
        sig = "NONE"
    name = sym.replace("/USDT:USDT", "")
    print(f"{name:6s} {last:8.4f} {mean5:8.4f} {mn:8.4f} {mx:8.4f} {trend:6d} {sig:>8s}")
