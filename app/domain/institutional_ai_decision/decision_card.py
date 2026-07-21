"""Explainable Decision Cards — why accept / reject."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.ai_trading_robot.strategy_health import StrategyHealth
from app.domain.institutional_ai_decision.adaptive_risk import AdaptiveRiskAllocation
from app.domain.institutional_ai_decision.confidence import InstitutionalConfidence
from app.domain.institutional_ai_decision.layers import LayerResult
from app.domain.institutional_ai_decision.loss_protection import LossProtectionResult


@dataclass(frozen=True, slots=True)
class DecisionCard:
    decision: str  # WAIT | TRADE_IDEA | SUSPENDED
    headline: str
    accepted: bool
    why_accepted: tuple[str, ...]
    why_rejected: tuple[str, ...]
    layer_summaries: tuple[str, ...]
    risk_note: str
    health_note: str
    dry_run: bool
    disclaimer: str

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": self.decision,
            "headline": self.headline,
            "accepted": self.accepted,
            "why_accepted": list(self.why_accepted),
            "why_rejected": list(self.why_rejected),
            "layer_summaries": list(self.layer_summaries),
            "risk_note": self.risk_note,
            "health_note": self.health_note,
            "dry_run": self.dry_run,
            "disclaimer": self.disclaimer,
        }


def build_decision_card(
    *,
    decision: str,
    layers: tuple[LayerResult, ...],
    confidence: InstitutionalConfidence,
    risk: AdaptiveRiskAllocation,
    loss_protection: LossProtectionResult,
    health: StrategyHealth,
    dry_run: bool,
) -> DecisionCard:
    why_ok: list[str] = []
    why_no: list[str] = []
    layer_summaries = tuple(
        f"{layer.name}: {'PASS' if layer.passed else 'BLOCK'} — {layer.reason}"
        for layer in layers
    )

    for layer in layers:
        if layer.passed:
            why_ok.append(layer.reason)
        elif layer.required:
            why_no.append(layer.reason)

    if confidence.passed:
        why_ok.append(
            f"Institutional confidence {confidence.score} ({confidence.band})."
        )
    else:
        fallback = [f"Confidence {confidence.score}."]
        why_no.extend(confidence.adjustments[-2:] or fallback)

    if not loss_protection.passed:
        why_no.extend(loss_protection.reasons)

    if health.auto_pause:
        why_no.append(
            f"Strategy {health.strategy_id} auto-suspended "
            f"(health {health.score})."
        )

    if decision == "TRADE_IDEA":
        headline = (
            "TRADE_IDEA — advisory only; dry-run validates signal without orders."
            if dry_run
            else "TRADE_IDEA — still requires Execution Gateway after Risk+Safety."
        )
        accepted = True
    elif decision == "SUSPENDED":
        headline = "SUSPENDED — strategy health below auto-suspend threshold."
        accepted = False
    else:
        headline = "WAIT — capital preservation; insufficient institutional edge."
        accepted = False

    return DecisionCard(
        decision=decision,
        headline=headline,
        accepted=accepted,
        why_accepted=tuple(why_ok[:8]),
        why_rejected=tuple(why_no[:8]),
        layer_summaries=layer_summaries,
        risk_note=(
            f"Adaptive risk {risk.risk_pct}% → {risk.approved_lots} lots. "
            + (" ".join(risk.reasons[:2]))
        ),
        health_note=(
            f"Strategy {health.strategy_id}: health {health.score} "
            f"({health.status})"
            + ("; AUTO-SUSPEND" if health.auto_pause else "")
        ),
        dry_run=dry_run,
        disclaimer=(
            "This card explains process discipline only. It is not a profitability "
            "promise. Live orders must still pass Risk Engine and Safety Engine "
            "via the production execution pipeline. Decision Engine V1 never "
            "calls order_send."
        ),
    )
