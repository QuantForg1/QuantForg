"""Champion vs Candidate comparison — risk-adjusted, not raw-return chasing."""

from __future__ import annotations

from typing import Any, Sequence

from app.domain.institutional_trading.phase_c.fair_comparison import (
    compare_champion_challenger,
)


def compare_champion_candidate(
    *,
    champion_r: Sequence[float],
    candidate_r: Sequence[float],
    min_sample: int = 20,
    champion_mae: Sequence[float] | None = None,
    candidate_mae: Sequence[float] | None = None,
    champion_mfe: Sequence[float] | None = None,
    candidate_mfe: Sequence[float] | None = None,
    champion_slippage: Sequence[float] | None = None,
    candidate_slippage: Sequence[float] | None = None,
) -> dict[str, Any]:
    base = compare_champion_challenger(
        champion_r=champion_r,
        challenger_r=candidate_r,
        min_sample=min_sample,
        champion_mae=champion_mae,
        challenger_mae=candidate_mae,
        champion_mfe=champion_mfe,
        challenger_mfe=candidate_mfe,
    )
    # Rename challenger → candidate for Phase D language
    out = {
        "champion": base.get("champion"),
        "candidate": base.get("challenger"),
        "verdict": base.get("verdict"),
        "auto_promote": False,
        "raw_return_alone_insufficient": True,
    }
    if base.get("verdict") == "INSUFFICIENT_SAMPLE":
        out["state"] = "INSUFFICIENT_SAMPLE"
        return out

    ch = base.get("champion") or {}
    cd = base.get("candidate") or base.get("challenger") or {}
    # Prefer risk-adjusted: expectancy up AND drawdown/tail not worse
    de = (cd.get("expectancy") or 0) - (ch.get("expectancy") or 0)
    dd = (cd.get("max_drawdown") or 0) - (ch.get("max_drawdown") or 0)
    tl = (cd.get("tail_loss") or 0) - (ch.get("tail_loss") or 0)
    slip_ok = True
    if champion_slippage and candidate_slippage and len(champion_slippage) and len(
        candidate_slippage
    ):
        slip_ok = (sum(candidate_slippage) / len(candidate_slippage)) <= (
            sum(champion_slippage) / len(champion_slippage)
        ) * 1.25

    if de > 0 and dd <= 0 and tl >= 0 and slip_ok:
        out["state"] = "CANDIDATE_AHEAD_NEEDS_REVIEW"
    elif de < 0 or dd > 0:
        out["state"] = "CHAMPION_AHEAD"
    else:
        out["state"] = "MIXED_NEEDS_REVIEW"
    out["slippage_ok"] = slip_ok
    out["material_advantage"] = out["state"] == "CANDIDATE_AHEAD_NEEDS_REVIEW"
    return out
