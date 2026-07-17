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

# TEMPORARY — prove this file was imported (remove after diagnosis).
print(
    f"TEMPORARY_AUTH_IMPORT auth_file={__file__!s}",
    flush=True,
)

# TEMPORARY — remove after auth diagnosis. Do not ship permanently.
_ZERO_WIDTH_CHARS = (
    "\u200b",
    "\u200c",
    "\u200d",
    "\u2060",
    "\ufeff",
)


def _temporary_token_diff_debug(
    *,
    expected: str,
    provided: str,
    header_source: str,
) -> None:
    """TEMPORARY DEBUG: full token repr + first differing codepoint.

    Remove this helper and its call site once the 401 middle-diff is identified.
    """
    py_equal = expected == provided
    diff_index: int | None = None
    expected_cp: str | None = None
    provided_cp: str | None = None
    limit = min(len(expected), len(provided))
    for i in range(limit):
        if expected[i] != provided[i]:
            diff_index = i
            expected_cp = f"U+{ord(expected[i]):04X} ({expected[i]!r})"
            provided_cp = f"U+{ord(provided[i]):04X} ({provided[i]!r})"
            break
    if diff_index is None and len(expected) != len(provided):
        diff_index = limit
        if len(expected) > len(provided):
            expected_cp = f"U+{ord(expected[limit]):04X} ({expected[limit]!r})"
            provided_cp = "<missing>"
        else:
            expected_cp = "<missing>"
            provided_cp = f"U+{ord(provided[limit]):04X} ({provided[limit]!r})"

    def _flags(label: str, value: str) -> str:
        return (
            f"{label}: contains_CR={('\\r' in value)} contains_LF={('\\n' in value)} "
            f"contains_TAB={('\\t' in value)} contains_BOM={('\\ufeff' in value)} "
            f"contains_zero_width={any(z in value for z in _ZERO_WIDTH_CHARS)} "
            f"trailing_whitespace={bool(value) and value[-1].isspace()} "
            f"leading_whitespace={bool(value) and value[0].isspace()} "
            f"len={len(value)} utf8_bytes={len(value.encode('utf-8'))}"
        )

    lines = [
        "TEMPORARY_GATEWAY_TOKEN_DIFF header_source=%s" % header_source,
        "repr(expected)=%r" % expected,
        "repr(provided)=%r" % provided,
        "expected == provided → %s" % py_equal,
        "first_differing_index=%s" % diff_index,
        "expected_codepoint_at_diff=%s" % expected_cp,
        "provided_codepoint_at_diff=%s" % provided_cp,
        _flags("expected", expected),
        _flags("provided", provided),
        "codepoint_lists expected=%s" % [f"U+{ord(c):04X}" for c in expected],
        "codepoint_lists provided=%s" % [f"U+{ord(c):04X}" for c in provided],
    ]
    message = "\n".join(lines)
    # print() so it always hits the gateway console even if log level filters.
    print(message, flush=True)
    logger.warning(message)


def _token_candidates(
    *,
    authorization: str | None,
    credentials: HTTPAuthorizationCredentials | None,
    x_gateway_token: str | None,
) -> list[tuple[str, str]]:
    """Collect unique normalized secrets from every supported header.

    Important: do **not** prefer Authorization exclusively. Cloudflare tunnels and
    some proxies rewrite ``Authorization`` while leaving ``X-Gateway-Token``
    intact (or the reverse). A first-match-only extractor returns 401 even when
    another header carries the correct shared secret — and masks can still look
    identical when only the middle of the Bearer value was altered.
    """
    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(token: str, source: str) -> None:
        if not token or token in seen:
            return
        seen.add(token)
        candidates.append((token, source))

    # Prefer X-Gateway-Token first: Railway sends it alongside Authorization
    # specifically because tunnels/proxies may rewrite Bearer while leaving
    # this dedicated header intact.
    add(normalize_gateway_token(x_gateway_token), "x_gateway_token")

    # Explicit Bearer parse (handles BOM / odd spacing before "Bearer").
    add(parse_authorization_bearer(authorization), "authorization_bearer")

    # FastAPI HTTPBearer credentials (may differ if Authorization was rewritten).
    if credentials is not None and credentials.scheme.lower() == "bearer":
        add(normalize_gateway_token(credentials.credentials), "http_bearer")

    # Some proxies strip the scheme and forward only the secret in Authorization.
    auth_stripped = (authorization or "").lstrip("\ufeff").strip()
    if auth_stripped and not auth_stripped.lower().startswith("bearer"):
        add(normalize_gateway_token(authorization), "authorization_raw")

    return candidates


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
    )

    for provided, header_source in candidates:
        # TEMPORARY DEBUG — remove after diagnosis (does not affect accept/reject).
        _temporary_token_diff_debug(
            expected=expected,
            provided=provided,
            header_source=header_source,
        )
        equal = tokens_equal(provided, expected)
        logger.info(
            "gateway_auth_check token_source=%s expected_len=%s expected=%s "
            "authorization_present=%s header_source=%s received_len=%s "
            "received=%s equal=%s meta=%s",
            getattr(cfg, "token_source", meta.get("source")),
            len(expected),
            mask_gateway_token(expected),
            bool((authorization or "").strip()),
            header_source,
            len(provided),
            mask_gateway_token(provided),
            equal,
            meta,
        )
        if cfg.mt5_gateway_auth_debug:
            logger.info(
                "gateway_auth_debug settings.mt5_gateway_token=%r "
                "settings_len=%s received=%r received_len=%s header_source=%s",
                cfg.mt5_gateway_token,
                len(expected),
                provided,
                len(provided),
                header_source,
            )
        if equal:
            return provided

    # Exact 401 raise site — reached only when every candidate failed compare.
    best = candidates[0] if candidates else ("", "missing")
    provided, header_source = best
    logger.warning(
        "gateway_auth_rejected token_source=%s expected=%s received=%s "
        "expected_len=%s received_len=%s header_source=%s candidates=%s "
        "(hint: len 32 often means example placeholder "
        "'replace-with-strong-random-token' is still loaded from "
        "process_env/NSSM instead of the repo .env; "
        "matching masks with equal=false usually means the middle differs "
        "or Authorization was rewritten while X-Gateway-Token is intact)",
        getattr(cfg, "token_source", meta.get("source")),
        mask_gateway_token(expected),
        mask_gateway_token(provided),
        len(expected),
        len(provided),
        header_source,
        [(src, mask_gateway_token(tok), len(tok)) for tok, src in candidates],
    )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing gateway token",
        headers={"WWW-Authenticate": "Bearer"},
    )
