"""Integration — IRAP never modifies production."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.application.services import institutional_risk_analytics as svc
from app.domain.institutional_risk_analytics.models import ISOLATION_FLAGS
from app.domain.institutional_risk_analytics.platform import InstitutionalRiskAnalytics
from app.domain.institutional_risk_analytics.store import IrapStore
from app.main import _ROUTER_SPECS

pytestmark = pytest.mark.integration


def test_router_registered() -> None:
    assert "institutional_risk_analytics" in {n for n, _ in _ROUTER_SPECS}


def test_isolation_flags() -> None:
    assert ISOLATION_FLAGS["mutates_production"] is False
    assert ISOLATION_FLAGS["executes_trades"] is False
    assert ISOLATION_FLAGS["modifies_strategy"] is False
    assert ISOLATION_FLAGS["modifies_risk_parameters"] is False
    assert ISOLATION_FLAGS["modifies_safety"] is False
    assert ISOLATION_FLAGS["approves_releases"] is False


def test_service_dashboard_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    irap = InstitutionalRiskAnalytics(store=IrapStore(path=tmp_path / "irap.json"))
    monkeypatch.setattr("app.domain.institutional_risk_analytics._IRAP", irap)
    monkeypatch.setattr(svc, "get_irap", lambda: irap)
    monkeypatch.setattr(
        "app.domain.institutional_risk_analytics.platform.gather_risk_sources",
        lambda: {
            "sources": {
                "portfolio": {},
                "idw": {"trades": []},
                "ise": {"simulations": []},
                "cvf": {},
                "eqs": {},
                "res": {},
                "qkg": {},
                "sic": {},
            },
            "availability": {"portfolio": True},
            "source_count": 1,
            "read_only": True,
        },
    )
    payload = svc.build_irap_dashboard()
    assert payload["never_modifies_production"] is True
    assert payload["never_executes_trades"] is True
    assert payload["never_modifies_risk_parameters"] is True
    assert payload["influences_trading"] is False
    assert payload["mutates_engines"] is False
