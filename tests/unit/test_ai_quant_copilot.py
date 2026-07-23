"""Unit tests — AI Quant Copilot (read-only / advisory)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.domain.ai_quant_copilot.analysis import (
    build_executive_summaries,
    build_historical_comparison,
    build_investigations,
    correlate_systems,
    package_evidence,
    search_aqs_recommendations,
)
from app.domain.ai_quant_copilot.models import ISOLATION_FLAGS
from app.domain.ai_quant_copilot.nli import answer_question
from app.domain.ai_quant_copilot.platform import AiQuantCopilot
from app.domain.ai_quant_copilot.store import AqcStore

pytestmark = pytest.mark.unit


def _ctx() -> dict:
    return {
        "sources": {
            "execution_explain": {
                "cycles": [
                    {
                        "cycle_id": "c1",
                        "timestamp": "2026-07-23T10:00:00Z",
                        "live_execution_explain": {
                            "final_decision": "BLOCKED",
                            "stages": [
                                {
                                    "stage": "signal",
                                    "status": "PASS",
                                    "reason": "signal created",
                                    "timestamp": "2026-07-23T10:00:01Z",
                                },
                                {
                                    "stage": "mtf",
                                    "status": "FAIL",
                                    "reason": "HTF misaligned",
                                    "timestamp": "2026-07-23T10:00:02Z",
                                },
                                {
                                    "stage": "quality",
                                    "status": "FAIL",
                                    "reason": "quality below threshold",
                                    "timestamp": "2026-07-23T10:00:03Z",
                                },
                                {
                                    "stage": "risk",
                                    "status": "UNKNOWN",
                                    "reason": "not evaluated",
                                    "timestamp": "2026-07-23T10:00:04Z",
                                },
                            ],
                        },
                    }
                ]
            },
            "diagnostics": {"cycles": []},
            "portfolio": {
                "trade_count": 12,
                "sections": {
                    "performance": {
                        "profit_factor": 1.4,
                        "win_rate_pct": 52.0,
                        "trade_count": 12,
                    },
                    "risk": {"max_drawdown_pct": 8.5},
                },
            },
            "icc": {
                "alerts": [{"id": "a1", "subsystem": "gateway", "message": "latency"}],
                "operational_timeline": [
                    {
                        "timestamp": "2026-07-23T09:00:00Z",
                        "subsystem": "icc",
                        "event": "heartbeat",
                    }
                ],
                "executive_kpis": {"health": "amber", "profit_factor": 1.4},
            },
            "aqs": {
                "recommendations": [
                    {
                        "id": "r1",
                        "title": "Regime study",
                        "type": "Observation",
                        "status": "Open",
                        "research_area": "regime",
                        "scores": {"research_confidence_score": 78},
                    }
                ]
            },
            "regime": {"current": {"current_regime": "TRENDING"}},
            "irl": {
                "leaderboard": {
                    "rows": [
                        {"name": "Exp A", "composite_score": 88, "profit_factor": 2.1}
                    ]
                }
            },
            "idw": {"quality": {"integrity_score": 91}},
            "audit": [],
            "opportunity": {"points": []},
            "sic": {},
        },
        "availability": {
            "icc": True,
            "diagnostics": True,
            "execution_explain": True,
            "portfolio": True,
            "aqs": True,
        },
        "source_count": 5,
    }


class TestAqcAnalysis:
    def test_investigation_timeline(self) -> None:
        invs = build_investigations(_ctx())
        assert invs
        assert invs[0]["first_block"]["stage"] == "mtf"
        assert any(s["stage"] == "quality" for s in invs[0]["timeline"])

    def test_comparison_and_summaries(self) -> None:
        cmp = build_historical_comparison(_ctx())
        assert "today" in cmp["periods"]
        assert cmp["never_modifies_production"] is True
        summaries = build_executive_summaries(_ctx())
        assert "daily" in summaries and "weekly" in summaries

    def test_recommendations_filter_and_evidence(self) -> None:
        rows = search_aqs_recommendations(
            _ctx(), min_confidence=70, research_area="regime"
        )
        assert len(rows) == 1
        pkg = package_evidence(
            answer="test",
            evidence=rows,
            source_subsystem="aqs",
            confidence=0.9,
        )
        assert pkg["evidence"]
        assert pkg["never_modifies_production"] is True

    def test_correlations(self) -> None:
        corr = correlate_systems(_ctx())
        assert corr["correlations"]
        assert corr["never_modifies_production"] is True


class TestAqcNli:
    def test_no_trade_and_quality_have_evidence(self) -> None:
        ctx = _ctx()
        invs = build_investigations(ctx)
        r1 = answer_question("Why was no trade opened today?", ctx=ctx, pack={"investigations": invs})
        assert r1["evidence"]
        assert r1["source_subsystem"]
        assert r1["confidence"] > 0
        r2 = answer_question("Why did Quality fail?", ctx=ctx, pack={"investigations": invs})
        assert "Quality" in r2["answer"] or "quality" in r2["answer"].lower()
        assert r2["evidence"]

    def test_never_answer_without_evidence_keys(self) -> None:
        r = answer_question("random ops question xyz", ctx=_ctx())
        assert "evidence" in r
        assert "source_subsystem" in r
        assert "confidence" in r
        assert r["advisory_only"] is True


class TestAqcPlatform:
    def test_isolation_and_conversation(self, tmp_path: Path) -> None:
        assert ISOLATION_FLAGS["executes_trades"] is False
        assert ISOLATION_FLAGS["modifies_thresholds"] is False
        assert ISOLATION_FLAGS["approves_promotions"] is False
        copilot = AiQuantCopilot(store=AqcStore(path=tmp_path / "aqc.json"))
        # Inject lightweight path by asking with persist after patching gather
        from app.domain.ai_quant_copilot import platform as plat

        original = plat.gather_ops_context
        plat.gather_ops_context = lambda: _ctx()  # type: ignore[assignment]
        try:
            t0 = time.perf_counter()
            ans = copilot.ask("Show the evidence.")
            elapsed = time.perf_counter() - t0
            assert ans["evidence"]
            assert elapsed < 45
            hist = copilot.list_conversations(limit=5)
            assert hist
        finally:
            plat.gather_ops_context = original  # type: ignore[assignment]
