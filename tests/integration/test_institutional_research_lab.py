"""Integration — IRL isolation from production trading."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.application.services import institutional_research_lab as svc
from app.domain.institutional_research_lab.platform import InstitutionalResearchLab
from app.domain.institutional_research_lab.store import IrlStore
from app.main import _ROUTER_SPECS

pytestmark = pytest.mark.integration


def test_router_registered() -> None:
    names = [n for n, _ in _ROUTER_SPECS]
    assert "institutional_research_lab" in names
    mod = dict(_ROUTER_SPECS)["institutional_research_lab"]
    assert mod == "app.presentation.routers.institutional_research_lab"


def test_service_isolation_payload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lab = InstitutionalResearchLab(store=IrlStore(path=tmp_path / "irl.json"))
    monkeypatch.setattr(
        "app.domain.institutional_research_lab._LAB",
        lab,
    )
    monkeypatch.setattr(svc, "get_irl", lambda: lab)

    dash = svc.build_irl_dashboard()
    assert dash["mutates_engines"] is False
    assert dash["never_modifies_strategy_risk_safety_oms_execution_auto_trading_thresholds"] is True
    assert dash["isolation"]["executes_live_trades"] is False
    assert dash["isolation"]["writes_production_tables"] is False

    exp = svc.irl_create_experiment(name="integ", author="ci")
    result = svc.irl_run_replay(experiment_id=exp["uuid"], window="30d")
    assert result["isolation"]["never_auto_promotes"] is True
    assert result["report"]["verdict"]["promotion_requires_governance_workflow"] is True
