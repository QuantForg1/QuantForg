"""Unit tests — Institutional Control Center (read-only)."""

from __future__ import annotations

import time

import pytest

from app.application.services.institutional_control_center import (
    ARCHITECTURE_NODES,
    build_institutional_control_center,
    section_architecture,
    section_system_status,
)

pytestmark = pytest.mark.unit


class TestInstitutionalControlCenter:
    def test_build_payload_flags_and_sections(self) -> None:
        payload = build_institutional_control_center()
        assert payload["mutates_engines"] is False
        assert payload["influences_trading"] is False
        assert payload["advisory_only"] is True
        assert payload[
            "never_modifies_strategy_risk_safety_oms_gateway_auto_trading_thresholds_research_warehouse"
        ] is True
        sections = payload["sections"]
        for key in (
            "system_status",
            "live_trading",
            "portfolio",
            "research",
            "analytics",
            "data_warehouse",
            "alerts",
            "operational_timeline",
            "executive_kpis",
            "architecture",
        ):
            assert key in sections

        system = sections["system_status"]
        names = {s["name"] for s in system["subsystems"]}
        for required in (
            "Trading Engine",
            "Risk Engine",
            "Safety Engine",
            "OMS",
            "Gateway",
            "Broker",
            "Scheduler",
            "Research Lab",
            "Data Warehouse",
        ):
            assert required in names
        assert system["overall"] in {"PASS", "WARNING", "FAIL"}

        kpis = sections["executive_kpis"]
        for k in (
            "overall_platform_health",
            "trading_readiness",
            "operational_stability",
            "research_progress",
            "data_integrity",
            "system_availability",
        ):
            assert k in kpis

        assert sections["live_trading"]["symbol"] == "XAUUSD"
        assert sections["architecture"]["clickable"] is True
        assert len(ARCHITECTURE_NODES) >= 10

    def test_architecture_groups(self) -> None:
        arch = section_architecture()
        assert "Trading Core" in arch["groups"]
        assert "Data Warehouse" in arch["groups"]

    def test_system_status_shape(self) -> None:
        system = section_system_status()
        assert "counts" in system
        assert system["counts"]["total"] == len(system["subsystems"])

    def test_performance_budget(self) -> None:
        t0 = time.perf_counter()
        payload = build_institutional_control_center()
        elapsed = time.perf_counter() - t0
        assert payload["elapsed_ms"] is not None
        assert elapsed < 45.0
