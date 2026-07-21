"""Dynamic position sizing — risk shrinks after drawdown / loss streaks."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

from app.domain.ai_trading_robot.config import RobotV1Config
from app.domain.ai_trading_robot.invariants import risk_must_decrease_after_drawdown
from app.domain.trading.xauusd_specs import CONTRACT_SIZE, VOLUME_MIN, VOLUME_STEP


@dataclass(frozen=True, slots=True)
class DynamicSizeResult:
    approved_lots: Decimal
    risk_pct: Decimal
    base_risk_pct: Decimal
    dollar_risk: Decimal
    reduced: bool
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "approved_lots": str(self.approved_lots),
            "risk_pct": str(self.risk_pct),
            "base_risk_pct": str(self.base_risk_pct),
            "dollar_risk": str(self.dollar_risk),
            "reduced": self.reduced,
            "reasons": list(self.reasons),
            "contract_size": str(CONTRACT_SIZE),
        }


def _round_lot(lots: Decimal) -> Decimal:
    if lots < VOLUME_MIN:
        return Decimal("0")
    steps = (lots / VOLUME_STEP).to_integral_value(rounding=ROUND_DOWN)
    return (steps * VOLUME_STEP).quantize(VOLUME_STEP)


def compute_dynamic_size(
    *,
    config: RobotV1Config,
    equity: Decimal,
    stop_distance: Decimal,
    current_drawdown_pct: Decimal,
    consecutive_losses: int,
) -> DynamicSizeResult:
    """Percentage-risk sizing with mandatory post-drawdown reduction."""
    reasons: list[str] = []
    risk_pct = risk_must_decrease_after_drawdown(
        base_risk_pct=config.base_risk_pct,
        current_drawdown_pct=max(Decimal("0"), current_drawdown_pct),
        consecutive_losses=max(0, consecutive_losses),
        reduction_per_loss=config.reduction_per_consecutive_loss,
        reduction_per_dd_pct=config.reduction_per_drawdown_pct,
        floor_pct=config.risk_floor_pct,
    )
    reduced = risk_pct < config.base_risk_pct
    if reduced:
        reasons.append(
            f"Risk reduced from {config.base_risk_pct}% to {risk_pct}% "
            f"(losses={consecutive_losses}, drawdown={current_drawdown_pct}%)."
        )
    if equity <= 0:
        return DynamicSizeResult(
            approved_lots=Decimal("0"),
            risk_pct=risk_pct,
            base_risk_pct=config.base_risk_pct,
            dollar_risk=Decimal("0"),
            reduced=reduced,
            reasons=("Equity must be positive for sizing.",),
        )
    dollar = (equity * risk_pct / Decimal("100")).quantize(Decimal("0.01"))
    if stop_distance <= 0:
        reasons.append("Stop distance missing — size floored to minimum lot or zero.")
        lots = VOLUME_MIN if dollar > 0 else Decimal("0")
    else:
        raw = dollar / (stop_distance * CONTRACT_SIZE)
        lots = _round_lot(raw)
        if lots <= 0:
            reasons.append("Computed size below minimum lot.")
    return DynamicSizeResult(
        approved_lots=lots,
        risk_pct=risk_pct,
        base_risk_pct=config.base_risk_pct,
        dollar_risk=dollar,
        reduced=reduced,
        reasons=tuple(reasons),
    )
