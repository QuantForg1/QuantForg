"""Gateway token authentication — not Supabase user auth."""

from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from services.mt5_gateway.settings import get_gateway_settings

_bearer = HTTPBearer(auto_error=False)


def _extract_token(
    credentials: HTTPAuthorizationCredentials | None,
    x_gateway_token: str | None,
) -> str:
    if credentials is not None and credentials.scheme.lower() == "bearer":
        return credentials.credentials.strip()
    if x_gateway_token:
        return x_gateway_token.strip()
    return ""


def require_gateway_token(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer)
    ] = None,
    x_gateway_token: Annotated[
        str | None, Header(alias="X-Gateway-Token")
    ] = None,
) -> str:
    """Validate shared gateway token. Broker passwords are never involved."""
    cfg = get_gateway_settings()
    expected = (cfg.mt5_gateway_token or "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "MT5_GATEWAY_TOKEN is not configured on this Windows host. "
                "Set a strong token locally — never store broker credentials "
                "in Railway."
            ),
        )
    provided = _extract_token(credentials, x_gateway_token)
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing gateway token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return provided
