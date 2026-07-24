"""Unit tests — Institutional Strategy Lifecycle Manager."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.domain.institutional_strategy_lifecycle.analytics import (
    build_alerts,
    build_health_scores,
    build_registry_from_sources,
    build_reports,
    infer_lifecycle_state,
    next_lifecycle_state,
)
from app.domain.institutional_strategy_lifecycle.models import (
    ISOLATION_FLAGS,
    LIFECYCLE_ORDER,
    LifecycleState,
)
from app.domain.institutional_strategy_lifecycle.platform import (
    InstitutionalStrategyLifecycleManager,
)
from app.domain.institutional_strategy_lifecycle.store import IslmStore

pytestmark = pytest.mark.unit


def _ctx() -> dict:
    return {
        "sources": {
            "portfolio": {
                "trade_count": 40,
                "sections": {
                    "performance": {"sharpe_ratio": 0.9, "profit_factor": 1.4},
                    "risk": {"max_drawdown_pct": 22.0, "current_drawdown_pct": 18.0},
                },
            },
            "irl": {
                "experiments": [
                    {
                        "experiment_id": "e1",
                        "name": "lab-alpha",
                        "status": "done",
                        "composite": 70,
                    }
                ],
                "leaderboard": {"top": {"composite": 70}},
            },
            "aqs": {"recommendations": [{"recommendation_id": "r1", "title": "tune"}]},
            "ise": {
                "simulations": [
                    {
                        "simulation_id": "s1",
                        "mode": "Historical Replay",
                        "metrics": {"drawdown": 10},
                    },
                    {
                        "simulation_id": "s2",
                        "scenario": "monte_carlo",
                        "metrics": {"drawdown": 15},
                    },
                ]
            },
            "cvf": {"confidence": {"confidence": 40}, "alerts": [{"kind": "drift"}]},
            "irap": {
                "metrics": {"maximum_drawdown": 22, "sharpe_ratio": 0.9},
                "alerts": [{"kind": "High drawdown", "severity": "warning"}],
            },
            "eqs": {
                "execution_score": {"overall_execution_score": 55},
                "alerts": [{"kind": "slippage"}],
            },
            "res": {
                "reliability_score": {"overall_reliability_score": 70},
                "alerts": [{"kind": "a"}, {"kind": "b"}, {"kind": "c"}],
            },
            "irdp": [
                {
                    "release_id": "rel1",
                    "version": "3.3.0",
                    "status": "awaiting_approval",
                    "stage": "human_approval",
                }
            ],
            "qkg": {
                "nodes": [
                    {"id": "n1", "label": "XAU strategy", "type": "strategy"},
                    {"id": "n2", "label": "other", "type": "metric"},
                ]
            },
            "sic": {"present": True},
        },
        "availability": {"portfolio": True, "irl": True, "ise": True},
        "source_count": 3,
        "read_only": True,
    }


class TestLifecycleConsistency:
    def test_order_and_inference(self) -> None:
        assert LIFECYCLE_ORDER[0] == LifecycleState.DRAFT.value
        assert LIFECYCLE_ORDER[-1] == LifecycleState.RETIRED.value
        evidence = {
            "research_history": [{}],
            "replay_results": [{}],
            "simulation_results": [{}],
            "cvf_findings": {"confidence": 50},
            "risk_analytics": {"metrics": {}},
            "release_history": [{}],
            "production_signals": True,
            "monitoring_signals": True,
        }
        assert infer_lifecycle_state(evidence) == LifecycleState.MONITORING.value
        assert next_lifecycle_state(LifecycleState.DRAFT.value) == (
            LifecycleState.RESEARCH.value
        )
        assert next_lifecycle_state(LifecycleState.RETIRED.value) is None

    def test_never_auto_flags(self) -> None:
        assert ISOLATION_FLAGS["executes_trades"] is False
        assert ISOLATION_FLAGS["modifies_production"] is False
        assert ISOLATION_FLAGS["changes_strategy_parameters"] is False
        assert ISOLATION_FLAGS["approves_promotions_automatically"] is False
        assert ISOLATION_FLAGS["retires_strategies_automatically"] is False
        assert ISOLATION_FLAGS["human_approval_required_for_transitions"] is True


class TestHealthAndAlerts:
    def test_health_composite(self) -> None:
        h = build_health_scores(
            research=80, validation=70, execution=60, reliability=90, risk=50
        )
        assert 0 <= h["overall_strategy_health"] <= 100
        assert h["research_score"] == 80

    def test_alerts_readonly(self) -> None:
        strategies = build_registry_from_sources(_ctx())
        alerts = build_alerts(strategies, _ctx())
        kinds = {a["kind"] for a in alerts}
        assert "High drawdown" in kinds
        assert "Validation drift" in kinds
        assert "Execution degradation" in kinds
        assert "Repeated incidents" in kinds
        assert all(a.get("read_only") for a in alerts if "source" not in a or True)


class TestEvidenceIntegrity:
    def test_registry_and_reports(self) -> None:
        rows = build_registry_from_sources(_ctx())
        assert rows
        assert all(r.get("strategy_id") for r in rows)
        assert all(r.get("requires_human_approval_to_advance") for r in rows)
        assert all(r.get("never_auto_promotes") for r in rows)
        primary = rows[0]
        assert primary["evidence"]["knowledge_graph_links"]
        reports = build_reports(strategies=rows, alerts=[])
        integrity = reports["evidence_report"]["integrity"]
        assert integrity["has_unique_ids"] is True
        assert integrity["lifecycle_in_enum"] is True


class TestPlatformHumanApproval:
    def test_approve_locks_lifecycle(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        store = IslmStore(path=tmp_path / "islm.json")
        islm = InstitutionalStrategyLifecycleManager(store=store)
        monkeypatch.setattr(
            "app.domain.institutional_strategy_lifecycle.platform.gather_lifecycle_sources",
            _ctx,
        )
        pack = islm.dashboard()
        assert pack["never_executes_trades"] is True
        assert pack["never_approves_promotions_automatically"] is True
        sid = pack["registry"][0]["strategy_id"]
        nxt = pack["registry"][0].get("recommended_next_state") or LifecycleState.RESEARCH.value
        result = islm.approve_transition(
            strategy_id=sid,
            to_state=nxt,
            approver="alice",
            decision="approved",
            comment="ok",
        )
        assert result["approval"]["decision"] == "approved"
        assert result["never_modifies_production"] is True
        locked = store.get_strategy(sid)
        assert locked is not None
        assert locked["lifecycle_state"] == nxt
        assert locked["lifecycle_locked"] is True
