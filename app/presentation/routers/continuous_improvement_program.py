"""Institutional Live Validation & Continuous Improvement API.

Additive observe-only. Never modifies trading, AI, OMS, MT5, execution,
adaptive intelligence, COP, Enterprise rules, auth, or pricing.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Query

from app.application.dto.auth import AuthUserDTO
from app.domain.continuous_improvement.continuous_validation import (
    build_continuous_validation,
    list_validation_history,
)
from app.domain.continuous_improvement.historical_trends import (
    build_historical_trends,
)
from app.domain.continuous_improvement.learning_review import build_learning_review
from app.domain.continuous_improvement.platform import (
    build_continuous_improvement_noc_panels,
    build_continuous_improvement_program,
)
from app.domain.continuous_improvement.release_confidence import (
    build_release_confidence,
    record_deployment,
    record_rollback,
)
from app.domain.continuous_improvement.trading_effectiveness import (
    build_trading_effectiveness,
)
from app.domain.enums.user import UserRole
from app.presentation.dependencies.auth import require_roles

router = APIRouter(
    prefix="/continuous-improvement",
    tags=["continuous-improvement"],
)

OperatorUser = Annotated[
    AuthUserDTO,
    Depends(require_roles(UserRole.OWNER, UserRole.ADMIN)),
]


@router.get("/program")
async def program(_user: OperatorUser) -> dict[str, Any]:
    return await build_continuous_improvement_program()


@router.get("/validation")
async def validation(_user: OperatorUser) -> dict[str, Any]:
    return build_continuous_validation(record_history=True)


@router.get("/validation/history")
async def validation_history(
    _user: OperatorUser,
    limit: int = Query(default=100, ge=1, le=2000),
) -> dict[str, Any]:
    rows = list_validation_history(limit=limit)
    return {"history": rows, "count": len(rows), "fabricated": False}


@router.get("/trading-effectiveness")
async def trading_effectiveness(_user: OperatorUser) -> dict[str, Any]:
    return build_trading_effectiveness()


@router.get("/learning-review")
async def learning_review(_user: OperatorUser) -> dict[str, Any]:
    return build_learning_review()


@router.get("/release-confidence")
async def release_confidence(_user: OperatorUser) -> dict[str, Any]:
    val = build_continuous_validation(record_history=False)
    return build_release_confidence(validation=val)


@router.post("/release-confidence/deployments")
async def add_deployment(
    _user: OperatorUser,
    body: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    row = record_deployment(
        platform=str(body.get("platform") or "unknown"),
        deployment_id=str(body.get("deployment_id") or ""),
        commit_sha=str(body.get("commit_sha") or ""),
        status=str(body.get("status") or "SUCCESS"),
        note=str(body.get("note") or ""),
    )
    return {"ok": True, "deployment": row}


@router.post("/release-confidence/rollbacks")
async def add_rollback(
    _user: OperatorUser,
    body: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    row = record_rollback(
        platform=str(body.get("platform") or "unknown"),
        from_deployment=str(body.get("from_deployment") or ""),
        to_deployment=str(body.get("to_deployment") or ""),
        reason=str(body.get("reason") or ""),
    )
    return {"ok": True, "rollback": row}


@router.get("/scorecard")
async def scorecard(_user: OperatorUser) -> dict[str, Any]:
    pack = await build_continuous_improvement_program()
    return pack.get("operational_scorecard") or {}


@router.get("/trends")
async def trends(_user: OperatorUser) -> dict[str, Any]:
    val = build_continuous_validation(record_history=False)
    trade = build_trading_effectiveness()
    return build_historical_trends(validation=val, trading=trade)


@router.get("/reports")
async def reports(_user: OperatorUser) -> dict[str, Any]:
    pack = await build_continuous_improvement_program()
    return pack.get("auto_reports") or {}


@router.get("/noc-panels")
async def noc_panels(_user: OperatorUser) -> dict[str, Any]:
    return await build_continuous_improvement_noc_panels()
