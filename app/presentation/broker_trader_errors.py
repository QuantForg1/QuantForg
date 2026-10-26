"""Trader-safe broker connection errors.

Maps gateway/runtime failures to explicit codes. Never echoes raw gateway
text, stack traces, or secrets to the trader UI.
"""

from __future__ import annotations

from typing import NoReturn

from app.domain.exceptions.base import (
    ConflictError,
    DomainError,
    ServiceUnavailableError,
    ValidationError,
)

INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
CONNECTION_FAILED = "CONNECTION_FAILED"
GATEWAY_UNAVAILABLE = "GATEWAY_UNAVAILABLE"
CLOUDFLARE_ORIGIN_UNREACHABLE = "CLOUDFLARE_ORIGIN_UNREACHABLE"
ACCOUNT_SESSION_MISMATCH = "ACCOUNT_SESSION_MISMATCH"
BROKER_NOT_CONNECTED = "BROKER_NOT_CONNECTED"
CATALOGUE_UNAVAILABLE = "CATALOGUE_UNAVAILABLE"
OPEN_EXPOSURE = "OPEN_EXPOSURE"
EXPOSURE_UNVERIFIED = "EXPOSURE_UNVERIFIED"
ACCOUNT_MODE_MISMATCH = "ACCOUNT_MODE_MISMATCH"
OWNERSHIP_HELD = "OWNERSHIP_HELD"

TRADER_BROKER_MESSAGES: dict[str, str] = {
    INVALID_CREDENTIALS: "Broker login or password was not accepted.",
    CONNECTION_FAILED: "Could not verify the broker connection.",
    GATEWAY_UNAVAILABLE:
        "Broker Gateway Offline — Windows MT5 Gateway is unreachable. "
        "Check the tunnel/URL and that the Gateway process is running.",
    CLOUDFLARE_ORIGIN_UNREACHABLE:
        "Cloudflare tunnel cannot reach the Windows Gateway origin "
        "(HTTP 530). Start/repair the cloudflared connector — this is not "
        "an authentication failure.",
    ACCOUNT_SESSION_MISMATCH: "Your trading session needs to be reconnected.",
    BROKER_NOT_CONNECTED: "Connect your broker account to start.",
    CATALOGUE_UNAVAILABLE: "Connect or verify your broker and refresh market data.",
    OPEN_EXPOSURE: (
        "This account has open positions or pending orders. They stay at the "
        "broker and are not closed. Confirm the switch to leave them without "
        "management from this terminal."
    ),
    EXPOSURE_UNVERIFIED: (
        "Open positions could not be read, so the account was not switched."
    ),
    ACCOUNT_MODE_MISMATCH: (
        "Live or Demo does not match the account the terminal verified."
    ),
    OWNERSHIP_HELD: (
        "This attached account is owned by another user. Enter the account "
        "password to claim it. A gateway that is online does not grant ownership."
    ),
}


def classify_broker_connect_error(
    exc: BaseException,
) -> tuple[type[DomainError], str, str]:
    """Return (exception class, code, public message). Never returns raw exc text."""
    text = str(exc).lower()
    if "open_exposure" in text:
        code = OPEN_EXPOSURE
        return ConflictError, code, TRADER_BROKER_MESSAGES[code]
    if "exposure_unverified" in text:
        code = EXPOSURE_UNVERIFIED
        return ServiceUnavailableError, code, TRADER_BROKER_MESSAGES[code]
    if "account_mode_mismatch" in text:
        code = ACCOUNT_MODE_MISMATCH
        return ValidationError, code, TRADER_BROKER_MESSAGES[code]
    if (
        "ownership_claim_failed" in text
        or "login_owned_by_other_user" in text
        or "role_not_privileged" in text
    ):
        code = OWNERSHIP_HELD
        return ConflictError, code, TRADER_BROKER_MESSAGES[code]
    if (
        "account_session_mismatch" in text
        or ("mismatch" in text and "session" in text)
        or ("different account" in text)
        or ("belongs to a different" in text)
    ):
        code = ACCOUNT_SESSION_MISMATCH
        return ConflictError, code, TRADER_BROKER_MESSAGES[code]
    if any(
        token in text
        for token in (
            "invalid credential",
            "invalid_credentials",
            "unauthorized",
            "auth failed",
            "authentication failed",
            "wrong password",
            "incorrect password",
            "invalid password",
            "invalid login",
            "login failed",
            "rejected credentials",
            "bad password",
        )
    ):
        code = INVALID_CREDENTIALS
        return ValidationError, code, TRADER_BROKER_MESSAGES[code]
    # Cloudflare HTTP 530 / error 1033 — tunnel cannot reach origin (not auth).
    if any(
        token in text
        for token in (
            "cloudflare_origin_unreachable",
            "origin unreachable",
            "error code: 1033",
            "error code 1033",
            " http 530",
            "status 530",
            "status_code=530",
            "530 origin",
            "error 530",
        )
    ) or text.strip().endswith("530") or " 530 " in text:
        code = CLOUDFLARE_ORIGIN_UNREACHABLE
        return ServiceUnavailableError, code, TRADER_BROKER_MESSAGES[code]
    if any(
        token in text
        for token in (
            "gateway",
            "unreachable",
            "timed out",
            "timeout",
            "connection refused",
            "connection reset",
            "503",
            "not connected to mt5",
        )
    ):
        code = GATEWAY_UNAVAILABLE
        return ServiceUnavailableError, code, TRADER_BROKER_MESSAGES[code]
    code = CONNECTION_FAILED
    return ServiceUnavailableError, code, TRADER_BROKER_MESSAGES[code]


def raise_trader_broker_failure(exc: BaseException) -> NoReturn:
    cls, code, message = classify_broker_connect_error(exc)
    raise cls(message, code=code) from exc
