"""Human-gated promotion wall. Research never becomes live automatically."""

from __future__ import annotations

from typing import Any

from app.domain.market_universe.constants import (
    ALLOW_LIVE_PROMOTION,
    FROZEN_DIRECTIONAL_EDGE,
    FROZEN_OPPORTUNITY_THRESHOLD,
    PROMOTION_CHAIN,
    PROMOTION_N_EARLY,
    PROMOTION_N_REVIEW,
    PROMOTION_N_STRONG,
)

CAPABILITY_CHAIN: tuple[str, ...] = (
    "DISCOVERED",
    "DATA_READY",
    "ANALYZABLE",
    "RESEARCH_SIGNAL",
    "SHADOW_ELIGIBLE",
    "SHADOW_VALIDATED",
    "PROMOTION_CANDIDATE",
    "LIVE_ELIGIBLE",
)


def research_board_status(
    *,
    data_state: str,
    opportunity: Any = None,
    edge: Any = None,
    direction: str = "",
    has_score: bool = False,
    shadow_n: int = 0,
) -> str:
    """Map facts onto the research ladder. Never returns LIVE_ELIGIBLE."""
    state = str(data_state or "UNKNOWN").upper()
    if state != "LIVE":
        return "DISCOVERED"
    status = "DATA_READY"
    if has_score:
        status = "ANALYZED"
    opp_ok = (
        isinstance(opportunity, int)
        and opportunity >= FROZEN_OPPORTUNITY_THRESHOLD
    )
    edge_ok = isinstance(edge, int) and edge >= FROZEN_DIRECTIONAL_EDGE
    side = str(direction or "").upper()
    if status == "ANALYZED" and opp_ok and edge_ok and side in {"BUY", "SELL"}:
        status = "QUALIFIED"
    if shadow_n > 0 and status in {"ANALYZED", "QUALIFIED", "DATA_READY"}:
        status = "SHADOW"
    return status


def promotion_gate(
    *,
    research_status: str,
    human_authorized: bool = False,
    risk_reviewed: bool = False,
    safety_reviewed: bool = False,
    oos_positive: bool = False,
    lookahead: bool = False,
    n: int = 0,
) -> dict[str, Any]:
    """LIVE_ELIGIBLE is unreachable without explicit human authorization.

    Even then this module never calls OMS. A future authorized phase would
    still have to pass existing Risk / Safety / OMS / MT5.
    """
    blocked = {
        "DISCOVERY_TO_OMS": False,
        "SHADOW_TO_OMS": False,
        "RESEARCH_TO_LIVE": False,
        "LIVE_ELIGIBLE": False,
        "authorizes_trade": False,
        "ALLOW_LIVE_PROMOTION": False,
        "chain": list(PROMOTION_CHAIN),
        "capability_chain": list(CAPABILITY_CHAIN),
        "requires_human_authorization": True,
        "PROMOTION_STATUS": "HUMAN_REVIEW_REQUIRED"
        if research_status
        in {"QUALIFIED", "SHADOW", "MEANINGFUL_RESEARCH", "PROMOTION_CANDIDATE"}
        else research_status,
    }
    if lookahead or n < 20 or not oos_positive:
        blocked["PROMOTION_STATUS"] = (
            "INSUFFICIENT_SAMPLE" if n < 20 else blocked["PROMOTION_STATUS"]
        )
        blocked["blocker"] = (
            "LOOKAHEAD"
            if lookahead
            else "INSUFFICIENT_SAMPLE"
            if n < 20
            else "OOS_NOT_POSITIVE"
        )
        return blocked
    if not (human_authorized and risk_reviewed and safety_reviewed):
        blocked["blocker"] = "HUMAN_RISK_SAFETY_REVIEW_REQUIRED"
        return blocked
    if ALLOW_LIVE_PROMOTION:
        blocked["blocker"] = "ALLOW_LIVE_PROMOTION_MUST_STAY_FALSE"
        return blocked
    blocked["blocker"] = "LIVE_PROMOTION_NOT_ACTIVATED"
    blocked["note"] = (
        "Architecture can receive a future human-authorized candidate. "
        "This phase does not enable live expansion."
    )
    return blocked


def research_sample_gate(n: int) -> dict[str, Any]:
    """Matched-sample confidence. Never grants LIVE_ELIGIBLE."""
    count = max(0, int(n or 0))
    if count < PROMOTION_N_EARLY:
        status = "INSUFFICIENT_SAMPLE"
    elif count < PROMOTION_N_REVIEW:
        status = "EARLY_QUALIFICATION"
    elif count < PROMOTION_N_STRONG:
        status = "PROMOTION_REVIEW"
    else:
        status = "STRONGER_EVIDENCE"
    return {
        "n": count,
        "status": status,
        "automatic_promotion": False,
        "LIVE_ELIGIBLE": False,
        "authorizes_trade": False,
        "ALLOW_LIVE_PROMOTION": False,
        "thresholds": {
            "early": PROMOTION_N_EARLY,
            "review": PROMOTION_N_REVIEW,
            "stronger": PROMOTION_N_STRONG,
        },
        "note": "Research gates only. Human authorization still required.",
    }


def capability_state(board_status: str) -> str:
    """Research capability ladder. LIVE_ELIGIBLE is never returned."""
    mapping = {
        "DISCOVERED": "DISCOVERED",
        "DATA_READY": "DATA_READY",
        "ANALYZED": "ANALYZABLE",
        "QUALIFIED": "RESEARCH_SIGNAL",
        "SHADOW": "SHADOW_ELIGIBLE",
        "MEANINGFUL_RESEARCH": "SHADOW_VALIDATED",
        "PROMOTION_CANDIDATE": "PROMOTION_CANDIDATE",
        "LIVE_ELIGIBLE": "PROMOTION_CANDIDATE",
    }
    mapped = mapping.get(str(board_status or "").upper(), "DISCOVERED")
    if mapped == "LIVE_ELIGIBLE":
        return "PROMOTION_CANDIDATE"
    return mapped
