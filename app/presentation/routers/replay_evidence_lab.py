"""Institutional Replay & Evidence Lab API — advisory; never mixes lanes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Query

from app.application.services.replay_evidence_lab import run_replay_evidence_lab
from app.domain.replay_evidence_lab.counterfactual import (
    analyze_no_trade_counterfactuals,
)
from app.domain.replay_evidence_lab.evidence_store import get_evidence_database
from app.domain.replay_evidence_lab.gates import (
    evaluate_evidence_gates,
    merge_thresholds,
)
from app.domain.replay_evidence_lab.models import EVIDENCE_LANES
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(
    prefix="/replay-evidence-lab",
    tags=["replay-evidence-lab"],
)


def _pack_from_store(thresholds: dict[str, Any] | None = None) -> dict[str, Any]:
    db = get_evidence_database()
    research = db.list("research")
    return run_replay_evidence_lab(
        opportunities=db.list("replay"),
        live_closed_trades=db.list("live"),
        demo_records=db.list("demo"),
        research_records=[
            r for r in research if r.get("kind") != "no_trade_counterfactual"
        ],
        thresholds=thresholds,
        use_process_store=False,
    )


@router.get("/dashboard")
async def replay_evidence_dashboard(_user: CurrentUser) -> dict[str, Any]:
    """Lab overview from process evidence store (empty until ingest)."""
    pack = _pack_from_store()
    pack["process_store"] = get_evidence_database().inventory()
    return pack


@router.post("/replay")
async def run_lab_replay(
    _user: CurrentUser,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    """Replay supplied XAUUSD bars + opportunities into the Replay lane."""
    bars = payload.get("bars") if isinstance(payload.get("bars"), list) else []
    opps = (
        payload.get("opportunities")
        if isinstance(payload.get("opportunities"), list)
        else []
    )
    thresholds = payload.get("thresholds")
    live = payload.get("live") if isinstance(payload.get("live"), list) else []
    demo = payload.get("demo") if isinstance(payload.get("demo"), list) else []
    research = (
        payload.get("research") if isinstance(payload.get("research"), list) else []
    )
    return run_replay_evidence_lab(
        bars=bars,
        opportunities=opps,
        live_closed_trades=live,
        demo_records=demo,
        research_records=research,
        thresholds=thresholds if isinstance(thresholds, dict) else None,
        use_process_store=True,
    )


@router.get("/evidence/{lane}")
async def evidence_lane(
    lane: str,
    _user: CurrentUser,
    limit: int = Query(default=200, ge=1, le=2000),
) -> dict[str, Any]:
    """Read a single evidence lane — never merges datasets."""
    if lane not in EVIDENCE_LANES:
        return {
            "status": "unavailable",
            "reason": f"Unknown lane '{lane}' — allowed: {list(EVIDENCE_LANES)}",
            "never_mix_evidence_lanes": True,
        }
    typed = lane  # narrowed by membership check
    rows = get_evidence_database().list(typed)  # type: ignore[arg-type]
    return {
        "status": "available",
        "lane": lane,
        "count": len(rows),
        "items": rows[:limit],
        "never_mix_evidence_lanes": True,
    }


@router.get("/counterfactual")
async def counterfactual_summary(_user: CurrentUser) -> dict[str, Any]:
    opps = get_evidence_database().list("replay")
    return analyze_no_trade_counterfactuals(opps)


@router.get("/confidence")
async def confidence_summary(_user: CurrentUser) -> dict[str, Any]:
    pack = _pack_from_store()
    return pack.get("confidence") or {"status": "unavailable"}


@router.get("/gates")
async def evidence_gates(
    _user: CurrentUser,
    min_live_closed_trades: int | None = Query(default=None),
    min_replay_opportunities: int | None = Query(default=None),
    min_no_trade_observations: int | None = Query(default=None),
) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    if min_live_closed_trades is not None:
        overrides["min_live_closed_trades"] = min_live_closed_trades
    if min_replay_opportunities is not None:
        overrides["min_replay_opportunities"] = min_replay_opportunities
    if min_no_trade_observations is not None:
        overrides["min_no_trade_observations"] = min_no_trade_observations
    th = merge_thresholds(overrides or None)
    db = get_evidence_database()
    lanes = db.counts()
    research = db.list("research")
    no_trade_obs = sum(
        1
        for r in research
        if r.get("kind") == "no_trade_counterfactual"
        or str(r.get("decision") or "").upper() == "NO_TRADE"
    )
    return evaluate_evidence_gates(
        live_closed_trades=lanes.get("live", 0),
        replay_opportunities=lanes.get("replay", 0),
        no_trade_observations=no_trade_obs,
        thresholds=th,
    )


@router.get("/reports")
async def lab_reports(_user: CurrentUser) -> dict[str, Any]:
    pack = _pack_from_store()
    return {
        "status": "available",
        "reports": pack.get("reports"),
        "recommendations": pack.get("recommendations"),
        "hard_locks": pack.get("hard_locks"),
    }
