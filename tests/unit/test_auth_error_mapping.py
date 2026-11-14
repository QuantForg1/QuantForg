"""Auth error mapping and public HTTP messages."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.domain.exceptions.auth import AuthenticationError
from app.infrastructure.auth.supabase_auth import _map_auth_error
from app.presentation.middleware.error_handler import register_exception_handlers


class _StubAuthError(Exception):
    def __init__(
        self,
        *,
        message: str = "",
        status: int | None = None,
        error_description: str | None = None,
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.error_description = error_description
        self.code = code


def test_map_rate_limit_phrase() -> None:
    err = _map_auth_error(_StubAuthError(message="Email rate limit exceeded"))
    assert err.code == "auth_rate_limited"


def test_map_status_429() -> None:
    err = _map_auth_error(_StubAuthError(message="Too many", status=429))
    assert err.code == "auth_rate_limited"


def test_map_duplicate_email() -> None:
    err = _map_auth_error(_StubAuthError(message="User already registered"))
    assert err.code == "email_already_registered"
    err2 = _map_auth_error(_StubAuthError(message="error email_exists"))
    assert err2.code == "email_already_registered"


def test_map_signup_disabled() -> None:
    err = _map_auth_error(_StubAuthError(message="Signups not allowed"))
    assert err.code == "signup_disabled"


def test_map_supabase_internal_500() -> None:
    err = _map_auth_error(_StubAuthError(message="Internal Server Error", status=500))
    assert err.code == "auth_provider_error"


def test_map_confirmation_email_send_failure() -> None:
    err = _map_auth_error(
        _StubAuthError(
            message="Error sending confirmation email",
            status=500,
            code="unexpected_failure",
        )
    )
    assert err.code == "auth_email_delivery_failed"


def test_map_confirmation_email_send_failure_422() -> None:
    err = _map_auth_error(
        _StubAuthError(
            message="Error sending confirmation email",
            status=422,
            code="unexpected_failure",
        )
    )
    assert err.code == "auth_email_delivery_failed"


def test_public_messages_via_test_client() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/probe/{code}")
    async def probe(code: str) -> None:
        raise AuthenticationError("internal", code=code)

    client = TestClient(app, raise_server_exceptions=False)

    rate = client.get("/probe/auth_rate_limited")
    assert rate.status_code == 429
    assert rate.headers.get("Retry-After") == "60"
    body = rate.json()["error"]
    assert body["code"] == "auth_rate_limited"
    assert "Google" in body["message"]

    dup = client.get("/probe/email_already_registered")
    assert dup.status_code == 409
    assert dup.json()["error"]["message"] == (
        "An account with this email already exists"
    )

    weak = client.get("/probe/weak_password")
    assert weak.status_code == 400
    assert "security" in weak.json()["error"]["message"].lower()

    disabled = client.get("/probe/signup_disabled")
    assert disabled.status_code == 400

    generic = client.get("/probe/authentication_failed")
    assert generic.status_code == 401
    assert generic.json()["error"]["message"] == "Authentication failed"

    provider = client.get("/probe/auth_provider_error")
    assert provider.status_code == 503
    assert "temporarily unavailable" in provider.json()["error"]["message"].lower()

    email_delivery = client.get("/probe/auth_email_delivery_failed")
    assert email_delivery.status_code == 503
    assert "confirmation email" in email_delivery.json()["error"]["message"].lower()
