"""Isolated MT5 worker lifecycle state machine (Phase 1B).

READY / CONNECTED is only allowed after AUTHENTICATING → VERIFYING succeed.
A registry row alone never implies a live terminal.
"""

from __future__ import annotations

from enum import StrEnum

from app.domain.exceptions.base import ValidationError


class WorkerLifecycleState(StrEnum):
    PENDING = "pending"
    PROVISIONING = "provisioning"
    STARTING = "starting"
    AUTHENTICATING = "authenticating"
    VERIFYING = "verifying"
    READY = "ready"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    RECONNECTING = "reconnecting"
    STOPPING = "stopping"
    STOPPED = "stopped"
    REVOKED = "revoked"


# Allowed transitions. Missing edges are rejected (fail closed).
_ALLOWED: dict[WorkerLifecycleState, frozenset[WorkerLifecycleState]] = {
    WorkerLifecycleState.PENDING: frozenset(
        {
            WorkerLifecycleState.PROVISIONING,
            WorkerLifecycleState.REVOKED,
            WorkerLifecycleState.STOPPED,
        }
    ),
    WorkerLifecycleState.PROVISIONING: frozenset(
        {
            WorkerLifecycleState.STARTING,
            WorkerLifecycleState.ERROR,
            WorkerLifecycleState.STOPPING,
            WorkerLifecycleState.REVOKED,
        }
    ),
    WorkerLifecycleState.STARTING: frozenset(
        {
            WorkerLifecycleState.AUTHENTICATING,
            WorkerLifecycleState.ERROR,
            WorkerLifecycleState.STOPPING,
            WorkerLifecycleState.REVOKED,
        }
    ),
    WorkerLifecycleState.AUTHENTICATING: frozenset(
        {
            WorkerLifecycleState.VERIFYING,
            WorkerLifecycleState.ERROR,
            WorkerLifecycleState.STOPPING,
            WorkerLifecycleState.REVOKED,
        }
    ),
    WorkerLifecycleState.VERIFYING: frozenset(
        {
            WorkerLifecycleState.READY,
            WorkerLifecycleState.ERROR,
            WorkerLifecycleState.STOPPING,
            WorkerLifecycleState.REVOKED,
        }
    ),
    WorkerLifecycleState.READY: frozenset(
        {
            WorkerLifecycleState.DISCONNECTED,
            WorkerLifecycleState.ERROR,
            WorkerLifecycleState.STOPPING,
            WorkerLifecycleState.REVOKED,
        }
    ),
    WorkerLifecycleState.DISCONNECTED: frozenset(
        {
            WorkerLifecycleState.RECONNECTING,
            WorkerLifecycleState.STOPPING,
            WorkerLifecycleState.ERROR,
            WorkerLifecycleState.REVOKED,
        }
    ),
    WorkerLifecycleState.ERROR: frozenset(
        {
            WorkerLifecycleState.RECONNECTING,
            WorkerLifecycleState.STOPPING,
            WorkerLifecycleState.REVOKED,
            WorkerLifecycleState.STOPPED,
        }
    ),
    WorkerLifecycleState.RECONNECTING: frozenset(
        {
            WorkerLifecycleState.AUTHENTICATING,
            WorkerLifecycleState.ERROR,
            WorkerLifecycleState.STOPPING,
            WorkerLifecycleState.REVOKED,
        }
    ),
    WorkerLifecycleState.STOPPING: frozenset(
        {
            WorkerLifecycleState.STOPPED,
            WorkerLifecycleState.REVOKED,
            WorkerLifecycleState.ERROR,
        }
    ),
    WorkerLifecycleState.STOPPED: frozenset(
        {
            WorkerLifecycleState.PROVISIONING,
            WorkerLifecycleState.REVOKED,
        }
    ),
    WorkerLifecycleState.REVOKED: frozenset(),
}


def can_transition(current: WorkerLifecycleState, target: WorkerLifecycleState) -> bool:
    if current is target:
        return True
    return target in _ALLOWED.get(current, frozenset())


def transition(
    current: WorkerLifecycleState, target: WorkerLifecycleState
) -> WorkerLifecycleState:
    if current is target:
        return current
    if not can_transition(current, target):
        raise ValidationError(
            "Illegal worker lifecycle transition",
            details={"from": current.value, "to": target.value},
        )
    return target


def is_terminal(state: WorkerLifecycleState) -> bool:
    return state is WorkerLifecycleState.REVOKED


def is_session_ready(state: WorkerLifecycleState) -> bool:
    """True only when the worker has completed auth + verification."""
    return state is WorkerLifecycleState.READY


CONNECTED_ALIASES = frozenset({"connected", "ready"})


def assert_not_connected_until_ready(state: WorkerLifecycleState, label: str) -> None:
    """UI/API must not advertise Connected unless lifecycle is READY."""
    if label.strip().lower() in CONNECTED_ALIASES and not is_session_ready(state):
        raise ValidationError(
            "Cannot report Connected before READY after MT5 auth+verify",
            details={"lifecycle": state.value, "label": label},
        )
