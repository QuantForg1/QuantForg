"""Adaptive risk allocation based on institutional confidence.

Risk never increases after drawdown / loss streaks.
Never martingale / grid / average-down.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

from app.domain.ai_trading_robot.invariants import risk_must_decrease_after_drawdown
from app.domain.institutional_ai_decision.confidence import InstitutionalConfidence
from app.domain.institutional_ai_decision.config import DecisionEngineV1Config
from app.domain.trading.xauusd_specs import CONTRACT_SIZE, VOLUME_MIN, VOLUME_STEP


@dataclass(frozen=True, slots=True)
class AdaptiveRiskAllocation:
    risk_pct: Decimal
    base_from_confidence: Decimal
    dollar_risk: Decimal
    approved_lots: Decimal
    reduced_for_drawdown: bool
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "risk_pct": str(self.risk_pct),
            "base_from_confidence": str(self.base_from_confidence),
            "dollar_risk": str(self.dollar_risk),
            "approved_lots": str(self.approved_lots),
            "reduced_for_drawdown": self.reduced_for_drawdown,
            "reasons": list(self.reasons),
            "contract_size": str(CONTRACT_SIZE),
        }


def _round_lot(lots: Decimal) -> Decimal:
    if lots < VOLUME_MIN:
        return Decimal("0")
    steps = (lots / VOLUME_STEP).to_integral_value(rounding=ROUND_DOWN)
    return (steps * VOLUME_STEP).quantize(VOLUME_STEP)


def allocate_adaptive_risk(
    config: DecisionEngineV1Config,
    confidence: InstitutionalConfidence,
    *,
    equity: Decimal,
    stop_distance: Decimal,
    daily_drawdown_pct: Decimal,
    consecutive_losses: int,
) -> AdaptiveRiskAllocation:
    reasons: list[str] = []
    if confidence.band == "high":
        base = config.high_conf_risk_pct
        reasons.append(f"High confidence → risk {base}%.")
    elif confidence.band == "medium":
        base = config.mid_conf_risk_pct
        reasons.append(f"Medium confidence → risk {base}%.")
    elif confidence.band == "low":
        base = config.low_conf_risk_pct
        reasons.append(f"Low confidence → risk {base}%.")
    else:
        base = config.risk_floor_pct
        reasons.append("Blocked confidence → floor risk only (no entry).")

    # Never above configured base ceiling
    if base > config.base_risk_pct:
        base = config.base_risk_pct

    risk_pct = risk_must_decrease_after_drawdown(
        base_risk_pct=base,
        current_drawdown_pct=max(Decimal("0"), daily_drawdown_pct),
        consecutive_losses=max(0, consecutive_losses),
        reduction_per_loss=Decimal("0.15"),
        reduction_per_dd_pct=Decimal("0.10"),
        floor_pct=config.risk_floor_pct,
    )
    reduced = risk_pct < base
    if reduced:
        reasons.append(
            f"Risk reduced to {risk_pct}% after drawdown/losses "
            f"(never increases after losses)."
        )

    if equity <= 0 or stop_distance <= 0:
        return AdaptiveRiskAllocation(
            risk_pct=risk_pct,
            base_from_confidence=base,
            dollar_risk=Decimal("0"),
            approved_lots=Decimal("0"),
            reduced_for_drawdown=reduced,
            reasons=(*reasons, "Equity/stop invalid - size zero."),
        )

    dollar = (equity * risk_pct / Decimal("100")).quantize(Decimal("0.01"))
    raw = dollar / (stop_distance * CONTRACT_SIZE)
    lots = _round_lot(raw)
    if lots <= 0:
        reasons.append("Computed size below minimum lot.")
    if not confidence.passed:
        lots = Decimal("0")
        reasons.append("Confidence below minimum — lots forced to zero.")

    return AdaptiveRiskAllocation(
        risk_pct=risk_pct,
        base_from_confidence=base,
        dollar_risk=dollar,
        approved_lots=lots,
        reduced_for_drawdown=reduced,
        reasons=tuple(reasons),
    )
