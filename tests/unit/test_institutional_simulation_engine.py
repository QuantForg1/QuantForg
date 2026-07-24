"""Unit tests — Institutional Simulation Engine (isolated digital twin)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.domain.institutional_simulation_engine.engine import (
    PIPELINE_STAGES,
    aqs_analysis_pack,
    catalog,
    simulate_monte_carlo,
    simulate_replay,
    simulate_scenario,
    simulate_stress,
    simulate_walk_forward,
)
from app.domain.institutional_simulation_engine.models import (
    ISOLATION_FLAGS,
    PIPELINE_STAGES as MODEL_STAGES,
    SimulationMode,
)
from app.domain.institutional_simulation_engine.platform import (
    InstitutionalSimulationEngine,
)
from app.domain.institutional_simulation_engine.store import IseStore

pytestmark = pytest.mark.unit


def _ctx() -> dict:
    return {
        "sources": {
            "portfolio": {
                "trade_count": 100,
                "sections": {
                    "performance": {
                        "profit_factor": 1.8,
                        "win_rate_pct": 54.0,
                        "expectancy": 3.0,
                        "average_rr": 1.4,
                        "trade_count": 100,
                    },
                    "risk": {"max_drawdown_pct": 9.0},
                    "behavior": {"average_holding_time_sec": 1500},
                },
            },
            "irl": {
                "leaderboard": {"rows": [{"profit_factor": 2.0, "win_rate": 55}]},
                "benchmark": {
                    "production_baseline": {
                        "profit_factor": 1.7,
                        "win_rate": 53,
                        "total_trades": 120,
                    }
                },
            },
            "idw": {"trades": [], "signals": [], "regimes": []},
            "regime": {},
        },
        "availability": {"portfolio": True, "irl": True},
    }


class TestIseEngine:
    def test_pipeline_and_scenario(self) -> None:
        assert list(PIPELINE_STAGES) == list(MODEL_STAGES)
        row = simulate_scenario(_ctx(), scenario="higher_spread")
        assert row["never_modifies_production"] is True
        assert len(row["pipeline"]) == len(PIPELINE_STAGES)
        assert row["metrics"]["profit_factor"] is not None

    def test_monte_carlo_and_walk_forward(self) -> None:
        mc = simulate_monte_carlo(_ctx(), paths=100)
        assert mc["monte_carlo"]["paths"] == 100
        assert "probability_of_ruin" in mc["monte_carlo"]
        assert "confidence_interval" in mc["monte_carlo"]
        wf = simulate_walk_forward(_ctx())
        assert "train" in wf["walk_forward"]
        assert "generalization_score" in wf["walk_forward"]
        stress = simulate_stress(_ctx(), stress="gap")
        assert stress["mode"] == SimulationMode.STRESS_TEST.value
        replay = simulate_replay(_ctx())
        assert replay["mode"] == SimulationMode.HISTORICAL_REPLAY.value

    def test_aqs_pack_and_catalog(self) -> None:
        cat = catalog()
        assert "Historical Monte Carlo" in cat["modes"]
        row = simulate_monte_carlo(_ctx(), paths=100)
        pack = aqs_analysis_pack(row)
        assert pack["for_aqs"] is True
        assert pack["never_modifies_production"] is True


class TestIsePlatform:
    def test_isolation_consistency_perf(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert ISOLATION_FLAGS["executes_trades"] is False
        assert ISOLATION_FLAGS["modifies_oms"] is False
        assert ISOLATION_FLAGS["digital_twin_isolated"] is True
        ise = InstitutionalSimulationEngine(store=IseStore(path=tmp_path / "ise.json"))
        monkeypatch.setattr(
            "app.domain.institutional_simulation_engine.platform.gather_simulation_context",
            _ctx,
        )
        t0 = time.perf_counter()
        dash = ise.dashboard()
        elapsed = time.perf_counter() - t0
        assert dash["never_modifies_production"] is True
        assert dash["digital_twin"] is True
        assert dash["knowledge_nodes"]
        # Deterministic consistency: same scenario twice → same metric envelope
        a = ise.simulate(mode="scenario", scenario="higher_spread", persist=True)
        b = ise.simulate(mode="scenario", scenario="higher_spread", persist=True)
        assert a["metrics"]["profit_factor"] == b["metrics"]["profit_factor"]
        assert elapsed < 45
