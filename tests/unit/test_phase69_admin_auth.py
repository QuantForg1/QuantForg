"""Phase 69 — admin authorization (server-side require_roles)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from app.application.dto.auth import AuthUserDTO
from app.domain.enums.user import UserRole
from app.domain.exceptions.auth import AuthorizationError
from app.presentation.dependencies.auth import require_roles

ROOT = Path(__file__).resolve().parents[2]


def _user(role: str, email: str = "user@example.com") -> AuthUserDTO:
    return AuthUserDTO(
        id=uuid4(),
        email=email,
        display_name="Test",
        role=role,
        status="active",
        auth_user_id=uuid4(),
    )


@pytest.mark.unit
@pytest.mark.trading_core
@pytest.mark.asyncio
async def test_admin_api_allows_admin() -> None:
    dep = require_roles(UserRole.OWNER, UserRole.ADMIN)
    result = await dep(user=_user(UserRole.ADMIN.value, "admin@example.com"))
    assert result.role == UserRole.ADMIN.value


@pytest.mark.unit
@pytest.mark.trading_core
@pytest.mark.asyncio
async def test_admin_api_allows_owner() -> None:
    dep = require_roles(UserRole.OWNER, UserRole.ADMIN)
    result = await dep(user=_user(UserRole.OWNER.value))
    assert result.role == UserRole.OWNER.value


@pytest.mark.unit
@pytest.mark.trading_core
@pytest.mark.asyncio
async def test_admin_api_rejects_trader() -> None:
    dep = require_roles(UserRole.OWNER, UserRole.ADMIN)
    with pytest.raises(AuthorizationError) as err:
        await dep(user=_user(UserRole.TRADER.value, "trader@example.com"))
    assert err.value.code == "insufficient_role"


@pytest.mark.unit
@pytest.mark.trading_core
@pytest.mark.asyncio
async def test_admin_api_rejects_empty_role() -> None:
    dep = require_roles(UserRole.OWNER, UserRole.ADMIN)
    with pytest.raises(AuthorizationError) as err:
        await dep(user=_user(""))
    assert err.value.code == "insufficient_role"


@pytest.mark.unit
@pytest.mark.trading_core
def test_provision_script_secure() -> None:
    script = ROOT / "scripts" / "provision_admin_user.py"
    text = script.read_text(encoding="utf-8")
    assert "ADMIN_EMAIL" in text
    assert "ADMIN_PASSWORD" in text
    assert "getenv" in text or "environ" in text
    assert "infojimvio@gmail.com" not in text
    assert 'password = "' not in text
    assert "password='" not in text
