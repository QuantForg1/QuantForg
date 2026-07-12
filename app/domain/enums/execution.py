"""Execution decision and gateway outcome enumerations."""

from __future__ import annotations

from enum import StrEnum


class ExecutionDecision(StrEnum):
    """Final gate outcome before any broker submission.

    ALLOW / REJECT / RETRY only — never EXECUTE.
    """

    ALLOW = "allow"
    REJECT = "reject"
    RETRY = "retry"


class ExecutionOutcome(StrEnum):
    """Result of an Execution Gateway attempt (infrastructure layer)."""

    SUCCESS = "success"
    FAILED = "failed"
    DISABLED = "disabled"
    RETRY = "retry"
    CANCELLED = "cancelled"
    PREPARED = "prepared"
