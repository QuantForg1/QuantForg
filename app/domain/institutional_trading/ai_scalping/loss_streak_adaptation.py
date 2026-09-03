"""Loss-streak adaptation — temporary defense, never permanent disable / martingale.

Modes:
  NORMAL     (0-2 consecutive losses)
  TIGHTENED  (3 consecutive losses) - stronger selection / ranking bias
  DEFENSIVE  (4+ consecutive losses) - strongest setups only, reduce exposure

A loss never stops the worker/scanner. Time-boxed cooldown pauses new entries
briefly; after expiry trading resumes under the adaptation mode until a win.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

MODE_NORMAL = "NORMAL"
MODE_TIGHTENED = "TIGHTENED"
MODE_DEFENSIVE = "DEFENSIVE"


@dataclass(frozen=True, slots=True)
class LossStreakAdaptation:
    consecutive_losses: int
    mode: str
    cooldown_active: bool
    cooldown_remaining_minutes: int
    require_stronger_selection: bool
    min_expected_rr_soft: float
    ranking_rr_boost: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "consecutive_losses": self.consecutive_losses,
            "mode": self.mode,
            "cooldown_active": self.cooldown_active,
            "cooldown_remaining_minutes": self.cooldown_remaining_minutes,
            "require_stronger_selection": self.require_stronger_selection,
            "min_expected_rr_soft": self.min_expected_rr_soft,
            "ranking_rr_boost": self.ranking_rr_boost,
            "reason": self.reason,
            "allow_martingale": False,
            "permanent_disable": False,
            "worker_continues": True,
        }


def resolve_loss_streak_adaptation(
    *,
    consecutive_losses: int,
    cooldown_until: datetime | None = None,
    now: datetime | None = None,
    base_min_rr: float = 1.20,
) -> LossStreakAdaptation:
    losses = max(0, int(consecutive_losses or 0))
    clock = now or datetime.now(UTC)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=UTC)
    remaining = 0
    active = False
    if cooldown_until is not None:
        until = cooldown_until
        if until.tzinfo is None:
            until = until.replace(tzinfo=UTC)
        if clock < until:
            active = True
            remaining = max(1, int((until - clock).total_seconds() // 60))

    if losses >= 4:
        mode = MODE_DEFENSIVE
        soft_rr = max(float(base_min_rr), 1.35)
        boost = 0.25
        reason = (
            f"{losses} consecutive losses — DEFENSIVE: strongest setups only; "
            "no martingale; exposure reduced by existing adaptive sizing"
        )
    elif losses >= 3:
        mode = MODE_TIGHTENED
        soft_rr = max(float(base_min_rr), 1.25)
        boost = 0.15
        reason = (
            f"{losses} consecutive losses — TIGHTENED selection / ranking bias"
        )
    else:
        mode = MODE_NORMAL
        soft_rr = float(base_min_rr)
        boost = 0.0
        reason = "NORMAL exposure and selection"

    return LossStreakAdaptation(
        consecutive_losses=losses,
        mode=mode,
        cooldown_active=active,
        cooldown_remaining_minutes=remaining,
        require_stronger_selection=mode != MODE_NORMAL,
        min_expected_rr_soft=soft_rr,
        ranking_rr_boost=boost,
        reason=reason,
    )


def cooldown_until_after_streak(
    *,
    consecutive_losses: int,
    max_consecutive_losses: int,
    cooldown_minutes: int,
    now: datetime | None = None,
) -> datetime | None:
    """When streak first reaches the policy max, start a time-boxed cooldown."""
    if max_consecutive_losses <= 0:
        return None
    if int(consecutive_losses) < int(max_consecutive_losses):
        return None
    minutes = max(1, int(cooldown_minutes or 60))
    clock = now or datetime.now(UTC)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=UTC)
    return clock + timedelta(minutes=minutes)
