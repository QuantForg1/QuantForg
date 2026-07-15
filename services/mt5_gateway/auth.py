"""Gateway token authentication — not Supabase user auth."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from services.mt5_gateway.settings import get_gateway_settings
from services.mt5_gateway.token_util import (
    mask_gateway_token,
    normalize_gateway_token,
    parse_authorization_bearer,
    tokens_equal,
)

logger = logging.getLogger("quantforg.mt5_gateway.auth")

_bearer = HTTPBearer(auto_error=False)


def _extract_token(
    *,
    authorization: str | None,
    credentials: HTTPAuthorizationCredentials | None,
    x_gateway_token: str | None,
) -> tuple[str, str]:
    """Return ``(token, source)`` preferring Authorization Bearer.

    Sources (first win):
    1. Raw ``Authorization`` header (manual Bearer parse)
    2. FastAPI ``HTTPBearer`` credentials
    3. ``X-Gateway-Token`` header
    """
    from_header = parse_authorization_bearer(authorization)
    if from_header:
        return from_header, "authorization_bearer"

    if credentials is not None and credentials.scheme.lower() == "bearer":
        token = normalize_gateway_token(credentials.credentials)
        if token:
            return token, "http_bearer"

    x_tok = normalize_gateway_token(x_gateway_token)
    if x_tok:
        return x_tok, "x_gateway_token"

    return "", "missing"


def require_gateway_token(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer)
    ],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    x_gateway_token: Annotated[
        str | None, Header(alias="X-Gateway-Token")
    ] = None,
) -> str:
    """Validate shared gateway token. Broker passwords are never involved."""
    cfg = get_gateway_settings()
    expected = normalize_gateway_token(cfg.mt5_gateway_token)
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "MT5_GATEWAY_TOKEN is not configured on this Windows host. "
                "Set a strong token in the gateway .env "
                "(see deploy/mt5_gateway/gateway.env.example), then restart. "
                "Never store broker credentials in Railway."
            ),
        )

    provided, source = _extract_token(
        authorization=authorization,
        credentials=credentials,
        x_gateway_token=x_gateway_token,
    )
    equal = tokens_equal(provided, expected)

    # Temporary / ops-safe auth diagnostics (never log full secrets).
    logger.info(
        "gateway_auth_check loaded=%s expected_len=%s expected=%s "
        "authorization_present=%s x_gateway_token_present=%s "
        "source=%s received_len=%s received=%s equal=%s",
        bool(expected),
        len(expected),
        mask_gateway_token(expected),
        bool((authorization or "").strip()),
        bool((x_gateway_token or "").strip()),
        source,
        len(provided),
        mask_gateway_token(provided),
        equal,
    )

    if not equal:
        logger.warning(
            "gateway_auth_rejected expected=%s received=%s source=%s "
            "expected_len=%s received_len=%s",
            mask_gateway_token(expected),
            mask_gateway_token(provided),
            source,
            len(expected),
            len(provided),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing gateway token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return provided
