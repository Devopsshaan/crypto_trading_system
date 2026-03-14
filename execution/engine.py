"""
Execution Engine — Place orders on Bybit or log paper trades.
==============================================================
Handles order placement, stop-loss / take-profit, and position queries.
When PAPER_TRADE is True, orders are logged but NOT sent to the exchange.
"""

from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import ccxt

from config.settings import (
    BYBIT_API_KEY, BYBIT_API_SECRET, BYBIT_TESTNET,
    DEFAULT_LEVERAGE, PAPER_TRADE,
)

log = logging.getLogger(__name__)

PAPER_LOG = Path(__file__).resolve().parent.parent / "logs" / "paper_trades.jsonl"


class Executor:
    """Thin wrapper around CCXT for Bybit perpetual futures execution."""

    def __init__(self):
        self.exchange = ccxt.bybit({
            "apiKey": BYBIT_API_KEY,
            "secret": BYBIT_API_SECRET,
            "enableRateLimit": True,
            "options": {"defaultType": "swap"},
        })
        if BYBIT_TESTNET:
            self.exchange.set_sandbox_mode(True)
        self._mode = "TESTNET" if BYBIT_TESTNET else "LIVE"
        self._paper = PAPER_TRADE
        mode_label = f"{self._mode} | PAPER" if self._paper else self._mode
        log.info("Executor initialized [%s]", mode_label)

    # ── Balance ──────────────────────────────────────────────────────────

    def fetch_balance(self) -> float:
        """Return total USDT equity."""
        bal = self.exchange.fetch_balance({"type": "swap"})
        usdt = bal.get("USDT", {})
        total = float(usdt.get("total", 0))
        log.info("Balance: $%.2f USDT [%s]", total, self._mode)
        return total

    # ── Leverage ─────────────────────────────────────────────────────────

    def set_leverage(self, symbol: str, leverage: int = DEFAULT_LEVERAGE):
        """Set leverage for a symbol."""
        if self._paper:
            log.info("📝 PAPER: leverage %dx for %s (not sent)", leverage, symbol)
            return
        try:
            self.exchange.set_leverage(leverage, symbol)
            log.info("Leverage set to %dx for %s", leverage, symbol)
        except Exception as e:
            log.warning("set_leverage: %s (may already be set)", e)

    # ── Orders ───────────────────────────────────────────────────────────

    def market_order(
        self,
        symbol: str,
        side: str,  # "buy" or "sell"
        amount: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        entry_price: float | None = None,
    ) -> dict:
        """
        Place a market order with optional SL/TP.
        In paper-trade mode, logs the order to a JSONL file instead.
        """
        if self._paper:
            paper_order = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "mode": "PAPER",
                "symbol": symbol,
                "side": side.upper(),
                "amount": amount,
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "status": "PAPER_FILLED",
            }
            PAPER_LOG.parent.mkdir(parents=True, exist_ok=True)
            with open(PAPER_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(paper_order) + "\n")
            log.info("📝 PAPER ORDER: %s %s %.6f  SL=%s  TP=%s  (logged, not sent)",
                     side.upper(), symbol, amount, stop_loss, take_profit)
            return paper_order

        params = {}
        if stop_loss is not None:
            params["stopLoss"] = {"triggerPrice": stop_loss, "type": "market"}
        if take_profit is not None:
            params["takeProfit"] = {"triggerPrice": take_profit, "type": "market"}

        log.info("ORDER [%s] %s %s %.6f  SL=%s  TP=%s",
                 self._mode, side.upper(), symbol, amount, stop_loss, take_profit)

        order = self.exchange.create_order(
            symbol=symbol,
            type="market",
            side=side,
            amount=amount,
            params=params,
        )
        log.info("Order filled: id=%s  avg_price=%s", order.get("id"), order.get("average"))
        return order

    # ── Positions ────────────────────────────────────────────────────────

    def open_positions(self, symbol: str | None = None) -> list[dict]:
        """Fetch open positions (optionally filtered by symbol)."""
        positions = self.exchange.fetch_positions([symbol] if symbol else None)
        open_pos = [p for p in positions if float(p.get("contracts", 0)) > 0]
        return open_pos

    # ── Close ────────────────────────────────────────────────────────────

    def close_position(self, symbol: str, side: str, amount: float) -> dict:
        """
        Close a position.

        side: "buy" means we are long → close by selling, pass side="sell"
        """
        close_side = "sell" if side == "buy" else "buy"
        return self.market_order(symbol, close_side, amount)
