"""Dynamic risk allocation + smart recovery (never martingale/grid)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from threading import Lock

from app.domain.institutional_trading.alpha_engine.config import (
    DEFAULT_ALPHA_CONFIG,
    InstitutionalAlphaConfig,
)


@dataclass(frozen=True, slots=True)
class RiskAllocation:
    risk_pct: Decimal
    band: str
    recovery_active: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "risk_pct": str(self.risk_pct),
            "band": self.band,
            "recovery_active": self.recovery_active,
            "reason": self.reason,
        }


class SmartRecoveryState:
    """Temporary risk reduction after losses — configurable, never martingale."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._remaining: int = 0
        self._last_loss: bool = False

    def record_outcome(self, *, win: bool, config: InstitutionalAlphaConfig | None = None) -> None:
        cfg = config or DEFAULT_ALPHA_CONFIG
        with self._lock:
            if win:
                self._remaining = 0
                self._last_loss = False
                return
            self._last_loss = True
            if cfg.recovery_enabled:
                self._remaining = max(self._remaining, int(cfg.recovery_trades))

    def consume_trade(self) -> None:
        with self._lock:
            if self._remaining > 0:
                self._remaining -= 1

    def active(self) -> bool:
        with self._lock:
            return self._remaining > 0

    def remaining(self) -> int:
        with self._lock:
            return self._remaining

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "active": self._remaining > 0,
                "remaining_trades": self._remaining,
                "last_loss": self._last_loss,
            }


_RECOVERY = SmartRecoveryState()


def get_smart_recovery() -> SmartRecoveryState:
    return _RECOVERY


def allocate_risk_pct(
    opportunity_score: int,
    *,
    daily_risk_used_pct: Decimal = Decimal("0"),
    account_exposure_pct: Decimal = Decimal("0"),
    drawdown_pct: Decimal = Decimal("0"),
    config: InstitutionalAlphaConfig | None = None,
    recovery: SmartRecoveryState | None = None,
) -> RiskAllocation:
    cfg = config or DEFAULT_ALPHA_CONFIG
    rec = recovery or get_smart_recovery()

    if cfg.allow_martingale or cfg.allow_grid or cfg.allow_average_down:
        return RiskAllocation(
            Decimal("0"),
            "blocked",
            False,
            "Unsafe recovery modes permanently disabled",
        )

    if drawdown_pct >= cfg.max_drawdown_pct:
        return RiskAllocation(
            Decimal("0"),
            "drawdown",
            rec.active(),
            f"Drawdown {drawdown_pct}% at max {cfg.max_drawdown_pct}%",
        )
    if daily_risk_used_pct >= cfg.max_daily_risk_pct:
        return RiskAllocation(
            Decimal("0"),
            "daily_cap",
            rec.active(),
            f"Daily risk {daily_risk_used_pct}% at max {cfg.max_daily_risk_pct}%",
        )
    if account_exposure_pct >= cfg.max_account_exposure_pct:
        return RiskAllocation(
            Decimal("0"),
            "exposure_cap",
            rec.active(),
            f"Exposure {account_exposure_pct}% at max {cfg.max_account_exposure_pct}%",
        )

    if opportunity_score >= cfg.high_score_floor:
        band, risk = "high", cfg.risk_pct_high
    elif opportunity_score >= cfg.mid_score_floor:
        band, risk = "mid", cfg.risk_pct_mid
    elif opportunity_score >= cfg.min_opportunity_score:
        band, risk = "low", cfg.risk_pct_low
    else:
        return RiskAllocation(
            Decimal("0"),
            "below_min",
            rec.active(),
            f"Score {opportunity_score} below min {cfg.min_opportunity_score}",
        )

    reason = f"Quality band={band} score={opportunity_score} → risk={risk}%"
    recovery_on = rec.active()
    if recovery_on:
        risk = (risk * cfg.recovery_risk_mult).quantize(Decimal("0.01"))
        reason += f" · recovery×{cfg.recovery_risk_mult}"

    remaining_daily = cfg.max_daily_risk_pct - daily_risk_used_pct
    if risk > remaining_daily:
        risk = max(Decimal("0"), remaining_daily)
        reason += " · capped by daily risk"

    return RiskAllocation(risk, band, recovery_on, reason)


def min_score_with_recovery(
    *,
    config: InstitutionalAlphaConfig | None = None,
    recovery: SmartRecoveryState | None = None,
) -> int:
    cfg = config or DEFAULT_ALPHA_CONFIG
    rec = recovery or get_smart_recovery()
    base = cfg.min_opportunity_score
    if rec.active():
        return base + int(cfg.recovery_min_score_bonus)
    return base
