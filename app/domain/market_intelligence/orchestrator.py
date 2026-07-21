"""Market Intelligence Engine V1 orchestrator — evaluate only; never order_send."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.ai_trading_robot.invariants import assert_no_forbidden_technique
from app.domain.market_intelligence.config import (
    DEFAULT_MI_CONFIG,
    MarketIntelligenceConfig,
)
from app.domain.market_intelligence.consensus import (
    ConsensusResult,
    StrategySignal,
    build_strategy_consensus,
)
from app.domain.market_intelligence.daily_report import (
    DailyValidationReport,
    DayTradeRecord,
    RuleViolation,
    build_daily_validation_report,
)
from app.domain.market_intelligence.execution_quality import (
    ExecutionQualityInput,
    ExecutionQualityReview,
    review_execution_quality,
)
from app.domain.market_intelligence.health_dashboard import (
    AiHealthDashboard,
    AiHealthInput,
    build_ai_health_dashboard,
)
from app.domain.market_intelligence.opportunity import (
    OpportunityCandidate,
    OpportunityRanking,
    rank_opportunities,
)
from app.domain.market_intelligence.portfolio_risk import (
    PortfolioRiskDashboard,
    PortfolioRiskInput,
    build_portfolio_risk_dashboard,
)
from app.domain.market_intelligence.regime import (
    RegimeAssessment,
    RegimeInput,
    detect_market_regime,
)
from app.domain.market_intelligence.trade_review import (
    AiTradeReview,
    build_ai_trade_review,
)
from app.domain.trading.gold_only import GOLD_SYMBOL


@dataclass(frozen=True, slots=True)
class MarketIntelligenceInput:
    regime: RegimeInput = field(default_factory=RegimeInput)
    strategy_signals: tuple[StrategySignal, ...] = ()
    opportunities: tuple[OpportunityCandidate, ...] = ()
    execution_quality: ExecutionQualityInput = field(
        default_factory=ExecutionQualityInput
    )
    portfolio_risk: PortfolioRiskInput = field(default_factory=PortfolioRiskInput)
    ai_health: AiHealthInput = field(default_factory=AiHealthInput)
    day_trades: tuple[DayTradeRecord, ...] = ()
    violations: tuple[RuleViolation, ...] = ()
    technique: str | None = None
    risk_engine_passed: bool | None = None
    safety_engine_passed: bool | None = None


@dataclass(frozen=True, slots=True)
class MarketIntelligenceResult:
    version: str
    symbol: str
    allow_submit: bool
    regime: RegimeAssessment
    consensus: ConsensusResult
    opportunities: OpportunityRanking
    execution_quality: ExecutionQualityReview
    trade_review: AiTradeReview
    portfolio_risk: PortfolioRiskDashboard
    ai_health: AiHealthDashboard
    daily_report: DailyValidationReport
    blocked_reasons: tuple[str, ...]
    capabilities: dict[str, bool]

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "symbol": self.symbol,
            "allow_submit": self.allow_submit,
            "regime": self.regime.to_dict(),
            "consensus": self.consensus.to_dict(),
            "opportunities": self.opportunities.to_dict(),
            "execution_quality": self.execution_quality.to_dict(),
            "trade_review": self.trade_review.to_dict(),
            "portfolio_risk": self.portfolio_risk.to_dict(),
            "ai_health": self.ai_health.to_dict(),
            "daily_report": self.daily_report.to_dict(),
            "blocked_reasons": list(self.blocked_reasons),
            "capabilities": dict(self.capabilities),
            "execution_note": (
                "Market Intelligence V1 never calls order_send and does not "
                "modify the execution pipeline. allow_submit only means "
                "pre-submit gates cleared; live paths still require Risk + "
                "Safety ALLOW via Execution Gateway."
            ),
        }


class MarketIntelligenceEngine:
    """Institutional Market Intelligence Engine V1."""

    def __init__(self, config: MarketIntelligenceConfig | None = None) -> None:
        self.config = config or DEFAULT_MI_CONFIG

    def capabilities(self) -> dict[str, bool]:
        return {
            "market_regime_detection": True,
            "strategy_consensus": True,
            "opportunity_ranking": True,
            "execution_quality_review": True,
            "ai_trade_review": True,
            "portfolio_risk_dashboard": True,
            "ai_health_dashboard": True,
            "daily_validation_report": True,
            "martingale": False,
            "grid": False,
            "average_down": False,
        }

    def status(self) -> dict[str, object]:
        cfg = self.config.to_dict()
        return {
            "version": self.config.version,
            "symbol": GOLD_SYMBOL,
            "mission": cfg["mission"],
            "capabilities": self.capabilities(),
            "config": cfg,
            "disclaimer": (
                "Market Intelligence Engine V1 evaluates conditions before "
                "submit. It never invents market data, never promises "
                "profitability, and never bypasses Risk Engine or Safety Engine."
            ),
        }

    def evaluate(self, inp: MarketIntelligenceInput) -> MarketIntelligenceResult:
        blocked: list[str] = []

        tech = assert_no_forbidden_technique(inp.technique)
        if not tech.ok:
            blocked.extend(tech.reasons)

        regime = detect_market_regime(self.config, inp.regime)
        if regime.status != "available":
            blocked.append(regime.reason)

        consensus = build_strategy_consensus(self.config, inp.strategy_signals)
        if not consensus.accepted:
            blocked.extend(consensus.reasons)

        opportunities = rank_opportunities(self.config, inp.opportunities)
        if not opportunities.eligible:
            blocked.extend(opportunities.reasons)

        execution = review_execution_quality(self.config, inp.execution_quality)
        if not execution.passed:
            blocked.extend(execution.reasons[:2])

        portfolio = build_portfolio_risk_dashboard(
            self.config, inp.portfolio_risk
        )
        if not portfolio.within_budget:
            blocked.extend(portfolio.reasons[:2])

        health = build_ai_health_dashboard(self.config, inp.ai_health)
        # Health is advisory for dashboard; only block if explicitly unhealthy
        # when metrics are available
        if health.status == "available" and not health.healthy:
            blocked.append(
                f"AI health below configured thresholds (overall {health.overall})."
            )

        risk_ok = inp.risk_engine_passed is True
        safety_ok = inp.safety_engine_passed is True
        if inp.risk_engine_passed is None:
            blocked.append(
                "Risk Engine not assessed — fail closed before any submit."
            )
        elif not risk_ok:
            blocked.append("Risk Engine did not ALLOW.")
        if inp.safety_engine_passed is None:
            blocked.append(
                "Safety Engine not assessed — fail closed before any submit."
            )
        elif not safety_ok:
            blocked.append("Safety Engine did not ALLOW.")

        allow = (
            tech.ok
            and regime.status == "available"
            and consensus.accepted
            and bool(opportunities.eligible)
            and execution.passed
            and portfolio.within_budget
            and risk_ok
            and safety_ok
            and not (health.status == "available" and not health.healthy)
        )

        review = build_ai_trade_review(
            gate_open=allow,
            regime=regime,
            consensus=consensus,
            opportunities=opportunities,
            execution=execution,
            risk_passed=inp.risk_engine_passed,
            safety_passed=inp.safety_engine_passed,
        )
        daily = build_daily_validation_report(
            trades=inp.day_trades, violations=inp.violations
        )

        seen: set[str] = set()
        unique: list[str] = []
        for reason in blocked:
            if reason not in seen:
                seen.add(reason)
                unique.append(reason)

        return MarketIntelligenceResult(
            version=self.config.version,
            symbol=GOLD_SYMBOL,
            allow_submit=allow,
            regime=regime,
            consensus=consensus,
            opportunities=opportunities,
            execution_quality=execution,
            trade_review=review,
            portfolio_risk=portfolio,
            ai_health=health,
            daily_report=daily,
            blocked_reasons=tuple(unique),
            capabilities=self.capabilities(),
        )
