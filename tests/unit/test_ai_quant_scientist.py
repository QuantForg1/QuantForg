"""Unit tests — AI Quant Scientist (read-only / advisory)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.domain.ai_quant_scientist.analysis import (
    build_recommendations,
    compare_strategies,
    detect_weaknesses,
    discover_patterns,
    parameter_sensitivity,
    regime_research,
)
from app.domain.ai_quant_scientist.models import ISOLATION_FLAGS, RecommendationType
from app.domain.ai_quant_scientist.nli import answer_question
from app.domain.ai_quant_scientist.platform import AiQuantScientist
from app.domain.ai_quant_scientist.store import AqsStore

pytestmark = pytest.mark.unit


def _ctx() -> dict:
    return {
        "sources": {
            "portfolio": {
                "sections": {
                    "performance": {
                        "profit_factor": 0.8,
                        "expectancy": -1.2,
                        "win_rate_pct": 42.0,
                        "trade_count": 20,
                    },
                    "risk": {"max_drawdown_pct": 18.0, "ulcer_index": 9.0},
                    "behavior": {
                        "session_performance": {
                            "london": {"count": 8, "win_rate": 62.0, "total_pnl": 40},
                            "tokyo": {"count": 5, "win_rate": 30.0, "total_pnl": -20},
                        },
                        "average_holding_time_sec": 1800,
                    },
                    "time": {
                        "hour": {"best": "14:00 UTC", "worst": "03:00 UTC"},
                        "dow": {"best": "Tuesday", "worst": "Friday"},
                    },
                }
            },
            "irl": {
                "leaderboard": {
                    "rows": [
                        {
                            "uuid": "e1",
                            "name": "Candidate A",
                            "profit_factor": 2.5,
                            "expectancy": 5.0,
                            "maximum_drawdown_pct": 6.0,
                            "composite_score": 80,
                            "verdict": "Research Passed",
                        }
                    ]
                },
                "benchmark": {
                    "production_baseline": {
                        "profit_factor": 2.31,
                        "expectancy": 4.2,
                        "win_rate": 54,
                        "total_trades": 100,
                    }
                },
                "jobs": [],
            },
            "regime": {
                "current": {
                    "current_regime": "TRENDING",
                    "historical_performance": {"win_rate": 0.55, "profit_factor": 1.8},
                },
                "history": [{"regime": "TRENDING"}],
            },
            "idw": {"quality": {"integrity_score": 88, "duplicates": 0}},
        },
        "availability": {"portfolio": True, "irl": True},
    }


class TestAqsAnalysis:
    def test_patterns_and_weaknesses(self) -> None:
        ctx = _ctx()
        patterns = discover_patterns(ctx)
        weaknesses = detect_weaknesses(ctx)
        assert any(p["kind"] == "session" for p in patterns)
        assert any(w["kind"] == "high_drawdown" for w in weaknesses)

    def test_comparison_and_sensitivity_never_apply(self) -> None:
        ctx = _ctx()
        comparison = compare_strategies(ctx)
        assert comparison["never_auto_promotes"] is True
        assert comparison["profit_factor_difference_pct"] is not None
        sensitivity = parameter_sensitivity(ctx)
        assert sensitivity["never_changes_thresholds"] is True
        assert sensitivity["most_stable"] is not None

    def test_recommendations_have_explainability(self) -> None:
        ctx = _ctx()
        patterns = discover_patterns(ctx)
        weaknesses = detect_weaknesses(ctx)
        comparison = compare_strategies(ctx)
        regimes = regime_research(ctx)
        sensitivity = parameter_sensitivity(ctx)
        recs = build_recommendations(
            patterns=patterns,
            weaknesses=weaknesses,
            comparison=comparison,
            regimes=regimes,
            sensitivity=sensitivity,
        )
        assert recs
        for r in recs:
            assert r["type"] in {t.value for t in RecommendationType}
            ex = r["explainability"]
            assert "evidence" in ex
            assert "confidence" in ex
            assert "counter_arguments" in ex
            assert "potential_risks" in ex
            assert "scores" in r

    def test_nli_regime_question(self) -> None:
        ctx = _ctx()
        pack = {
            "patterns": discover_patterns(ctx),
            "weaknesses": detect_weaknesses(ctx),
            "comparison": compare_strategies(ctx),
            "regimes": regime_research(ctx),
            "sensitivity": parameter_sensitivity(ctx),
            "recommendations": [],
        }
        ans = answer_question("Which regime produces highest PF?", pack=pack)
        assert "PF" in ans["answer"] or "pf" in ans["answer"].lower() or "regime" in ans["answer"].lower()
        assert ans["never_modifies_production"] is True


class TestAqsPlatform:
    def test_dashboard_isolation(self, tmp_path: Path) -> None:
        aqs = AiQuantScientist(store=AqsStore(path=tmp_path / "aqs.json"))
        # Inject analysis via run with empty gather — still ok
        payload = aqs.run_research(persist=True)
        assert payload["isolation"]["executes_trades"] is False
        assert payload["isolation"]["approves_promotion"] is False
        assert ISOLATION_FLAGS["writes_production_tables"] is False
        assert "recommendations" in payload
        assert "latest_report" in payload

    def test_status_accepted_does_not_claim_production_write(self, tmp_path: Path) -> None:
        aqs = AiQuantScientist(store=AqsStore(path=tmp_path / "aqs.json"))
        pack = aqs.run_research(persist=True)
        rid = pack["recommendations"][0]["id"]
        updated = aqs.set_recommendation_status(rid, "Accepted")
        assert updated is not None
        assert updated["status"] == "Accepted"
        assert "never changes production" in str(updated.get("status_note", "")).lower()

    def test_performance_budget(self, tmp_path: Path) -> None:
        aqs = AiQuantScientist(store=AqsStore(path=tmp_path / "aqs.json"))
        t0 = time.perf_counter()
        aqs.run_research(persist=True)
        assert time.perf_counter() - t0 < 45.0
