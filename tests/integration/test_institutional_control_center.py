"""Integration — ICC read-only guarantees."""

from __future__ import annotations

import pytest

import app.application.services.institutional_control_center as icc

pytestmark = pytest.mark.integration


def test_module_is_read_only() -> None:
    assert "never" in (icc.__doc__ or "").lower()
    assert callable(icc.build_institutional_control_center)


def test_build_never_influences_trading() -> None:
    payload = icc.build_institutional_control_center()
    assert payload["influences_trading"] is False
    assert payload["mutates_engines"] is False
    assert payload["analytics_only"] is True


def test_alerts_active_only() -> None:
    payload = icc.build_institutional_control_center()
    alerts = payload["sections"]["alerts"]["alerts"]
    assert all(a.get("active") for a in alerts)
