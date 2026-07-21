"""Opportunity Discovery + Ranking — supplied candidates only."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.domain.trading_brain_v3.config import TradingBrainConfig
from app.domain.trading_brain_v3.types import BrainInput, ModuleResult


def discover_opportunities(
    inp: BrainInput, config: TradingBrainConfig
) -> ModuleResult:
    cands = inp.opportunity_candidates
    if cands is None:
        return ModuleResult(
            module="opportunity_discovery",
            status="unavailable",
            score=None,
            passed=None,
            recommendation="No Trade",
            reasons=(
                "No opportunity candidates supplied — never invents setups",
            ),
            details={"count": 0},
        )
    if len(cands) == 0:
        return ModuleResult(
            module="opportunity_discovery",
            status="empty",
            score=Decimal("0"),
            passed=False,
            recommendation="No Trade",
            reasons=("Empty opportunity list — recommend No Trade",),
            details={"count": 0},
        )

    scored: list[dict[str, Any]] = []
    for i, raw in enumerate(cands):
        if not isinstance(raw, dict):
            continue
        label = str(raw.get("label") or raw.get("id") or f"opp_{i}")
        try:
            s = Decimal(str(raw.get("score"))) if raw.get("score") is not None else None
        except Exception:
            s = None
        if s is None:
            scored.append(
                {
                    "id": label,
                    "score": None,
                    "status": "unavailable",
                    "reason": "Candidate missing score — not invented",
                }
            )
            continue
        scored.append(
            {
                "id": label,
                "score": str(s),
                "status": "available",
                "meets_min": s >= config.min_opportunity_score,
            }
        )

    available = [c for c in scored if c.get("status") == "available"]
    if not available:
        return ModuleResult(
            module="opportunity_discovery",
            status="unavailable",
            score=None,
            passed=False,
            recommendation="No Trade",
            reasons=("Candidates present but unscored — No Trade",),
            details={"candidates": scored, "count": len(scored)},
        )

    best = max(Decimal(str(c["score"])) for c in available)
    passed = best >= config.min_opportunity_score
    return ModuleResult(
        module="opportunity_discovery",
        status="available",
        score=best,
        passed=passed,
        recommendation="Proceed" if passed else "No Trade",
        reasons=(
            f"Discovered {len(available)} scored candidates (supplied)",
            f"Best score {best} vs min {config.min_opportunity_score}",
            "Never invents opportunities",
        ),
        details={"candidates": scored, "count": len(available)},
    )


def rank_opportunities(
    discovery: ModuleResult, config: TradingBrainConfig
) -> ModuleResult:
    if discovery.status in {"unavailable", "empty"}:
        return ModuleResult(
            module="opportunity_ranking",
            status=discovery.status,
            score=discovery.score,
            passed=False,
            recommendation="No Trade",
            reasons=("Ranking skipped — no discoverable opportunities",),
            details={},
        )

    cands = list(discovery.details.get("candidates") or [])
    ranked = sorted(
        [c for c in cands if c.get("status") == "available" and c.get("score")],
        key=lambda c: Decimal(str(c["score"])),
        reverse=True,
    )
    if not ranked:
        return ModuleResult(
            module="opportunity_ranking",
            status="unavailable",
            score=None,
            passed=False,
            recommendation="No Trade",
            reasons=("No rankable scored candidates",),
            details={"ranked": []},
        )

    top = ranked[0]
    top_score = Decimal(str(top["score"]))
    passed = top_score >= config.min_rank_score
    return ModuleResult(
        module="opportunity_ranking",
        status="available",
        score=top_score,
        passed=passed,
        recommendation="Proceed" if passed else "No Trade",
        reasons=(
            f"Top ranked {top.get('id')} at {top_score}",
            f"Min rank score {config.min_rank_score}",
            "Ranking uses supplied scores only",
        ),
        details={
            "ranked": ranked[:10],
            "top_id": top.get("id"),
            "min_rank_score": str(config.min_rank_score),
        },
    )
