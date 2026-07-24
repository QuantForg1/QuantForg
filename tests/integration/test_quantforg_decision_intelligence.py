"""Integration — QDIE is advisory and never modifies production."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.application.services import quantforg_decision_intelligence as svc
from app.domain.quantforg_decision_intelligence.models import (
    DATA_SOURCES,
    ISOLATION_FLAGS,
)
from app.domain.quantforg_decision_intelligence.platform import (
    QuantForgDecisionIntelligenceEngine,
)
from app.domain.quantforg_decision_intelligence.store import QdieStore
from app.main import _ROUTER_SPECS

pytestmark = pytest.mark.integration


def test_router_registered() -> None:
    assert "quantforg_decision_intelligence" in {n for n, _ in _ROUTER_SPECS}


def test_isolation_flags() -> None:
    assert ISOLATION_FLAGS["executes_trades"] is False
    assert ISOLATION_FLAGS["modifies_production"] is False
    assert ISOLATION_FLAGS["modifies_strategies"] is False
    assert ISOLATION_FLAGS["modifies_risk"] is False
    assert ISOLATION_FLAGS["approves_releases"] is False
    assert ISOLATION_FLAGS["allocates_capital"] is False
    assert ISOLATION_FLAGS["performs_automatic_actions"] is False
    assert ISOLATION_FLAGS["human_approval_required"] is True
    assert ISOLATION_FLAGS["advisory_only"] is True


def test_service_dashboard_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    qdie = QuantForgDecisionIntelligenceEngine(
        store=QdieStore(path=tmp_path / "qdie.json")
    )
    monkeypatch.setattr("app.domain.quantforg_decision_intelligence._QDIE", qdie)
    monkeypatch.setattr(svc, "get_qdie", lambda: qdie)
    monkeypatch.setattr(
        "app.domain.quantforg_decision_intelligence.platform.gather_decision_sources",
        lambda: {
            "sources": {s: {} for s in DATA_SOURCES},
            "availability": {s: False for s in DATA_SOURCES},
            "source_count": 0,
            "read_only": True,
        },
    )
    payload = svc.build_qdie_dashboard()
    assert payload["never_executes_trades"] is True
    assert payload["never_modifies_production"] is True
    assert payload["never_modifies_strategies"] is True
    assert payload["never_modifies_risk"] is True
    assert payload["never_approves_releases"] is True
    assert payload["never_allocates_capital"] is True
    assert payload["never_performs_automatic_actions"] is True
    assert payload["human_approval_required"] is True
    assert payload["advisory_only"] is True
    assert payload["mutates_engines"] is False
    assert payload["decision_consistency"]["ok"] is True
    assert payload["evidence_consistency"]["ok"] is True
    assert payload["explainability_validation"]["ok"] is True
    assert payload["recommendations"]
    assert payload["scores"]
