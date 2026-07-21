"""Application service — Market Intelligence Engine V1."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from app.domain.market_intelligence import (
    MarketIntelligenceEngine,
    MarketIntelligenceInput,
)
from app.domain.market_intelligence.config import (
    DEFAULT_MI_CONFIG,
    MarketIntelligenceConfig,
)
from app.domain.market_intelligence.consensus import StrategySignal
from app.domain.market_intelligence.daily_report import DayTradeRecord, RuleViolation
from app.domain.market_intelligence.execution_quality import ExecutionQualityInput
from app.domain.market_intelligence.health_dashboard import AiHealthInput
from app.domain.market_intelligence.opportunity import OpportunityCandidate
from app.domain.market_intelligence.portfolio_risk import PortfolioRiskInput
from app.domain.market_intelligence.regime import RegimeInput


def _dec(value: Any, default: str | None = None) -> Decimal | None:
    if value is None:
        return Decimal(default) if default is not None else None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal(default) if default is not None else None


def _opt_bool(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


class MarketIntelligenceService:
    def __init__(self, config: MarketIntelligenceConfig | None = None) -> None:
        self._engine = MarketIntelligenceEngine(config or DEFAULT_MI_CONFIG)

    def status(self) -> dict[str, object]:
        return self._engine.status()

    def evaluate(self, payload: dict[str, Any]) -> dict[str, object]:
        regime_raw = payload.get("regime") or {}
        if not isinstance(regime_raw, dict):
            regime_raw = {}

        signals: list[StrategySignal] = []
        for row in payload.get("strategy_signals") or []:
            if not isinstance(row, dict):
                continue
            conf = _dec(row.get("confidence"), "0") or Decimal("0")
            signals.append(
                StrategySignal(
                    strategy_id=str(row.get("strategy_id") or "unknown"),
                    enabled=bool(row.get("enabled", True)),
                    side=str(row.get("side") or "flat"),
                    confidence=conf,
                    notes=str(row.get("notes") or ""),
                )
            )

        opps: list[OpportunityCandidate] = []
        for row in payload.get("opportunities") or []:
            if not isinstance(row, dict):
                continue
            conf = _dec(row.get("confidence"), "0") or Decimal("0")
            score = _dec(row.get("score"))
            opps.append(
                OpportunityCandidate(
                    signal_id=str(row.get("signal_id") or "sig"),
                    strategy_id=str(row.get("strategy_id") or "unknown"),
                    side=str(row.get("side") or "buy"),
                    confidence=conf,
                    score=score,
                    notes=str(row.get("notes") or ""),
                )
            )

        eq_raw = payload.get("execution_quality") or {}
        if not isinstance(eq_raw, dict):
            eq_raw = {}
        pr_raw = payload.get("portfolio_risk") or {}
        if not isinstance(pr_raw, dict):
            pr_raw = {}
        ah_raw = payload.get("ai_health") or {}
        if not isinstance(ah_raw, dict):
            ah_raw = {}

        trades: list[DayTradeRecord] = []
        for row in payload.get("day_trades") or []:
            if not isinstance(row, dict):
                continue
            trades.append(
                DayTradeRecord(
                    trade_id=str(row.get("trade_id") or "t"),
                    side=str(row.get("side") or "buy"),
                    pnl=_dec(row.get("pnl")),
                    accepted=_opt_bool(row.get("accepted")),
                    notes=str(row.get("notes") or ""),
                )
            )

        violations: list[RuleViolation] = []
        for row in payload.get("violations") or []:
            if not isinstance(row, dict):
                continue
            violations.append(
                RuleViolation(
                    code=str(row.get("code") or "rule"),
                    detail=str(row.get("detail") or ""),
                )
            )

        inp = MarketIntelligenceInput(
            regime=RegimeInput(
                trend=(
                    str(regime_raw["trend"]) if regime_raw.get("trend") else None
                ),
                atr=_dec(regime_raw.get("atr")),
                price=_dec(regime_raw.get("price")),
                news_driven=_opt_bool(regime_raw.get("news_driven")),
                structure_label=(
                    str(regime_raw["structure_label"])
                    if regime_raw.get("structure_label")
                    else None
                ),
            ),
            strategy_signals=tuple(signals),
            opportunities=tuple(opps),
            execution_quality=ExecutionQualityInput(
                entry_quality=_dec(eq_raw.get("entry_quality")),
                exit_quality=_dec(eq_raw.get("exit_quality")),
                timing_quality=_dec(eq_raw.get("timing_quality")),
                sample_note=(
                    str(eq_raw["sample_note"])
                    if eq_raw.get("sample_note")
                    else None
                ),
            ),
            portfolio_risk=PortfolioRiskInput(
                equity=_dec(pr_raw.get("equity")),
                allocated_pct=_dec(pr_raw.get("allocated_pct")),
                daily_risk_used_pct=_dec(pr_raw.get("daily_risk_used_pct")),
            ),
            ai_health=AiHealthInput(
                decision_quality=_dec(ah_raw.get("decision_quality")),
                execution_success=_dec(ah_raw.get("execution_success")),
                risk_discipline=_dec(ah_raw.get("risk_discipline")),
                system_reliability=_dec(ah_raw.get("system_reliability")),
            ),
            day_trades=tuple(trades),
            violations=tuple(violations),
            technique=(
                str(payload["technique"]) if payload.get("technique") else None
            ),
            risk_engine_passed=_opt_bool(payload.get("risk_engine_passed")),
            safety_engine_passed=_opt_bool(payload.get("safety_engine_passed")),
        )
        return self._engine.evaluate(inp).to_dict()
