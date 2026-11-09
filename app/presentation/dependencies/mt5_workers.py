"""Dependencies for MT5 Windows worker control-plane routes."""

from __future__ import annotations

import hmac
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, Header, Request

from app.application.services.mt5_worker_api import Mt5WorkerApiFacade
from app.application.services.mt5_worker_control_plane import Mt5WorkerControlPlane
from app.domain.exceptions.auth import AuthenticationError
from core.config.settings import Settings, get_settings


def _expected_worker_token(settings: Settings) -> str:
    secret = settings.worker_service_token
    if secret is None:
        return ""
    return secret.get_secret_value().strip()


def require_worker_service_token(
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    """Bearer WORKER_SERVICE_TOKEN — required on every worker control route."""
    expected = _expected_worker_token(settings)
    if len(expected) < 16:
        raise AuthenticationError(
            "WORKER_SERVICE_TOKEN is not configured on the API",
            code="worker_token_not_configured",
        )
    raw = (authorization or "").strip()
    if not raw.lower().startswith("bearer "):
        raise AuthenticationError(
            "Missing bearer token",
            code="worker_auth_required",
        )
    provided = raw[7:].strip()
    if not hmac.compare_digest(provided, expected):
        raise AuthenticationError(
            "Invalid worker service token",
            code="worker_auth_invalid",
        )
    # Never return the secret to handlers — just confirm auth.
    return "authenticated"


def get_mt5_worker_api(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Mt5WorkerApiFacade:
    """Process-durable facade singleton on app.state."""
    existing = getattr(request.app.state, "mt5_worker_api", None)
    if isinstance(existing, Mt5WorkerApiFacade):
        return existing
    token = _expected_worker_token(settings)
    plane = Mt5WorkerControlPlane(service_token=token or "unconfigured-worker-token")
    facade = Mt5WorkerApiFacade(
        plane=plane,
        stale_after=timedelta(seconds=int(settings.worker_heartbeat_stale_seconds)),
    )
    request.app.state.mt5_worker_api = facade
    return facade


WorkerAuth = Annotated[str, Depends(require_worker_service_token)]
WorkerApi = Annotated[Mt5WorkerApiFacade, Depends(get_mt5_worker_api)]
