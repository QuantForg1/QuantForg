"""Market expansion scorecard — research labels, never auto-promotion."""

from __future__ import annotations

from typing import Any

from app.domain.market_universe.constants import UNKNOWN
from app.domain.market_universe.honesty import sample_status
from app.domain.market_universe.promotion import (
    capability_state,
    promotion_gate,
    research_board_status,
)


def instrument_scorecard(
    item: dict[str, Any],
    *,
    scored: dict[str, Any] | None = None,
    shadow_n: int = 0,
    matched_n: int = 0,
) -> dict[str, Any]:
    """Map discovery → readiness. Never jumps to LIVE_ELIGIBLE."""
    state = str(
        (item.get("data_quality") or {}).get("state")
        or item.get("data_availability")
        or "UNKNOWN"
    )
    has_score = bool(
        scored
        and scored.get("opportunity_score") not in (None, "", UNKNOWN)
    )
    opp = (scored or {}).get("opportunity_score")
    edge = (scored or {}).get("directional_edge")
    status = research_board_status(
        data_state=state,
        opportunity=opp if isinstance(opp, int) else None,
        edge=edge if isinstance(edge, int) else None,
        direction=str((scored or {}).get("direction") or ""),
        has_score=has_score,
        shadow_n=shadow_n,
    )
    research = sample_status(int(shadow_n or matched_n or 0))
    if (
        status == "SHADOW"
        and int(shadow_n) >= 20
        and research
        in {
            "MEANINGFUL_RESEARCH",
            "STRONGER_EVIDENCE",
            "HIGHER_CONFIDENCE",
        }
    ):
        status = "MEANINGFUL_RESEARCH"
    gate = promotion_gate(
        research_status=status,
        n=int(shadow_n or matched_n or 0),
    )
    return {
        "MARKET_READINESS": status,
        "DATA_QUALITY": state,
        "ANALYSIS_QUALITY": "READY" if has_score else "NOT_SCORED",
        "OPPORTUNITY_QUALITY": (scored or {}).get("opportunity_score", UNKNOWN),
        "DIRECTIONAL_QUALITY": (scored or {}).get("directional_edge", UNKNOWN),
        "SHADOW_PERFORMANCE": (
            sample_status(shadow_n) if shadow_n else "INSUFFICIENT_SAMPLE"
        ),
        "OOS_PERFORMANCE": UNKNOWN,
        "EXECUTION_READINESS": "BLOCKED_GOLD_ONLY_LIVE_CONTRACT",
        "RISK_READINESS": "UNCHANGED_LIVE_RISK",
        "PROMOTION_STATUS": gate.get("PROMOTION_STATUS"),
        "ALLOW_LIVE_PROMOTION": False,
        "authorizes_trade": False,
        "never_auto_live": True,
        "LIVE_ELIGIBLE": False,
        "CAPABILITY_STATE": capability_state(status),
        "CAPABILITY_LIVE_DISABLED": True,
        "DISCOVERY_TO_OMS": False,
        "SHADOW_TO_OMS": False,
        "RESEARCH_TO_LIVE": False,
    }
