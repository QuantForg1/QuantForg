"""Broker certification engine — advances workflow from real MT5 probes only."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from app.domain.broker_connectivity.certification_diagnostics import (
    classify_diagnostic,
    diagnostics_from_probes,
)
from app.domain.broker_connectivity.certification_states import (
    CertificationDiagnostic,
    CertificationState,
)
from app.domain.broker_connectivity.certification_store import CertificationStore
from app.domain.broker_connectivity.mt5_ecosystem import (
    ecosystem_profiles,
    match_broker_for_server,
    profile_by_slug,
)
from app.domain.broker_connectivity.types import ConnectivityStatus
from core.config.settings import get_settings

InvokeFn = Callable[..., dict[str, Any]]


def _ok(result: dict[str, Any]) -> bool:
    return str(result.get("status") or "").lower() == ConnectivityStatus.OK.value


def _data(result: dict[str, Any]) -> dict[str, Any]:
    raw = result.get("data")
    return raw if isinstance(raw, dict) else {}


def build_certification_report(
    *,
    broker_slug: str,
    broker_name: str,
    probes: dict[str, dict[str, Any]],
    connected: bool,
    session_matched: bool,
    paper_available: bool,
    last_certification_at: str | None,
) -> dict[str, Any]:
    """Assemble report fields from live probes — null when not observed."""
    health = probes.get("health", {})
    balances = probes.get("balances", {})
    symbols = probes.get("symbols", {})
    quotes = probes.get("quotes", {})
    heartbeat = probes.get("heartbeat", {})
    trading = probes.get("trading", {})

    h_data = _data(health)
    b_data = _data(balances)
    s_data = _data(symbols)
    q_data = _data(quotes)
    hb_data = _data(heartbeat)

    symbol_items: list[Any] = (
        s_data["items"] if isinstance(s_data.get("items"), list) else []
    )
    hb_ok = _ok(heartbeat) if connected and session_matched else False

    return {
        "broker": broker_slug,
        "broker_name": broker_name,
        "server_name": h_data.get("server") if connected else None,
        "mt5_build": h_data.get("terminal_build") if connected else None,
        "hedging_netting_mode": None,
        "hedging_netting_note": (
            "Not exposed by live MT5 account snapshot — "
            "do not invent mode from documentation alone"
        ),
        "account_currency": b_data.get("currency") if _ok(balances) else None,
        "leverage": b_data.get("leverage") if _ok(balances) else None,
        "symbols_available": len(symbol_items) if _ok(symbols) else None,
        "execution_latency_ms": trading.get("latency_ms") if session_matched else None,
        "quote_latency_ms": quotes.get("latency_ms") if _ok(quotes) else None,
        "heartbeat_stability": (
            "stable"
            if hb_ok
            else ("unavailable" if not connected else "unstable_or_missing")
        ),
        "heartbeat_ping_ms": hb_data.get("ping_ms") if hb_ok else None,
        "last_certification_time": last_certification_at,
        "paper_available": paper_available,
        "quote_sample": (
            {
                "symbol": q_data.get("symbol"),
                "bid": q_data.get("bid"),
                "ask": q_data.get("ask"),
            }
            if _ok(quotes)
            else None
        ),
        "session_matched": session_matched,
        "observed_at": datetime.now(UTC).isoformat() if connected else None,
    }


def evaluate_workflow(
    *,
    connected: bool,
    session_matched: bool,
    probes: dict[str, dict[str, Any]],
    paper_available: bool,
) -> tuple[CertificationState, str]:
    """Derive certification state from real probe outcomes."""
    if not connected:
        return (
            CertificationState.PENDING_SESSION,
            "No live MT5 session — connect via /mt5",
        )

    if not session_matched:
        return (
            CertificationState.PENDING_SESSION,
            "Live session server does not match this broker brand",
        )

    # Hard failures on login/health
    health = probes.get("health", {})
    if not _ok(health):
        reason = str(health.get("reason") or "health probe failed")
        diag = classify_diagnostic(
            reason=reason, capability="health", status=str(health.get("status"))
        )
        if diag is CertificationDiagnostic.INVALID_CREDENTIALS:
            return CertificationState.FAILED, reason
        return CertificationState.FAILED, reason

    state = CertificationState.CONNECTED
    failure = ""

    balances = probes.get("balances", {})
    if _ok(balances):
        state = CertificationState.SYNC_VERIFIED
    else:
        failure = str(balances.get("reason") or "account sync failed")
        return CertificationState.CONNECTED, failure

    quotes = probes.get("quotes", {})
    candles = probes.get("candles", {})
    symbols = probes.get("symbols", {})
    if _ok(symbols) and _ok(quotes) and _ok(candles):
        state = CertificationState.MARKET_DATA_VERIFIED
    else:
        bad = next(
            (p for p in (symbols, quotes, candles) if not _ok(p)),
            {},
        )
        failure = str(bad.get("reason") or "market data probe failed")
        return state, failure

    if paper_available:
        state = CertificationState.PAPER_TRADING_VERIFIED
    else:
        return (
            state,
            "Paper trading engine not registered in this process",
        )

    trading = probes.get("trading", {})
    t_status = str(trading.get("status") or "").lower()
    # Gate must respond cleanly (ok or unavailable when EXECUTION_ENABLED off)
    if t_status in {
        ConnectivityStatus.OK.value,
        ConnectivityStatus.UNAVAILABLE.value,
    }:
        state = CertificationState.EXECUTION_CHECK_VERIFIED
    else:
        failure = str(trading.get("reason") or "execution check probe failed")
        return state, failure

    return CertificationState.CERTIFIED, ""


def run_certification(
    *,
    store: CertificationStore,
    invoke: InvokeFn,
    broker_slug: str | None = None,
    quote_symbol: str = "EURUSD",
    paper_available: bool = False,
    tester: str = "operator",
    persist: bool = True,
) -> dict[str, Any]:
    """Run certification for ecosystem brokers using the live MT5 adapter."""
    _ = get_settings()  # ensure settings load; EXECUTION_ENABLED never flipped
    health = invoke("mt5", "health")
    connected = _ok(health)
    server = str(_data(health).get("server") or "")
    matched = match_broker_for_server(server) if connected and server else None
    matched_slug = matched.slug if matched else None

    probes: dict[str, dict[str, Any]] = {"health": health}
    if connected:
        probes.update(
            {
                "heartbeat": invoke("mt5", "heartbeat"),
                "balances": invoke("mt5", "balances"),
                "positions": invoke("mt5", "positions"),
                "orders": invoke("mt5", "orders"),
                "history": invoke("mt5", "history"),
                "symbols": invoke("mt5", "symbols"),
                "quotes": invoke("mt5", "quotes", symbol=quote_symbol),
                "candles": invoke(
                    "mt5",
                    "candles",
                    symbol=quote_symbol,
                    timeframe="H1",
                    count=20,
                ),
                "trading": invoke("mt5", "trading", intent={}),
            }
        )

    profiles = ecosystem_profiles()
    if broker_slug:
        one = profile_by_slug(broker_slug)
        profiles = [one] if one is not None else []

    brokers_out: list[dict[str, Any]] = []
    for profile in profiles:
        session_matched = bool(
            matched_slug and matched_slug == profile.slug and connected
        )
        prior = store.get_status(profile.slug)
        last_at = (
            str(prior.get("last_certification_time"))
            if prior and prior.get("last_certification_time")
            else None
        )

        state, failure = evaluate_workflow(
            connected=connected,
            session_matched=session_matched,
            probes=probes if session_matched or not connected else {"health": health},
            paper_available=paper_available,
        )

        # Wrong-server diagnostic when connected but not matched
        extra_diags: list[dict[str, str]] = []
        if connected and not session_matched:
            extra_diags.append(
                {
                    "capability": "login",
                    "diagnostic": CertificationDiagnostic.WRONG_SERVER.value,
                    "reason": (
                        f"Session server '{server}' does not match {profile.name}"
                    ),
                }
            )
            state = CertificationState.PENDING_SESSION

        if (
            not connected
            and state is CertificationState.PENDING_SESSION
            and prior is None
            and not persist
        ):
            state = CertificationState.NOT_TESTED

        diags = diagnostics_from_probes(
            probes if session_matched else {"health": health}
        )
        diags = extra_diags + diags

        report = build_certification_report(
            broker_slug=profile.slug,
            broker_name=profile.name,
            probes=probes if session_matched else {"health": health},
            connected=connected,
            session_matched=session_matched,
            paper_available=paper_available,
            last_certification_at=last_at,
        )

        if state is CertificationState.CERTIFIED:
            result = "certified"
            failure_reason = ""
        elif state is CertificationState.FAILED:
            result = "failed"
            failure_reason = failure
        elif state is CertificationState.PENDING_SESSION:
            result = "pending"
            failure_reason = failure
        elif state is CertificationState.NOT_TESTED:
            result = "not_tested"
            failure_reason = ""
        else:
            result = "in_progress"
            failure_reason = failure

        now = datetime.now(UTC).isoformat()
        if persist and state is CertificationState.CERTIFIED:
            report["last_certification_time"] = now
            last_at = now
        elif persist and result in {"failed", "pending", "in_progress"}:
            report["last_certification_time"] = last_at

        status_payload = {
            "slug": profile.slug,
            "name": profile.name,
            "state": state.value,
            "result": result,
            "failure_reason": failure_reason,
            "diagnostics": diags,
            "report": report,
            "health_status": (
                "healthy"
                if state is CertificationState.CERTIFIED
                else (
                    "pending"
                    if state
                    in {
                        CertificationState.PENDING_SESSION,
                        CertificationState.NOT_TESTED,
                    }
                    else (
                        "failed" if state is CertificationState.FAILED else "degraded"
                    )
                )
            ),
            "last_test_at": now if persist else (prior or {}).get("last_test_at"),
            "last_certification_time": report.get("last_certification_time"),
            "tester": tester,
        }

        if persist:
            store.set_status(profile.slug, status_payload)
            store.append_history(
                broker_slug=profile.slug,
                broker_name=profile.name,
                result=result,
                state=state,
                failure_reason=failure_reason,
                tester=tester,
                diagnostics=diags,
                report=report,
            )

        brokers_out.append(status_payload)

    certified = [
        b for b in brokers_out if b["state"] == CertificationState.CERTIFIED.value
    ]
    pending = [
        b
        for b in brokers_out
        if b["state"]
        in {
            CertificationState.PENDING_SESSION.value,
            CertificationState.NOT_TESTED.value,
        }
        or b["result"] == "in_progress"
    ]
    failed = [b for b in brokers_out if b["state"] == CertificationState.FAILED.value]

    return {
        "version": "1.0",
        "session": {
            "connected": connected,
            "server": server or None,
            "matched_broker": matched_slug,
            "quote_symbol": quote_symbol,
        },
        "brokers": brokers_out,
        "certified": certified,
        "pending": pending,
        "failed": failed,
        "history": store.history(limit=50),
        "notes": (
            "Certification requires a real MT5 session for the matched brand. "
            "No simulated broker data is used."
        ),
    }


def certification_dashboard(store: CertificationStore) -> dict[str, Any]:
    """Dashboard snapshot from stored status (plus empty defaults for ecosystem)."""
    known = {p.slug: p for p in ecosystem_profiles()}
    rows = store.all_status()
    by_slug = {str(r.get("slug")): r for r in rows}

    brokers: list[dict[str, Any]] = []
    for slug, profile in known.items():
        if slug in by_slug:
            brokers.append(by_slug[slug])
        else:
            brokers.append(
                {
                    "slug": slug,
                    "name": profile.name,
                    "state": CertificationState.NOT_TESTED.value,
                    "result": "not_tested",
                    "failure_reason": "",
                    "diagnostics": [],
                    "report": {
                        "broker": slug,
                        "broker_name": profile.name,
                        "server_name": None,
                        "mt5_build": None,
                        "hedging_netting_mode": None,
                        "account_currency": None,
                        "leverage": None,
                        "symbols_available": None,
                        "execution_latency_ms": None,
                        "quote_latency_ms": None,
                        "heartbeat_stability": "unavailable",
                        "last_certification_time": None,
                    },
                    "health_status": "pending",
                    "last_test_at": None,
                    "last_certification_time": None,
                    "tester": None,
                }
            )

    certified = [
        b for b in brokers if b.get("state") == CertificationState.CERTIFIED.value
    ]
    pending = [
        b
        for b in brokers
        if b.get("state")
        in {
            CertificationState.NOT_TESTED.value,
            CertificationState.PENDING_SESSION.value,
        }
        or b.get("result") == "in_progress"
    ]
    failed = [b for b in brokers if b.get("state") == CertificationState.FAILED.value]
    last_tests = sorted(
        [b for b in brokers if b.get("last_test_at")],
        key=lambda r: str(r.get("last_test_at")),
        reverse=True,
    )

    return {
        "title": "Broker Certification Dashboard",
        "certified_brokers": certified,
        "pending_brokers": pending,
        "failed_certifications": failed,
        "last_test": last_tests[0] if last_tests else None,
        "health_status": [
            {
                "slug": b.get("slug"),
                "name": b.get("name"),
                "health_status": b.get("health_status"),
                "state": b.get("state"),
            }
            for b in brokers
        ],
        "brokers": brokers,
        "history": store.history(limit=50),
        "workflow_states": [s.value for s in CertificationState],
        "notes": (
            "Run POST /broker-connectivity/certification/run with a live MT5 "
            "session to advance Pending Session → Certified."
        ),
    }
