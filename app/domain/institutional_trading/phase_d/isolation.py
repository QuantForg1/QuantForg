"""Candidate execution isolation — DENY OMS / Gateway / MT5 until LIVE deploy."""

from __future__ import annotations

FORBIDDEN_CANDIDATE_CALLS = frozenset(
    {
        "OMS",
        "ExecutionBridge",
        "Gateway",
        "MT5",
        "order_send",
        "submit_market",
    }
)


class CandidateExecutionForbidden(RuntimeError):
    """Raised if any candidate path attempts live execution."""


def forbid_candidate_execution(target: str) -> None:
    if str(target) in FORBIDDEN_CANDIDATE_CALLS:
        raise CandidateExecutionForbidden(f"Candidate must not call {target}")


def assert_candidate_cannot_execute(*, may_execute: bool = False) -> None:
    if may_execute:
        raise CandidateExecutionForbidden("candidate_may_execute must be False")
