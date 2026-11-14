"""Autonomous strategy supervisor — default MONITOR_ONLY."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from threading import Lock
from typing import Any
from uuid import uuid4


class SupervisorMode(StrEnum):
    MONITOR_ONLY = "MONITOR_ONLY"
    RECOMMENDATION = "RECOMMENDATION"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    APPROVED_AUTOMATION = "APPROVED_AUTOMATION"


_ALLOWED_AUTO_ACTIONS = frozenset({"pause_strategy", "tighten_risk", "no_op"})


@dataclass(frozen=True, slots=True)
class SupervisorEvent:
    event_id: str
    at: datetime
    mode: SupervisorMode
    action: str
    detail: str
    applied: bool
    reject_reason: str | None


@dataclass
class SupervisorState:
    mode: SupervisorMode = SupervisorMode.MONITOR_ONLY
    _audit: list[SupervisorEvent] = field(default_factory=list)
    _lock: Lock = field(default_factory=Lock)

    def set_mode(
        self, mode: SupervisorMode, *, actor: str = "owner"
    ) -> SupervisorEvent:
        with self._lock:
            self.mode = mode
            ev = SupervisorEvent(
                event_id=str(uuid4()),
                at=datetime.now(UTC),
                mode=mode,
                action="set_mode",
                detail=f"actor={actor}",
                applied=True,
                reject_reason=None,
            )
            self._audit.append(ev)
            return ev

    def evaluate_action(
        self,
        *,
        action: str,
        detail: str = "",
        owner_approved: bool = False,
        increases_risk: bool = False,
        enables_live: bool = False,
        disables_safety: bool = False,
    ) -> SupervisorEvent:
        """Decide whether an action may apply under current mode."""
        with self._lock:
            mode = self.mode
            applied = False
            reject: str | None = None

            if enables_live:
                reject = "cannot_enable_live"
            elif increases_risk:
                reject = "cannot_increase_risk"
            elif disables_safety:
                reject = "cannot_disable_safety"
            elif mode == SupervisorMode.MONITOR_ONLY:
                reject = "monitor_only_no_mutate"
            elif mode == SupervisorMode.RECOMMENDATION:
                reject = "recommendation_mode_no_mutate"
            elif mode == SupervisorMode.APPROVAL_REQUIRED:
                if not owner_approved:
                    reject = "owner_approval_required"
                elif action not in _ALLOWED_AUTO_ACTIONS:
                    reject = "action_not_in_allowlist"
                else:
                    applied = True
            elif mode == SupervisorMode.APPROVED_AUTOMATION:
                if action not in _ALLOWED_AUTO_ACTIONS:
                    reject = "action_not_in_allowlist"
                else:
                    # Automation may only tighten/pause — never raise risk (gated above)
                    applied = True
            else:
                reject = "unknown_mode"

            ev = SupervisorEvent(
                event_id=str(uuid4()),
                at=datetime.now(UTC),
                mode=mode,
                action=action,
                detail=detail,
                applied=applied,
                reject_reason=reject,
            )
            self._audit.append(ev)
            return ev

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "mode": self.mode.value,
                "default_mode": SupervisorMode.MONITOR_ONLY.value,
                "allowed_auto_actions": sorted(_ALLOWED_AUTO_ACTIONS),
                "audit_tail": [
                    {
                        "event_id": e.event_id,
                        "at": e.at.isoformat(),
                        "mode": e.mode.value,
                        "action": e.action,
                        "detail": e.detail,
                        "applied": e.applied,
                        "reject_reason": e.reject_reason,
                    }
                    for e in self._audit[-50:]
                ],
            }


_SUPERVISOR = SupervisorState()


def get_supervisor() -> SupervisorState:
    return _SUPERVISOR
