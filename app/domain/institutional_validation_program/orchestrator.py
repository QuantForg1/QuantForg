"""IVP orchestrator — continuous evidence evaluation; never production mutation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from app.domain.institutional_validation_program.config import (
    DEFAULT_IVP_CONFIG,
    IvpConfig,
)
from app.domain.institutional_validation_program.modules import (
    confidence_analysis,
    configuration_comparison,
    evidence_dashboard,
    human_decision_package,
    regime_validation,
    replay_vs_paper,
    risk_validation,
    stability_analysis,
    statistical_validation,
    validation_history,
)
from app.domain.institutional_validation_program.types import IvpInput, ModuleResult
from app.domain.trading.gold_only import GOLD_SYMBOL


@dataclass
class InstitutionalValidationProgram:
    config: IvpConfig = field(default_factory=lambda: DEFAULT_IVP_CONFIG)
    history: list[dict[str, Any]] = field(default_factory=list)

    def status(self) -> dict[str, object]:
        return {
            **self.config.to_dict(),
            "modules": [
                "statistical_validation",
                "confidence_analysis",
                "regime_validation",
                "configuration_comparison",
                "stability_analysis",
                "risk_validation",
                "replay_vs_paper",
                "evidence_dashboard",
                "human_decision_package",
                "validation_history",
            ],
            "capabilities": {
                "xauusd_only": True,
                "read_only": True,
                "never_order_send": True,
                "never_place_trades": True,
                "never_modify_strategies": True,
                "never_modify_execution": True,
                "never_modify_risk_engine": True,
                "never_modify_safety_engine": True,
                "never_modify_decision_engine": True,
                "never_auto_promote_research": True,
                "never_fabricate_metrics": True,
                "append_only_history": True,
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
        return {
            "status": "available" if rows else "empty",
            "items": rows,
            "append_only": True,
            "overwrites_prior": False,
        }

    def evaluate(self, inp: IvpInput) -> dict[str, Any]:
        audit_id = f"ivp_{uuid4().hex[:12]}"
        flags = self.config.feature_flags
        modules: dict[str, ModuleResult] = {}

        if flags.get("statistical_validation", True):
            modules["statistical_validation"] = statistical_validation(
                inp, self.config
            )
        if flags.get("confidence_analysis", True):
            modules["confidence_analysis"] = confidence_analysis(
                inp, self.config
            )
        if flags.get("regime_validation", True):
            modules["regime_validation"] = regime_validation(inp, self.config)
        if flags.get("configuration_comparison", True):
            modules["configuration_comparison"] = configuration_comparison(
                inp, self.config
            )
        if flags.get("stability_analysis", True):
            modules["stability_analysis"] = stability_analysis(
                inp, self.config
            )
        if flags.get("risk_validation", True):
            modules["risk_validation"] = risk_validation(inp, self.config)
        if flags.get("replay_vs_paper", True):
            modules["replay_vs_paper"] = replay_vs_paper(inp, self.config)
        if flags.get("evidence_dashboard", True):
            modules["evidence_dashboard"] = evidence_dashboard(dict(modules))
        if flags.get("human_decision_package", True):
            modules["human_decision_package"] = human_decision_package(
                inp, dict(modules)
            )

        dash = modules.get("evidence_dashboard")
        hdp = modules.get("human_decision_package")
        snapshot = {
            "evidence_strength_pct": (
                (dash.details or {}).get("evidence_strength_pct")
                if dash
                else None
            ),
            "sample_size": (
                (dash.details or {}).get("sample_size") if dash else None
            ),
            "deployment_recommendation": (
                (hdp.details or {}).get("deployment_recommendation")
                if hdp
                else "NONE — insufficient or unstable evidence"
            ),
        }

        if flags.get("validation_history", True):
            modules["validation_history"] = validation_history(
                inp,
                prior=list(self.history),
                audit_id=audit_id,
                snapshot=snapshot,
            )
            entry = (modules["validation_history"].details or {}).get("entry")
            if isinstance(entry, dict):
                self.history.insert(0, entry)
                # Append-only: truncate from the end, never mutate prior rows
                if len(self.history) > self.config.max_history:
                    self.history = self.history[: self.config.max_history]

        result = {
            "version": self.config.version,
            "symbol": GOLD_SYMBOL,
            "audit_id": audit_id,
            "modules": {k: v.to_dict() for k, v in modules.items()},
            "evidence_summary": {
                "strength_pct": snapshot["evidence_strength_pct"],
                "sample_size": snapshot["sample_size"],
                "deployment_recommendation": snapshot[
                    "deployment_recommendation"
                ],
                "strategy_id": inp.strategy_id,
                "configuration_id": inp.configuration_id,
            },
            "read_only": True,
            "advisory_only": True,
            "never_order_send": True,
            "never_place_trades": True,
            "modifies_strategies": False,
            "modifies_execution": False,
            "modifies_risk_engine": False,
            "modifies_safety_engine": False,
            "modifies_decision_engine": False,
            "auto_promote_research": False,
            "promise_profitability": False,
            "append_only_history": True,
            "explainable": True,
            "auditable": True,
        }
        return result


def input_from_dict(data: dict[str, Any]) -> IvpInput:
    return IvpInput(
        completed_trades=(
            data.get("completed_trades")
            if isinstance(data.get("completed_trades"), list)
            else None
        ),
        configurations=(
            data.get("configurations")
            if isinstance(data.get("configurations"), list)
            else None
        ),
        risk_facts=(
            data.get("risk_facts")
            if isinstance(data.get("risk_facts"), dict)
            else None
        ),
        replay_results=(
            data.get("replay_results")
            if isinstance(data.get("replay_results"), dict)
            else None
        ),
        paper_results=(
            data.get("paper_results")
            if isinstance(data.get("paper_results"), dict)
            else None
        ),
        strategy_id=(
            str(data["strategy_id"]) if data.get("strategy_id") else None
        ),
        configuration_id=(
            str(data["configuration_id"])
            if data.get("configuration_id")
            else None
        ),
        history_event=(
            data.get("history_event")
            if isinstance(data.get("history_event"), dict)
            else None
        ),
    )
