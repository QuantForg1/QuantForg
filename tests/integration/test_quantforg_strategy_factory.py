"""Integration — QSF preserves safety guarantees; human-gated transitions only."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.application.services import quantforg_strategy_factory as svc
from app.domain.quantforg_strategy_factory.models import INTEGRATIONS, ISOLATION_FLAGS
from app.domain.quantforg_strategy_factory.platform import QuantForgStrategyFactory
from app.domain.quantforg_strategy_factory.store import QsfStore
from app.main import _ROUTER_SPECS

pytestmark = pytest.mark.integration


def test_router_registered() -> None:
    assert "quantforg_strategy_factory" in {n for n, _ in _ROUTER_SPECS}


def test_isolation_flags() -> None:
    assert ISOLATION_FLAGS["executes_trades"] is False
    assert ISOLATION_FLAGS["modifies_production"] is False
    assert ISOLATION_FLAGS["approves_releases"] is False
    assert ISOLATION_FLAGS["deploys_strategies"] is False
    assert ISOLATION_FLAGS["allocates_capital"] is False
    assert ISOLATION_FLAGS["human_approval_required_for_transitions"] is True
    assert ISOLATION_FLAGS["preserves_existing_safety_guarantees"] is True


def test_service_dashboard_and_approve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    qsf = QuantForgStrategyFactory(store=QsfStore(path=tmp_path / "qsf.json"))
    monkeypatch.setattr("app.domain.quantforg_strategy_factory._QSF", qsf)
    monkeypatch.setattr(svc, "get_qsf", lambda: qsf)
    monkeypatch.setattr(
        "app.domain.quantforg_strategy_factory.platform.gather_factory_sources",
        lambda: {
            "sources": {
                **{s: {} for s in INTEGRATIONS},
                "islm": {
                    "registry": [
                        {
                            "strategy_id": "st1",
                            "name": "Alpha",
                            "lifecycle_state": "Idea",
                            "owner": "desk",
                        }
                    ],
                    "approvals": [],
                },
            },
            "availability": {s: False for s in INTEGRATIONS},
            "source_count": 0,
            "read_only": True,
        },
    )
    payload = svc.build_qsf_dashboard()
    assert payload["never_executes_trades"] is True
    assert payload["never_modifies_production"] is True
    assert payload["never_approves_releases"] is True
    assert payload["never_deploys_strategies"] is True
    assert payload["never_allocates_capital"] is True
    assert payload["preserves_existing_safety_guarantees"] is True
    assert payload["human_approval_required_for_transitions"] is True
    assert payload["workflow_consistency"]["ok"] is True
    assert payload["evidence_integrity"]["ok"] is True

    item = payload["work_items"][0]
    approved = svc.qsf_approve_transition(
        strategy_id="st1",
        to_stage=item["next_stage"],
        approver="integration-tester",
        decision="approved",
        work_item_id=item["work_item_id"],
    )
    assert approved["never_deploys_strategies"] is True
    assert approved["human_explicit"] is True
    assert approved["approval"]["decision"] == "approved"
