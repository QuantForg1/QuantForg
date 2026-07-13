"""Live MT5 broker compatibility validation — never invents probe results."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.domain.broker_connectivity.mt5_ecosystem import (
    COMPATIBILITY_CHECKS,
    MT5BrokerProfile,
    ecosystem_profiles,
    match_broker_for_server,
    profile_by_slug,
)
from app.domain.broker_connectivity.types import ConnectivityStatus
from core.config.settings import get_settings

InvokeFn = Callable[..., dict[str, Any]]


def _check_row(
    *,
    check: str,
    status: str,
    detail: str = "",
    evidence: Any = None,
) -> dict[str, Any]:
    return {
        "check": check,
        "status": status,
        "detail": detail,
        "evidence": evidence,
    }


def _status_from_result(result: dict[str, Any]) -> str:
    raw = str(result.get("status") or "").lower()
    if raw == ConnectivityStatus.OK.value:
        return "compatible"
    if raw == ConnectivityStatus.UNAVAILABLE.value:
        return "unavailable"
    if raw == ConnectivityStatus.UNSUPPORTED.value:
        return "unsupported"
    if raw == ConnectivityStatus.ERROR.value:
        return "error"
    return "unavailable"


def run_compatibility_suite(
    *,
    invoke: InvokeFn,
    broker_slug: str | None = None,
    quote_symbol: str = "EURUSD",
    paper_available: bool | None = None,
) -> dict[str, Any]:
    """Validate ecosystem brokers against the live MT5 adapter when connected.

    Documented profiles always appear. Live checks only pass when the MT5
    session is up and probes return real ``ok`` results. No simulated ticks.
    """
    settings = get_settings()
    health = invoke("mt5", "health")
    connected = _status_from_result(health) == "compatible"
    server = ""
    health_data = health.get("data") if isinstance(health.get("data"), dict) else {}
    if isinstance(health_data, dict):
        server = str(health_data.get("server") or "")

    matched = match_broker_for_server(server) if connected and server else None
    matched_slug = matched.slug if matched else None

    profiles = ecosystem_profiles()
    if broker_slug:
        one = profile_by_slug(broker_slug)
        profiles = [one] if one is not None else []

    # Shared live probes (one MT5 session serves the matched brand only).
    live_probe_cache: dict[str, dict[str, Any]] = {}
    if connected:
        live_probe_cache = {
            "login": health,
            "balances": invoke("mt5", "balances"),
            "positions": invoke("mt5", "positions"),
            "pending_orders": invoke("mt5", "orders"),
            "history": invoke("mt5", "history"),
            "symbols": invoke("mt5", "symbols"),
            "quotes": invoke("mt5", "quotes", symbol=quote_symbol),
            "candles": invoke(
                "mt5", "candles", symbol=quote_symbol, timeframe="H1", count=20
            ),
            "execution_checks": invoke("mt5", "trading", intent={}),
        }

    paper_status = "compatible" if paper_available else "unavailable"
    paper_detail = (
        "Paper trading engine registered in DI"
        if paper_available
        else "Paper engine not registered in this process — use /paper when available"
    )

    brokers_out: list[dict[str, Any]] = []
    for profile in profiles:
        is_session_brand = bool(
            matched_slug and matched_slug == profile.slug and connected
        )
        checks = _build_checks(
            profile=profile,
            connected=connected,
            is_session_brand=is_session_brand,
            server=server,
            live_probe_cache=live_probe_cache,
            paper_status=paper_status,
            paper_detail=paper_detail,
            execution_enabled=bool(settings.execution_enabled),
            quote_symbol=quote_symbol,
        )
        summary = _summarize(checks)
        brokers_out.append(
            {
                **profile.to_dict(),
                "session_matched": is_session_brand,
                "checks": checks,
                "summary": summary,
            }
        )

    matrix = [
        {
            "slug": b["slug"],
            "name": b["name"],
            "platform": b["platform"],
            "session_matched": b["session_matched"],
            **{c["check"]: c["status"] for c in b["checks"]},
            "overall": b["summary"]["overall"],
        }
        for b in brokers_out
    ]

    return {
        "version": "1.1",
        "platform": "mt5",
        "session": {
            "connected": connected,
            "server": server or None,
            "matched_broker": matched_slug,
            "health": health,
            "quote_symbol": quote_symbol,
            "execution_enabled": bool(settings.execution_enabled),
            "note": (
                "Live compatibility applies only to the MT5 brand matching "
                "the connected server. Other brands stay pending_session."
            ),
        },
        "checks": list(COMPATIBILITY_CHECKS),
        "brokers": brokers_out,
        "matrix": matrix,
        "operator_actions": _operator_actions(
            connected=connected, matched_slug=matched_slug, profiles=profiles
        ),
    }


def _build_checks(
    *,
    profile: MT5BrokerProfile,
    connected: bool,
    is_session_brand: bool,
    server: str,
    live_probe_cache: dict[str, dict[str, Any]],
    paper_status: str,
    paper_detail: str,
    execution_enabled: bool,
    quote_symbol: str,
) -> list[dict[str, Any]]:
    if not connected:
        pending = [
            _check_row(
                check=c,
                status="pending_session",
                detail=(
                    f"Connect {profile.name} MT5 via /mt5 to validate "
                    f"'{c}' against a live terminal"
                ),
            )
            for c in COMPATIBILITY_CHECKS
            if c not in {"paper_trading", "execution_checks"}
        ]
        pending.append(
            _check_row(
                check="paper_trading",
                status=paper_status,
                detail=paper_detail,
            )
        )
        pending.append(
            _check_row(
                check="execution_checks",
                status="documented",
                detail=(
                    "Execution path: POST /execution/check — "
                    f"EXECUTION_ENABLED={execution_enabled} (not flipped here)"
                ),
                evidence={"execution_enabled": execution_enabled},
            )
        )
        return pending

    if not is_session_brand:
        rows = [
            _check_row(
                check=c,
                status="pending_session",
                detail=(
                    f"Live session server '{server}' does not match "
                    f"{profile.name}. Connect that brand to validate '{c}'."
                ),
            )
            for c in COMPATIBILITY_CHECKS
            if c not in {"paper_trading", "execution_checks"}
        ]
        rows.append(
            _check_row(
                check="paper_trading",
                status=paper_status,
                detail=paper_detail,
            )
        )
        rows.append(
            _check_row(
                check="execution_checks",
                status="documented",
                detail=(
                    "Execution path: POST /execution/check — "
                    f"EXECUTION_ENABLED={execution_enabled}"
                ),
                evidence={"execution_enabled": execution_enabled},
            )
        )
        return rows

    # Matched live session — probe real MT5 results only.
    balances = live_probe_cache.get("balances", {})
    bal_status = _status_from_result(balances)
    bal_data = balances.get("data") if isinstance(balances.get("data"), dict) else {}

    checks = [
        _check_row(
            check="login",
            status=_status_from_result(live_probe_cache["login"]),
            detail=f"MT5 health for server '{server}'",
            evidence={"server": server},
        ),
        _check_row(
            check="account_sync",
            status=bal_status,
            detail="Account snapshot via balances probe",
            evidence=bal_data or None,
        ),
        _check_row(
            check="balances",
            status=bal_status,
            detail="Balance field from live account snapshot",
            evidence={"balance": (bal_data or {}).get("balance")},
        ),
        _check_row(
            check="equity",
            status=bal_status,
            detail="Equity field from live account snapshot",
            evidence={"equity": (bal_data or {}).get("equity")},
        ),
        _map_probe("positions", live_probe_cache["positions"]),
        _map_probe("pending_orders", live_probe_cache["pending_orders"]),
        _map_probe("history", live_probe_cache["history"]),
        _map_probe("symbols", live_probe_cache["symbols"]),
        _map_probe(
            "quotes",
            live_probe_cache["quotes"],
            detail=f"latest_tick({quote_symbol})",
        ),
        _map_probe(
            "candles",
            live_probe_cache["candles"],
            detail=f"copy_rates({quote_symbol}, H1)",
        ),
        _check_row(
            check="paper_trading",
            status=paper_status,
            detail=paper_detail,
        ),
        _execution_check(
            live_probe_cache["execution_checks"],
            execution_enabled=execution_enabled,
        ),
    ]
    return checks


def _map_probe(
    check: str, result: dict[str, Any], *, detail: str = ""
) -> dict[str, Any]:
    return _check_row(
        check=check,
        status=_status_from_result(result),
        detail=detail or str(result.get("reason") or ""),
        evidence={
            "status": result.get("status"),
            "latency_ms": result.get("latency_ms"),
        },
    )


def _execution_check(
    result: dict[str, Any], *, execution_enabled: bool
) -> dict[str, Any]:
    """Trading probe never order_send; compatible means gate reported cleanly."""
    status = _status_from_result(result)
    # unavailable when execution disabled is expected — still a valid check
    if status in {"compatible", "unavailable"}:
        mapped = "compatible"
        detail = (
            "Execution gate probed without order_send; "
            f"EXECUTION_ENABLED={execution_enabled}"
        )
    else:
        mapped = status
        detail = str(result.get("reason") or "execution probe failed")
    return _check_row(
        check="execution_checks",
        status=mapped,
        detail=detail,
        evidence={
            "probe_status": result.get("status"),
            "execution_enabled": execution_enabled,
            "submit_path": "POST /execution/submit",
            "check_path": "POST /execution/check",
        },
    )


def _summarize(checks: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {
        "compatible": 0,
        "pending_session": 0,
        "unavailable": 0,
        "documented": 0,
        "error": 0,
        "unsupported": 0,
    }
    for c in checks:
        key = str(c.get("status") or "unavailable")
        counts[key] = counts.get(key, 0) + 1
    if counts.get("error", 0):
        overall = "error"
    elif counts.get("compatible", 0) and not counts.get("pending_session", 0):
        overall = "compatible"
    elif counts.get("compatible", 0):
        overall = "partial"
    elif counts.get("pending_session", 0):
        overall = "pending_session"
    else:
        overall = "unavailable"
    return {"overall": overall, "counts": counts}


def _operator_actions(
    *,
    connected: bool,
    matched_slug: str | None,
    profiles: list[MT5BrokerProfile],
) -> list[str]:
    actions: list[str] = []
    if not connected:
        actions.append(
            "Connect a priority broker MT5 account via POST /mt5/connect "
            "(or /mt5 UI) using the exact server from the broker portal."
        )
    else:
        if matched_slug:
            actions.append(
                f"Live session matched '{matched_slug}' — review matrix "
                "cells marked compatible/error for that brand."
            )
        else:
            actions.append(
                "MT5 is connected but server did not match a v1.1 priority "
                "brand pattern — confirm server string or extend patterns "
                "after verifying the portal assignment."
            )
    for p in profiles:
        if matched_slug == p.slug:
            continue
        actions.append(
            f"To validate {p.name}: disconnect current session if needed, "
            f"then connect with that brand's MT5 credentials ({p.website})."
        )
    actions.append(
        "Keep EXECUTION_ENABLED unchanged until intentional live trading; "
        "use /paper and /execution/check first."
    )
    actions.append(
        "Do not treat documented capability profiles as live market data."
    )
    return actions
