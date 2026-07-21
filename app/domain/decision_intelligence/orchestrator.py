"""Decision Intelligence Center orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from uuid import uuid4

from app.domain.ai_trading_robot.invariants import assert_no_forbidden_technique
from app.domain.decision_intelligence.confidence import (
    ConfidenceBreakdown,
    ConfidenceFactors,
    breakdown_confidence,
)
from app.domain.decision_intelligence.config import (
    DEFAULT_DI_CONFIG,
    DecisionIntelligenceConfig,
)
from app.domain.decision_intelligence.history import DecisionHistoryStore
from app.domain.decision_intelligence.override import (
    OperatorOverride,
    apply_operator_override,
)
from app.domain.decision_intelligence.quality import (
    DecisionQualityDashboard,
    QualityInput,
    build_quality_dashboard,
)
from app.domain.decision_intelligence.summary import (
    ExecutivePanel,
    ExplainableSummary,
    build_explainable_summary,
)
from app.domain.decision_intelligence.veto import VetoInput, VetoResult, evaluate_vetoes
from app.domain.decision_intelligence.waterfall import (
    WaterfallInput,
    WaterfallStage,
    evaluate_waterfall,
)
from app.domain.trading.gold_only import GOLD_SYMBOL


@dataclass(frozen=True, slots=True)
class DecisionCenterInput:
    side: str = "buy"
    strategy_id: str = "default"
    technique: str | None = None
    signal_present: bool | None = None
    strategy_consensus_ok: bool | None = None
    market_regime_ok: bool | None = None
    confidence_factors: ConfidenceFactors = field(
        default_factory=ConfidenceFactors
    )
    spread: Decimal | None = None
    daily_drawdown_pct: Decimal = Decimal("0")
    consecutive_losses: int = 0
    risk_engine_passed: bool | None = None
    safety_engine_passed: bool | None = None
    quality: QualityInput = field(default_factory=QualityInput)
    operator_action: str | None = None
    operator: str = "system"
    operator_reason: str = ""


@dataclass(frozen=True, slots=True)
class DecisionCenterResult:
    version: str
    symbol: str
    decision: str
    allow_execution_path: bool
    audit_id: str
    executive_panel: ExecutivePanel
    waterfall: tuple[WaterfallStage, ...]
    veto: VetoResult
    confidence: ConfidenceBreakdown
    summary: ExplainableSummary
    quality: DecisionQualityDashboard
    override: OperatorOverride | None
    policies: dict[str, object]
    capabilities: dict[str, bool]

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "symbol": self.symbol,
            "decision": self.decision,
            "allow_execution_path": self.allow_execution_path,
            "audit_id": self.audit_id,
            "executive_panel": self.executive_panel.to_dict(),
            "waterfall": [s.to_dict() for s in self.waterfall],
            "veto": self.veto.to_dict(),
            "confidence": self.confidence.to_dict(),
            "summary": self.summary.to_dict(),
            "quality": self.quality.to_dict(),
            "override": self.override.to_dict() if self.override else None,
            "policies": dict(self.policies),
            "capabilities": dict(self.capabilities),
            "execution_note": (
                "Decision Intelligence Center never calls order_send and never "
                "force-executes. APPROVE only means pre-execution advisory path "
                "is clear after Risk+Safety ALLOW — Execution Gateway unchanged."
            ),
        }


class DecisionIntelligenceCenter:
    def __init__(self, config: DecisionIntelligenceConfig | None = None) -> None:
        self.config = config or DEFAULT_DI_CONFIG
        self._store = DecisionHistoryStore(self.config)

    def capabilities(self) -> dict[str, bool]:
        return {
            "executive_decision_panel": True,
            "decision_waterfall": True,
            "trade_veto_system": True,
            "confidence_breakdown": True,
            "decision_history": True,
            "explainable_ai_summary": True,
            "decision_quality_dashboard": True,
            "operator_override_controls": True,
            "decision_replay": True,
            "configurable_decision_policies": True,
            "force_execution": False,
            "bypass_risk": False,
            "bypass_safety": False,
        }

    def status(self) -> dict[str, object]:
        cfg = self.config.to_dict()
        return {
            "version": self.config.version,
            "symbol": GOLD_SYMBOL,
            "mission": cfg["mission"],
            "capabilities": self.capabilities(),
            "policies": cfg,
            "recent_decisions": self._store.list_recent(limit=10),
            "disclaimer": (
                "Decision Intelligence Center is the final institutional gate. "
                "It may REJECT or HOLD. It never force-executes and never "
                "bypasses Risk Engine or Safety Engine."
            ),
        }

    def update_policies(self, updates: dict[str, Any]) -> dict[str, object]:
        """Apply allowed policy knobs; hard locks always remain False."""
        cur = self.config
        min_confidence = cur.min_confidence
        high_confidence = cur.high_confidence
        require_signal = cur.require_signal
        require_strategy_consensus = cur.require_strategy_consensus
        require_market_regime_ok = cur.require_market_regime_ok
        max_spread = cur.max_spread
        max_daily_drawdown_pct = cur.max_daily_drawdown_pct
        max_consecutive_losses = cur.max_consecutive_losses
        min_decision_quality = cur.min_decision_quality
        max_history = cur.max_history

        if "min_confidence" in updates:
            min_confidence = Decimal(str(updates["min_confidence"]))
        if "high_confidence" in updates:
            high_confidence = Decimal(str(updates["high_confidence"]))
        if "require_signal" in updates:
            require_signal = bool(updates["require_signal"])
        if "require_strategy_consensus" in updates:
            require_strategy_consensus = bool(
                updates["require_strategy_consensus"]
            )
        if "require_market_regime_ok" in updates:
            require_market_regime_ok = bool(updates["require_market_regime_ok"])
        if "max_spread" in updates:
            max_spread = Decimal(str(updates["max_spread"]))
        if "max_daily_drawdown_pct" in updates:
            max_daily_drawdown_pct = Decimal(
                str(updates["max_daily_drawdown_pct"])
            )
        if "max_consecutive_losses" in updates:
            max_consecutive_losses = int(updates["max_consecutive_losses"])
        if "min_decision_quality" in updates:
            min_decision_quality = Decimal(str(updates["min_decision_quality"]))
        if "max_history" in updates:
            max_history = int(updates["max_history"])

        old_rows = self._store.list_recent(limit=max_history)
        self.config = DecisionIntelligenceConfig(
            min_confidence=min_confidence,
            high_confidence=high_confidence,
            require_signal=require_signal,
            require_strategy_consensus=require_strategy_consensus,
            require_market_regime_ok=require_market_regime_ok,
            max_spread=max_spread,
            max_daily_drawdown_pct=max_daily_drawdown_pct,
            max_consecutive_losses=max_consecutive_losses,
            min_decision_quality=min_decision_quality,
            max_history=max_history,
        )
        self._store = DecisionHistoryStore(self.config)
        for row in reversed(old_rows):
            self._store.record(row)
        return self.config.to_dict()

    def evaluate(self, inp: DecisionCenterInput) -> DecisionCenterResult:
        audit_id = str(uuid4())
        override: OperatorOverride | None = None
        operator_veto = False
        if inp.operator_action:
            override = apply_operator_override(
                action=inp.operator_action,
                operator=inp.operator,
                reason=inp.operator_reason,
            )
            if override.action == "reject":
                operator_veto = True

        tech = assert_no_forbidden_technique(inp.technique)
        veto = evaluate_vetoes(
            self.config,
            VetoInput(
                spread=inp.spread,
                daily_drawdown_pct=inp.daily_drawdown_pct,
                consecutive_losses=inp.consecutive_losses,
                forbidden_technique=not tech.ok,
                operator_veto=operator_veto,
                operator_veto_reason=(
                    override.reason if override and operator_veto else ""
                ),
            ),
        )

        confidence = breakdown_confidence(self.config, inp.confidence_factors)
        stages = evaluate_waterfall(
            self.config,
            WaterfallInput(
                signal_present=inp.signal_present,
                strategy_consensus_ok=inp.strategy_consensus_ok,
                market_regime_ok=inp.market_regime_ok,
                confidence=(
                    confidence.score if confidence.status == "available" else None
                ),
                veto_clear=veto.clear,
                risk_engine_passed=inp.risk_engine_passed,
                safety_engine_passed=inp.safety_engine_passed,
            ),
        )

        risk_ok = inp.risk_engine_passed is True
        safety_ok = inp.safety_engine_passed is True
        waterfall_ok = all(s.passed for s in stages if s.required)

        # Incomplete Risk/Safety → HOLD; hard fails → REJECT; else APPROVE advisory
        if inp.risk_engine_passed is None or inp.safety_engine_passed is None:
            decision = "HOLD"
        elif override and override.action == "reject":
            decision = "REJECT"
        elif override and override.action == "hold":
            decision = "HOLD"
        elif (
            waterfall_ok
            and risk_ok
            and safety_ok
            and veto.clear
            and confidence.passed
        ):
            decision = "APPROVE"
        else:
            decision = "REJECT"

        # Never allow execution path unless Risk+Safety ALLOW and APPROVE
        allow_path = decision == "APPROVE" and risk_ok and safety_ok
        # Even APPROVE cannot force execution — flag is advisory only
        allow_execution_path = allow_path

        summary = build_explainable_summary(
            decision=decision,
            stages=stages,
            confidence=confidence,
            veto=veto,
        )
        quality = build_quality_dashboard(self.config, inp.quality)
        panel = ExecutivePanel(
            decision=decision,
            allow_execution_path=allow_execution_path,
            confidence=str(confidence.score),
            risk_passed=inp.risk_engine_passed,
            safety_passed=inp.safety_engine_passed,
            veto_clear=veto.clear,
            audit_id=audit_id,
            note=(
                "Executive panel is advisory. Production Execution Gateway "
                "remains unchanged and must still enforce Risk/Safety."
            ),
        )

        result = DecisionCenterResult(
            version=self.config.version,
            symbol=GOLD_SYMBOL,
            decision=decision,
            allow_execution_path=allow_execution_path,
            audit_id=audit_id,
            executive_panel=panel,
            waterfall=stages,
            veto=veto,
            confidence=confidence,
            summary=summary,
            quality=quality,
            override=override,
            policies=self.config.to_dict(),
            capabilities=self.capabilities(),
        )
        self._store.record(result.to_dict())
        return result

    def list_history(self, *, limit: int = 50) -> list[dict[str, object]]:
        return self._store.list_recent(limit=limit)

    def replay(self, audit_id: str) -> dict[str, object]:
        return self._store.replay(audit_id)
