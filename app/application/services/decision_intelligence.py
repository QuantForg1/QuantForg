"""Application service — Decision Intelligence Center."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

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
        cf_raw = payload.get("confidence_factors") or {}
        if not isinstance(cf_raw, dict):
            cf_raw = {}
        q_raw = payload.get("quality") or {}
        if not isinstance(q_raw, dict):
            q_raw = {}

        inp = DecisionCenterInput(
            side=str(payload.get("side") or "buy"),
            strategy_id=str(payload.get("strategy_id") or "default"),
            technique=(
                str(payload["technique"]) if payload.get("technique") else None
            ),
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
            daily_drawdown_pct=_dec(payload.get("daily_drawdown_pct"))
            or Decimal("0"),
            consecutive_losses=int(payload.get("consecutive_losses") or 0),
            risk_engine_passed=_opt_bool(payload.get("risk_engine_passed")),
            safety_engine_passed=_opt_bool(payload.get("safety_engine_passed")),
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
        return self._center.evaluate(inp).to_dict()

    def history(self, *, limit: int = 50) -> dict[str, object]:
        return {"decisions": self._center.list_history(limit=limit)}

    def replay(self, audit_id: str) -> dict[str, object]:
        return self._center.replay(audit_id)

    def policies(self) -> dict[str, object]:
        return self._center.config.to_dict()

    def update_policies(self, updates: dict[str, Any]) -> dict[str, object]:
        return self._center.update_policies(updates)
