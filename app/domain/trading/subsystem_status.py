"""Subsystem health labels — Gateway / MT5 / Research / Signals / Execution.

Each plane reports its own evidence. Research is not marked UNAVAILABLE solely
because a personal MT5 login is missing; it IS degraded when the broker market
catalogue (Gateway → MT5 symbols/quotes) required for live Gold analysis is
unreachable. Never invents LIVE_BROKER or confidence scores.
"""

from __future__ import annotations

from typing import Any


def classify_gateway_reachability(
    *,
    gateway_url_configured: bool,
    gateway_online: bool | None = None,
    gateway_reachable: bool | None = None,
    last_error: str | None = None,
) -> dict[str, Any]:
    """Map gateway evidence to a UI-safe status (no secrets)."""
    online = bool(gateway_online or gateway_reachable)
    if not gateway_url_configured:
        return {
            "status": "NOT_CONFIGURED",
            "label": "Gateway not configured",
            "detail": (
                "MT5_GATEWAY_BASE_URL is not set on the API. "
                "Broker connect and live Gold catalogue require a reachable Windows Gateway."
            ),
        }
    if online:
        return {
            "status": "ONLINE",
            "label": "Gateway Online",
            "detail": "Gateway health probe succeeded",
        }
    err = (last_error or "").strip().lower()
    if (
        "cloudflare_origin_unreachable" in err
        or "origin unreachable" in err
        or "error code: 1033" in err
        or "error code 1033" in err
        or " 530" in err
        or err.endswith("530")
    ):
        detail = (
            "Cloudflare tunnel cannot reach the Windows Gateway origin (HTTP 530). "
            "This is not an authentication failure — start/repair cloudflared."
        )
        label = "CLOUDFLARE_ORIGIN_UNREACHABLE"
    elif "timeout" in err:
        detail = "Gateway health probe timed out — tunnel or host may be offline"
        label = "Gateway timeout"
    elif "refused" in err or "connect" in err:
        detail = "Gateway refused connection — local Gateway process may be stopped"
        label = "Gateway Offline"
    elif "401" in err or "token" in err or "forbidden" in err or "403" in err:
        detail = "Gateway rejected the caller token — check token match (never log the token)"
        label = "Gateway auth failed"
    elif err:
        detail = "Gateway unreachable — see operator diagnostics for the safe error class"
        label = "Gateway Offline"
    else:
        detail = "Gateway unreachable — broker market catalogue cannot refresh"
        label = "Gateway Offline"
    return {"status": "OFFLINE", "label": label, "detail": detail}


def classify_mt5_attachment(
    *,
    mt5_connected: bool = False,
    mt5_attached: bool = False,
    owned_session: bool = False,
) -> dict[str, Any]:
    if owned_session or mt5_connected or mt5_attached:
        return {
            "status": "ATTACHED",
            "label": "MT5 Attached",
            "detail": "Broker terminal session is attached via Gateway",
        }
    return {
        "status": "DETACHED",
        "label": "MT5 Not attached",
        "detail": "No owned MT5 session — live trading unavailable",
    }


def classify_research_plane(
    *,
    worker_status: str | None,
    catalogue_source: str | None,
    last_error: str | None = None,
    gateway_online: bool = False,
) -> dict[str, Any]:
    """Research uses broker catalogue quotes when LIVE_BROKER is the source.

    Personal MT5 login is not required to *call* the research API, but live
    Gold OHLC still depends on a reachable Gateway catalogue today.
    """
    status = str(worker_status or "UNKNOWN").strip().upper()
    source = str(catalogue_source or "").strip().upper()
    if status in {"STOPPED"}:
        return {
            "status": "STOPPED",
            "label": "Research Stopped",
            "detail": "Research analysis worker is not running",
            "broker_catalogue_required": True,
        }
    if source in {"UNAVAILABLE", "ERROR", "MOCK"} or not gateway_online:
        return {
            "status": "DEGRADED",
            "label": "Research Degraded",
            "detail": (
                last_error
                or "Broker Gold catalogue unavailable — Gateway offline or not attached. "
                "Research cannot score XAUUSD without live broker market data."
            ),
            "broker_catalogue_required": True,
            "degraded_reason": "broker_catalogue_unavailable",
        }
    if status == "DEGRADED":
        return {
            "status": "DEGRADED",
            "label": "Research Degraded",
            "detail": last_error or "Research cycle reported degraded coverage",
            "broker_catalogue_required": True,
            "degraded_reason": "coverage_or_cycle_error",
        }
    if status in {"RUNNING", "READY"}:
        return {
            "status": "RUNNING",
            "label": "Research Running",
            "detail": "Research worker active with live broker catalogue",
            "broker_catalogue_required": True,
        }
    return {
        "status": "UNKNOWN",
        "label": "Research Unknown",
        "detail": "Research health not yet reported",
        "broker_catalogue_required": True,
    }


def classify_execution_plane(
    *,
    execution_enabled: bool = False,
    gateway_execution_enabled: bool = False,
    orders_may_submit: bool = False,
) -> dict[str, Any]:
    if orders_may_submit and execution_enabled and gateway_execution_enabled:
        return {
            "status": "READY",
            "label": "Execution Ready",
            "detail": "Both execution flags allow submit",
        }
    reasons: list[str] = []
    if not execution_enabled:
        reasons.append("EXECUTION_ENABLED=false")
    if not gateway_execution_enabled:
        reasons.append("MT5_GATEWAY_EXECUTION_ENABLED=false")
    if not orders_may_submit:
        reasons.append("orders_may_submit=false")
    return {
        "status": "BLOCKED",
        "label": "Execution Blocked",
        "detail": "; ".join(reasons) or "Execution not authorized",
    }


def build_subsystem_status(
    *,
    gateway_url_configured: bool = False,
    gateway_online: bool = False,
    gateway_reachable: bool = False,
    gateway_last_error: str | None = None,
    mt5_connected: bool = False,
    mt5_attached: bool = False,
    owned_session: bool = False,
    worker_status: str | None = None,
    catalogue_source: str | None = None,
    research_last_error: str | None = None,
    signal_count: int = 0,
    execution_enabled: bool = False,
    gateway_execution_enabled: bool = False,
    orders_may_submit: bool = False,
) -> dict[str, Any]:
    gateway = classify_gateway_reachability(
        gateway_url_configured=gateway_url_configured,
        gateway_online=gateway_online,
        gateway_reachable=gateway_reachable,
        last_error=gateway_last_error,
    )
    mt5 = classify_mt5_attachment(
        mt5_connected=mt5_connected,
        mt5_attached=mt5_attached,
        owned_session=owned_session,
    )
    research = classify_research_plane(
        worker_status=worker_status,
        catalogue_source=catalogue_source,
        last_error=research_last_error,
        gateway_online=bool(gateway_online or gateway_reachable),
    )
    if signal_count > 0:
        signals = {
            "status": "ACTIVE",
            "label": "Signals Present",
            "detail": f"{signal_count} research row(s)",
        }
    elif research["status"] == "DEGRADED":
        signals = {
            "status": "UNAVAILABLE",
            "label": "No Gold Signals",
            "detail": research["detail"],
        }
    else:
        signals = {
            "status": "EMPTY",
            "label": "No Qualifying Setup",
            "detail": "Scan completed without a qualifying BUY/SELL for XAUUSD",
        }
    execution = classify_execution_plane(
        execution_enabled=execution_enabled,
        gateway_execution_enabled=gateway_execution_enabled,
        orders_may_submit=orders_may_submit,
    )
    return {
        "gateway": gateway,
        "mt5": mt5,
        "research": research,
        "signals": signals,
        "execution": execution,
        "authorizes_trade": False,
    }
