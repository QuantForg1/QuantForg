"""IRL models — research-only; never applied to production engines."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ExperimentStatus(StrEnum):
    DRAFT = "Draft"
    QUEUED = "Queued"
    RUNNING = "Running"
    COMPLETED = "Completed"
    ARCHIVED = "Archived"


class ReplayWindow(StrEnum):
    D30 = "30d"
    D90 = "90d"
    D180 = "180d"
    D365 = "365d"
    CUSTOM = "custom"


class ResearchVerdict(StrEnum):
    RESEARCH_PASSED = "Research Passed"
    RESEARCH_FAILED = "Research Failed"
    PENDING = "Pending"


CANDIDATE_PARAM_KEYS: tuple[str, ...] = (
    "candidate_mtf_model",
    "candidate_quality_formula",
    "candidate_confluence_formula",
    "candidate_regime_filter",
    "candidate_atr_rules",
    "candidate_spread_rules",
    "candidate_time_filters",
    "candidate_session_filters",
    "candidate_position_scoring",
    "candidate_entry_ranking",
    "candidate_exit_ranking",
)


def empty_candidate_params() -> dict[str, Any]:
    return {k: None for k in CANDIDATE_PARAM_KEYS}


def sanitize_candidate_params(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Accept only research candidate keys — never production config keys."""
    base = empty_candidate_params()
    if not isinstance(raw, dict):
        return base
    for key in CANDIDATE_PARAM_KEYS:
        if key in raw:
            base[key] = raw[key]
    return base
