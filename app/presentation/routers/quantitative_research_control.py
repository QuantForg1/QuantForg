"""Phase 8 — Quantitative Research Control API.

Prefix: /quantitative-research-control
Research-only. Never order_send. Never auto LIVE deploy.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.application.services import quantitative_research_control as qrc
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(
    prefix="/quantitative-research-control",
    tags=["quantitative-research-control"],
)


class ProjectBody(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    hypothesis: str = ""
    instruments: list[str] = Field(default_factory=list)
    timeframe: str | None = None


class ExperimentBody(BaseModel):
    project_id: str | None = None
    strategy_id: str | None = None
    strategy_version: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class ApprovalBody(BaseModel):
    strategy_id: str = Field(min_length=1, max_length=128)
    strategy_version: str = Field(min_length=1, max_length=64)
    bound_params: dict[str, Any] = Field(default_factory=dict)
    stage: str = "Human Approval"


class ApprovalActionBody(BaseModel):
    action: str = Field(min_length=1, max_length=64)
    note: str = ""
    current_params: dict[str, Any] | None = None


@router.get("/health")
async def health(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return qrc.health()


@router.get("/summary")
async def summary(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return qrc.summary()


@router.get("/projects")
async def list_projects(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return qrc.list_projects()


@router.post("/projects")
async def create_project(body: ProjectBody, user: CurrentUser) -> dict[str, Any]:
    actor = str(getattr(user, "email", None) or getattr(user, "id", "") or "user")
    return qrc.create_project(
        name=body.name,
        hypothesis=body.hypothesis,
        instruments=body.instruments,
        timeframe=body.timeframe,
        actor=actor,
    )


@router.get("/projects/{project_id}")
async def get_project(project_id: str, user: CurrentUser) -> dict[str, Any]:
    _ = user
    row = qrc.get_project(project_id)
    if row is None:
        raise HTTPException(status_code=404, detail="project_not_found")
    return row


@router.get("/experiments")
async def list_experiments(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return qrc.list_experiments()


@router.post("/experiments")
async def create_experiment(body: ExperimentBody, user: CurrentUser) -> dict[str, Any]:
    actor = str(getattr(user, "email", None) or getattr(user, "id", "") or "user")
    return qrc.create_experiment(
        project_id=body.project_id,
        strategy_id=body.strategy_id,
        strategy_version=body.strategy_version,
        config=body.config,
        actor=actor,
    )


@router.get("/strategy/spec/templates")
async def templates(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return qrc.get_templates()


@router.post("/strategy/spec/validate")
async def validate_spec(body: dict[str, Any], user: CurrentUser) -> dict[str, Any]:
    _ = user
    return qrc.validate_spec(body if isinstance(body, dict) else {})


@router.post("/strategy/ai/hypothesize")
async def hypothesize(body: dict[str, Any], user: CurrentUser) -> dict[str, Any]:
    _ = user
    return qrc.hypothesize(body if isinstance(body, dict) else {})


@router.get("/data/overview")
async def data_overview(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return qrc.get_data_overview()


@router.get("/backtests/overview")
async def backtests_overview(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return qrc.get_backtests_overview()


@router.post("/backtests/run")
async def backtests_run(body: dict[str, Any], user: CurrentUser) -> dict[str, Any]:
    payload = dict(body) if isinstance(body, dict) else {}
    payload["actor"] = str(
        getattr(user, "email", None) or getattr(user, "id", "") or "user"
    )
    return qrc.run_backtest(payload)


@router.get("/walkforward/overview")
async def walkforward_overview(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return qrc.get_walkforward_overview()


@router.post("/walkforward/run")
async def walkforward_run(body: dict[str, Any], user: CurrentUser) -> dict[str, Any]:
    _ = user
    return qrc.run_walkforward(body if isinstance(body, dict) else {})


@router.get("/montecarlo/overview")
async def montecarlo_overview(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return qrc.get_montecarlo_overview()


@router.post("/montecarlo/run")
async def montecarlo_run(body: dict[str, Any], user: CurrentUser) -> dict[str, Any]:
    _ = user
    return qrc.run_montecarlo(body if isinstance(body, dict) else {})


@router.get("/robustness/overview")
async def robustness_overview(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return qrc.get_robustness()


@router.get("/optimization/overview")
async def optimization_overview(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return qrc.get_optimization()


@router.post("/optimization/run")
async def optimization_run(body: dict[str, Any], user: CurrentUser) -> dict[str, Any]:
    _ = user
    return qrc.run_optimization(body if isinstance(body, dict) else {})


@router.get("/leaderboard")
async def leaderboard(user: CurrentUser) -> dict[str, Any]:
    _ = user
    rows: list[dict[str, Any]] = []
    try:
        import importlib

        irl = importlib.import_module(
            "app.application.services.institutional_research_lab"
        )
        for name in ("build_leaderboard", "leaderboard", "build_dashboard"):
            fn = getattr(irl, name, None)
            if callable(fn):
                pack = fn()
                if isinstance(pack, dict):
                    cand = (
                        pack.get("rows")
                        or pack.get("strategies")
                        or pack.get("leaderboard")
                        or []
                    )
                    if isinstance(cand, list):
                        rows = [r for r in cand if isinstance(r, dict)]
                    break
    except Exception:
        rows = []
    return qrc.get_leaderboard(rows=rows)


@router.get("/validation/pipeline")
async def validation_pipeline(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return qrc.get_validation_pipeline()


@router.get("/validation/approvals")
async def list_approvals(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return qrc.list_approvals()


@router.post("/validation/approvals")
async def create_approval(body: ApprovalBody, user: CurrentUser) -> dict[str, Any]:
    actor = str(getattr(user, "email", None) or getattr(user, "id", "") or "user")
    return qrc.create_approval(
        strategy_id=body.strategy_id,
        strategy_version=body.strategy_version,
        bound_params=body.bound_params,
        stage=body.stage,
        actor=actor,
    )


@router.post("/validation/approvals/{approval_id}/action")
async def approval_action(
    approval_id: str,
    body: ApprovalActionBody,
    user: CurrentUser,
) -> dict[str, Any]:
    actor = str(getattr(user, "email", None) or getattr(user, "id", "") or "user")
    out = qrc.approval_action(
        approval_id,
        action=body.action,
        actor=actor,
        note=body.note,
        current_params=body.current_params,
    )
    if out is None:
        raise HTTPException(status_code=404, detail="approval_not_found")
    if out.get("ok") is False:
        raise HTTPException(status_code=400, detail=out)
    return out


@router.get("/paper/overview")
async def paper_overview(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return qrc.get_paper()


@router.get("/governance/audit")
async def governance_audit(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return qrc.audit_log()
