"""Phase 4.1 — ordinary customer denied Owner control plane (isolated).

Live Production ordinary-customer session remains BLOCKED without credentials.
These tests exercise the same ``require_roles(UserRole.OWNER)`` gate used by
``/admin/control`` without touching Production.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.dto.auth import AuthUserDTO
from app.domain.enums.user import UserRole
from app.domain.exceptions.auth import AuthorizationError
from app.domain.identity.designated_owner import DESIGNATED_OWNER_EMAIL
from app.presentation.dependencies.auth import require_roles
from app.presentation.routers import admin_control as admin_control_router

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _user(role: str, email: str = "customer@example.com") -> AuthUserDTO:
    return AuthUserDTO(
        id=uuid4(),
        email=email,
        display_name="Customer",
        role=role,
        status="active",
        auth_user_id=uuid4(),
    )


@pytest.mark.asyncio
async def test_ordinary_trader_denied_owner_control_dependency() -> None:
    dep = require_roles(UserRole.OWNER)
    with pytest.raises(AuthorizationError) as err:
        await dep(user=_user(UserRole.TRADER.value, "trader@example.com"))
    assert err.value.code == "insufficient_role"


@pytest.mark.asyncio
async def test_admin_non_owner_denied_owner_only_control() -> None:
    """``/admin/control`` is OWNER-only — ADMIN is not enough."""
    dep = require_roles(UserRole.OWNER)
    with pytest.raises(AuthorizationError):
        await dep(user=_user(UserRole.ADMIN.value, "admin@example.com"))


@pytest.mark.asyncio
async def test_designated_owner_allowed_owner_control_dependency() -> None:
    dep = require_roles(UserRole.OWNER)
    result = await dep(user=_user(UserRole.OWNER.value, DESIGNATED_OWNER_EMAIL))
    assert result.role == UserRole.OWNER.value


def test_admin_control_router_is_owner_only() -> None:
    from pathlib import Path

    src = Path(admin_control_router.__file__ or "")
    text = src.read_text(encoding="utf-8")
    assert "require_roles(UserRole.OWNER)" in text
    assert "OwnerUser" in text
