"""AI v8 Adaptive Intelligence — observe / recommend only; never auto-applies."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.domain.institutional_trading.ai_scalping.adaptive_recommendations import (
    build_adaptive_recommendations,
)
from app.domain.institutional_trading.ai_scalping.adaptive_replay_explain import (
    enrich_replay_library,
    explain_trade_replay,
)
from app.domain.institutional_trading.ai_scalping.institutional_learning_engine import (
    InstitutionalLearningEngine,
    LearningObservation,
    observe_from_learning_trade,
)
from app.domain.institutional_trading.ai_scalping.institutional_performance_kpis import (  # noqa: E501
    build_institutional_performance_kpis,
)
from app.domain.institutional_trading.ai_scalping.institutional_period_reports import (
    build_institutional_period_reports,
)
from app.domain.institutional_trading.ai_scalping.pattern_intelligence import (
    build_pattern_intelligence,
)
from app.domain.institutional_trading.ai_scalping.portfolio_intelligence_v2 import (
    build_portfolio_intelligence_v2,
)


@dataclass
class _FakeTrade:
    ticket: str = "T1"
    symbol: str = "XAUUSD"
    direction: str = "BUY"
    entry_reason: str | None = "confluence"
    exit_reason: str | None = "tp"
    holding_time_minutes: float | None = 12.0
    pnl: float | None = 15.5
    win: bool = True
    regime: str | None = "trend"
    session: str | None = "london"
    atr_pct: float | None = 0.4
    spread: float | None = 0.12
    quality: int = 88
    confidence: int = 82
    r_multiple: float | None = 1.2
    mae_r: float | None = 0.3
    mfe_r: float | None = 1.5
    slippage: float | None = 0.01
    indicators: dict | None = None


def test_learning_engine_append_only_never_overwrites(tmp_path: Path) -> None:
    eng = InstitutionalLearningEngine(max_records=100)
    eng._path = tmp_path / "obs.json"
    eng._records = []

    o1 = LearningObservation(
        observed_at="2026-08-01T00:00:00Z",
        ticket="1",
        symbol="XAUUSD",
        direction="BUY",
        entry_reason="e",
        exit_reason="x",
        duration_minutes=5.0,
        management_phase="tp",
        pnl=10.0,
        win=True,
        execution_quality=None,
        market_regime="trend",
        session="london",
        volatility="normal",
        atr_pct=0.3,
        spread=0.1,
        liquidity=0.8,
        quality=90,
        confidence=85,
        mtf=2,
        correlation_group="metals",
        r_multiple=1.0,
        mae_r=0.2,
        mfe_r=1.1,
        slippage=0.0,
    )
    eng.observe(o1)
    o2 = LearningObservation(
        observed_at="2026-08-01T01:00:00Z",
        ticket="2",
        symbol="EURUSD",
        direction="SELL",
        entry_reason="e",
        exit_reason="sl",
        duration_minutes=8.0,
        management_phase="sl",
        pnl=-5.0,
        win=False,
        execution_quality=None,
        market_regime="range",
        session="ny",
        volatility="elevated",
        atr_pct=0.9,
        spread=0.2,
        liquidity=0.5,
        quality=75,
        confidence=70,
        mtf=1,
        correlation_group="fx",
        r_multiple=-1.0,
        mae_r=1.0,
        mfe_r=0.1,
        slippage=0.05,
    )
    eng.observe(o2)

    snap = eng.snapshot()
    assert snap["count"] == 2
    assert snap["overwrite_forbidden"] is True
    assert snap["auto_applies_to_strategy"] is False
    assert snap["observe_only"] is True
    assert eng._records[0]["ticket"] == "1"
    assert eng._records[1]["ticket"] == "2"


def test_observe_from_learning_trade_records_real_fields() -> None:
    row = observe_from_learning_trade(
        _FakeTrade(indicators={"mtf": 2, "management_reason": "tp"}),
        management_phase="tp",
        liquidity=0.9,
        mtf=2,
        extras={"auto_applies": False},
    )
    assert row["symbol"] == "XAUUSD"
    assert row["fabricated"] is False
    assert row["source"] == "real_completed_trade"
    assert row["extras"]["auto_applies"] is False


def test_recommendations_never_auto_apply() -> None:
    out = build_adaptive_recommendations()
    assert out["auto_applies"] is False
    assert out["modifies_strategy"] is False
    assert out["operator_controlled"] is True
    assert out["observe_only"] is True
    for rec in out["recommendations"]:
        assert rec.get("requires_human_approval") is True


def test_pattern_intelligence_does_not_modify_strategy() -> None:
    out = build_pattern_intelligence()
    assert out["modifies_strategy"] is False
    assert out["auto_applies"] is False
    assert out["fabricated"] is False


def test_kpis_null_safe_empty() -> None:
    out = build_institutional_performance_kpis()
    assert out["fabricated"] is False
    assert out["auto_applies"] is False
    assert out["observe_only"] is True
    assert "expectancy" in out
    assert "sharpe" in out
    assert "sortino" in out
    assert "calmar" in out
    assert "profit_factor" in out
    assert "recovery_factor" in out
    assert "ulcer_index" in out
    assert "average_mae" in out
    assert "average_mfe" in out
    assert "execution_quality_index" in out
    assert "institutional_score" in out


def test_portfolio_forecast_warnings_only() -> None:
    out = build_portfolio_intelligence_v2(positions=[])
    assert out["blocks_risk_engine"] is False
    assert out["auto_applies"] is False
    assert out["observe_only"] is True
    assert isinstance(out["warnings"], list)


def test_period_reports_structure() -> None:
    out = build_institutional_period_reports()
    assert out["auto_applies"] is False
    for key in ("daily", "weekly", "monthly", "quarterly", "yearly"):
        assert key in out["periods"]


def test_adaptive_replay_evidence_only_no_hallucination() -> None:
    explain = explain_trade_replay(
        {
            "symbol": "XAUUSD",
            "direction": "BUY",
            "entry": 2000.0,
            "exit": 2005.0,
            "close_reason": "tp",
            "ai_decision": "BUY confluence",
            "market_snapshot": {
                "institutional": {
                    "execution_decision": {
                        "execution_quality_score": 80,
                        "recommendation": "PROCEED",
                    }
                }
            },
        }
    )
    assert explain["hallucinations"] is False
    assert explain["evidence_only"] is True
    assert explain["fabricated"] is False
    assert explain["succeeded"] is True
    assert any("Close reason" in s for s in explain["why_succeeded"])


def test_enrich_replay_library_attaches_explain() -> None:
    out = enrich_replay_library(
        [
            {
                "id": "r1",
                "symbol": "XAUUSD",
                "direction": "SELL",
                "entry": 1.1,
                "exit": 1.2,
            }
        ],
        limit=5,
    )
    assert out["count"] == 1
    assert "adaptive_explain" in out["items"][0]


def test_noc_panels_include_v8_keys() -> None:
    from app.application.services.noc_intelligence_panels import (
        build_intelligence_panels,
    )

    panels = build_intelligence_panels(runtime_scan={})
    for key in (
        "learning_dashboard",
        "pattern_library",
        "adaptive_recommendations",
        "institutional_kpis",
        "portfolio_forecast",
        "period_reports",
    ):
        assert key in panels
    assert panels["flags"]["adaptive_auto_applies"] is False
    assert panels["flags"]["ai_version"] == "v8"
    assert panels["adaptive_recommendations"].get("auto_applies") is False
    assert panels["portfolio_forecast"].get("blocks_risk_engine") is False


def test_config_version_v8() -> None:
    from app.domain.institutional_trading.ai_scalping.config import (
        DEFAULT_AI_SCALPING_CONFIG,
    )

    assert DEFAULT_AI_SCALPING_CONFIG.version.startswith("ai-scalping-v8")
