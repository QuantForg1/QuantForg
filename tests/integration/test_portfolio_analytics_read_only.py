"""Integration tests — Portfolio Analytics read-only guarantees."""

from __future__ import annotations

import pytest

import app.application.services.institutional_portfolio_analytics as ipa

pytestmark = pytest.mark.integration


def test_service_module_read_only_flags_present() -> None:
    assert hasattr(ipa, "analyze_portfolio")
    assert hasattr(ipa, "build_institutional_portfolio_analytics")
    assert "never modifies" in (ipa.__doc__ or "").lower()


def test_analyze_portfolio_never_modifies_flags() -> None:
    payload = ipa.analyze_portfolio([], starting_equity=10_000.0)
    assert payload["mutates_engines"] is False
    assert payload["analytics_only"] is True
    assert payload["never_modifies_strategy_risk_safety_oms_execution_auto_trading_thresholds"] is True
