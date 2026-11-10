"""Phase 7 — multi-account dispatch observability APIs (read-only)."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends

from app.application.dto.auth import AuthUserDTO
from app.application.services.multi_account_ops_service import (
    customer_dispatch_status,
    owner_ops_snapshot,
)
from app.domain.enums.user import UserRole
from app.domain.exceptions.auth import AuthorizationError
from app.domain.identity.designated_owner import is_designated_owner_email
from app.presentation.dependencies.auth import CurrentUser, require_roles

router = APIRouter(prefix="/multi-account", tags=["multi-account-ops"])

OwnerUser = Annotated[AuthUserDTO, Depends(require_roles(UserRole.OWNER))]


@router.get("/dispatch/status")
async def my_dispatch_status(user: CurrentUser) -> dict[str, Any]:
    return customer_dispatch_status(user_id=UUID(str(user.id)))


@router.get("/ops/summary")
async def owner_multi_account_ops(user: OwnerUser) -> dict[str, Any]:
    if not is_designated_owner_email(getattr(user, "email", "")):
        raise AuthorizationError(
            "Designated owner required",
            code="designated_owner_required",
        )
    worker_summary: dict[str, Any] = {}
    try:
        from datetime import timedelta

        from app.application.services.mt5_worker_api import Mt5WorkerApiFacade
        from app.application.services.mt5_worker_control_plane import (
            Mt5WorkerControlPlane,
        )
        from core.config.settings import get_settings

        settings = get_settings()
        token = ""
        secret = getattr(settings, "worker_service_token", None)
        if secret is not None:
            token = secret.get_secret_value().strip()
        plane = Mt5WorkerControlPlane(service_token=token or "unconfigured")
        facade = Mt5WorkerApiFacade(
            plane=plane,
            stale_after=timedelta(
                seconds=int(getattr(settings, "worker_heartbeat_stale_seconds", 90))
            ),
        )
        worker_summary = {
            "worker_count": facade.ops_summary().get("worker_count"),
            "credentials_exposed": False,
        }
    except Exception:
        worker_summary = {"worker_count": None, "unavailable": True}
    return owner_ops_snapshot(worker_summary=worker_summary)
