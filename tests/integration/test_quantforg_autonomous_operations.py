"""Integration — AOC preserves all existing safety guarantees."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.application.services import quantforg_autonomous_operations as svc
from app.domain.quantforg_autonomous_operations.models import (
    DATA_SOURCES,
    ISOLATION_FLAGS,
)
from app.domain.quantforg_autonomous_operations.platform import (
    QuantForgAutonomousOperationsCenter,
)
from app.domain.quantforg_autonomous_operations.store import AocStore
from app.main import _ROUTER_SPECS

pytestmark = pytest.mark.integration


def test_router_registered() -> None:
    assert "quantforg_autonomous_operations" in {n for n, _ in _ROUTER_SPECS}


def test_isolation_flags() -> None:
    assert ISOLATION_FLAGS["executes_trades"] is False
    assert ISOLATION_FLAGS["modifies_production"] is False
    assert ISOLATION_FLAGS["modifies_strategies"] is False
    assert ISOLATION_FLAGS["modifies_risk"] is False
    assert ISOLATION_FLAGS["modifies_safety"] is False
    assert ISOLATION_FLAGS["approves_releases"] is False
    assert ISOLATION_FLAGS["allocates_capital"] is False
    assert ISOLATION_FLAGS["deploys_strategies"] is False
    assert ISOLATION_FLAGS["performs_automatic_remediation"] is False
    assert ISOLATION_FLAGS["human_approval_required_for_recommendations"] is True
    assert ISOLATION_FLAGS["preserves_existing_safety_guarantees"] is True


def test_service_dashboard_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    aoc = QuantForgAutonomousOperationsCenter(
        store=AocStore(path=tmp_path / "aoc.json")
    )
    monkeypatch.setattr("app.domain.quantforg_autonomous_operations._AOC", aoc)
    monkeypatch.setattr(svc, "get_aoc", lambda: aoc)
    monkeypatch.setattr(
        "app.domain.quantforg_autonomous_operations.platform.gather_operations_sources",
        lambda: {
            "sources": {s: {} for s in DATA_SOURCES},
            "availability": {s: False for s in DATA_SOURCES},
            "source_count": 0,
            "read_only": True,
        },
    )
    payload = svc.build_aoc_dashboard()
    assert payload["never_executes_trades"] is True
    assert payload["never_modifies_production"] is True
    assert payload["never_modifies_strategies"] is True
    assert payload["never_modifies_risk"] is True
    assert payload["never_modifies_safety"] is True
    assert payload["never_approves_releases"] is True
    assert payload["never_allocates_capital"] is True
    assert payload["never_deploys_strategies"] is True
    assert payload["never_performs_automatic_remediation"] is True
    assert payload["human_approval_required_for_recommendations"] is True
    assert payload["preserves_existing_safety_guarantees"] is True
    assert payload["mutates_engines"] is False
    assert payload["executive_scores"]
