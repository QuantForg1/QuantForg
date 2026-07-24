"""Institutional Research Platform v10 — config."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ResearchPlatformConfig:
    version: str = "research-platform-v10.0.0"

    # Hard locks
    auto_promote_to_production: bool = False
    auto_apply_optimizations: bool = False
    research_isolated_from_live: bool = True

    max_experiments: int = 500
    max_optimization_runs: int = 1_000
    max_models: int = 200
    max_audit_events: int = 10_000
    max_reports: int = 365
    max_promotions: int = 500

    # Guidance: collect live evidence before promotion
    min_recommended_live_days: int = 14
    recommended_live_days: int = 28

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "auto_promote_to_production": False,
            "auto_apply_optimizations": False,
            "research_isolated_from_live": True,
            "min_recommended_live_days": self.min_recommended_live_days,
            "recommended_live_days": self.recommended_live_days,
            "note": (
                "Research never modifies live trading automatically. "
                "Prefer demo/low-risk live for 2–4 weeks before promotions."
            ),
        }


DEFAULT_RESEARCH_CONFIG = ResearchPlatformConfig()

EXPERIMENT_STATUSES = ("Draft", "Running", "Completed", "Archived")
PROMOTION_STAGES = (
    "Development",
    "Research",
    "Paper Trading",
    "Demo",
    "Limited Live",
    "Production",
)
MODEL_APPROVAL = ("pending", "approved", "rejected", "archived")
