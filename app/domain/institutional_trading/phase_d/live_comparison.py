"""Post-canary / live A-B comparison states."""

from __future__ import annotations

from typing import Any, Sequence

from app.domain.institutional_trading.phase_d.champion_candidate import (
    compare_champion_candidate,
)


def live_ab_state(
    *,
    champion_r: Sequence[float],
    candidate_r: Sequence[float],
    min_sample: int = 20,
) -> dict[str, Any]:
    cmp = compare_champion_candidate(
        champion_r=champion_r,
        candidate_r=candidate_r,
        min_sample=min_sample,
    )
    if cmp.get("state") == "INSUFFICIENT_SAMPLE":
        return {**cmp, "live_state": "INSUFFICIENT_SAMPLE"}
    state = cmp.get("state")
    if state == "CANDIDATE_AHEAD_NEEDS_REVIEW":
        live_state = "BETTER"
    elif state == "CHAMPION_AHEAD":
        live_state = "WORSE"
    else:
        live_state = "ALIGNED"
    return {**cmp, "live_state": live_state, "declared_superior": False}
