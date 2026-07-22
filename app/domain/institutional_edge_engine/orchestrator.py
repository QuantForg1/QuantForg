"""IEE orchestrator — advisory edge analytics; never order_send."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

from app.domain.institutional_edge_engine.config import (
    DEFAULT_IEE_CONFIG,
    IeeConfig,
)
from app.domain.institutional_edge_engine.modules import (
    detect_edge_decay,
    evaluate_entry_quality,
    evaluate_exit_quality,
    evaluate_regime_performance,
    evaluate_risk_discipline,
    evaluate_strategy_stability,
    explainable_edge_report,
    institutional_scorecard,
    monthly_research_package,
    score_edge,
)
from app.domain.institutional_edge_engine.types import IeeInput, ModuleResult
from app.domain.trading.gold_only import GOLD_SYMBOL


@dataclass
class InstitutionalEdgeEngine:
    config: IeeConfig = field(default_factory=lambda: DEFAULT_IEE_CONFIG)
    history: list[dict[str, Any]] = field(default_factory=list)

    def status(self) -> dict[str, object]:
        return {
            **self.config.to_dict(),
            "modules": [
                "edge_scoring",
                "strategy_stability",
                "regime_performance",
                "entry_quality",
                "exit_quality",
                "risk_discipline",
                "edge_decay",
                "explainable_edge_report",
                "institutional_scorecard",
                "monthly_research_package",
            ],
            "capabilities": {
                "xauusd_only": True,
                "advisory_only": True,
                "analytical_only": True,
                "never_order_send": True,
                "never_disables_trading": True,
                "never_fabricate_metrics": True,
                "never_modify_auto_trading": True,
                "never_modify_execution_pipeline": True,
                "never_modify_decision_engine": True,
                "never_modify_risk_engine": True,
                "never_modify_safety_engine": True,
                "never_modify_asi": True,
                "never_auto_modify_strategy_rules": True,
                "insufficient_data_label": "Insufficient Data",
                "promise_profitability": False,
                "symbol": GOLD_SYMBOL,
            },
            "recent": self.history[:10],
        }

    def update_policies(self, updates: dict[str, object]) -> dict[str, object]:
        self.config = self.config.update(updates)
        return self.config.to_dict()

    def list_history(self, *, limit: int = 50) -> dict[str, Any]:
        rows = self.history[: max(1, min(limit, self.config.max_history))]
        return {"status": "available" if rows else "empty", "items": rows}

    def evaluate(self, inp: IeeInput) -> dict[str, Any]:
        audit_id = f"iee_{uuid4().hex[:12]}"
        flags = self.config.feature_flags
        modules: dict[str, ModuleResult] = {}

        if flags.get("edge_scoring", True):
            modules["edge_scoring"] = score_edge(inp, self.config)
        if flags.get("strategy_stability", True):
            modules["strategy_stability"] = evaluate_strategy_stability(
                inp, self.config
            )
        if flags.get("regime_performance", True):
            modules["regime_performance"] = evaluate_regime_performance(
                inp, self.config
            )
        if flags.get("entry_quality", True):
            modules["entry_quality"] = evaluate_entry_quality(inp, self.config)
        if flags.get("exit_quality", True):
            modules["exit_quality"] = evaluate_exit_quality(inp, self.config)
        if flags.get("risk_discipline", True):
            modules["risk_discipline"] = evaluate_risk_discipline(
                inp, self.config
            )
        if flags.get("edge_decay", True):
            modules["edge_decay"] = detect_edge_decay(
                inp,
                self.config,
                modules.get(
                    "edge_scoring",
                    ModuleResult(
                        module="edge_scoring",
                        status="empty",
                        score=None,
                        recommendation="Insufficient Data",
                        reasons=(),
                    ),
                ),
            )
        if flags.get("explainable_edge_report", True):
            modules["explainable_edge_report"] = explainable_edge_report(
                dict(modules)
            )
        if flags.get("institutional_scorecard", True):
            modules["institutional_scorecard"] = institutional_scorecard(
                dict(modules)
            )
        if flags.get("monthly_research_package", True):
            modules["monthly_research_package"] = monthly_research_package(
                inp, self.config, dict(modules)
            )

        scorecard = modules.get("institutional_scorecard")
        edge = modules.get("edge_scoring")
        decay = modules.get("edge_decay")
        report = modules.get("explainable_edge_report")

        result = {
            "version": self.config.version,
            "symbol": GOLD_SYMBOL,
            "audit_id": audit_id,
            "modules": {k: v.to_dict() for k, v in modules.items()},
            "edge_report_summary": {
                "edge_score": (
                    str(edge.score)
                    if edge and edge.score is not None
                    else None
                ),
                "edge_status": edge.status if edge else "empty",
                "edge_recommendation": (
                    edge.recommendation if edge else "Insufficient Data"
                ),
                "edge_warning": bool(
                    decay and (decay.details or {}).get("edge_warning")
                ),
                "explainability": (
                    list(report.reasons) if report else []
                ),
            },
            "institutional_score": {
                "overall_score": (
                    str(scorecard.score)
                    if scorecard and scorecard.score is not None
                    else None
                ),
                "overall_grade": (
                    (scorecard.details or {}).get("overall_grade")
                    if scorecard
                    else None
                ),
                "panels": (
                    (scorecard.details or {}).get("panels")
                    if scorecard
                    else {}
                ),
                "status": scorecard.status if scorecard else "empty",
            },
            "advisory_only": True,
            "analytical_only": True,
            "never_order_send": True,
            "never_disables_trading": True,
            "never_fabricate_metrics": True,
            "modifies_auto_trading": False,
            "modifies_execution_pipeline": False,
            "modifies_decision_engine": False,
            "modifies_risk_engine": False,
            "modifies_safety_engine": False,
            "modifies_asi": False,
            "auto_modifies_strategy_rules": False,
            "promise_profitability": False,
            "explainable": True,
            "auditable": True,
        }
        self.history.insert(
            0,
            {
                "audit_id": audit_id,
                "edge_score": result["edge_report_summary"]["edge_score"],
                "grade": result["institutional_score"]["overall_grade"],
            },
        )
        if len(self.history) > self.config.max_history:
            self.history = self.history[: self.config.max_history]
        return result


def input_from_dict(data: dict[str, Any]) -> IeeInput:
    def d(v: Any) -> Decimal | None:
        if v is None:
            return None
        try:
            return Decimal(str(v))
        except (InvalidOperation, ValueError, TypeError):
            return None

    return IeeInput(
        completed_trades=(
            data.get("completed_trades")
            if isinstance(data.get("completed_trades"), list)
            else None
        ),
        discipline_facts=(
            data.get("discipline_facts")
            if isinstance(data.get("discipline_facts"), dict)
            else None
        ),
        prior_edge_score=d(data.get("prior_edge_score")),
        research_month=(
            str(data["research_month"]) if data.get("research_month") else None
        ),
    )
