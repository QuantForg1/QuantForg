"""Control-plane communication faults — never a trading NO_TRADE.

Frontend status mapping:

* 0   → API_UNREACHABLE
* 408 → API_TIMEOUT
* 401 → AUTH_REQUIRED / AUTH_REFRESH
* 422 → CONTRACT_VALIDATION_ERROR
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from app.domain.trading.gold_only import CANONICAL_GOLD_BROKER_DISPLAY

CANONICAL_BROKER_SYMBOL = CANONICAL_GOLD_BROKER_DISPLAY

# Browser/UI is never on the ITE decision path.
AUTONOMOUS_PATH_INDEPENDENT_OF_UI = True


class CommunicationFault(StrEnum):
    API_UNREACHABLE = "API_UNREACHABLE"
    API_TIMEOUT = "API_TIMEOUT"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    AUTH_REFRESH = "AUTH_REFRESH"
    CONTRACT_VALIDATION_ERROR = "CONTRACT_VALIDATION_ERROR"
    FORBIDDEN = "FORBIDDEN"
    MARKET_DATA_UNAVAILABLE = "MARKET_DATA_UNAVAILABLE"
    SERVER_ERROR = "SERVER_ERROR"
    OK = "OK"


NO_TRADE = "NO_TRADE"


def classify_http_fault(
    *,
    status: int | None = None,
    code: str | None = None,
    refresh_attempted: bool = False,
) -> CommunicationFault:
    code_key = (code or "").strip()
    if code_key == "network_error" or status == 0:
        return CommunicationFault.API_UNREACHABLE
    if code_key == "timeout" or status == 408:
        return CommunicationFault.API_TIMEOUT
    if code_key in {"missing_token", "auth_bootstrap_pending", "AUTH_REQUIRED"}:
        return CommunicationFault.AUTH_REQUIRED
    if status == 401 or code_key in {
        "unauthorized",
        "authentication_failed",
        "invalid_token",
        "AUTH_REFRESH",
    }:
        if refresh_attempted:
            return CommunicationFault.AUTH_REQUIRED
        return CommunicationFault.AUTH_REFRESH
    if status == 422 or code_key in {
        "request_validation_error",
        "CONTRACT_VALIDATION_ERROR",
    }:
        return CommunicationFault.CONTRACT_VALIDATION_ERROR
    if status == 403 or code_key in {"insufficient_role", "forbidden"}:
        return CommunicationFault.FORBIDDEN
    if status is not None and status >= 500:
        return CommunicationFault.SERVER_ERROR
    if code_key == "market_data_unavailable":
        return CommunicationFault.MARKET_DATA_UNAVAILABLE
    if status is None and not code_key:
        return CommunicationFault.OK
    return CommunicationFault.SERVER_ERROR


def is_no_trade_fault(fault: CommunicationFault) -> bool:
    """Communication faults must never be rewritten as strategy NO_TRADE."""
    _ = fault
    return False


def telemetry_must_not_block_decision(fault: CommunicationFault | None) -> bool:
    """Observability / dashboard / audit failures stay off the critical path."""
    if fault is None:
        return True
    return fault not in {
        CommunicationFault.MARKET_DATA_UNAVAILABLE,
    }


def market_data_failure_blocks(fault: CommunicationFault) -> bool:
    return fault is CommunicationFault.MARKET_DATA_UNAVAILABLE


def should_replay_after_refresh(*, method: str, path: str) -> bool:
    verb = (method or "GET").upper()
    route = (path or "").split("?", 1)[0]
    if verb not in {"GET", "HEAD"}:
        return False
    blocked = (
        "/execution/submit",
        "/execution/cancel",
        "/execution/manage",
        "/mt5/order",
    )
    return not any(token in route for token in blocked)


def should_blind_retry_order_submit() -> bool:
    return False


def snapshot_reuse_key(*, cycle_id: str, snapshot_id: str, symbol: str) -> str:
    return f"{cycle_id}:{snapshot_id}:{symbol}"


def communication_latency_fields(
    measured: dict[str, Any] | None = None,
) -> dict[str, float]:
    src = dict(measured or {})

    def _ms(key: str, *aliases: str) -> float:
        for name in (key, *aliases):
            raw = src.get(name)
            if raw is None:
                continue
            try:
                return round(float(raw), 3)
            except (TypeError, ValueError):
                continue
        return 0.0

    market = _ms("market_data_ms", "market_ms")
    decision = _ms("decision_ms")
    risk = _ms("risk_ms")
    safety = _ms("safety_ms")
    oms = _ms("oms_ms")
    signal_to_decision = _ms(
        "signal_to_decision_ms",
        "probability_to_decision_ms",
    )
    if signal_to_decision <= 0:
        signal_to_decision = round(
            _ms("signal_detect_to_snapshot_ms")
            + _ms("snapshot_to_probability_ms")
            + _ms("probability_to_decision_ms"),
            3,
        )
    signal_to_ready = _ms("signal_to_execution_ready_ms")
    if signal_to_ready <= 0:
        signal_to_ready = round(
            signal_to_decision
            + _ms("decision_to_risk_ms")
            + _ms("risk_to_safety_ms")
            + _ms("safety_to_plan_ms"),
            3,
        )
    return {
        "api_connectivity_ms": _ms("api_connectivity_ms"),
        "auth_ms": _ms("auth_ms"),
        "strategy_ms": _ms("strategy_ms", "probability_ms"),
        "market_data_ms": market,
        "risk_ms": risk,
        "safety_ms": safety,
        "decision_ms": decision,
        "oms_ms": oms,
        "signal_to_decision_ms": signal_to_decision,
        "signal_to_execution_ready_ms": signal_to_ready,
    }
