"""Unit tests for MT5 Broker Ecosystem compatibility (no simulated venues)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from app.application.services.broker_connectivity import BrokerConnectivityService
from app.domain.broker_connectivity.compatibility import run_compatibility_suite
from app.domain.broker_connectivity.mt5_ecosystem import (
    MT5_ECOSYSTEM,
    match_broker_for_server,
    profile_by_slug,
)
from app.domain.broker_connectivity.types import ConnectivityStatus


@pytest.mark.unit
class TestMT5EcosystemProfiles:
    def test_priority_brokers_present(self) -> None:
        slugs = {p.slug for p in MT5_ECOSYSTEM}
        assert slugs == {
            "weltrade",
            "xm",
            "exness",
            "ic-markets",
            "pepperstone",
        }

    def test_all_mt5_platform(self) -> None:
        assert all(p.platform == "mt5" for p in MT5_ECOSYSTEM)

    def test_onboarding_steps_present(self) -> None:
        for p in MT5_ECOSYSTEM:
            assert len(p.onboarding) >= 5
            assert profile_by_slug(p.slug) is p

    def test_server_match_xm(self) -> None:
        hit = match_broker_for_server("XMGlobal-MT5 5")
        assert hit is not None
        assert hit.slug == "xm"

    def test_server_match_ic_markets(self) -> None:
        hit = match_broker_for_server("ICMarketsSC-MT5-2")
        assert hit is not None
        assert hit.slug == "ic-markets"

    def test_unknown_server(self) -> None:
        assert match_broker_for_server("UnknownBroker-Live") is None


@pytest.mark.unit
class TestCompatibilitySuite:
    def test_pending_when_disconnected(self) -> None:
        def invoke(platform: str, capability: str, **_: Any) -> dict[str, Any]:
            assert platform == "mt5"
            if capability == "health":
                return {
                    "status": ConnectivityStatus.UNAVAILABLE.value,
                    "capability": "health",
                    "platform": "mt5",
                    "data": None,
                    "reason": "MT5 not connected",
                }
            return {
                "status": ConnectivityStatus.UNAVAILABLE.value,
                "capability": capability,
                "platform": "mt5",
            }

        suite = run_compatibility_suite(invoke=invoke, paper_available=False)
        assert suite["session"]["connected"] is False
        assert len(suite["matrix"]) == 5
        for row in suite["matrix"]:
            assert row["login"] == "pending_session"
            assert row["quotes"] == "pending_session"
            assert row["overall"] == "pending_session"

    def test_live_matched_brand_only(self) -> None:
        def invoke(platform: str, capability: str, **kwargs: Any) -> dict[str, Any]:
            _ = kwargs
            assert platform == "mt5"
            if capability == "health":
                return {
                    "status": ConnectivityStatus.OK.value,
                    "capability": "health",
                    "platform": "mt5",
                    "data": {"server": "Exness-MT5Real", "connected": True},
                }
            if capability == "trading":
                return {
                    "status": ConnectivityStatus.UNAVAILABLE.value,
                    "capability": "trading",
                    "platform": "mt5",
                    "reason": "execution disabled",
                }
            return {
                "status": ConnectivityStatus.OK.value,
                "capability": capability,
                "platform": "mt5",
                "data": {"balance": "1000", "equity": "1000", "items": []},
            }

        suite = run_compatibility_suite(invoke=invoke, paper_available=True)
        assert suite["session"]["matched_broker"] == "exness"
        by_slug = {r["slug"]: r for r in suite["matrix"]}
        assert by_slug["exness"]["login"] == "compatible"
        assert by_slug["exness"]["quotes"] == "compatible"
        assert by_slug["exness"]["paper_trading"] == "compatible"
        assert by_slug["exness"]["execution_checks"] == "compatible"
        assert by_slug["weltrade"]["login"] == "pending_session"
        assert by_slug["xm"]["balances"] == "pending_session"


@pytest.mark.unit
class TestBrokerConnectivityServiceEcosystem:
    def test_ecosystem_and_dashboard(self) -> None:
        svc = BrokerConnectivityService.create(mt5=None, paper_available=False)
        eco = svc.ecosystem()
        assert eco["version"] == "1.1"
        assert len(eco["items"]) == 5
        guide = svc.onboarding("pepperstone")
        assert guide is not None
        assert guide["slug"] == "pepperstone"
        assert len(guide["steps"]) >= 5
        dash = svc.compatibility_dashboard()
        assert "matrix" in dash
        assert "operator_actions" in dash

    def test_onboarding_unknown(self) -> None:
        svc = BrokerConnectivityService.create(mt5=None)
        assert svc.onboarding("nope") is None

    def test_create_with_mt5_still_registers(self) -> None:
        mt5 = MagicMock()
        mt5._live_session_ref = None
        mt5.client = MagicMock(is_connected=False)
        svc = BrokerConnectivityService.create(mt5=mt5)
        assert svc.get("mt5") is not None
        full = svc.dashboard()
        assert "ecosystem" in full
        assert "compatibility" in full
