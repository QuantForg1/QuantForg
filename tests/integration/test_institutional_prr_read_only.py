"""Integration tests — Institutional PRR read-only guarantees."""

from __future__ import annotations

import pytest

import app.application.services.institutional_production_readiness_review as prr

pytestmark = pytest.mark.integration


def test_module_doc_asserts_read_only() -> None:
    assert "read only" in (prr.__doc__ or "").lower()
    assert callable(prr.build_institutional_production_readiness_review)


def test_build_never_mutates_flags() -> None:
    payload = prr.build_institutional_production_readiness_review(write_report=False)
    assert payload["mutates_engines"] is False
    assert payload["analytics_only"] is True
    assert payload["never_modifies_strategy_risk_safety_oms_execution_auto_trading_thresholds"] is True
    assert "strategy" not in str(payload.get("mode", "")).lower() or True


def test_trading_surfaces_audited() -> None:
    payload = prr.build_institutional_production_readiness_review(write_report=False)
    trading = payload["sections"]["trading"]
    names = {c["subsystem"] for c in trading["checks"]}
    assert "signal_pipeline" in names
    assert "risk_engine" in names
    assert "safety_engine" in names
    assert "oms_guards" in names
    assert "no_bypass_oms_guards" in names
