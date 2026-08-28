"""Explainable research ranking. Not a second scoring engine.

Uses existing Opportunity / edge / RR / spread / data-state fields.
Missing measurements are omitted — never invented as 0.
Unrankable data states stay out of the live board.
"""

from __future__ import annotations

from typing import Any

from app.domain.market_universe.constants import UNKNOWN

UNRANKABLE_STATES = frozenset(
    {
        "NO_DATA",
        "STALE",
        "MARKET_CLOSED",
        "DISABLED",
        "UNSUPPORTED",
        "ERROR",
        "INSUFFICIENT_HISTORY",
    }
)


def _as_int(value: Any) -> int | None:
    if value in (None, "", UNKNOWN):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    if value in (None, "", UNKNOWN):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compute_research_rank(row: dict[str, Any]) -> dict[str, Any]:
    """Composite research rank from measured fields only.

    quality = existing Opportunity score (authoritative contract)
    + directional_edge when measured
    + RR when measured (capped)
    - spread_penalty when measured
    Data penalty is applied only for known non-LIVE freshness, never for UNKNOWN.
    """
    state = str(row.get("data_state") or "").upper()
    opp = _as_int(row.get("opportunity_score"))
    components: dict[str, Any] = {
        "quality": UNKNOWN,
        "directional_edge": UNKNOWN,
        "rr": UNKNOWN,
        "spread_penalty": UNKNOWN,
        "data_penalty": UNKNOWN,
        "formula": (
            "quality + directional_edge + min(RR,5) - min(spread,20) "
            "- data_penalty(known non-LIVE only)"
        ),
    }
    if state in UNRANKABLE_STATES or opp is None:
        return {
            "research_rank_score": UNKNOWN,
            "research_rank_components": {
                **components,
                "reason": "unrankable_or_opportunity_unknown_not_zero",
            },
            "rankable": False,
        }
    score = float(opp)
    components["quality"] = opp
    edge = _as_int(row.get("directional_edge"))
    if edge is not None:
        components["directional_edge"] = edge
        score += float(edge)
    rr = _as_float(row.get("RR") or row.get("rr"))
    if rr is not None:
        rr_term = min(max(rr, 0.0), 5.0)
        components["rr"] = rr
        score += rr_term
    spread = _as_float(row.get("spread"))
    if spread is not None and spread >= 0:
        penalty = min(spread, 20.0)
        components["spread_penalty"] = penalty
        score -= penalty
    freshness = str(row.get("data_freshness") or "").upper()
    if freshness in {"STALE", "OLD"}:
        components["data_penalty"] = 5
        score -= 5
    elif freshness in {"LIVE", "FRESH", "OK"}:
        components["data_penalty"] = 0
    return {
        "research_rank_score": round(score, 4),
        "research_rank_components": components,
        "rankable": True,
        "does_not_change_live_opportunity_70": True,
    }
