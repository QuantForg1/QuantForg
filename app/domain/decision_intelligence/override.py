"""Operator override controls — reject/hold only; never force execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class OperatorOverride:
    action: str  # reject | hold | clear_veto_request (ignored for force)
    operator: str
    reason: str
    applied_at: str
    forced_execution: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "action": self.action,
            "operator": self.operator,
            "reason": self.reason,
            "applied_at": self.applied_at,
            "forced_execution": False,
            "note": (
                "Operator may REJECT or HOLD only. "
                "Force-approve / force-execution is hard-locked off."
            ),
        }


def apply_operator_override(
    *,
    action: str,
    operator: str,
    reason: str = "",
) -> OperatorOverride:
    act = action.strip().lower()
    if act in {"force_approve", "force_execute", "bypass_risk", "bypass_safety"}:
        # Hard reject — convert to hold with audit reason
        return OperatorOverride(
            action="hold",
            operator=operator,
            reason=(
                f"Rejected force action '{act}'. "
                "Decision Center never force-executes or bypasses Risk/Safety."
            ),
            applied_at=datetime.now(UTC).isoformat(),
            forced_execution=False,
        )
    if act not in {"reject", "hold", "clear"}:
        act = "hold"
    return OperatorOverride(
        action=act,
        operator=operator,
        reason=reason or f"Operator {act}",
        applied_at=datetime.now(UTC).isoformat(),
        forced_execution=False,
    )
