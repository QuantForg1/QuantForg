"""Integration — RES never modifies production."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.application.services import reliability_engineering_suite as svc
from app.domain.reliability_engineering_suite.models import ISOLATION_FLAGS
from app.domain.reliability_engineering_suite.platform import ReliabilityEngineeringSuite
from app.domain.reliability_engineering_suite.store import ResStore
from app.main import _ROUTER_SPECS

pytestmark = pytest.mark.integration


def test_router_registered() -> None:
    assert "reliability_engineering_suite" in {n for n, _ in _ROUTER_SPECS}


def test_isolation_flags() -> None:
    assert ISOLATION_FLAGS["mutates_production"] is False
    assert ISOLATION_FLAGS["executes_trades"] is False
    assert ISOLATION_FLAGS["modifies_strategy"] is False
    assert ISOLATION_FLAGS["modifies_thresholds"] is False
    assert ISOLATION_FLAGS["modifies_risk"] is False
    assert ISOLATION_FLAGS["modifies_safety"] is False
    assert ISOLATION_FLAGS["modifies_oms"] is False
    assert ISOLATION_FLAGS["modifies_gateway"] is False
    assert ISOLATION_FLAGS["modifies_scheduler"] is False
    assert ISOLATION_FLAGS["triggers_automation"] is False


def test_service_dashboard_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    res = ReliabilityEngineeringSuite(store=ResStore(path=tmp_path / "res.json"))
    monkeypatch.setattr("app.domain.reliability_engineering_suite._RES", res)
    monkeypatch.setattr(svc, "get_res", lambda: res)
    monkeypatch.setattr(
        "app.domain.reliability_engineering_suite.platform.gather_reliability_sources",
        lambda: {
            "sources": {
                "idw": {},
                "icc": {},
                "diagnostics": {},
                "audit": [],
                "eqs": {},
                "qkg": {},
                "rc1": {},
                "live_metrics": {},
            },
            "availability": {"icc": True},
            "source_count": 1,
            "read_only": True,
        },
    )
    payload = svc.build_res_dashboard()
    assert payload["never_modifies_production"] is True
    assert payload["never_executes_trades"] is True
    assert payload["influences_trading"] is False
    assert payload["mutates_engines"] is False
