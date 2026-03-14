"""Debug: check actual feature values for each symbol."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.pipeline import fetch_ohlcv, _get_public_exchange
from features.engineer import build_features
from config.settings import SYMBOLS, ENTRY_TF

ex = _get_public_exchange()

print(f"{'SYM':>5}  {'MOM':>8}  {'HURST':>6}  {'VWAP':>8}  {'REG':>4}  {'SLOPE':>8}  {'BB%B':>6}  {'RSI_D':>5}  {'OBV_S':>8}")
print("-" * 80)

for sym in SYMBOLS:
    df = fetch_ohlcv(sym, ENTRY_TF, limit=300, exchange=ex)
    df = build_features(df)
    df.dropna(inplace=True)
    last = df.iloc[-1]
    name = sym.split("/")[0]
    print(f"{name:>5}  {last['momentum']:>8.5f}  {last['hurst']:>6.3f}  {last['price_vs_vwap']:>8.5f}  {last['market_regime']:>4.0f}  {last['ema20_slope']:>8.5f}  {last['bb_percent_b']:>6.3f}  {last['rsi_divergence']:>5.0f}  {last['obv_slope']:>8.5f}")
