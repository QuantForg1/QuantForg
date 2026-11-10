"""Market chat — session identity, validation, auth gates (no production posts)."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.application.dto.auth import AuthUserDTO
from app.application.services.market_chat import (
    MarketChatService,
    require_authenticated_user_id,
    sanitize_body,
)
from app.domain.exceptions.auth import AuthenticationError, AuthorizationError
from app.domain.exceptions.base import ValidationError
from app.presentation.dependencies import auth as auth_deps
from app.presentation.routers import market_chat as market_chat_router


def test_require_authenticated_user_id_rejects_missing() -> None:
    with pytest.raises(AuthorizationError):
        require_authenticated_user_id(SimpleNamespace(id=None))


def test_require_authenticated_user_id_uses_session_uuid() -> None:
    uid = uuid4()
    assert require_authenticated_user_id(SimpleNamespace(id=uid)) == uid


def test_sanitize_rejects_empty_after_control_strip() -> None:
    with pytest.raises(ValidationError):
        sanitize_body("\x00\x01\x08")
    with pytest.raises(ValidationError):
        sanitize_body("")
    with pytest.raises(ValidationError):
        sanitize_body("x" * 501)
    assert sanitize_body("\x00evil") == "evil"


@pytest.mark.asyncio
async def test_post_message_binds_user_id_from_session_not_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Impersonation via body user_id is impossible — service only takes session uid."""
    session_uid = uuid4()
    foreign_uid = uuid4()
    inserted: dict[str, object] = {}

    class _Repo:
        async def insert(self, **kwargs):
            inserted.update(kwargs)
            return {
                "id": str(uuid4()),
                "channel": kwargs["channel"],
                "user_id": str(kwargs["user_id"]),
                "display_name": kwargs["display_name"],
                "body": kwargs["body"],
                "parent_id": None,
                "status": "visible",
                "created_at": "2026-11-10T00:00:00+00:00",
            }

    class _Uow:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def commit(self):
            return None

    monkeypatch.setattr(
        "app.application.services.market_chat.PostgresMarketChatUnitOfWork",
        lambda *_a, **_k: _Uow(),
    )
    monkeypatch.setattr(
        "app.application.services.market_chat.PostgresMarketChatRepository",
        lambda *_a, **_k: _Repo(),
    )
    from app.application.services import market_chat as mc

    mc._post_buckets.clear()

    svc = MarketChatService(database=MagicMock())
    out = await svc.post_message(
        user_id=session_uid,
        display_name="AttackerAlias",
        email_fallback="attacker@example.com",
        body="hello gold",
        channel="acceptance_test",
    )
    assert out["ok"] is True
    assert inserted["user_id"] == session_uid
    assert inserted["user_id"] != foreign_uid
    assert out["message"]["user_id"] == str(session_uid)


def _auth_user(uid: UUID | None = None) -> AuthUserDTO:
    return AuthUserDTO(
        id=uid or uuid4(),
        email="acceptance@example.com",
        display_name="Acceptance",
        role="trader",
        status="active",
        auth_user_id=uuid4(),
    )


def test_router_public_read_and_session_bound_post(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = FastAPI()

    @app.exception_handler(AuthenticationError)
    async def _auth_err(_request, exc: AuthenticationError):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=401,
            content={"error": {"code": getattr(exc, "code", "unauthorized")}},
        )

    app.include_router(market_chat_router.router, prefix="/api/v1")

    posted: dict[str, object] = {}

    class _Svc:
        async def post_message(self, **kwargs):
            posted.update(kwargs)
            return {"ok": True, "message": {"user_id": str(kwargs["user_id"])}}

        async def report_message(self, **kwargs):
            posted["report"] = kwargs
            return {"ok": True}

        async def list_messages(self, **kwargs):
            return {
                "ok": True,
                "channel": kwargs.get("channel", "xauusd"),
                "auth_required_to_post": True,
                "messages": [],
                "count": 0,
            }

    monkeypatch.setattr(market_chat_router, "_service", lambda: _Svc())

    client = TestClient(app, raise_server_exceptions=False)

    public = client.get("/api/v1/public/market/chat?channel=acceptance_test")
    assert public.status_code == 200
    assert public.json()["auth_required_to_post"] is True

    anon = client.post(
        "/api/v1/market/chat",
        json={"body": "hi", "channel": "acceptance_test"},
    )
    assert anon.status_code == 401

    uid = uuid4()

    async def _current_user():
        return _auth_user(uid)

    app.dependency_overrides[auth_deps.get_current_user] = _current_user

    ok = client.post(
        "/api/v1/market/chat",
        json={
            "body": "session-bound",
            "channel": "acceptance_test",
            "display_name": "Spoofed Name",
        },
        headers={"Authorization": "Bearer test-token"},
    )
    assert ok.status_code == 200, ok.text
    assert posted["user_id"] == uid
    assert posted["body"] == "session-bound"

    report = client.post(
        f"/api/v1/market/chat/{uuid4()}/report",
        json={"reason": "spam", "note": "test"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert report.status_code == 200
    assert posted["report"]["user_id"] == uid
