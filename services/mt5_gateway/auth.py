"""Gateway token authentication — not Supabase user auth."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
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

# Tunnel/proxy-safe auth headers (Authorization is sometimes stripped).
_TOKEN_HEADER_NAMES = (
    "x-gateway-token",
    "x-quantforg-gateway-token",
)


def _token_candidates(
    *,
    authorization: str | None,
    credentials: HTTPAuthorizationCredentials | None,
    x_gateway_token: str | None,
    x_quantforg_gateway_token: str | None,
    request: Request | None = None,
) -> list[tuple[str, str]]:
    """Collect unique normalized secrets from every supported header.

    Prefer custom gateway headers first: Railway sends them alongside
    Authorization because tunnels/proxies may rewrite Bearer while leaving
    these headers intact.
    """
    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(token: str, source: str) -> None:
        if not token or token in seen:
            return
        seen.add(token)
        candidates.append((token, source))

    add(normalize_gateway_token(x_gateway_token), "x_gateway_token")
    add(
        normalize_gateway_token(x_quantforg_gateway_token),
        "x_quantforg_gateway_token",
    )
    add(parse_authorization_bearer(authorization), "authorization_bearer")

    if credentials is not None and credentials.scheme.lower() == "bearer":
        add(normalize_gateway_token(credentials.credentials), "http_bearer")

    auth_stripped = (authorization or "").lstrip("\ufeff").strip()
    if auth_stripped and not auth_stripped.lower().startswith("bearer"):
        add(normalize_gateway_token(authorization), "authorization_raw")

    # Last resort: read raw ASGI headers. FastAPI Header()/HTTPBearer can miss
    # values when a proxy rewrites casing or duplicates Authorization.
    if request is not None and not candidates:
        headers = request.headers
        for name in _TOKEN_HEADER_NAMES:
            add(normalize_gateway_token(headers.get(name)), f"raw_{name}")
        add(
            parse_authorization_bearer(headers.get("authorization")),
            "raw_authorization_bearer",
        )

    return candidates


def _present_auth_header_names(request: Request | None) -> list[str]:
    if request is None:
        return []
    names: list[str] = []
    for key in request.headers.keys():
        low = key.lower()
        if low in {"authorization", *_TOKEN_HEADER_NAMES}:
            names.append(low)
    return sorted(set(names))


def require_gateway_token(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer)
    ],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    x_gateway_token: Annotated[
        str | None, Header(alias="X-Gateway-Token")
    ] = None,
    x_quantforg_gateway_token: Annotated[
        str | None, Header(alias="X-QuantForg-Gateway-Token")
    ] = None,
) -> str:
    """Validate shared gateway token. Broker passwords are never involved."""
    cfg = get_gateway_settings()
    expected = normalize_gateway_token(cfg.mt5_gateway_token)
    from services.mt5_gateway.settings import token_load_meta

    meta = token_load_meta()
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

    candidates = _token_candidates(
        authorization=authorization,
        credentials=credentials,
        x_gateway_token=x_gateway_token,
        x_quantforg_gateway_token=x_quantforg_gateway_token,
        request=request,
    )

    client = request.client.host if request.client else None
    path = request.url.path
    present = _present_auth_header_names(request)

    for provided, header_source in candidates:
        equal = tokens_equal(provided, expected)
        logger.info(
            "gateway_auth_check token_source=%s expected_len=%s expected=%s "
            "authorization_present=%s header_source=%s received_len=%s "
            "received=%s equal=%s path=%s client=%s present_headers=%s meta=%s",
            getattr(cfg, "token_source", meta.get("source")),
            len(expected),
            mask_gateway_token(expected),
            bool((authorization or "").strip())
            or bool((request.headers.get("authorization") or "").strip()),
            header_source,
            len(provided),
            mask_gateway_token(provided),
            equal,
            path,
            client,
            present,
            meta,
        )
        if cfg.mt5_gateway_auth_debug:
            logger.info(
                "gateway_auth_debug expected_len=%s expected=%s "
                "received_len=%s received=%s header_source=%s",
                len(expected),
                mask_gateway_token(expected),
                len(provided),
                mask_gateway_token(provided),
                header_source,
            )
        if equal:
            return provided

    best = candidates[0] if candidates else ("", "missing")
    provided, header_source = best
    logger.warning(
        "gateway_auth_rejected token_source=%s expected=%s received=%s "
        "expected_len=%s received_len=%s header_source=%s candidates=%s "
        "path=%s client=%s present_headers=%s user_agent=%r "
        "(hint: present_headers=[] means Railway/frontend never sent "
        "Authorization / X-Gateway-Token / X-QuantForg-Gateway-Token — "
        "set MT5_GATEWAY_CALLER_TOKEN on Railway to match Windows "
        "MT5_GATEWAY_TOKEN; len 32 often means example placeholder "
        "'replace-with-strong-random-token' is still loaded from "
        "process_env/NSSM instead of the repo .env)",
        getattr(cfg, "token_source", meta.get("source")),
        mask_gateway_token(expected),
        mask_gateway_token(provided),
        len(expected),
        len(provided),
        header_source,
        [(src, mask_gateway_token(tok), len(tok)) for tok, src in candidates],
        path,
        client,
        present,
        request.headers.get("user-agent"),
    )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing gateway token",
        headers={"WWW-Authenticate": "Bearer"},
    )
