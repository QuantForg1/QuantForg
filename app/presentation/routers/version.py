"""Version endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.application.services.version_service import VersionService
from app.presentation.dependencies.services import get_version_service
from app.presentation.schemas.version import VersionResponse

router = APIRouter(tags=["Version"])


@router.get(
    "/version",
    response_model=VersionResponse,
    summary="Application version",
    description="Returns application name, semantic version, and environment.",
)
async def get_version(
    service: VersionService = Depends(get_version_service),
) -> VersionResponse:
    """Return build and runtime identity metadata."""
    info = service.get_version()
    return VersionResponse(
        name=info.name,
        version=info.version,
        environment=info.environment,
        api_prefix=info.api_prefix,
    )
