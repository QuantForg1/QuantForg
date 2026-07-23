"""Unit tests — Institutional Research Lab (isolated)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.domain.institutional_research_lab.models import (
    ExperimentStatus,
    ResearchVerdict,
    sanitize_candidate_params,
)
from app.domain.institutional_research_lab.platform import InstitutionalResearchLab
from app.domain.institutional_research_lab.replay import replay_historical
from app.domain.institutional_research_lab.statistics import compute_statistics
from app.domain.institutional_research_lab.store import IrlStore

pytestmark = pytest.mark.unit


@pytest.fixture()
def lab(tmp_path: Path) -> InstitutionalResearchLab:
    return InstitutionalResearchLab(store=IrlStore(path=tmp_path / "irl.json"))


class TestIrlIsolation:
    def test_sanitize_rejects_production_keys(self) -> None:
        params = sanitize_candidate_params(
            {
                "candidate_mtf_model": "x",
                "EXECUTION_ENABLED": True,
                "live_threshold": 80,
            }
        )
        assert params["candidate_mtf_model"] == "x"
        assert "EXECUTION_ENABLED" not in params
        assert "live_threshold" not in params

    def test_isolation_flags(self, lab: InstitutionalResearchLab) -> None:
        assert lab.isolation["executes_live_trades"] is False
        assert lab.isolation["writes_production_tables"] is False
        assert lab.isolation["never_auto_promotes"] is True


class TestIrlExperimentLifecycle:
    def test_create_replay_leaderboard(self, lab: InstitutionalResearchLab) -> None:
        exp = lab.create_experiment(
            name="Candidate A",
            description="test",
            author="unit",
            candidate_params={
                "candidate_mtf_model": "strict",
                "candidate_quality_formula": "conservative",
                "candidate_session_filters": "london",
            },
        )
        assert exp["status"] == ExperimentStatus.DRAFT.value
        assert exp["uuid"]

        result = lab.queue_and_run_replay(experiment_id=exp["uuid"], window="30d")
        assert result["job"]["live_execution"] is False
        assert result["report"]["replay_meta"]["live_execution"] is False
        assert result["report"]["replay_meta"]["writes_production_tables"] is False
        stats = result["experiment"]["statistics"]
        assert stats["total_trades"] >= 5
        assert "profit_factor" in stats
        assert "sharpe" in stats
        assert result["experiment"]["verdict"] in {
            ResearchVerdict.RESEARCH_PASSED.value,
            ResearchVerdict.RESEARCH_FAILED.value,
        }
        assert result["report"]["verdict"]["never_auto_promotes"] is True

        board = lab.leaderboard(rank_by="composite")
        assert board["rows"]
        assert board["rows"][0]["rank"] == 1


class TestReplayValidation:
    def test_replay_never_live(self) -> None:
        out = replay_historical(
            experiment_id="exp-1",
            candidate_params={"candidate_mtf_model": "a"},
            window="90d",
        )
        assert out["live_execution"] is False
        assert out["writes_production_tables"] is False
        assert out["influences_production_decisions"] is False
        assert len(out["trades"]) >= 5

    def test_replay_with_supplied_bars(self) -> None:
        bars = [{"close": 2300 + i * 0.1} for i in range(200)]
        out = replay_historical(
            experiment_id="exp-bars",
            candidate_params={},
            window="30d",
            bars=bars,
        )
        assert out["source"] == "supplied_historical_bars"
        assert out["live_execution"] is False
        stats = compute_statistics(out["trades"])
        assert stats["total_trades"] >= 1

    def test_custom_window(self) -> None:
        out = replay_historical(
            experiment_id="exp-c",
            candidate_params={},
            window="custom",
            custom_start="2026-01-01T00:00:00+00:00",
            custom_end="2026-02-15T00:00:00+00:00",
        )
        assert out["window_days"] == 45


class TestPerformance:
    def test_replay_budget(self, lab: InstitutionalResearchLab) -> None:
        exp = lab.create_experiment(name="perf", author="unit")
        t0 = time.perf_counter()
        lab.queue_and_run_replay(experiment_id=exp["uuid"], window="365d")
        assert time.perf_counter() - t0 < 5.0
