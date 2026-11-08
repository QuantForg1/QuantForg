"""Admin assign-plan must reject invalid user_id with 422, not 500."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.presentation.routers.billing import AdminAssignPlanRequest


def test_admin_assign_plan_request_rejects_non_uuid() -> None:
    with pytest.raises(PydanticValidationError):
        AdminAssignPlanRequest(
            user_id="not-a-uuid",
            plan_id="starter",
            days=1,
            reason="e2e-validation",
        )


def test_admin_assign_plan_request_accepts_uuid() -> None:
    uid = uuid4()
    body = AdminAssignPlanRequest(
        user_id=uid,
        plan_id="starter",
        days=30,
        reason="owner-grant",
    )
    assert body.user_id == uid
