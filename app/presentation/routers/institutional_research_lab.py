"""Institutional Research Lab API — completely isolated from production trading.

Prefix: /irl
Never order_send. Never writes production tables. Never auto-promotes.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/irl", tags=["institutional-research-lab"])


class ExperimentCreateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str = Field(default="", max_length=2000)
    author: str = Field(default="researcher", max_length=128)
    candidate_params: dict[str, Any] = Field(default_factory=dict)


class ExperimentUpdateBody(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None, max_length=2000)
    candidate_params: dict[str, Any] | None = None
    status: str | None = None


class ReplayBody(BaseModel):
    window: str = Field(default="90d", max_length=16)
    custom_start: str | None = None
    custom_end: str | None = None
    bars: list[dict[str, Any]] | None = None
    use_live_portfolio_baseline: bool = False


class NoteBody(BaseModel):
    body: str = Field(..., min_length=1, max_length=4000)
    author: str = Field(default="researcher", max_length=128)


class VerdictBody(BaseModel):
    verdict: str = Field(..., max_length=64)


def _flags() -> dict[str, Any]:
    return {
        "advisory_only": True,
        "mutates_engines": False,
        "executes_live_trades": False,
        "writes_production_tables": False,
        "influences_production_decisions": False,
        "never_auto_promotes": True,
        "never_modifies_strategy_risk_safety_oms_execution_auto_trading_thresholds": True,
    }


@router.get("/dashboard")
def irl_dashboard(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.institutional_research_lab import build_irl_dashboard

    payload = build_irl_dashboard()
    payload.update(_flags())
    return payload


@router.get("/experiments")
def irl_experiments(
    _user: CurrentUser,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    from app.application.services.institutional_research_lab import irl_list_experiments

    payload = irl_list_experiments(limit=limit)
    payload.update(_flags())
    return payload


@router.post("/experiments")
def irl_create_experiment(
    body: ExperimentCreateBody,
    user: CurrentUser,
) -> dict[str, Any]:
    from app.application.services.institutional_research_lab import irl_create_experiment as create

    author = body.author or getattr(user, "email", None) or "researcher"
    exp = create(
        name=body.name,
        description=body.description,
        author=str(author)[:128],
        candidate_params=body.candidate_params,
    )
    return {"experiment": exp, **_flags()}


@router.get("/experiments/{experiment_id}")
def irl_get_experiment(experiment_id: str, _user: CurrentUser) -> dict[str, Any]:
    from app.application.services.institutional_research_lab import irl_get_experiment as get_exp

    exp = get_exp(experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="experiment_not_found")
    return {"experiment": exp, **_flags()}


@router.patch("/experiments/{experiment_id}")
def irl_patch_experiment(
    experiment_id: str,
    body: ExperimentUpdateBody,
    _user: CurrentUser,
) -> dict[str, Any]:
    from app.application.services.institutional_research_lab import irl_update_experiment

    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    exp = irl_update_experiment(experiment_id, updates)
    if not exp:
        raise HTTPException(status_code=404, detail="experiment_not_found")
    return {"experiment": exp, **_flags()}


@router.post("/experiments/{experiment_id}/replay")
def irl_replay(
    experiment_id: str,
    body: ReplayBody,
    user: CurrentUser,
) -> dict[str, Any]:
    from app.application.services.institutional_research_lab import irl_run_replay

    try:
        result = irl_run_replay(
            experiment_id=experiment_id,
            window=body.window,
            custom_start=body.custom_start,
            custom_end=body.custom_end,
            bars=body.bars,
            author=str(getattr(user, "email", None) or "researcher")[:128],
            use_live_portfolio_baseline=body.use_live_portfolio_baseline,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="experiment_not_found") from None
    result.update(_flags())
    return result


@router.get("/jobs")
def irl_jobs(
    _user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
    experiment_id: str | None = None,
) -> dict[str, Any]:
    from app.application.services.institutional_research_lab import irl_list_jobs

    payload = irl_list_jobs(limit=limit, experiment_id=experiment_id)
    payload.update(_flags())
    return payload


@router.get("/leaderboard")
def irl_leaderboard(
    _user: CurrentUser,
    rank_by: str = Query(default="composite"),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    from app.application.services.institutional_research_lab import irl_leaderboard as board

    payload = board(rank_by=rank_by, limit=limit)
    payload.update(_flags())
    return payload


@router.get("/reports")
def irl_reports(
    _user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    from app.application.services.institutional_research_lab import irl_list_reports

    payload = irl_list_reports(limit=limit)
    payload.update(_flags())
    return payload


@router.get("/benchmark")
def irl_benchmark(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.institutional_research_lab import irl_benchmark_view

    payload = irl_benchmark_view()
    payload.update(_flags())
    return payload


@router.post("/experiments/{experiment_id}/notes")
def irl_notes(
    experiment_id: str,
    body: NoteBody,
    user: CurrentUser,
) -> dict[str, Any]:
    from app.application.services.institutional_research_lab import irl_add_note

    try:
        note = irl_add_note(
            experiment_id,
            author=body.author or str(getattr(user, "email", None) or "researcher"),
            body=body.body,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="experiment_not_found") from None
    return {"note": note, **_flags()}


@router.post("/experiments/{experiment_id}/archive")
def irl_archive_exp(experiment_id: str, _user: CurrentUser) -> dict[str, Any]:
    from app.application.services.institutional_research_lab import irl_archive

    exp = irl_archive(experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="experiment_not_found")
    return {"experiment": exp, **_flags()}


@router.post("/experiments/{experiment_id}/verdict")
def irl_verdict(
    experiment_id: str,
    body: VerdictBody,
    _user: CurrentUser,
) -> dict[str, Any]:
    from app.application.services.institutional_research_lab import irl_set_verdict

    try:
        exp = irl_set_verdict(experiment_id, body.verdict)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid_verdict") from None
    if not exp:
        raise HTTPException(status_code=404, detail="experiment_not_found")
    return {
        "experiment": exp,
        "note": "Research verdict only — governance workflow required for any promotion",
        **_flags(),
    }
