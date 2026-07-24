"""Unit tests — QuantForg Strategy Factory."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.domain.quantforg_strategy_factory.analytics import (
    build_approval_queue,
    build_dossiers,
    build_pipeline_board,
    build_work_items,
    evidence_integrity_check,
    next_stage,
    workflow_consistency_check,
)
from app.domain.quantforg_strategy_factory.models import (
    INTEGRATIONS,
    ISOLATION_FLAGS,
    PIPELINE_STAGES,
    PipelineStage,
)
from app.domain.quantforg_strategy_factory.platform import QuantForgStrategyFactory
from app.domain.quantforg_strategy_factory.store import QsfStore

pytestmark = pytest.mark.unit


def _ctx() -> dict:
    return {
        "sources": {
            "irl": {"experiments": [{"experiment_id": "e0"}], "jobs": []},
            "iep": {
                "registry": [
                    {"experiment_id": "e1", "strategy_id": "st1", "status": "completed"}
                ],
                "snapshot": {},
            },
            "replay": {"simulations": []},
            "ise": {"simulations": [{"simulation_id": "s1", "mode": "Monte Carlo"}]},
            "cvf": {"confidence": {"confidence": 55}},
            "irap": {"alerts": [{"kind": "drawdown"}]},
            "qcs": {
                "level": {"level": "Not Ready"},
                "scores": {"overall_institutional_readiness_score": 52},
            },
            "qdie": {"recommendation_count": 2},
            "islm": {
                "registry": [
                    {
                        "strategy_id": "st1",
                        "name": "Alpha",
                        "lifecycle_state": "Research",
                        "owner": "desk",
                    }
                ],
                "approvals": [],
            },
            "qsmr": {},
            "qkg": {},
            "qem": {},
            "qcdm": {"schema_version": "1.0.0"},
        },
        "availability": {s: True for s in INTEGRATIONS},
        "source_count": len(INTEGRATIONS),
        "read_only": True,
    }


class TestIsolation:
    def test_flags(self) -> None:
        assert ISOLATION_FLAGS["executes_trades"] is False
        assert ISOLATION_FLAGS["modifies_production"] is False
        assert ISOLATION_FLAGS["approves_releases"] is False
        assert ISOLATION_FLAGS["deploys_strategies"] is False
        assert ISOLATION_FLAGS["allocates_capital"] is False
        assert ISOLATION_FLAGS["human_approval_required_for_transitions"] is True
        assert ISOLATION_FLAGS["preserves_existing_safety_guarantees"] is True


class TestWorkflowConsistency:
    def test_pipeline_and_integrity(self) -> None:
        ctx = _ctx()
        items = build_work_items(ctx)
        assert items
        assert all(i.get("requires_human_approval") for i in items)
        board = build_pipeline_board(items)
        assert set(board["stages"]) == set(PIPELINE_STAGES)
        dossiers = build_dossiers(ctx, items)
        queue = build_approval_queue(items, [])
        assert workflow_consistency_check(items, queue)["ok"] is True
        assert evidence_integrity_check(items, dossiers)["ok"] is True
        assert next_stage(PipelineStage.IDEA.value) == PipelineStage.HYPOTHESIS.value
        assert next_stage(PipelineStage.PAPER_TRADING_READY.value) is None


class TestHumanApproval:
    def test_approve_advances_one_step(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        qsf = QuantForgStrategyFactory(store=QsfStore(path=tmp_path / "qsf.json"))
        monkeypatch.setattr(
            "app.domain.quantforg_strategy_factory.platform.gather_factory_sources",
            _ctx,
        )
        pack = qsf.dashboard()
        item = pack["work_items"][0]
        from_stage = item["pipeline_stage"]
        to_stage = item["next_stage"]
        assert to_stage
        result = qsf.approve_transition(
            strategy_id="st1",
            to_stage=to_stage,
            approver="tester",
            decision="approved",
            work_item_id=item["work_item_id"],
        )
        assert result["human_explicit"] is True
        assert result["never_deploys_strategies"] is True
        assert result["never_executes_trades"] is True
        assert result["approval"]["decision"] == "approved"
        assert result["work_item"]["pipeline_stage"] == to_stage
        assert result["work_item"]["pipeline_stage"] != from_stage or to_stage == from_stage


class TestPlatform:
    def test_dashboard(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        qsf = QuantForgStrategyFactory(store=QsfStore(path=tmp_path / "qsf.json"))
        monkeypatch.setattr(
            "app.domain.quantforg_strategy_factory.platform.gather_factory_sources",
            _ctx,
        )
        t0 = time.perf_counter()
        pack = qsf.dashboard()
        elapsed = (time.perf_counter() - t0) * 1000.0
        assert pack["never_executes_trades"] is True
        assert pack["never_modifies_production"] is True
        assert pack["never_approves_releases"] is True
        assert pack["never_deploys_strategies"] is True
        assert pack["never_allocates_capital"] is True
        assert pack["preserves_existing_safety_guarantees"] is True
        assert pack["workflow_consistency"]["ok"] is True
        assert pack["evidence_integrity"]["ok"] is True
        assert pack["sections"]["factory_dashboard"]
        assert pack["sections"]["pipeline_board"]
        assert pack["sections"]["strategy_workspace"]
        assert pack["sections"]["evidence_center"]
        assert pack["sections"]["approval_queue"]
        assert pack["elapsed_ms"] < 500
        assert elapsed < 2000
