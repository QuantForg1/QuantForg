"""PRC orchestrator — readiness certification; never production mutation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from app.domain.production_readiness_certification.config import (
    DEFAULT_PRC_CONFIG,
    PrcConfig,
)
from app.domain.production_readiness_certification.modules import (
    INSUFFICIENT,
    continuous_certification,
    data_certification,
    decision_certification,
    execution_certification,
    human_signoff_package,
    operational_certification,
    readiness_dashboard,
    reliability_certification,
    research_certification,
    risk_certification,
)
from app.domain.production_readiness_certification.types import (
    ModuleResult,
    PrcInput,
)
from app.domain.trading.gold_only import GOLD_SYMBOL


@dataclass
class ProductionReadinessCertification:
    config: PrcConfig = field(default_factory=lambda: DEFAULT_PRC_CONFIG)
    history: list[dict[str, Any]] = field(default_factory=list)
    last_status: str | None = None

    def status(self) -> dict[str, object]:
        return {
            **self.config.to_dict(),
            "modules": [
                "reliability_certification",
                "risk_certification",
                "execution_certification",
                "decision_certification",
                "data_certification",
                "research_certification",
                "operational_certification",
                "readiness_dashboard",
                "human_signoff_package",
                "continuous_certification",
            ],
            "capabilities": {
                "xauusd_only": True,
                "read_only": True,
                "certifies_only": True,
                "never_order_send": True,
                "never_place_trades": True,
                "never_change_strategies": True,
                "never_modify_risk_engine": True,
                "never_modify_safety_engine": True,
                "never_modify_decision_engine": True,
                "never_modify_execution_pipeline": True,
                "never_modify_auto_trading": True,
                "never_change_configuration_automatically": True,
                "never_fabricate_evidence": True,
                "human_approval_required": True,
                "notify_on_status_change_only": True,
                "promise_profitability": False,
                "symbol": GOLD_SYMBOL,
            },
            "last_certification_status": self.last_status,
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
            "changes_production": False,
        }

    def evaluate(self, inp: PrcInput) -> dict[str, Any]:
        audit_id = f"prc_{uuid4().hex[:12]}"
        flags = self.config.feature_flags
        modules: dict[str, ModuleResult] = {}

        if flags.get("reliability_certification", True):
            modules["reliability_certification"] = reliability_certification(
                inp, self.config
            )
        if flags.get("risk_certification", True):
            modules["risk_certification"] = risk_certification(
                inp, self.config
            )
        if flags.get("execution_certification", True):
            modules["execution_certification"] = execution_certification(
                inp, self.config
            )
        if flags.get("decision_certification", True):
            modules["decision_certification"] = decision_certification(
                inp, self.config
            )
        if flags.get("data_certification", True):
            modules["data_certification"] = data_certification(
                inp, self.config
            )
        if flags.get("research_certification", True):
            modules["research_certification"] = research_certification(
                inp, self.config
            )
        if flags.get("operational_certification", True):
            modules["operational_certification"] = operational_certification(
                inp, self.config
            )
        if flags.get("readiness_dashboard", True):
            modules["readiness_dashboard"] = readiness_dashboard(
                dict(modules), self.config
            )
        if flags.get("human_signoff_package", True):
            modules["human_signoff_package"] = human_signoff_package(
                dict(modules)
            )

        dash = modules.get("readiness_dashboard")
        current_status = str(
            (dash.details or {}).get("certification_status")
            if dash
            else INSUFFICIENT
        )
        prior = inp.prior_certification_status or self.last_status
        snapshot = {
            "overall_readiness": (
                (dash.details or {}).get("overall_readiness") if dash else None
            ),
            "certification_status": current_status,
        }

        if flags.get("continuous_certification", True):
            modules["continuous_certification"] = continuous_certification(
                prior_status=prior,
                current_status=current_status,
                prior=list(self.history),
                audit_id=audit_id,
                snapshot=snapshot,
            )
            entry = (modules["continuous_certification"].details or {}).get(
                "entry"
            )
            if isinstance(entry, dict):
                self.history.insert(0, entry)
                if len(self.history) > self.config.max_history:
                    self.history = self.history[: self.config.max_history]

        self.last_status = current_status
        hsp = modules.get("human_signoff_package")

        return {
            "version": self.config.version,
            "symbol": GOLD_SYMBOL,
            "audit_id": audit_id,
            "modules": {k: v.to_dict() for k, v in modules.items()},
            "certification_report": {
                "overall_readiness_score": snapshot["overall_readiness"],
                "certification_status": current_status,
                "human_approval_required": True,
                "certification_decision": (
                    (hsp.details or {}).get("certification_decision")
                    if hsp
                    else None
                ),
                "known_risks": (
                    (hsp.details or {}).get("known_risks") if hsp else []
                ),
                "open_issues": (
                    (hsp.details or {}).get("open_issues") if hsp else []
                ),
                "recommended_restrictions": (
                    (hsp.details or {}).get("recommended_restrictions")
                    if hsp
                    else []
                ),
                "notify_operators": (
                    (modules.get("continuous_certification").details or {}).get(
                        "notify_operators"
                    )
                    if modules.get("continuous_certification")
                    else False
                ),
            },
            "read_only": True,
            "certifies_only": True,
            "advisory_only": True,
            "never_order_send": True,
            "never_place_trades": True,
            "changes_strategies": False,
            "modifies_risk_engine": False,
            "modifies_safety_engine": False,
            "modifies_decision_engine": False,
            "modifies_execution_pipeline": False,
            "modifies_auto_trading": False,
            "changes_configuration_automatically": False,
            "human_approval_required": True,
            "promise_profitability": False,
            "explainable": True,
            "auditable": True,
        }


def input_from_dict(data: dict[str, Any]) -> PrcInput:
    return PrcInput(
        reliability=(
            data.get("reliability")
            if isinstance(data.get("reliability"), dict)
            else None
        ),
        risk=(
            data.get("risk") if isinstance(data.get("risk"), dict) else None
        ),
        execution=(
            data.get("execution")
            if isinstance(data.get("execution"), dict)
            else None
        ),
        decision=(
            data.get("decision")
            if isinstance(data.get("decision"), dict)
            else None
        ),
        data=(
            data.get("data") if isinstance(data.get("data"), dict) else None
        ),
        research=(
            data.get("research")
            if isinstance(data.get("research"), dict)
            else None
        ),
        operations=(
            data.get("operations")
            if isinstance(data.get("operations"), dict)
            else None
        ),
        prior_certification_status=(
            str(data["prior_certification_status"])
            if data.get("prior_certification_status")
            else None
        ),
    )
