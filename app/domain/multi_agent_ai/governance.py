"""AI Governance — hard locks and operator checklist."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.multi_agent_ai.config import MultiAgentConfig
from app.domain.multi_agent_ai.types import AgentOutput

GOVERNANCE_CHECKLIST: tuple[str, ...] = (
    "XAUUSD-only agent collaboration",
    "Risk Engine remains authoritative",
    "Safety Engine remains authoritative",
    "Coordinator never bypasses Risk or Safety",
    "Execution pipeline unchanged (no order_send)",
    "AI Memory does not rewrite trading rules",
    "Every agent output is explainable",
    "Every decision is auditable via events",
)


@dataclass(frozen=True, slots=True)
class GovernanceResult:
    status: str
    passed: bool
    violations: tuple[str, ...]
    checklist: list[dict[str, Any]]
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "passed": self.passed,
            "violations": list(self.violations),
            "checklist": list(self.checklist),
            "detail": self.detail,
            "allow_bypass_risk": False,
            "allow_bypass_safety": False,
            "allow_order_send": False,
            "allow_memory_rewrite_rules": False,
        }


def evaluate_governance(
    *,
    config: MultiAgentConfig,
    outputs: list[AgentOutput],
    decision: str,
    allow_execution_path: bool,
    risk_engine_passed: bool | None,
    safety_engine_passed: bool | None,
) -> GovernanceResult:
    violations: list[str] = []

    if (
        config.allow_bypass_risk
        or config.allow_bypass_safety
        or config.allow_order_send
    ):
        violations.append("Config hard-lock compromised")
    if config.allow_memory_rewrite_rules:
        violations.append("Memory rewrite rules must stay disabled")

    if decision == "APPROVE" and risk_engine_passed is not True:
        violations.append("APPROVE attempted without Risk Engine pass — blocked")
    if decision == "APPROVE" and safety_engine_passed is not True:
        violations.append("APPROVE attempted without Safety Engine pass — blocked")

    if allow_execution_path and (
        risk_engine_passed is not True or safety_engine_passed is not True
    ):
        violations.append("Execution path claimed without Risk+Safety — blocked")

    for out in outputs:
        if not out.explainable or not out.reasons:
            violations.append(f"Agent {out.agent} missing explainable reasons")
        if out.agent in {"risk", "safety"} and not out.authoritative:
            violations.append(f"{out.agent} must be marked authoritative")

    # Governance may force HOLD/REJECT semantics at coordinator; here we report.
    passed = len(violations) == 0
    return GovernanceResult(
        status="available",
        passed=passed,
        violations=tuple(violations),
        checklist=[
            {"step": i + 1, "text": t, "done": passed}
            for i, t in enumerate(GOVERNANCE_CHECKLIST)
        ],
        detail=(
            "Governance passed — advisory collaboration within hard locks"
            if passed
            else "Governance violations detected — fail closed"
        ),
    )
