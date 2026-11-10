"""Phase 7 — multi-account dispatch observability APIs (read-only).

Customer: own dispatch status only.
Worker token: aggregate queue metrics (already on /mt5-workers/ops/summary).
Never exposes credentials. LIVE submit remains off.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter

from app.application.services.multi_account_ops_service import (
    customer_dispatch_status,
)
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/multi-account", tags=["multi-account-ops"])


@router.get("/dispatch/status")
async def my_dispatch_status(user: CurrentUser) -> dict[str, Any]:
    """Authenticated customer: own dispatch jobs and recent events only."""
    return customer_dispatch_status(user_id=UUID(str(user.id)))
