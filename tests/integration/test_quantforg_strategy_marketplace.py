"""Integration — QSMR never modifies production."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.application.services import quantforg_strategy_marketplace as svc
from app.domain.quantforg_strategy_marketplace.models import ISOLATION_FLAGS
from app.domain.quantforg_strategy_marketplace.platform import (
    QuantForgStrategyMarketplace,
)
from app.domain.quantforg_strategy_marketplace.store import QsmrStore
from app.main import _ROUTER_SPECS

pytestmark = pytest.mark.integration


def test_router_registered() -> None:
    assert "quantforg_strategy_marketplace" in {n for n, _ in _ROUTER_SPECS}


def test_isolation_flags() -> None:
    assert ISOLATION_FLAGS["executes_trades"] is False
    assert ISOLATION_FLAGS["modifies_strategies"] is False
    assert ISOLATION_FLAGS["modifies_production"] is False
    assert ISOLATION_FLAGS["approves_certifications"] is False
    assert ISOLATION_FLAGS["deploys_strategies"] is False
    assert ISOLATION_FLAGS["registry_read_only"] is True


def test_service_dashboard_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    qsmr = QuantForgStrategyMarketplace(
        store=QsmrStore(path=tmp_path / "qsmr.json")
    )
    monkeypatch.setattr("app.domain.quantforg_strategy_marketplace._QSMR", qsmr)
    monkeypatch.setattr(svc, "get_qsmr", lambda: qsmr)
    monkeypatch.setattr(
        "app.domain.quantforg_strategy_marketplace.platform.gather_marketplace_sources",
        lambda: {
            "sources": {
                "islm": {"registry": [], "approvals": []},
                "irl": {"experiments": [], "leaderboard": {}},
                "ise": {"simulations": []},
                "cvf": {},
                "irap": {},
                "eqs": {},
                "qcs": {},
                "irdp": {"releases": []},
                "iep": {"registry": []},
                "aqs": {"recommendations": []},
                "qkg": {},
                "portfolio": {},
            },
            "availability": {"islm": True},
            "source_count": 1,
            "read_only": True,
        },
    )
    payload = svc.build_qsmr_dashboard()
    assert payload["never_executes_trades"] is True
    assert payload["never_modifies_strategies"] is True
    assert payload["never_modifies_production"] is True
    assert payload["never_approves_certifications"] is True
    assert payload["never_deploys_strategies"] is True
    assert payload["mutates_engines"] is False
    assert payload["registry"]
