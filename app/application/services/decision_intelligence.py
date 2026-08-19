"""Application service — Decision Intelligence Center."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from app.application.services.decision_intelligence_assessment import (
    assess_decision_center_engines,
    resolve_claimed_bool,
)
from app.domain.decision_intelligence import (
    DecisionCenterInput,
    DecisionIntelligenceCenter,
)
from app.domain.decision_intelligence.confidence import ConfidenceFactors
from app.domain.decision_intelligence.config import (
    DEFAULT_DI_CONFIG,
    DecisionIntelligenceConfig,
)
from app.domain.decision_intelligence.quality import QualityInput


def _dec(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _opt_bool(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


class DecisionIntelligenceService:
    def __init__(self, config: DecisionIntelligenceConfig | None = None) -> None:
        self._center = DecisionIntelligenceCenter(config or DEFAULT_DI_CONFIG)

    def status(self) -> dict[str, object]:
        return self._center.status()

    def evaluate(self, payload: dict[str, Any]) -> dict[str, object]:
        payload = _merge_alpha_advisory(dict(payload))
        cf_raw = payload.get("confidence_factors") or {}
        if not isinstance(cf_raw, dict):
            cf_raw = {}
        q_raw = payload.get("quality") or {}
        if not isinstance(q_raw, dict):
            q_raw = {}

        use_live = payload.get("use_live_facts") is not False
        _facts, risk_gate, safety_gate = assess_decision_center_engines(
            payload,
            use_live=bool(use_live),
        )
        claimed_risk = _opt_bool(payload.get("risk_engine_passed"))
        claimed_safety = _opt_bool(payload.get("safety_engine_passed"))
        # Engine result wins. Claimed True cannot bypass a FAIL.
        # Claimed bool is only used when the engine was genuinely not runnable.
        risk_passed = resolve_claimed_bool(engine=risk_gate, claimed=claimed_risk)
        safety_passed = resolve_claimed_bool(engine=safety_gate, claimed=claimed_safety)

        inp = DecisionCenterInput(
            side=str(payload.get("side") or "buy"),
            strategy_id=str(payload.get("strategy_id") or "default"),
            technique=(str(payload["technique"]) if payload.get("technique") else None),
            signal_present=_opt_bool(payload.get("signal_present")),
            strategy_consensus_ok=_opt_bool(payload.get("strategy_consensus_ok")),
            market_regime_ok=_opt_bool(payload.get("market_regime_ok")),
            confidence_factors=ConfidenceFactors(
                signal_strength=_dec(cf_raw.get("signal_strength")),
                structure_align=_dec(cf_raw.get("structure_align")),
                consensus=_dec(cf_raw.get("consensus")),
                regime_fit=_dec(cf_raw.get("regime_fit")),
                execution_quality=_dec(cf_raw.get("execution_quality")),
            ),
            spread=_dec(payload.get("spread")),
            daily_drawdown_pct=_dec(payload.get("daily_drawdown_pct")) or Decimal("0"),
            consecutive_losses=int(payload.get("consecutive_losses") or 0),
            risk_engine_passed=risk_passed,
            safety_engine_passed=safety_passed,
            risk_engine_reason=risk_gate.reason,
            safety_engine_reason=safety_gate.reason,
            quality=QualityInput(
                approve_precision=_dec(q_raw.get("approve_precision")),
                reject_precision=_dec(q_raw.get("reject_precision")),
                override_rate=_dec(q_raw.get("override_rate")),
                audit_completeness=_dec(q_raw.get("audit_completeness")),
            ),
            operator_action=(
                str(payload["operator_action"])
                if payload.get("operator_action")
                else None
            ),
            operator=str(payload.get("operator") or "system"),
            operator_reason=str(payload.get("operator_reason") or ""),
        )
        result = self._center.evaluate(inp).to_dict()
        result["assessment"] = {
            "symbol": risk_gate.symbol,
            "evaluated_at": risk_gate.evaluated_at or safety_gate.evaluated_at,
            "risk": risk_gate.to_dict(),
            "safety": safety_gate.to_dict(),
            "force_execution": False,
            "bypass_risk": False,
            "bypass_safety": False,
            "execute_now_required": False,
            "order_send": False,
            "note": (
                "Risk/Safety are assessed when prerequisites exist. "
                "NOT_ASSESSED is not PASS. Confidence never bypasses either engine."
            ),
        }
        try:
            from app.domain.institutional_trading.operations.system_coherence import (
                Plane,
                get_coherence_store,
            )

            get_coherence_store().publish(
                Plane.DECISION_INTELLIGENCE.value,
                {
                    "symbol": risk_gate.symbol,
                    "as_of": risk_gate.evaluated_at,
                    "risk": risk_gate.to_dict(),
                    "safety": safety_gate.to_dict(),
                    "decision": result.get("decision"),
                },
                source="decision_intelligence.evaluate",
                event_type="DECISION_INTELLIGENCE",
            )
        except Exception:
            from core.logging import get_logger

            get_logger(__name__).debug(
                "decision_intelligence_coherence_publish_failed", exc_info=True
            )
        if payload.get("_alpha_audit"):
            result["alpha_integration"] = payload["_alpha_audit"]
        return result

    def history(self, *, limit: int = 50) -> dict[str, object]:
        return {"decisions": self._center.list_history(limit=limit)}

    def replay(self, audit_id: str) -> dict[str, object]:
        return self._center.replay(audit_id)

    def policies(self) -> dict[str, object]:
        return self._center.config.to_dict()

    def update_policies(self, updates: dict[str, Any]) -> dict[str, object]:
        return self._center.update_policies(updates)


def _merge_alpha_advisory(payload: dict[str, Any]) -> dict[str, Any]:
    """Map Alpha Engine advisory into DI fields without touching Risk/Safety."""
    alpha = payload.get("alpha") or payload.get("alpha_advisory")
    if not isinstance(alpha, dict) or not alpha:
        return payload

    # Never allow alpha to set risk/safety.
    alpha.pop("risk_engine_passed", None)
    alpha.pop("safety_engine_passed", None)

    if payload.get("market_regime_ok") is None and "market_regime_ok" in alpha:
        payload["market_regime_ok"] = alpha.get("market_regime_ok")

    cf = payload.get("confidence_factors")
    if not isinstance(cf, dict):
        cf = {}
    alpha_cf = alpha.get("confidence_factors")
    if isinstance(alpha_cf, dict):
        for key, value in alpha_cf.items():
            if cf.get(key) is None and value is not None:
                cf[key] = value
    payload["confidence_factors"] = cf

    if not payload.get("strategy_id") or payload.get("strategy_id") == "default":
        payload["strategy_id"] = str(alpha.get("strategy_id") or "alpha-engine-v1")

    payload["_alpha_audit"] = {
        "integrated": True,
        "alpha_composite_score": alpha.get("alpha_composite_score"),
        "alpha_market_quality_band": alpha.get("alpha_market_quality_band"),
        "never_sets_risk_or_safety": True,
        "note": alpha.get("note") or "Alpha advisory mapped — Risk/Safety unchanged",
    }
    return payload
