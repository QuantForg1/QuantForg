"""Robot V1 orchestrator — evaluate only; never order_send.

Pipeline (mandatory, no shortcuts):
  Signal → Strategy Validation → Risk Engine → Safety Engine → Execution

This module produces an evaluation decision and sizing advice. Execution
remains the sole responsibility of the production Execution Gateway after
Risk + Safety have both allowed the order.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from app.domain.ai_trading_robot.confidence import ConfidenceScore, score_ai_confidence
from app.domain.ai_trading_robot.config import DEFAULT_ROBOT_CONFIG, RobotV1Config
from app.domain.ai_trading_robot.dynamic_sizing import (
    DynamicSizeResult,
    compute_dynamic_size,
)
from app.domain.ai_trading_robot.filters import (
    FilterResult,
    NewsCalendarPort,
    evaluate_consecutive_losses,
    evaluate_daily_drawdown,
    evaluate_news_filter,
    evaluate_session_filter,
    evaluate_spread_filter,
    evaluate_volatility_filter,
)
from app.domain.ai_trading_robot.invariants import (
    assert_no_forbidden_technique,
    reject_averaging_into_loss,
)
from app.domain.ai_trading_robot.journal_intelligence import (
    JournalIntelligence,
    JournalTradeView,
    analyze_journal,
)
from app.domain.ai_trading_robot.self_analysis import (
    SelfAnalysisReport,
    build_self_analysis_report,
)
from app.domain.ai_trading_robot.session_manager import (
    SessionManagerState,
    evaluate_session_manager,
)
from app.domain.ai_trading_robot.smart_management import (
    SmartManagementPolicy,
    smart_management_policy,
)
from app.domain.ai_trading_robot.strategy_health import (
    StrategyHealth,
    compute_strategy_performance,
    score_strategy_health,
)
from app.domain.trading.gold_only import GOLD_SYMBOL

PIPELINE_STAGES: tuple[str, ...] = (
    "signal",
    "strategy_validation",
    "risk_engine",
    "safety_engine",
    "execution",
)


@dataclass(frozen=True, slots=True)
class RobotEvaluateInput:
    """Inputs for a Robot V1 evaluation (no broker side effects)."""

    side: str
    signal_present: bool = True
    strategy_id: str = "default"
    strategy_valid: bool = True
    technique: str | None = None
    equity: Decimal = Decimal("10000")
    stop_distance: Decimal = Decimal("5")
    spread: Decimal | None = None
    atr: Decimal | None = None
    price: Decimal | None = None
    daily_drawdown_pct: Decimal = Decimal("0")
    consecutive_losses: int = 0
    cooldown_active: bool = False
    confluence: Decimal | None = None
    trade_quality: Decimal | None = None
    structure_bias_aligned: bool | None = None
    closed_pnls: tuple[Decimal, ...] = ()
    r_multiples: tuple[Decimal, ...] = ()
    journal_trades: tuple[JournalTradeView, ...] = ()
    open_side: str | None = None
    open_unrealized_pnl: Decimal | None = None
    risk_engine_passed: bool | None = None
    safety_engine_passed: bool | None = None
    as_of: datetime | None = None
    news_calendar: NewsCalendarPort | None = None


@dataclass(frozen=True, slots=True)
class PipelineStageResult:
    name: str
    passed: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {"name": self.name, "passed": self.passed, "reason": self.reason}


@dataclass(frozen=True, slots=True)
class RobotEvaluateResult:
    version: str
    symbol: str
    allow_entry: bool
    pipeline: tuple[PipelineStageResult, ...]
    filters: tuple[FilterResult, ...]
    sizing: DynamicSizeResult
    confidence: ConfidenceScore
    health: StrategyHealth
    session: SessionManagerState
    smart_management: SmartManagementPolicy
    journal: JournalIntelligence
    self_analysis: SelfAnalysisReport
    blocked_reasons: tuple[str, ...]
    capabilities: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "symbol": self.symbol,
            "allow_entry": self.allow_entry,
            "pipeline": [p.to_dict() for p in self.pipeline],
            "filters": [f.to_dict() for f in self.filters],
            "sizing": self.sizing.to_dict(),
            "confidence": self.confidence.to_dict(),
            "health": self.health.to_dict(),
            "session": self.session.to_dict(),
            "smart_management": self.smart_management.to_dict(),
            "journal": self.journal.to_dict(),
            "self_analysis": self.self_analysis.to_dict(),
            "blocked_reasons": list(self.blocked_reasons),
            "capabilities": dict(self.capabilities),
            "execution_note": (
                "Robot V1 never calls order_send. If allow_entry is true, the "
                "operator/gateway must still submit via Execution Gateway after "
                "Risk Engine and Safety Engine ALLOW."
            ),
        }


class RobotV1Orchestrator:
    """Capital-preservation orchestrator for QuantForg AI Trading Robot V1."""

    def __init__(self, config: RobotV1Config | None = None) -> None:
        self.config = config or DEFAULT_ROBOT_CONFIG

    def capabilities(self) -> dict[str, bool]:
        return {
            "dynamic_position_sizing": True,
            "daily_drawdown_protection": True,
            "consecutive_loss_protection": True,
            "session_filter": True,
            "spread_filter": True,
            "volatility_filter": True,
            "news_filter_architecture": True,
            "ai_confidence_scoring": True,
            "smart_trade_management": True,
            "strategy_performance_engine": True,
            "strategy_health_score": True,
            "automatic_strategy_pause": True,
            "trading_session_manager": True,
            "trade_journal_intelligence": True,
            "self_analysis_reports": True,
            "martingale": False,
            "grid": False,
            "average_losing_positions": False,
        }

    def evaluate(self, inp: RobotEvaluateInput) -> RobotEvaluateResult:
        blocked: list[str] = []
        as_of = inp.as_of or datetime.now(UTC)

        # --- Invariants ---
        tech = assert_no_forbidden_technique(inp.technique)
        if not tech.ok:
            blocked.extend(tech.reasons)
        avg = reject_averaging_into_loss(
            open_side=inp.open_side,
            proposed_side=inp.side,
            open_unrealized_pnl=inp.open_unrealized_pnl,
        )
        if not avg.ok:
            blocked.extend(avg.reasons)

        # --- Filters (1-7) ---
        session_f = evaluate_session_filter(self.config, as_of=as_of)
        spread_f = evaluate_spread_filter(self.config, spread=inp.spread)
        vol_f = evaluate_volatility_filter(
            self.config, atr=inp.atr, price=inp.price
        )
        news_f = evaluate_news_filter(
            self.config, as_of=as_of, calendar=inp.news_calendar
        )
        dd_f = evaluate_daily_drawdown(
            self.config, daily_drawdown_pct=inp.daily_drawdown_pct
        )
        loss_f = evaluate_consecutive_losses(
            self.config,
            consecutive_losses=inp.consecutive_losses,
            cooldown_active=inp.cooldown_active,
        )
        filters: tuple[FilterResult, ...] = (
            session_f,
            spread_f,
            vol_f,
            news_f,
            dd_f,
            loss_f,
        )
        for f in filters:
            if not f.passed:
                blocked.append(f.reason)

        # --- Strategy performance + health (10-12) ---
        perf = compute_strategy_performance(
            strategy_id=inp.strategy_id,
            closed_pnls=list(inp.closed_pnls),
            r_multiples=list(inp.r_multiples) if inp.r_multiples else None,
        )
        health = score_strategy_health(self.config, perf)
        if health.auto_pause:
            blocked.append(
                f"Strategy {health.strategy_id} auto-paused (health {health.score})."
            )
        elif not inp.strategy_valid:
            blocked.append("Strategy validation failed.")

        # --- Dynamic sizing (1) ---
        sizing = compute_dynamic_size(
            config=self.config,
            equity=inp.equity,
            stop_distance=inp.stop_distance,
            current_drawdown_pct=inp.daily_drawdown_pct,
            consecutive_losses=inp.consecutive_losses,
        )

        # --- AI confidence (8) ---
        confidence = score_ai_confidence(
            self.config,
            confluence=inp.confluence,
            trade_quality=inp.trade_quality,
            structure_bias_aligned=inp.structure_bias_aligned,
            spread_ok=spread_f.passed,
            volatility_ok=vol_f.passed,
            strategy_health=health.score,
        )
        if not confidence.passed:
            blocked.extend(confidence.reasons)

        # --- Session manager (13) ---
        session = evaluate_session_manager(self.config, as_of=as_of)
        if not session.entries_allowed:
            blocked.append(session.reason)

        # --- Smart management policy (9) ---
        smart = smart_management_policy(self.config)

        # --- Journal + self-analysis (14-15) ---
        journal = analyze_journal(inp.journal_trades)

        # --- Pipeline stages ---
        risk_passed = inp.risk_engine_passed
        safety_passed = inp.safety_engine_passed
        # Fail closed when Risk/Safety not yet assessed for a live entry path
        if risk_passed is None:
            risk_ok = False
            risk_reason = (
                "Risk Engine not assessed — fail closed. "
                "Call /risk/check before execution."
            )
            blocked.append(risk_reason)
        else:
            risk_ok = risk_passed
            risk_reason = (
                "Risk Engine ALLOW"
                if risk_passed
                else "Risk Engine did not ALLOW — entry blocked."
            )
            if not risk_passed:
                blocked.append(risk_reason)

        if safety_passed is None:
            safety_ok = False
            safety_reason = (
                "Safety Engine not assessed — fail closed. "
                "Execution Safety must ALLOW before order_send."
            )
            blocked.append(safety_reason)
        else:
            safety_ok = safety_passed
            safety_reason = (
                "Safety Engine ALLOW"
                if safety_passed
                else "Safety Engine did not ALLOW — entry blocked."
            )
            if not safety_passed:
                blocked.append(safety_reason)

        signal_ok = inp.signal_present and tech.ok and avg.ok
        strategy_ok = (
            inp.strategy_valid
            and not health.auto_pause
            and all(f.passed for f in filters)
            and confidence.passed
            and session.entries_allowed
        )
        # Execution stage is never claimed complete by Robot V1
        exec_ok = False
        exec_reason = (
            "Execution reserved for Execution Gateway after Risk+Safety ALLOW. "
            "Robot V1 does not order_send."
        )

        pipeline = (
            PipelineStageResult(
                "signal",
                signal_ok,
                "Signal present" if signal_ok else "Signal/invariant failed",
            ),
            PipelineStageResult(
                "strategy_validation",
                strategy_ok,
                (
                    "Strategy + filters + confidence OK"
                    if strategy_ok
                    else "Strategy validation / filters / confidence blocked"
                ),
            ),
            PipelineStageResult("risk_engine", risk_ok, risk_reason),
            PipelineStageResult("safety_engine", safety_ok, safety_reason),
            PipelineStageResult("execution", exec_ok, exec_reason),
        )

        allow_entry = (
            signal_ok
            and strategy_ok
            and risk_ok
            and safety_ok
            and sizing.approved_lots > 0
            and not blocked
        )
        # If somehow blocked empty but stages fail, still deny
        if not (signal_ok and strategy_ok and risk_ok and safety_ok):
            allow_entry = False
        if sizing.approved_lots <= 0:
            allow_entry = False
            blocked.append("Approved lots is zero — no entry.")

        # Deduplicate blocked reasons while preserving order
        seen: set[str] = set()
        unique_blocked: list[str] = []
        for r in blocked:
            if r not in seen:
                seen.add(r)
                unique_blocked.append(r)

        filters_passed = sum(1 for f in filters if f.passed)
        report = build_self_analysis_report(
            self.config,
            journal=journal,
            health=health,
            filters_passed=filters_passed,
            filters_total=len(filters),
            risk_passed=risk_passed,
            safety_passed=safety_passed,
            forbidden_attempts=0 if tech.ok and avg.ok else 1,
        )

        return RobotEvaluateResult(
            version=self.config.version,
            symbol=GOLD_SYMBOL,
            allow_entry=allow_entry,
            pipeline=pipeline,
            filters=filters,
            sizing=sizing,
            confidence=confidence,
            health=health,
            session=session,
            smart_management=smart,
            journal=journal,
            self_analysis=report,
            blocked_reasons=tuple(unique_blocked),
            capabilities=self.capabilities(),
        )

    def status(self) -> dict[str, object]:
        cfg = self.config.to_dict()
        return {
            "version": self.config.version,
            "symbol": GOLD_SYMBOL,
            "mission": cfg["mission"],
            "pipeline": list(PIPELINE_STAGES),
            "capabilities": self.capabilities(),
            "config": cfg,
            "smart_management": smart_management_policy(self.config).to_dict(),
            "disclaimer": (
                "QuantForg AI Trading Robot V1 maximizes discipline and capital "
                "preservation. It never promises profitability and never bypasses "
                "Risk Engine or Safety Engine."
            ),
        }

    def self_analysis(
        self,
        *,
        journal_trades: Sequence[JournalTradeView] = (),
        closed_pnls: Sequence[Decimal] = (),
        strategy_id: str = "default",
    ) -> SelfAnalysisReport:
        journal = analyze_journal(journal_trades)
        perf = compute_strategy_performance(
            strategy_id=strategy_id, closed_pnls=list(closed_pnls)
        )
        health = score_strategy_health(self.config, perf)
        return build_self_analysis_report(
            self.config, journal=journal, health=health
        )
