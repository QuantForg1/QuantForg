"""Unit tests — QuantForg Paper Trading Campaign Manager."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.domain.quantforg_paper_trading_campaign.analytics import (
    build_campaigns,
    build_daily_timeline,
    build_graduation_workspace,
    evidence_integrity_check,
    next_lifecycle,
    workflow_consistency_check,
)
from app.domain.quantforg_paper_trading_campaign.models import (
    CAMPAIGN_LIFECYCLE,
    CampaignLifecycle,
    DATA_SOURCES,
    ISOLATION_FLAGS,
)
from app.domain.quantforg_paper_trading_campaign.platform import (
    QuantForgPaperTradingCampaignManager,
)
from app.domain.quantforg_paper_trading_campaign.store import QptcmStore

pytestmark = pytest.mark.unit


def _ctx() -> dict:
    return {
        "sources": {
            "qsf": {"work_item_count": 1},
            "islm": {
                "registry": [
                    {
                        "strategy_id": "st1",
                        "name": "Alpha Paper",
                        "lifecycle_state": "Paper Trading Ready",
                        "owner": "desk",
                        "market": "EURUSD",
                    }
                ],
                "approvals": [],
            },
            "qcs": {
                "scores": {"overall_institutional_readiness_score": 62},
                "level": {"level": "Ready"},
            },
            "qdie": {},
            "qsmr": {},
            "irap": {"alerts": [{"kind": "drawdown", "severity": "warning"}]},
            "eqs": {"execution_score": {"overall_execution_score": 70}},
            "res": {},
            "cvf": {},
            "qem": {},
            "qcdm": {},
        },
        "availability": {s: True for s in DATA_SOURCES},
        "source_count": len(DATA_SOURCES),
        "read_only": True,
    }


class TestIsolation:
    def test_flags(self) -> None:
        assert ISOLATION_FLAGS["places_live_trades"] is False
        assert ISOLATION_FLAGS["executes_trades"] is False
        assert ISOLATION_FLAGS["modifies_production"] is False
        assert ISOLATION_FLAGS["allocates_capital"] is False
        assert ISOLATION_FLAGS["approves_graduation_automatically"] is False
        assert ISOLATION_FLAGS["human_approval_required_for_transitions"] is True
        assert ISOLATION_FLAGS["preserves_existing_safety_guarantees"] is True
        assert ISOLATION_FLAGS["paper_trading_only"] is True


class TestWorkflow:
    def test_campaigns_consistency(self) -> None:
        campaigns = build_campaigns(_ctx())
        assert campaigns
        assert all(c.get("never_places_live_trades") for c in campaigns)
        assert all(c.get("graduation_auto_approved") is False for c in campaigns)
        assert all(c.get("lifecycle") in CAMPAIGN_LIFECYCLE for c in campaigns)
        assert workflow_consistency_check(campaigns)["ok"] is True
        assert evidence_integrity_check(campaigns)["ok"] is True
        assert build_daily_timeline(campaigns)
        assert next_lifecycle(CampaignLifecycle.DRAFT.value) == CampaignLifecycle.CONFIGURED.value
        assert next_lifecycle(CampaignLifecycle.GRADUATION_CANDIDATE.value) is None


class TestHumanApproval:
    def test_approve(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mgr = QuantForgPaperTradingCampaignManager(
            store=QptcmStore(path=tmp_path / "qptcm.json")
        )
        monkeypatch.setattr(
            "app.domain.quantforg_paper_trading_campaign.platform.gather_campaign_sources",
            _ctx,
        )
        pack = mgr.dashboard()
        c = pack["campaigns"][0]
        to_state = c["next_lifecycle"]
        assert to_state
        result = mgr.approve_transition(
            campaign_id=c["campaign_id"],
            to_state=to_state,
            approver="tester",
            decision="approved",
        )
        assert result["human_explicit"] is True
        assert result["never_places_live_trades"] is True
        assert result["never_approves_graduation_automatically"] is True
        assert result["live_deployment_blocked"] is True
        assert result["campaign"]["lifecycle"] == to_state


class TestPlatform:
    def test_dashboard(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mgr = QuantForgPaperTradingCampaignManager(
            store=QptcmStore(path=tmp_path / "qptcm.json")
        )
        monkeypatch.setattr(
            "app.domain.quantforg_paper_trading_campaign.platform.gather_campaign_sources",
            _ctx,
        )
        t0 = time.perf_counter()
        pack = mgr.dashboard()
        elapsed = (time.perf_counter() - t0) * 1000.0
        assert pack["never_places_live_trades"] is True
        assert pack["never_modifies_production"] is True
        assert pack["never_allocates_capital"] is True
        assert pack["never_approves_graduation_automatically"] is True
        assert pack["preserves_existing_safety_guarantees"] is True
        assert pack["workflow_consistency"]["ok"] is True
        assert pack["evidence_integrity"]["ok"] is True
        assert pack["sections"]["campaign_dashboard"]
        assert pack["sections"]["campaign_explorer"]
        assert pack["sections"]["daily_timeline"]
        assert pack["sections"]["evidence_center"]
        assert pack["sections"]["graduation_workspace"]
        assert build_graduation_workspace(pack["campaigns"])
        assert pack["elapsed_ms"] < 500
        assert elapsed < 2000
