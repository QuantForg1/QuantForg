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
ACCOUNT_SESSION_MISMATCH = "ACCOUNT_SESSION_MISMATCH"
BROKER_NOT_CONNECTED = "BROKER_NOT_CONNECTED"
CATALOGUE_UNAVAILABLE = "CATALOGUE_UNAVAILABLE"

TRADER_BROKER_MESSAGES: dict[str, str] = {
    INVALID_CREDENTIALS: "Broker login or password was not accepted.",
    CONNECTION_FAILED: "Could not verify the broker connection.",
    GATEWAY_UNAVAILABLE: "The broker gateway is temporarily unavailable.",
    ACCOUNT_SESSION_MISMATCH: "Your trading session needs to be reconnected.",
    BROKER_NOT_CONNECTED: "Connect your broker account to start.",
    CATALOGUE_UNAVAILABLE: "Connect or verify your broker and refresh market data.",
}


def classify_broker_connect_error(
    exc: BaseException,
) -> tuple[type[DomainError], str, str]:
    """Return (exception class, code, public message). Never returns raw exc text."""
    text = str(exc).lower()
    if "account_session_mismatch" in text or (
        "mismatch" in text and "session" in text
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
        )
    ):
        code = INVALID_CREDENTIALS
        return ValidationError, code, TRADER_BROKER_MESSAGES[code]
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
