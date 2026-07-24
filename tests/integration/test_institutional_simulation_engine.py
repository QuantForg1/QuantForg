"""Integration — ISE never modifies production."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.application.services import institutional_simulation_engine as svc
from app.domain.institutional_simulation_engine.models import ISOLATION_FLAGS
from app.domain.institutional_simulation_engine.platform import (
    InstitutionalSimulationEngine,
)
from app.domain.institutional_simulation_engine.store import IseStore
from app.main import _ROUTER_SPECS

pytestmark = pytest.mark.integration


def test_router_registered() -> None:
    assert "institutional_simulation_engine" in {n for n, _ in _ROUTER_SPECS}


def test_isolation_flags() -> None:
    assert ISOLATION_FLAGS["mutates_production"] is False
    assert ISOLATION_FLAGS["executes_trades"] is False
    assert ISOLATION_FLAGS["modifies_strategies"] is False
    assert ISOLATION_FLAGS["modifies_thresholds"] is False
    assert ISOLATION_FLAGS["modifies_risk"] is False
    assert ISOLATION_FLAGS["modifies_safety"] is False
    assert ISOLATION_FLAGS["modifies_oms"] is False
    assert ISOLATION_FLAGS["modifies_gateway"] is False
    assert ISOLATION_FLAGS["modifies_scheduler"] is False


def test_service_dashboard_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ise = InstitutionalSimulationEngine(store=IseStore(path=tmp_path / "ise.json"))
    monkeypatch.setattr("app.domain.institutional_simulation_engine._ISE", ise)
    monkeypatch.setattr(svc, "get_ise", lambda: ise)
    monkeypatch.setattr(
        "app.domain.institutional_simulation_engine.platform.gather_simulation_context",
        lambda: {
            "sources": {
                "idw": {},
                "portfolio": {
                    "trade_count": 20,
                    "sections": {
                        "performance": {
                            "profit_factor": 1.5,
                            "win_rate_pct": 50,
                            "trade_count": 20,
                        },
                        "risk": {"max_drawdown_pct": 8},
                        "behavior": {},
                    },
                },
                "irl": {},
                "regime": {},
            },
            "availability": {"portfolio": True},
            "source_count": 1,
            "read_only": True,
            "digital_twin": True,
        },
    )
    payload = svc.build_ise_dashboard()
    assert payload["never_modifies_production"] is True
    assert payload["never_executes_trades"] is True
    assert payload["digital_twin"] is True
    assert payload["mutates_engines"] is False
