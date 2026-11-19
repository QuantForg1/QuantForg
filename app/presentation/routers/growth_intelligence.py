"""Owner-only, read-only growth status. No writes, no trading calls."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.application.dto.auth import AuthUserDTO
from app.application.services.growth_intelligence import growth_intelligence_status
from app.domain.enums.user import UserRole
from app.presentation.dependencies.auth import require_roles

router = APIRouter(
    prefix="/growth",
    tags=["growth-intelligence"],
    dependencies=[Depends(require_roles(UserRole.OWNER))],
)


@router.get("/status")
def growth_status(
    _owner: Annotated[AuthUserDTO, Depends(require_roles(UserRole.OWNER))],
) -> dict[str, Any]:
    return growth_intelligence_status()
