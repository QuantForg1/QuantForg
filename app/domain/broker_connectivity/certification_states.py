"""Broker certification workflow states — real MT5 sessions only."""

from __future__ import annotations

from enum import StrEnum


class CertificationState(StrEnum):
    NOT_TESTED = "Not Tested"
    PENDING_SESSION = "Pending Session"
    CONNECTED = "Connected"
    SYNC_VERIFIED = "Sync Verified"
    MARKET_DATA_VERIFIED = "Market Data Verified"
    PAPER_TRADING_VERIFIED = "Paper Trading Verified"
    EXECUTION_CHECK_VERIFIED = "Execution Check Verified"
    CERTIFIED = "Certified"
    FAILED = "Failed"


# Ordered progression toward Certified (Failed is terminal side-path).
PROGRESSION: tuple[CertificationState, ...] = (
    CertificationState.NOT_TESTED,
    CertificationState.PENDING_SESSION,
    CertificationState.CONNECTED,
    CertificationState.SYNC_VERIFIED,
    CertificationState.MARKET_DATA_VERIFIED,
    CertificationState.PAPER_TRADING_VERIFIED,
    CertificationState.EXECUTION_CHECK_VERIFIED,
    CertificationState.CERTIFIED,
)


class CertificationDiagnostic(StrEnum):
    WRONG_SERVER = "wrong_server"
    INVALID_CREDENTIALS = "invalid_credentials"
    TIMEOUT = "timeout"
    MARKET_CLOSED = "market_closed"
    SYMBOL_UNAVAILABLE = "symbol_unavailable"
    PERMISSION_DENIED = "permission_denied"
    NOT_CONNECTED = "not_connected"
    PROBE_ERROR = "probe_error"
    NONE = "none"
