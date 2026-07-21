"""Unit tests — Institutional Market Intelligence Engine V1."""

from __future__ import annotations

from decimal import Decimal

from app.domain.market_intelligence import (
    MarketIntelligenceEngine,
    MarketIntelligenceInput,
)
from app.domain.market_intelligence.config import MarketIntelligenceConfig
from app.domain.market_intelligence.consensus import (
    StrategySignal,
    build_strategy_consensus,
)
from app.domain.market_intelligence.daily_report import (
    DayTradeRecord,
    RuleViolation,
    build_daily_validation_report,
)
from app.domain.market_intelligence.execution_quality import (
    ExecutionQualityInput,
    review_execution_quality,
)
from app.domain.market_intelligence.health_dashboard import AiHealthInput
from app.domain.market_intelligence.opportunity import (
    OpportunityCandidate,
    rank_opportunities,
)
from app.domain.market_intelligence.portfolio_risk import (
    PortfolioRiskInput,
    build_portfolio_risk_dashboard,
)
from app.domain.market_intelligence.regime import RegimeInput, detect_market_regime


def _full_input(**overrides: object) -> MarketIntelligenceInput:
    base = MarketIntelligenceInput(
        regime=RegimeInput(
            trend="up",
            atr=Decimal("8"),
            price=Decimal("4000"),
            news_driven=False,
            structure_label="bullish",
        ),
        strategy_signals=(
            StrategySignal("a", True, "buy", Decimal("80")),
            StrategySignal("b", True, "buy", Decimal("70")),
        ),
        opportunities=(
            OpportunityCandidate(
                "s1", "a", "buy", Decimal("80"), Decimal("82")
            ),
            OpportunityCandidate(
                "s2", "b", "buy", Decimal("70"), Decimal("74")
            ),
        ),
        execution_quality=ExecutionQualityInput(
            entry_quality=Decimal("70"),
            exit_quality=Decimal("68"),
            timing_quality=Decimal("72"),
        ),
        portfolio_risk=PortfolioRiskInput(
            equity=Decimal("10000"),
            allocated_pct=Decimal("20"),
            daily_risk_used_pct=Decimal("0.5"),
        ),
        ai_health=AiHealthInput(
            decision_quality=Decimal("70"),
            execution_success=Decimal("65"),
            risk_discipline=Decimal("80"),
            system_reliability=Decimal("85"),
        ),
        risk_engine_passed=True,
        safety_engine_passed=True,
    )
    if not overrides:
        return base
    data = {
        "regime": base.regime,
        "strategy_signals": base.strategy_signals,
        "opportunities": base.opportunities,
        "execution_quality": base.execution_quality,
        "portfolio_risk": base.portfolio_risk,
        "ai_health": base.ai_health,
        "day_trades": base.day_trades,
        "violations": base.violations,
        "technique": base.technique,
        "risk_engine_passed": base.risk_engine_passed,
        "safety_engine_passed": base.safety_engine_passed,
    }
    data.update(overrides)
    return MarketIntelligenceInput(**data)  # type: ignore[arg-type]


def test_regime_detection_types() -> None:
    cfg = MarketIntelligenceConfig()
    up = detect_market_regime(
        cfg, RegimeInput(trend="up", atr=Decimal("8"), price=Decimal("4000"))
    )
    assert up.primary.value == "trending_up"
    assert up.status == "available"

    high = detect_market_regime(
        cfg,
        RegimeInput(trend="ranging", atr=Decimal("80"), price=Decimal("4000")),
    )
    assert "high_volatility" in [r.value for r in high.regimes]

    news = detect_market_regime(
        cfg, RegimeInput(trend="down", news_driven=True)
    )
    assert "news_driven" in [r.value for r in news.regimes]

    empty = detect_market_regime(cfg, RegimeInput())
    assert empty.status == "unavailable"


def test_consensus_rejects_conflicts() -> None:
    cfg = MarketIntelligenceConfig(min_agreeing_strategies=2)
    conflict = build_strategy_consensus(
        cfg,
        (
            StrategySignal("a", True, "buy", Decimal("80")),
            StrategySignal("b", True, "sell", Decimal("80")),
        ),
    )
    assert conflict.accepted is False
    assert conflict.conflict is True

    ok = build_strategy_consensus(
        cfg,
        (
            StrategySignal("a", True, "buy", Decimal("80")),
            StrategySignal("b", True, "buy", Decimal("70")),
        ),
    )
    assert ok.accepted is True
    assert ok.side == "buy"


def test_opportunity_ranking_threshold() -> None:
    cfg = MarketIntelligenceConfig(min_opportunity_score=Decimal("70"))
    ranking = rank_opportunities(
        cfg,
        (
            OpportunityCandidate("a", "s", "buy", Decimal("90"), Decimal("90")),
            OpportunityCandidate("b", "s", "buy", Decimal("40"), Decimal("40")),
        ),
    )
    assert len(ranking.eligible) == 1
    assert ranking.ranked[0].signal_id == "a"


def test_execution_quality_fail_closed_without_metrics() -> None:
    cfg = MarketIntelligenceConfig()
    empty = review_execution_quality(cfg, ExecutionQualityInput())
    assert empty.passed is False
    assert empty.status == "unavailable"


def test_portfolio_risk_budget() -> None:
    cfg = MarketIntelligenceConfig(daily_risk_budget_pct=Decimal("3"))
    dash = build_portfolio_risk_dashboard(
        cfg,
        PortfolioRiskInput(
            equity=Decimal("10000"),
            allocated_pct=Decimal("10"),
            daily_risk_used_pct=Decimal("3.5"),
        ),
    )
    assert dash.within_budget is False
    assert dash.remaining_risk_budget_pct == Decimal("-0.50")


def test_daily_report_with_violations() -> None:
    report = build_daily_validation_report(
        trades=(
            DayTradeRecord("1", "buy", Decimal("10"), True),
            DayTradeRecord("2", "sell", Decimal("-5"), False),
        ),
        violations=(RuleViolation("spread", "Abnormal spread blocked"),),
    )
    assert report.trade_count == 2
    assert len(report.violations) == 1
    assert any("review" in r.lower() for r in report.recommendations)


def test_engine_fail_closed_without_risk_safety() -> None:
    engine = MarketIntelligenceEngine()
    result = engine.evaluate(
        _full_input(risk_engine_passed=None, safety_engine_passed=None)
    )
    assert result.allow_submit is False
    assert any("Risk Engine" in r for r in result.blocked_reasons)


def test_engine_allow_submit_when_gates_pass() -> None:
    engine = MarketIntelligenceEngine()
    result = engine.evaluate(_full_input())
    assert result.allow_submit is True
    assert result.trade_review.accepted is True
    assert result.capabilities["martingale"] is False


def test_forbidden_technique_blocks() -> None:
    engine = MarketIntelligenceEngine()
    result = engine.evaluate(_full_input(technique="grid"))
    assert result.allow_submit is False


def test_config_hard_locks() -> None:
    cfg = MarketIntelligenceConfig(
        allow_martingale=True,  # type: ignore[arg-type]
        allow_grid=True,  # type: ignore[arg-type]
        allow_average_down=True,  # type: ignore[arg-type]
    )
    assert cfg.allow_martingale is False
    assert cfg.allow_grid is False
    assert cfg.allow_average_down is False


def test_service_roundtrip() -> None:
    from app.application.services.market_intelligence import MarketIntelligenceService

    svc = MarketIntelligenceService()
    status = svc.status()
    assert "market-intelligence" in str(status["version"])
    out = svc.evaluate(
        {
            "regime": {"trend": "up", "atr": "8", "price": "4000"},
            "strategy_signals": [
                {
                    "strategy_id": "a",
                    "enabled": True,
                    "side": "buy",
                    "confidence": "80",
                },
                {
                    "strategy_id": "b",
                    "enabled": True,
                    "side": "buy",
                    "confidence": "75",
                },
            ],
            "opportunities": [
                {
                    "signal_id": "1",
                    "strategy_id": "a",
                    "side": "buy",
                    "confidence": "80",
                    "score": "85",
                }
            ],
            "execution_quality": {
                "entry_quality": "70",
                "exit_quality": "70",
                "timing_quality": "70",
            },
            "portfolio_risk": {
                "equity": "10000",
                "allocated_pct": "10",
                "daily_risk_used_pct": "0.2",
            },
            "ai_health": {
                "decision_quality": "70",
                "execution_success": "70",
                "risk_discipline": "80",
                "system_reliability": "90",
            },
            "risk_engine_passed": True,
            "safety_engine_passed": True,
        }
    )
    assert out["allow_submit"] is True
    assert "trade_review" in out
    assert "daily_report" in out
