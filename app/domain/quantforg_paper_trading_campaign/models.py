"""QPTCM models — Paper Trading Campaign Manager (governed, never live)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

ISOLATION_FLAGS: dict[str, Any] = {
    "mutates_production": False,
    "places_live_trades": False,
    "executes_trades": False,
    "modifies_production": False,
    "allocates_capital": False,
    "approves_graduation_automatically": False,
    "human_approval_required_for_transitions": True,
    "human_approval_required_for_graduation": True,
    "preserves_existing_safety_guarantees": True,
    "paper_trading_only": True,
    "writes_production_tables": False,
}


class CampaignLifecycle(StrEnum):
    DRAFT = "Draft"
    CONFIGURED = "Configured"
    RUNNING = "Running"
    PAUSED = "Paused"
    COMPLETED = "Completed"
    REVIEWED = "Reviewed"
    GRADUATION_CANDIDATE = "Graduation Candidate"


CAMPAIGN_LIFECYCLE: tuple[str, ...] = tuple(s.value for s in CampaignLifecycle)
LIFECYCLE_ORDER: tuple[str, ...] = CAMPAIGN_LIFECYCLE

DATA_SOURCES: tuple[str, ...] = (
    "qsf",
    "islm",
    "qcs",
    "qdie",
    "qsmr",
    "irap",
    "eqs",
    "res",
    "cvf",
    "qem",
    "qcdm",
)

REPORT_KINDS: tuple[str, ...] = (
    "daily_campaign_report",
    "weekly_campaign_report",
    "final_evaluation",
    "graduation_report",
    "lessons_learned",
)
