"""
Risk Manager — Position sizing, drawdown gears, and trade limits.
=================================================================
Includes Kelly Criterion (John Kelly, 1956) — mathematically optimal
position sizing from information theory.

Kelly Formula: f* = (b·p − q) / b
  where p = win probability, q = 1−p, b = win/loss ratio
  f* = fraction of bankroll to risk

We use fractional Kelly (25%) for safety — full Kelly is too aggressive
for finite bankrolls and estimation error.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from datetime import date

from config.settings import (
    RISK_PER_TRADE, MAX_RISK_PER_TRADE,
    MAX_TRADES_PER_DAY, MAX_DAILY_LOSS_PCT, MAX_WEEKLY_LOSS_PCT,
    DEFAULT_LEVERAGE, MIN_MARGIN_BUFFER, DRAWDOWN_GEARS,
)

log = logging.getLogger(__name__)


@dataclass
class PositionPlan:
    allow: bool
    reason: str
    size: float = 0.0           # in base asset units
    risk_usd: float = 0.0
    stop_distance: float = 0.0
    notional: float = 0.0
    margin: float = 0.0
    leverage: int = DEFAULT_LEVERAGE


@dataclass
class RiskState:
    """Tracks intra-day and intra-week risk state."""
    balance: float
    peak_balance: float
    daily_pnl: float = 0.0
    weekly_pnl: float = 0.0
    trades_today: int = 0
    today: date = field(default_factory=date.today)
    week_start: date = field(default_factory=lambda: date.today())
    consecutive_losses: int = 0
    open_margin: float = 0.0  # total margin used by all open positions

    def new_day(self, current_balance: float):
        """Reset daily counters."""
        self.balance = current_balance
        self.daily_pnl = 0.0
        self.trades_today = 0
        self.consecutive_losses = 0  # reset on new day
        self.today = date.today()
        if self.peak_balance < current_balance:
            self.peak_balance = current_balance

    def new_week(self, current_balance: float):
        """Reset weekly counters."""
        self.weekly_pnl = 0.0
        self.week_start = date.today()
        self.new_day(current_balance)

    def record_trade(self, pnl: float):
        """Update state after a trade closes."""
        self.daily_pnl += pnl
        self.weekly_pnl += pnl
        self.balance += pnl
        self.trades_today += 1
        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
        if self.balance > self.peak_balance:
            self.peak_balance = self.balance


class RiskManager:
    """Enforces all risk rules and computes position sizes."""

    def __init__(self, state: RiskState):
        self.state = state
        # Track win/loss history for Kelly Criterion
        self._trade_results: list[float] = []

    # ── Kelly Criterion (John Kelly, 1956) ───────────────────────────────

    def kelly_fraction(self, min_trades: int = 10, kelly_mult: float = 0.25) -> float:
        """
        Compute fractional Kelly Criterion optimal risk fraction.

        f* = (b·p − q) / b   (Kelly, 1956)

        where:
          p = historical win probability
          q = 1 − p
          b = average win / average loss (reward-to-risk ratio)

        Returns fractional Kelly (default 25% of full Kelly) for safety.
        Full Kelly is theoretically optimal but too volatile in practice.
        """
        if len(self._trade_results) < min_trades:
            return RISK_PER_TRADE  # not enough data — use default risk

        wins = [r for r in self._trade_results if r > 0]
        losses = [r for r in self._trade_results if r < 0]

        if not wins or not losses:
            return RISK_PER_TRADE  # can't compute Kelly without both

        p = len(wins) / len(self._trade_results)  # win probability
        q = 1 - p
        avg_win = sum(wins) / len(wins)
        avg_loss = abs(sum(losses) / len(losses))

        if avg_loss <= 0:
            return RISK_PER_TRADE

        b = avg_win / avg_loss  # reward-to-risk ratio

        full_kelly = (b * p - q) / b

        if full_kelly <= 0:
            # Negative Kelly = no edge → minimum risk
            return RISK_PER_TRADE * 0.5

        # Fractional Kelly for safety (25% of optimal)
        fractional = full_kelly * kelly_mult

        # Clamp between min and max risk
        return max(RISK_PER_TRADE * 0.5, min(fractional, MAX_RISK_PER_TRADE))

    def record_result(self, pnl: float):
        """Record a trade result for Kelly Criterion calculation."""
        self._trade_results.append(pnl)
        # Keep last 50 trades for rolling Kelly
        if len(self._trade_results) > 50:
            self._trade_results = self._trade_results[-50:]

    # ── Drawdown Gear ────────────────────────────────────────────────────

    def current_gear(self) -> dict:
        """Determine current drawdown gear."""
        dd = self._drawdown_pct()
        gear = DRAWDOWN_GEARS["NORMAL"]
        for name, g in DRAWDOWN_GEARS.items():
            if dd >= g["threshold"]:
                gear = {**g, "name": name}
        return gear

    def _drawdown_pct(self) -> float:
        if self.state.peak_balance <= 0:
            return 0.0
        return (self.state.peak_balance - self.state.balance) / self.state.peak_balance

    # ── Trade Allowance Checks ───────────────────────────────────────────

    def can_trade(self) -> tuple[bool, str]:
        """Check all risk gates. Returns (allowed, reason)."""
        gear = self.current_gear()

        if gear.get("name") == "PAUSE":
            return False, f"PAUSE gear active (drawdown {self._drawdown_pct():.1%}). No trading."

        if self.state.trades_today >= gear["max_trades"]:
            return False, f"Max trades reached ({self.state.trades_today}/{gear['max_trades']}) under {gear.get('name', 'NORMAL')} gear."

        daily_limit = self.state.balance * MAX_DAILY_LOSS_PCT
        if self.state.daily_pnl <= -daily_limit:
            return False, f"Daily loss limit hit (${self.state.daily_pnl:.2f} / -${daily_limit:.2f})."

        weekly_limit = self.state.balance * MAX_WEEKLY_LOSS_PCT
        if self.state.weekly_pnl <= -weekly_limit:
            return False, "Weekly loss limit hit."

        if self.state.consecutive_losses >= 8:
            return False, f"Consecutive loss cooldown ({self.state.consecutive_losses} losses in a row). Resets on next win or new day."

        return True, "OK"

    # ── Position Sizing ──────────────────────────────────────────────────

    def size_position(
        self,
        entry_price: float,
        stop_price: float,
        leverage: int | None = None,
    ) -> PositionPlan:
        """
        Compute position size respecting all risk rules.

        Returns a PositionPlan (allow=False if risk gate blocks the trade).
        """
        allowed, reason = self.can_trade()
        if not allowed:
            return PositionPlan(allow=False, reason=reason)

        if leverage is None:
            leverage = DEFAULT_LEVERAGE

        gear = self.current_gear()
        risk_pct = min(gear["risk"], MAX_RISK_PER_TRADE)

        # Use Kelly Criterion if enough historical trades exist
        kelly_pct = self.kelly_fraction()
        if len(self._trade_results) >= 10:
            # Blend Kelly with gear risk: Kelly adapts, gear provides safety floor
            risk_pct = min(kelly_pct, risk_pct) if gear.get("name") != "NORMAL" else kelly_pct
            log.info("  🎲 Kelly risk: %.2f%% (from %d trades)", risk_pct * 100, len(self._trade_results))

        risk_usd = self.state.balance * risk_pct
        stop_dist = abs(entry_price - stop_price)

        if stop_dist <= 0:
            return PositionPlan(allow=False, reason="Stop distance is zero or negative.")

        size = risk_usd / stop_dist
        notional = size * entry_price
        margin = notional / leverage

        # Sanity check: margin shouldn't be insane (3x balance max for paper trading)
        # Actual risk is controlled by the stop loss ($4), not the margin
        if margin > self.state.balance * 3:
            return PositionPlan(
                allow=False,
                reason=f"Trade margin ${margin:.2f} exceeds 3x balance ${self.state.balance * 3:.2f}.",
            )

        return PositionPlan(
            allow=True,
            reason=f"Gear={gear.get('name','NORMAL')} | Risk={risk_pct:.1%} | ${risk_usd:.2f}",
            size=round(size, 6),
            risk_usd=round(risk_usd, 2),
            stop_distance=round(stop_dist, 2),
            notional=round(notional, 2),
            margin=round(margin, 2),
            leverage=leverage,
        )
