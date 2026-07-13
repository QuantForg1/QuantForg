"""Unit tests for Broker Certification System — no simulated venues."""

from __future__ import annotations

from typing import Any

import pytest

from app.application.services.broker_connectivity import BrokerConnectivityService
from app.domain.broker_connectivity.certification import (
    evaluate_workflow,
    run_certification,
)
from app.domain.broker_connectivity.certification_diagnostics import (
    classify_diagnostic,
)
from app.domain.broker_connectivity.certification_states import (
    CertificationDiagnostic,
    CertificationState,
)
from app.domain.broker_connectivity.certification_store import CertificationStore
from app.domain.broker_connectivity.types import ConnectivityStatus


def _ok(capability: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "status": ConnectivityStatus.OK.value,
        "capability": capability,
        "platform": "mt5",
        "data": data or {},
        "latency_ms": 5.0,
    }


def _unavail(capability: str, reason: str) -> dict[str, Any]:
    return {
        "status": ConnectivityStatus.UNAVAILABLE.value,
        "capability": capability,
        "platform": "mt5",
        "reason": reason,
    }


@pytest.mark.unit
class TestDiagnostics:
    def test_wrong_server(self) -> None:
        assert (
            classify_diagnostic(reason="server does not match Weltrade")
            is CertificationDiagnostic.WRONG_SERVER
        )

    def test_invalid_credentials(self) -> None:
        assert (
            classify_diagnostic(reason="MT5 login failed")
            is CertificationDiagnostic.INVALID_CREDENTIALS
        )

    def test_symbol_unavailable(self) -> None:
        assert (
            classify_diagnostic(reason="symbol not found EURUSD")
            is CertificationDiagnostic.SYMBOL_UNAVAILABLE
        )


@pytest.mark.unit
class TestWorkflow:
    def test_pending_without_session(self) -> None:
        state, _ = evaluate_workflow(
            connected=False,
            session_matched=False,
            probes={},
            paper_available=True,
        )
        assert state is CertificationState.PENDING_SESSION

    def test_full_path_to_certified(self) -> None:
        probes = {
            "health": _ok("health", {"server": "Exness-MT5", "terminal_build": 4000}),
            "balances": _ok(
                "balances", {"currency": "USD", "leverage": 100, "balance": "1"}
            ),
            "symbols": _ok("symbols", {"items": [{"code": "EURUSD"}]}),
            "quotes": _ok("quotes", {"symbol": "EURUSD", "bid": "1", "ask": "1"}),
            "candles": _ok("candles", {"items": []}),
            "trading": _unavail("trading", "execution disabled"),
        }
        state, failure = evaluate_workflow(
            connected=True,
            session_matched=True,
            probes=probes,
            paper_available=True,
        )
        assert state is CertificationState.CERTIFIED
        assert failure == ""


@pytest.mark.unit
class TestCertificationRun:
    def test_run_without_session_pending(self) -> None:
        store = CertificationStore()

        def invoke(platform: str, capability: str, **_: Any) -> dict[str, Any]:
            assert platform == "mt5"
            return _unavail(capability, "MT5 not connected")

        out = run_certification(
            store=store,
            invoke=invoke,
            paper_available=True,
            tester="qa",
            persist=True,
        )
        assert out["session"]["connected"] is False
        assert len(out["certified"]) == 0
        assert len(out["pending"]) == 5
        assert len(store.history()) == 5
        assert all(
            b["state"] == CertificationState.PENDING_SESSION.value
            for b in out["brokers"]
        )

    def test_matched_broker_certifies(self) -> None:
        store = CertificationStore()

        def invoke(platform: str, capability: str, **kwargs: Any) -> dict[str, Any]:
            _ = kwargs
            assert platform == "mt5"
            if capability == "health":
                return _ok(
                    "health",
                    {
                        "server": "XMGlobal-MT5 1",
                        "terminal_build": 3815,
                        "connected": True,
                    },
                )
            if capability == "heartbeat":
                return _ok("heartbeat", {"ping_ms": 12.0})
            if capability == "balances":
                return _ok(
                    "balances",
                    {
                        "currency": "USD",
                        "leverage": 500,
                        "balance": "1000",
                        "equity": "1000",
                    },
                )
            if capability == "symbols":
                return _ok("symbols", {"items": [{"code": "EURUSD"}]})
            if capability == "quotes":
                return _ok(
                    "quotes", {"symbol": "EURUSD", "bid": "1.1", "ask": "1.2"}
                )
            if capability == "candles":
                return _ok("candles", {"items": [{"open": "1"}]})
            if capability == "trading":
                return _unavail("trading", "execution disabled")
            return _ok(capability, {"items": []})

        out = run_certification(
            store=store,
            invoke=invoke,
            paper_available=True,
            tester="qa",
            persist=True,
        )
        by_slug = {b["slug"]: b for b in out["brokers"]}
        assert by_slug["xm"]["state"] == CertificationState.CERTIFIED.value
        assert by_slug["xm"]["report"]["server_name"]
        assert by_slug["xm"]["report"]["account_currency"] == "USD"
        assert by_slug["weltrade"]["state"] == CertificationState.PENDING_SESSION.value
        assert len(out["certified"]) == 1
        hist = store.history(broker_slug="xm")
        assert hist
        assert hist[0]["result"] == "certified"
        assert hist[0]["tester"] == "qa"


@pytest.mark.unit
class TestBrokerConnectivityCertificationApi:
    def test_dashboard_and_run(self) -> None:
        svc = BrokerConnectivityService.create(mt5=None, paper_available=False)
        dash = svc.certification_dashboard()
        assert dash["title"]
        assert len(dash["pending_brokers"]) == 5
        assert dash["certified_brokers"] == []
        run = svc.run_certification(tester="ops")
        assert run["pending"]
        assert svc.certification_history()["items"]
        full = svc.dashboard()
        assert "certification" in full
