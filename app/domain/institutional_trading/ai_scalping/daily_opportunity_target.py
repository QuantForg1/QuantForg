"""Daily opportunity target — observe / governance only.

TARGET_TRADES_PER_DAY is an opportunity objective, NEVER a forced minimum.

This module:
- counts quality setups seen / rejected / executed
- tracks win/loss / expectancy for decision support
- exposes progress toward the daily target

It MUST NOT:
- force trades
- loosen Safety / Risk / OMS gates
- raise size after losses or wins
- bypass daily loss lock, max-open, min-lot, or correlation caps
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

DEFAULT_TARGET_TRADES_PER_DAY = 3
_ROLLING_20 = 20
_ROLLING_50 = 50


@dataclass(frozen=True, slots=True)
class ClosedTradeRecord:
    symbol: str
    strategy: str
    session: str
    market_regime: str
    realized_pnl: float
    risk_pct_at_entry: float
    equity_at_exit: float
    realized_r: float
    expected_r: float
    holding_seconds: float
    exit_reason: str
    won: bool
    closed_at: str


@dataclass(frozen=True, slots=True)
class PerformanceMetrics:
    win_rate: float | None
    average_win: float | None
    average_loss: float | None
    gross_profit: float
    gross_loss: float
    profit_factor: float | None
    expectancy_per_trade: float | None
    average_r: float | None
    average_win_r: float | None
    average_loss_r: float | None
    payoff_ratio: float | None
    max_consecutive_losses: int
    max_consecutive_wins: int
    rolling_20_expectancy: float | None
    rolling_50_expectancy: float | None
    sample_size: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "win_rate": self.win_rate,
            "average_win": self.average_win,
            "average_loss": self.average_loss,
            "gross_profit": self.gross_profit,
            "gross_loss": self.gross_loss,
            "profit_factor": self.profit_factor,
            "expectancy_per_trade": self.expectancy_per_trade,
            "average_r": self.average_r,
            "average_win_r": self.average_win_r,
            "average_loss_r": self.average_loss_r,
            "payoff_ratio": self.payoff_ratio,
            "max_consecutive_losses": self.max_consecutive_losses,
            "max_consecutive_wins": self.max_consecutive_wins,
            "rolling_20_trade_expectancy": self.rolling_20_expectancy,
            "rolling_50_trade_expectancy": self.rolling_50_expectancy,
            "sample_size": self.sample_size,
            "note": (
                "Observation / decision support only — never overrides "
                "Safety or Risk hard limits."
            ),
        }


def compute_performance_metrics(
    trades: list[ClosedTradeRecord],
    *,
    include_rolling: bool = True,
) -> PerformanceMetrics:
    """Expectancy = (win_rate × avg_win) − ((1 − win_rate) × avg_loss)."""
    n = len(trades)
    if n == 0:
        return PerformanceMetrics(
            win_rate=None,
            average_win=None,
            average_loss=None,
            gross_profit=0.0,
            gross_loss=0.0,
            profit_factor=None,
            expectancy_per_trade=None,
            average_r=None,
            average_win_r=None,
            average_loss_r=None,
            payoff_ratio=None,
            max_consecutive_losses=0,
            max_consecutive_wins=0,
            rolling_20_expectancy=None,
            rolling_50_expectancy=None,
            sample_size=0,
        )

    wins = [t for t in trades if t.won]
    losses = [t for t in trades if not t.won]
    win_rate = len(wins) / n
    avg_win = (
        sum(t.realized_pnl for t in wins) / len(wins) if wins else None
    )
    # average_loss stored as positive magnitude for expectancy formula
    avg_loss_mag = (
        abs(sum(t.realized_pnl for t in losses) / len(losses)) if losses else None
    )
    gross_profit = sum(t.realized_pnl for t in wins)
    gross_loss = abs(sum(t.realized_pnl for t in losses))
    profit_factor = (
        (gross_profit / gross_loss) if gross_loss > 0 else (None if gross_profit <= 0 else None)
    )
    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    elif gross_profit > 0:
        profit_factor = None
    expectancy = None
    if avg_win is not None and avg_loss_mag is not None:
        expectancy = (win_rate * avg_win) - ((1.0 - win_rate) * avg_loss_mag)
    elif avg_win is not None and not losses:
        expectancy = avg_win
    elif avg_loss_mag is not None and not wins:
        expectancy = -avg_loss_mag

    rs = [t.realized_r for t in trades]
    win_rs = [t.realized_r for t in wins]
    loss_rs = [abs(t.realized_r) for t in losses]
    average_r = sum(rs) / n if rs else None
    average_win_r = sum(win_rs) / len(win_rs) if win_rs else None
    average_loss_r = sum(loss_rs) / len(loss_rs) if loss_rs else None
    payoff_ratio = None
    if average_win_r is not None and average_loss_r and average_loss_r > 0:
        payoff_ratio = average_win_r / average_loss_r

    max_w = max_l = cur_w = cur_l = 0
    for t in trades:
        if t.won:
            cur_w += 1
            cur_l = 0
            max_w = max(max_w, cur_w)
        else:
            cur_l += 1
            cur_w = 0
            max_l = max(max_l, cur_l)

    def _roll_exp(window: int) -> float | None:
        subset = trades[-window:]
        if not subset:
            return None
        return compute_performance_metrics(
            subset, include_rolling=False
        ).expectancy_per_trade

    return PerformanceMetrics(
        win_rate=win_rate,
        average_win=avg_win,
        average_loss=avg_loss_mag,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        profit_factor=profit_factor,
        expectancy_per_trade=expectancy,
        average_r=average_r,
        average_win_r=average_win_r,
        average_loss_r=average_loss_r,
        payoff_ratio=payoff_ratio,
        max_consecutive_losses=max_l,
        max_consecutive_wins=max_w,
        rolling_20_expectancy=_roll_exp(_ROLLING_20) if include_rolling else None,
        rolling_50_expectancy=_roll_exp(_ROLLING_50) if include_rolling else None,
        sample_size=n,
    )


@dataclass
class DailyOpportunityTargetTracker:
    """Process-local daily opportunity governance (never forces entries)."""

    target_trades_per_day: int = DEFAULT_TARGET_TRADES_PER_DAY
    opportunity_review_interval_seconds: float = 30 * 60.0
    _day: date = field(default_factory=lambda: datetime.now(UTC).date())
    trades_today: int = 0
    quality_setups_seen: int = 0
    quality_setups_rejected: int = 0
    quality_setups_executed: int = 0
    last_analysis_at: str | None = None
    last_execution_decision: str | None = None
    last_reject_gate: str | None = None
    last_rescan_reason: str | None = None
    next_opportunity_review_at: str | None = None
    _closed: list[ClosedTradeRecord] = field(default_factory=list)
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)
    _last_review_mono: float = 0.0

    def _roll_day(self) -> None:
        today = datetime.now(UTC).date()
        if today != self._day:
            self._day = today
            self.trades_today = 0
            self.quality_setups_seen = 0
            self.quality_setups_rejected = 0
            self.quality_setups_executed = 0
            self.last_reject_gate = None

    @staticmethod
    def should_force_trade_for_target(
        *,
        trades_today: int,
        target: int,
        valid_setups: int,
    ) -> bool:
        """CRITICAL: always False — target never forces a trade."""
        _ = (trades_today, target, valid_setups)
        return False

    def remaining_trade_opportunities(self) -> int:
        self._roll_day()
        return max(0, int(self.target_trades_per_day) - int(self.trades_today))

    def seeking_mode(self) -> str:
        """Observational mode label — does not change gates."""
        self._roll_day()
        if self.trades_today < self.target_trades_per_day:
            return "seeking_quality_opportunities"
        if self.trades_today == self.target_trades_per_day:
            return "target_reached_exceptional_only"
        return "above_target_gates_unchanged"

    def note_analysis(self, *, decision: str | None = None) -> None:
        with self._lock:
            self._roll_day()
            self.last_analysis_at = datetime.now(UTC).isoformat()
            if decision:
                self.last_execution_decision = decision

    def note_quality_setup_seen(self) -> None:
        with self._lock:
            self._roll_day()
            self.quality_setups_seen += 1

    def note_quality_setup_rejected(self, *, gate: str) -> None:
        with self._lock:
            self._roll_day()
            self.quality_setups_rejected += 1
            self.last_reject_gate = str(gate or "unknown")[:200]
            self.last_execution_decision = f"REJECT:{self.last_reject_gate}"

    def note_trade_executed(self, *, symbol: str = "") -> None:
        with self._lock:
            self._roll_day()
            self.trades_today += 1
            self.quality_setups_executed += 1
            self.last_execution_decision = (
                f"EXECUTED:{symbol or 'unknown'}"
            )
            self.last_analysis_at = datetime.now(UTC).isoformat()

    def note_trade_closed(self, record: ClosedTradeRecord) -> None:
        with self._lock:
            self._roll_day()
            self._closed.append(record)
            # Keep memory bounded
            if len(self._closed) > 200:
                self._closed = self._closed[-200:]
            self.last_analysis_at = datetime.now(UTC).isoformat()

    def note_rescan(self, reason: str) -> None:
        with self._lock:
            self.last_rescan_reason = str(reason or "")[:120]
            self.last_analysis_at = datetime.now(UTC).isoformat()

    def due_for_opportunity_review(self, *, now_mono: float) -> bool:
        """True when ≥30 minutes since last focused review (soft cadence)."""
        with self._lock:
            interval = float(self.opportunity_review_interval_seconds or 1800.0)
            if self._last_review_mono <= 0:
                self._last_review_mono = now_mono
                self.next_opportunity_review_at = datetime.now(UTC).isoformat()
                return True
            if (now_mono - self._last_review_mono) >= interval:
                self._last_review_mono = now_mono
                self.next_opportunity_review_at = datetime.now(UTC).isoformat()
                return True
            return False

    def performance(self) -> PerformanceMetrics:
        with self._lock:
            return compute_performance_metrics(list(self._closed))

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            self._roll_day()
            perf = compute_performance_metrics(list(self._closed))
            return {
                "target_trades_per_day": int(self.target_trades_per_day),
                "trades_today": int(self.trades_today),
                "remaining_trade_opportunities": self.remaining_trade_opportunities(),
                "quality_setups_seen": int(self.quality_setups_seen),
                "quality_setups_rejected": int(self.quality_setups_rejected),
                "quality_setups_executed": int(self.quality_setups_executed),
                "seeking_mode": self.seeking_mode(),
                "forced": False,
                "force_trade_for_target": False,
                "policy": (
                    "Opportunity target only — never forces trades; "
                    "Safety/Risk/OMS gates always win."
                ),
                "last_analysis_at": self.last_analysis_at,
                "last_execution_decision": self.last_execution_decision,
                "last_reject_gate": self.last_reject_gate,
                "last_rescan_reason": self.last_rescan_reason,
                "next_opportunity_review_at": self.next_opportunity_review_at,
                "performance": perf.to_dict(),
                "day_utc": self._day.isoformat(),
                "daily_realized_profit": perf.gross_profit,
                "daily_unrealized_profit": None,
                "daily_R": perf.average_r,
                "win_rate": perf.win_rate,
                "average_R": perf.average_r,
                "profit_factor": perf.profit_factor,
                "trade_count": perf.sample_size,
                "opportunity_count": int(self.quality_setups_seen),
                "candidate_count": int(self.quality_setups_seen),
                "execution_ready_count": int(self.quality_setups_executed),
                "missed_opportunity_count": int(self.quality_setups_rejected),
                "risk_block_count": int(self.quality_setups_rejected),
                "largest_win": (
                    max((t.realized_pnl for t in self._closed if t.won), default=None)
                ),
                "largest_loss": (
                    min(
                        (t.realized_pnl for t in self._closed if not t.won),
                        default=None,
                    )
                ),
                "avg_hold_time": (
                    (
                        sum(t.holding_seconds for t in self._closed)
                        / len(self._closed)
                    )
                    if self._closed
                    else None
                ),
                "daily_profit_target_usd": None,
                "daily_profit_is_execution_obligation": False,
            }


_TRACKER: DailyOpportunityTargetTracker | None = None
_TRACKER_LOCK = threading.Lock()


def get_daily_opportunity_tracker(
    *,
    target_trades_per_day: int | None = None,
) -> DailyOpportunityTargetTracker:
    global _TRACKER
    with _TRACKER_LOCK:
        if _TRACKER is None:
            _TRACKER = DailyOpportunityTargetTracker(
                target_trades_per_day=int(
                    target_trades_per_day
                    if target_trades_per_day is not None
                    else DEFAULT_TARGET_TRADES_PER_DAY
                )
            )
        elif target_trades_per_day is not None:
            _TRACKER.target_trades_per_day = int(target_trades_per_day)
        return _TRACKER


def reset_daily_opportunity_tracker() -> None:
    """Test helper."""
    global _TRACKER
    with _TRACKER_LOCK:
        _TRACKER = None
