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


class ExecutionAuditStage(StrEnum):
    """Immutable execution-pipeline stage recorded by the Audit Engine."""

    VALIDATION = "validation"
    RISK = "risk"
    SAFETY = "safety"
    SUBMIT = "submit"
    MANAGE = "manage"
    CANCEL = "cancel"
    HISTORY = "history"
    REPLAY = "replay"
