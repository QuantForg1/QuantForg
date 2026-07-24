"""Integration — QPTCM preserves safety; human-gated lifecycle only."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.application.services import quantforg_paper_trading_campaign as svc
from app.domain.quantforg_paper_trading_campaign.models import (
    DATA_SOURCES,
    ISOLATION_FLAGS,
)
from app.domain.quantforg_paper_trading_campaign.platform import (
    QuantForgPaperTradingCampaignManager,
)
from app.domain.quantforg_paper_trading_campaign.store import QptcmStore
from app.main import _ROUTER_SPECS

pytestmark = pytest.mark.integration


def test_router_registered() -> None:
    assert "quantforg_paper_trading_campaign" in {n for n, _ in _ROUTER_SPECS}


def test_isolation_flags() -> None:
    assert ISOLATION_FLAGS["places_live_trades"] is False
    assert ISOLATION_FLAGS["modifies_production"] is False
    assert ISOLATION_FLAGS["allocates_capital"] is False
    assert ISOLATION_FLAGS["approves_graduation_automatically"] is False
    assert ISOLATION_FLAGS["human_approval_required_for_transitions"] is True
    assert ISOLATION_FLAGS["preserves_existing_safety_guarantees"] is True


def test_service_dashboard_and_approve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mgr = QuantForgPaperTradingCampaignManager(
        store=QptcmStore(path=tmp_path / "qptcm.json")
    )
    monkeypatch.setattr("app.domain.quantforg_paper_trading_campaign._QPTCM", mgr)
    monkeypatch.setattr(svc, "get_qptcm", lambda: mgr)
    monkeypatch.setattr(
        "app.domain.quantforg_paper_trading_campaign.platform.gather_campaign_sources",
        lambda: {
            "sources": {
                **{s: {} for s in DATA_SOURCES},
                "islm": {
                    "registry": [
                        {
                            "strategy_id": "st1",
                            "name": "Alpha",
                            "lifecycle_state": "Draft",
                            "owner": "desk",
                        }
                    ],
                    "approvals": [],
                },
                "qcs": {"scores": {"overall_institutional_readiness_score": 40}},
            },
            "availability": {s: False for s in DATA_SOURCES},
            "source_count": 0,
            "read_only": True,
        },
    )
    payload = svc.build_qptcm_dashboard()
    assert payload["never_places_live_trades"] is True
    assert payload["never_modifies_production"] is True
    assert payload["never_allocates_capital"] is True
    assert payload["never_approves_graduation_automatically"] is True
    assert payload["preserves_existing_safety_guarantees"] is True
    assert payload["workflow_consistency"]["ok"] is True
    assert payload["evidence_integrity"]["ok"] is True

    c = payload["campaigns"][0]
    approved = svc.qptcm_approve_transition(
        campaign_id=c["campaign_id"],
        to_state=c["next_lifecycle"],
        approver="integration-tester",
        decision="approved",
    )
    assert approved["never_places_live_trades"] is True
    assert approved["human_explicit"] is True
    assert approved["live_deployment_blocked"] is True
