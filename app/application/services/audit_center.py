"""Audit Center — categorize platform audit events for operators."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.enums.audit import AuditAction
from app.domain.interfaces.platform_uow import PlatformUnitOfWorkFactory

AUDIT_CATEGORIES: tuple[str, ...] = (
    "authentication",
    "broker",
    "strategy",
    "risk",
    "execution",
    "paper",
)


def categorize_audit_event(*, action: str, resource_type: str) -> str | None:
    """Map an audit row into an Audit Center category, or None if uncategorized."""
    rt = resource_type.strip().lower()
    act = action.strip().lower()
    if act in {AuditAction.LOGIN.value, AuditAction.LOGOUT.value} or rt == "auth":
        return "authentication"
    if rt.startswith("broker") or rt.startswith("mt5"):
        return "broker"
    if rt.startswith("strategy"):
        return "strategy"
    if rt.startswith("risk"):
        return "risk"
    if rt.startswith("execution"):
        return "execution"
    if rt.startswith("paper"):
        return "paper"
    return None


@dataclass(frozen=True, slots=True)
class AuditCenterService:
    """Read and group audit events for the Operations Audit Center."""

    platform_uow_factory: PlatformUnitOfWorkFactory

    async def collect(self, *, limit: int = 200) -> dict[str, Any]:
        buckets: dict[str, list[dict[str, Any]]] = {c: [] for c in AUDIT_CATEGORIES}
        try:
            async with self.platform_uow_factory() as uow:
                entries = await uow.audit_logs.list_recent(limit=limit)
        except Exception as exc:
            from core.logging import get_logger

            get_logger(__name__).warning(
                "ops_audit_collect_failed",
                error=str(exc),
            )
            return {
                "categories": list(AUDIT_CATEGORIES),
                "events": buckets,
                "counts": dict.fromkeys(AUDIT_CATEGORIES, 0),
            }

        for entry in entries:
            action = entry.action
            action_val = action.value if hasattr(action, "value") else str(action)
            resource_type = str(entry.resource_type)
            category = categorize_audit_event(
                action=action_val, resource_type=resource_type
            )
            if category is None:
                continue
            outcome = entry.outcome
            outcome_val = outcome.value if hasattr(outcome, "value") else str(outcome)
            occurred = entry.occurred_at or entry.created_at
            buckets[category].append(
                {
                    "id": str(entry.id),
                    "action": action_val,
                    "outcome": outcome_val,
                    "resource_type": resource_type,
                    "resource_id": (
                        str(entry.resource_id)
                        if entry.resource_id is not None
                        else None
                    ),
                    "actor_user_id": (
                        str(entry.actor_user_id)
                        if entry.actor_user_id is not None
                        else None
                    ),
                    "message": entry.message,
                    "occurred_at": (
                        occurred.isoformat() if occurred is not None else None
                    ),
                    "metadata": dict(entry.metadata or {}),
                }
            )
        return {
            "categories": list(AUDIT_CATEGORIES),
            "events": buckets,
            "counts": {k: len(v) for k, v in buckets.items()},
        }
