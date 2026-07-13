"""Trade lifecycle states for Execution Intelligence (analytics only)."""

from __future__ import annotations

from enum import StrEnum


class LifecycleState(StrEnum):
    DRAFT = "Draft"
    VALIDATED = "Validated"
    RISK_APPROVED = "Risk Approved"
    SUBMITTED = "Submitted"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"
    FILLED = "Filled"
    PARTIALLY_FILLED = "Partially Filled"
    MODIFIED = "Modified"
    CANCELLED = "Cancelled"
    CLOSED = "Closed"


# Allowed forward transitions (deterministic). Archive keeps history separately.
ALLOWED_TRANSITIONS: dict[LifecycleState, frozenset[LifecycleState]] = {
    LifecycleState.DRAFT: frozenset(
        {
            LifecycleState.VALIDATED,
            LifecycleState.REJECTED,
            LifecycleState.CANCELLED,
        }
    ),
    LifecycleState.VALIDATED: frozenset(
        {
            LifecycleState.RISK_APPROVED,
            LifecycleState.REJECTED,
            LifecycleState.CANCELLED,
            LifecycleState.SUBMITTED,
        }
    ),
    LifecycleState.RISK_APPROVED: frozenset(
        {
            LifecycleState.SUBMITTED,
            LifecycleState.REJECTED,
            LifecycleState.CANCELLED,
        }
    ),
    LifecycleState.SUBMITTED: frozenset(
        {
            LifecycleState.ACCEPTED,
            LifecycleState.REJECTED,
            LifecycleState.FILLED,
            LifecycleState.PARTIALLY_FILLED,
            LifecycleState.CANCELLED,
        }
    ),
    LifecycleState.ACCEPTED: frozenset(
        {
            LifecycleState.FILLED,
            LifecycleState.PARTIALLY_FILLED,
            LifecycleState.MODIFIED,
            LifecycleState.CANCELLED,
            LifecycleState.CLOSED,
        }
    ),
    LifecycleState.PARTIALLY_FILLED: frozenset(
        {
            LifecycleState.FILLED,
            LifecycleState.MODIFIED,
            LifecycleState.CANCELLED,
            LifecycleState.CLOSED,
        }
    ),
    LifecycleState.FILLED: frozenset({LifecycleState.CLOSED, LifecycleState.MODIFIED}),
    LifecycleState.MODIFIED: frozenset(
        {
            LifecycleState.ACCEPTED,
            LifecycleState.SUBMITTED,
            LifecycleState.CANCELLED,
            LifecycleState.FILLED,
            LifecycleState.CLOSED,
        }
    ),
    LifecycleState.REJECTED: frozenset(),
    LifecycleState.CANCELLED: frozenset(),
    LifecycleState.CLOSED: frozenset(),
}
