"""Integration — QPM never modifies production."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.application.services import quantforg_portfolio_manager as svc
from app.domain.quantforg_portfolio_manager.models import ISOLATION_FLAGS
from app.domain.quantforg_portfolio_manager.platform import QuantForgPortfolioManager
from app.domain.quantforg_portfolio_manager.store import QpmStore
from app.main import _ROUTER_SPECS

pytestmark = pytest.mark.integration


def test_router_registered() -> None:
    assert "quantforg_portfolio_manager" in {n for n, _ in _ROUTER_SPECS}


def test_isolation_flags() -> None:
    assert ISOLATION_FLAGS["executes_trades"] is False
    assert ISOLATION_FLAGS["modifies_production"] is False
    assert ISOLATION_FLAGS["changes_strategy_parameters"] is False
    assert ISOLATION_FLAGS["rebalances_automatically"] is False
    assert ISOLATION_FLAGS["allocates_capital_automatically"] is False
    assert ISOLATION_FLAGS["human_approval_required_for_actions"] is True
    assert ISOLATION_FLAGS["portfolio_orchestration_read_only"] is True


def test_service_dashboard_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    qpm = QuantForgPortfolioManager(store=QpmStore(path=tmp_path / "qpm.json"))
    monkeypatch.setattr("app.domain.quantforg_portfolio_manager._QPM", qpm)
    monkeypatch.setattr(svc, "get_qpm", lambda: qpm)
    monkeypatch.setattr(
        "app.domain.quantforg_portfolio_manager.platform.gather_portfolio_sources",
        lambda: {
            "sources": {
                "qsmr": {
                    "registry": [
                        {
                            "strategy_id": "x1",
                            "strategy_name": "X",
                            "status": "Active",
                            "lifecycle": "Monitoring",
                            "certification_status": "Staging Ready",
                            "scores": {"overall_strategy_score": 70},
                        }
                    ]
                },
                "irap": {"metrics": {"sharpe_ratio": 0.9, "maximum_drawdown": 12}},
                "cvf": {"confidence": {"confidence": 60}},
                "ise": {"simulations": []},
                "iep": {"registry": []},
                "islm": {"registry": []},
                "eqs": {},
                "res": {},
                "qcs": {"level": {"level": "Staging Ready"}, "scores": {}},
                "icp": {},
            },
            "availability": {"qsmr": True},
            "source_count": 1,
            "read_only": True,
        },
    )
    payload = svc.build_qpm_dashboard()
    assert payload["never_executes_trades"] is True
    assert payload["never_modifies_production"] is True
    assert payload["never_changes_strategy_parameters"] is True
    assert payload["never_rebalances_automatically"] is True
    assert payload["never_allocates_capital_automatically"] is True
    assert payload["human_approval_required_for_actions"] is True
    assert payload["mutates_engines"] is False
    assert payload["metrics"]
    assert payload["strategy_ranking"]
