"""Quick check: is the market actually moving in the direction the model predicts?"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.pipeline import fetch_ohlcv, _get_public_exchange
from features.engineer import build_features
from models.trainer import load_model, predict
from config.settings import SYMBOLS, ENTRY_TF, MODEL_FILE, PROB_LONG_THRESHOLD, PROB_SHORT_THRESHOLD

ex = _get_public_exchange()
model = load_model(MODEL_FILE)

print(f"{'SYM':>5}  {'CLOSE':>10}  {'5ago':>10}  {'CHG%':>7}  {'PROB':>5}  {'TREND':>5}  {'SIGNAL':>6}  {'MATCH':>5}")
print("-" * 72)

for sym in SYMBOLS:
    df = fetch_ohlcv(sym, ENTRY_TF, limit=300, exchange=ex)
    df = build_features(df)
    df.dropna(inplace=True)
    last = df.iloc[-1]
    c5 = df.iloc[-6]["close"]
    close = last["close"]
    chg = (close - c5) / c5 * 100
    trend = int(last["trend_dir"])
    probs = predict(model, df)
    prob = float(probs[-1])
    signal = "SHORT" if prob < PROB_SHORT_THRESHOLD else ("LONG" if prob > PROB_LONG_THRESHOLD else "NONE")
    # Does the market actually agree?
    if signal == "SHORT":
        match = "YES" if chg < 0 else "NO"
    elif signal == "LONG":
        match = "YES" if chg > 0 else "NO"
    else:
        match = "-"
    name = sym.split("/")[0]
    print(f"{name:>5}  {close:>10.4f}  {c5:>10.4f}  {chg:>+7.2f}  {prob:>5.2f}  {trend:>5d}  {signal:>6s}  {match:>5s}")
