"""Integration — EQS never modifies production."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.application.services import execution_quality_suite as svc
from app.domain.execution_quality_suite.models import ISOLATION_FLAGS
from app.domain.execution_quality_suite.platform import ExecutionQualitySuite
from app.domain.execution_quality_suite.store import EqsStore
from app.main import _ROUTER_SPECS

pytestmark = pytest.mark.integration


def test_router_registered() -> None:
    assert "execution_quality_suite" in {n for n, _ in _ROUTER_SPECS}


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
    assert ISOLATION_FLAGS["modifies_research"] is False
    assert ISOLATION_FLAGS["triggers_automation"] is False


def test_service_dashboard_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    eqs = ExecutionQualitySuite(store=EqsStore(path=tmp_path / "eqs.json"))
    monkeypatch.setattr("app.domain.execution_quality_suite._EQS", eqs)
    monkeypatch.setattr(svc, "get_eqs", lambda: eqs)
    monkeypatch.setattr(
        "app.domain.execution_quality_suite.platform.gather_execution_sources",
        lambda: {
            "sources": {
                "journal": [],
                "idw": {},
                "icc": {},
                "portfolio": {},
                "diagnostics": {},
                "audit": [],
                "qkg": {},
                "live_metrics": {},
                "rc1": {},
            },
            "availability": {"journal": True},
            "source_count": 1,
            "read_only": True,
        },
    )
    payload = svc.build_eqs_dashboard()
    assert payload["never_modifies_production"] is True
    assert payload["never_executes_trades"] is True
    assert payload["influences_trading"] is False
    assert payload["mutates_engines"] is False
