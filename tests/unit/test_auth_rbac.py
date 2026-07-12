"""Unit tests for auth RBAC dependency helpers."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.dto.auth import AuthUserDTO
from app.domain.enums.user import UserRole
from app.domain.exceptions.auth import AuthorizationError
from app.presentation.dependencies.auth import require_roles


@pytest.mark.unit
class TestRequireRoles:
    @pytest.mark.asyncio
    async def test_allows_matching_role(self) -> None:
        dep = require_roles(UserRole.ADMIN, UserRole.OWNER)
        user = AuthUserDTO(
            id=uuid4(),
            email="admin@quantforg.com",
            display_name="Admin",
            role=UserRole.ADMIN.value,
            status="active",
            auth_user_id=uuid4(),
        )
        result = await dep(user=user)
        assert result is user

    @pytest.mark.asyncio
    async def test_rejects_mismatched_role(self) -> None:
        dep = require_roles(UserRole.ADMIN)
        user = AuthUserDTO(
            id=uuid4(),
            email="trader@quantforg.com",
            display_name="Trader",
            role=UserRole.TRADER.value,
            status="active",
            auth_user_id=uuid4(),
        )
        with pytest.raises(AuthorizationError):
            await dep(user=user)
