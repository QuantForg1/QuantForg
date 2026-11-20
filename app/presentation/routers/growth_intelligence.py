"""Owner-only growth status and owner-invoked checks.

Checks do not place orders, change billing, publish, send email, or enable ads.
They are not registered on the trading scheduler. The emergency stop starts
engaged. Releasing it only allows a check or an unpublished draft.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.application.dto.auth import AuthUserDTO
from app.application.services.growth_automation import (
    UnknownGrowthJob,
    refuse_growth_publish,
    run_growth_job,
    save_growth_draft,
    set_growth_emergency_stop,
)
from app.application.services.growth_intelligence import growth_intelligence_status
from app.domain.enums.user import UserRole
from app.presentation.dependencies.auth import require_roles

router = APIRouter(
    prefix="/growth",
    tags=["growth-intelligence"],
    dependencies=[Depends(require_roles(UserRole.OWNER))],
)


class EmergencyStopBody(BaseModel):
    engaged: bool


class RunJobBody(BaseModel):
    job_id: str = Field(min_length=1, max_length=64)


class DraftBody(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=4000)


class PublishBody(BaseModel):
    draft_id: str = Field(min_length=1, max_length=64)


@router.get("/status")
def growth_status(
    _owner: Annotated[AuthUserDTO, Depends(require_roles(UserRole.OWNER))],
) -> dict[str, Any]:
    return growth_intelligence_status()


@router.post("/automation/emergency-stop")
def growth_emergency_stop(
    body: EmergencyStopBody,
    _owner: Annotated[AuthUserDTO, Depends(require_roles(UserRole.OWNER))],
) -> dict[str, Any]:
    return set_growth_emergency_stop(body.engaged)


@router.post("/automation/run")
def growth_run(
    body: RunJobBody,
    _owner: Annotated[AuthUserDTO, Depends(require_roles(UserRole.OWNER))],
) -> dict[str, Any]:
    try:
        return run_growth_job(body.job_id)
    except UnknownGrowthJob as exc:
        raise HTTPException(status_code=422, detail="Unknown growth job") from exc


@router.post("/content/drafts")
def growth_draft(
    body: DraftBody,
    _owner: Annotated[AuthUserDTO, Depends(require_roles(UserRole.OWNER))],
) -> dict[str, Any]:
    try:
        return save_growth_draft(body.title, body.body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Draft was empty or too long") from exc


@router.post("/content/publish")
def growth_publish(
    body: PublishBody,
    _owner: Annotated[AuthUserDTO, Depends(require_roles(UserRole.OWNER))],
) -> dict[str, Any]:
    return refuse_growth_publish(body.draft_id)
