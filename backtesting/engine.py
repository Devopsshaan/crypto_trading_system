"""
Walk-Forward Backtester — Test strategy on historical data.
=============================================================
Simulates the full bot pipeline (features → model → signals → risk → execution)
on historical OHLCV data with realistic fee simulation and SL/TP resolution
using actual candle high/low data.

Usage
-----
    # Backtest using locally stored data
    py -m backtesting.engine

    # Backtest with fresh data (fetches from Bybit)
    py -m backtesting.engine --fetch

    # Backtest a single symbol
    py -m backtesting.engine --symbol BTC/USDT:USDT
"""

from __future__ import annotations
import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import (
    SYMBOLS, ENTRY_TF, FEATURE_COLS,
    PROB_LONG_THRESHOLD, PROB_SHORT_THRESHOLD,
    RISK_PER_TRADE, DEFAULT_LEVERAGE, TAKER_FEE_RATE,
    STARTING_BALANCE, MIN_TRADE_GRADE, TARGET_THRESHOLD,
    PREDICTION_HORIZON, TRAIN_RATIO, DATA_RAW,
)
from features.engineer import build_features, prepare_dataset
from models.trainer import train_model, predict
from signals.generator import generate_signal

log = logging.getLogger("backtest")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


@dataclass
class BacktestTrade:
    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    size: float
    grade: str
    entry_bar: int
    exit_bar: int = -1
    exit_price: float = 0.0
    exit_type: str = ""   # "SL", "TP", "TIMEOUT"
    pnl: float = 0.0
    fee: float = 0.0


@dataclass
class BacktestResult:
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    total_fees: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    trades: list = field(default_factory=list)
    equity_curve: list = field(default_factory=list)


def _load_data(symbol: str) -> pd.DataFrame | None:
    """Load locally cached CSV data for a symbol."""
    fname = f"{symbol.replace('/', '').replace(':', '_')}_{ENTRY_TF}.csv"
    path = DATA_RAW / fname
    if path.exists():
        df = pd.read_csv(path, index_col="timestamp", parse_dates=True)
        return df
    return None


def backtest_symbol(
    symbol: str,
    model,
    df: pd.DataFrame,
    start_balance: float = STARTING_BALANCE,
    max_bars_per_trade: int = 12,   # 12 × 5m = 60 min max hold
    risk_pct: float = RISK_PER_TRADE,
    leverage: int = DEFAULT_LEVERAGE,
) -> BacktestResult:
    """
    Walk-forward backtest for one symbol.

    The model is already trained on an earlier portion of the data.
    This function walks through the OUT-OF-SAMPLE bars one by one,
    generating signals and resolving trades using actual candle high/low.
    """
    df = build_features(df)
    df.dropna(inplace=True)

    if len(df) < 50:
        log.warning("Not enough data for %s (%d bars)", symbol, len(df))
        return BacktestResult()

    result = BacktestResult()
    balance = start_balance
    peak_balance = start_balance
    open_trades: list[BacktestTrade] = []

    grade_scale = {"A+": 1.0, "A": 1.0, "B+": 0.75, "B": 0.60, "C": 0.50, "D": 0.40}
    exec_grades = {"A+", "A", "B+", "B", "C", "D"}
    grade_rank = {"A+": 6, "A": 5, "B+": 4, "B": 3, "C": 2, "D": 1, "SKIP": 0}
    min_rank = grade_rank.get(MIN_TRADE_GRADE, 3)

    # Walk through bars one at a time
    for i in range(60, len(df)):
        bar = df.iloc[i]
        bar_high = bar["high"]
        bar_low = bar["low"]
        bar_close = bar["close"]

        # ── Resolve open trades using this bar's high/low ────────────
        still_open = []
        for trade in open_trades:
            bars_held = i - trade.entry_bar
            resolved = False

            if trade.direction == "LONG":
                if bar_low <= trade.stop_loss:
                    trade.exit_price = trade.stop_loss
                    trade.pnl = (trade.stop_loss - trade.entry_price) * trade.size
                    trade.exit_type = "SL"
                    resolved = True
                elif bar_high >= trade.take_profit:
                    trade.exit_price = trade.take_profit
                    trade.pnl = (trade.take_profit - trade.entry_price) * trade.size
                    trade.exit_type = "TP"
                    resolved = True
                elif bars_held >= max_bars_per_trade:
                    trade.exit_price = bar_close
                    trade.pnl = (bar_close - trade.entry_price) * trade.size
                    trade.exit_type = "TIMEOUT"
                    resolved = True
            else:  # SHORT
                if bar_high >= trade.stop_loss:
                    trade.exit_price = trade.stop_loss
                    trade.pnl = (trade.entry_price - trade.stop_loss) * trade.size
                    trade.exit_type = "SL"
                    resolved = True
                elif bar_low <= trade.take_profit:
                    trade.exit_price = trade.take_profit
                    trade.pnl = (trade.entry_price - trade.take_profit) * trade.size
                    trade.exit_type = "TP"
                    resolved = True
                elif bars_held >= max_bars_per_trade:
                    trade.exit_price = bar_close
                    trade.pnl = (trade.entry_price - bar_close) * trade.size
                    trade.exit_type = "TIMEOUT"
                    resolved = True

            if resolved:
                # Deduct fees (round-trip)
                trade.fee = trade.entry_price * trade.size * TAKER_FEE_RATE * 2
                trade.pnl -= trade.fee
                trade.exit_bar = i
                balance += trade.pnl
                result.trades.append(trade)
                result.total_trades += 1
                result.total_fees += trade.fee
                result.total_pnl += trade.pnl
                if trade.pnl > 0:
                    result.wins += 1
                else:
                    result.losses += 1
            else:
                still_open.append(trade)

        open_trades = still_open

        # Track equity
        peak_balance = max(peak_balance, balance)
        dd = (peak_balance - balance) / peak_balance if peak_balance > 0 else 0
        result.max_drawdown_pct = max(result.max_drawdown_pct, dd)
        result.equity_curve.append(balance)

        # ── Generate new signal (if no open trade on this symbol) ────
        if len(open_trades) > 0:
            continue  # only one trade at a time per symbol

        # Need at least 60 bars of history for prediction
        window = df.iloc[max(0, i - 299):i + 1]
        if len(window) < 30:
            continue

        try:
            probs = predict(model, window)
            prob = float(probs[-1])
            signal = generate_signal(symbol, window, prob)
        except Exception:
            continue

        if signal.direction == "NONE" or signal.grade == "SKIP":
            continue
        if grade_rank.get(signal.grade, 0) < min_rank:
            continue
        if signal.grade not in exec_grades:
            continue

        # Size position
        scale = grade_scale.get(signal.grade, 0.5)
        atr_val = signal.atr if signal.atr > 0 else signal.entry_price * 0.005

        if signal.grade in ("A+", "A"):
            sl_mult, tp_mult = 1.2, 2.5
        elif signal.grade in ("B+", "B"):
            sl_mult, tp_mult = 1.0, 2.2
        else:
            sl_mult, tp_mult = 0.8, 1.8

        entry_price = bar_close
        if signal.direction == "LONG":
            stop_price = entry_price - atr_val * sl_mult
            tp_price = entry_price + atr_val * tp_mult
        else:
            stop_price = entry_price + atr_val * sl_mult
            tp_price = entry_price - atr_val * tp_mult

        stop_dist = abs(entry_price - stop_price)
        if stop_dist <= 0:
            continue

        risk_usd = balance * risk_pct * scale
        size = risk_usd / stop_dist
        notional = size * entry_price
        margin = notional / leverage

        # Check margin (5% buffer)
        if margin > balance * 0.95:
            continue

        # Min-profit filter
        est_fee = notional * TAKER_FEE_RATE * 2
        tp_profit = abs(tp_price - entry_price) * size
        if tp_profit < est_fee * 2:
            continue

        trade = BacktestTrade(
            symbol=symbol,
            direction=signal.direction,
            entry_price=entry_price,
            stop_loss=stop_price,
            take_profit=tp_price,
            size=size,
            grade=signal.grade,
            entry_bar=i,
        )
        open_trades.append(trade)

    # Compute summary stats
    if result.total_trades > 0:
        result.win_rate = result.wins / result.total_trades
        win_pnls = [t.pnl for t in result.trades if t.pnl > 0]
        loss_pnls = [t.pnl for t in result.trades if t.pnl <= 0]
        result.avg_win = np.mean(win_pnls) if win_pnls else 0
        result.avg_loss = np.mean(loss_pnls) if loss_pnls else 0
        total_wins = sum(win_pnls) if win_pnls else 0
        total_losses = abs(sum(loss_pnls)) if loss_pnls else 0
        result.profit_factor = total_wins / total_losses if total_losses > 0 else float("inf")

        # Sharpe (daily returns approximation — each trade is one "period")
        trade_returns = [t.pnl / start_balance for t in result.trades]
        if len(trade_returns) > 1:
            result.sharpe_ratio = np.mean(trade_returns) / (np.std(trade_returns) + 1e-10) * np.sqrt(252)

    return result


def run_backtest(symbols: list[str] | None = None, fetch_fresh: bool = False):
    """
    Full backtest across multiple symbols.

    Trains model on first 70% of data, tests on remaining 30%.
    """
    if symbols is None:
        symbols = list(SYMBOLS)

    log.info("═══ WALK-FORWARD BACKTEST ═══")
    log.info("Symbols: %s", ", ".join(s.replace("/USDT:USDT", "") for s in symbols))

    # Load and prepare data
    all_data = {}
    train_frames = []
    for sym in symbols:
        df = _load_data(sym)
        if df is None or len(df) < 100:
            log.warning("No data for %s — skipping", sym)
            continue
        all_data[sym] = df

        # Use first TRAIN_RATIO for training
        train_end = int(len(df) * TRAIN_RATIO)
        train_df = df.iloc[:train_end]
        dataset = prepare_dataset(train_df)
        dataset["symbol"] = sym
        train_frames.append(dataset)
        log.info("  %s: %d total bars, %d train, %d test",
                 sym.replace("/USDT:USDT", ""), len(df), train_end, len(df) - train_end)

    if not train_frames:
        log.error("No data available for backtesting.")
        return

    # Train model on combined training data
    combined = pd.concat(train_frames, ignore_index=True)
    log.info("Training model on %d rows...", len(combined))
    model = train_model(combined, save_path=ROOT / "models" / "backtest_model.txt")

    # Backtest each symbol on out-of-sample data
    log.info("\n═══ BACKTEST RESULTS ═══")
    overall_pnl = 0.0
    overall_trades = 0
    overall_wins = 0

    for sym in symbols:
        if sym not in all_data:
            continue
        df = all_data[sym]
        test_start = int(len(df) * TRAIN_RATIO)
        test_df = df.iloc[test_start:]

        result = backtest_symbol(sym, model, test_df)
        overall_pnl += result.total_pnl
        overall_trades += result.total_trades
        overall_wins += result.wins

        sym_short = sym.replace("/USDT:USDT", "")
        sl_count = sum(1 for t in result.trades if t.exit_type == "SL")
        tp_count = sum(1 for t in result.trades if t.exit_type == "TP")
        to_count = sum(1 for t in result.trades if t.exit_type == "TIMEOUT")

        log.info(
            "  %-5s  %3d trades  WR=%.0f%%  PnL=$%+.2f  PF=%.2f  MaxDD=%.1f%%  "
            "Fees=$%.2f  SL/TP/TO=%d/%d/%d",
            sym_short,
            result.total_trades,
            result.win_rate * 100,
            result.total_pnl,
            result.profit_factor,
            result.max_drawdown_pct * 100,
            result.total_fees,
            sl_count, tp_count, to_count,
        )

    log.info("─" * 72)
    overall_wr = overall_wins / overall_trades * 100 if overall_trades > 0 else 0
    log.info("  TOTAL  %d trades  WR=%.0f%%  PnL=$%+.2f",
             overall_trades, overall_wr, overall_pnl)
    log.info("═══ BACKTEST COMPLETE ═══")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Walk-Forward Backtester")
    parser.add_argument("--symbol", type=str, help="Backtest a single symbol")
    parser.add_argument("--fetch", action="store_true", help="Fetch fresh data first")
    args = parser.parse_args()

    symbols = [args.symbol] if args.symbol else None

    if args.fetch:
        from data.collector import collect_all
        from data.pipeline import _get_public_exchange
        log.info("Fetching fresh data...")
        collect_all(_get_public_exchange())

    run_backtest(symbols)
