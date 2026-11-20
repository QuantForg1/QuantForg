"""Phase 7 routes stay hidden while their flags are off."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.application.dto.auth import AuthUserDTO
from core.config.settings import Settings

pytestmark = pytest.mark.unit


def test_flags_default_off() -> None:
    assert Settings.model_fields["referral_enabled"].default is False
    assert Settings.model_fields["community_enabled"].default is False


@pytest.mark.asyncio
async def test_routes_do_not_touch_storage_while_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.presentation.routers import (
        community as community_router,
        referrals as referral_router,
    )

    def _boom() -> None:
        raise AssertionError("storage was opened while the flag is off")

    monkeypatch.setattr(referral_router, "_program", _boom)
    monkeypatch.setattr(community_router, "_board", _boom)
    monkeypatch.setattr(
        referral_router,
        "get_settings",
        lambda: SimpleNamespace(referral_enabled=False),
    )
    monkeypatch.setattr(
        community_router,
        "get_settings",
        lambda: SimpleNamespace(community_enabled=False),
    )
    user = AuthUserDTO(
        id=uuid4(),
        email="a@example.invalid",
        display_name="A",
        role="trader",
        status="active",
        auth_user_id=None,
    )
    with pytest.raises(HTTPException) as referral_error:
        await referral_router.referral_summary(user)
    with pytest.raises(HTTPException) as community_error:
        await community_router.list_posts(user)
    assert referral_error.value.status_code == 404
    assert community_error.value.status_code == 404
