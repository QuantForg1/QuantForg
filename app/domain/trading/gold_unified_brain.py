"""Gold Unified Decision Brain — coordinates existing XAUUSD strategy profiles.

Wraps the production AI-scalping strategy registry (SMC / trend / breakout /
range / momentum). Does **not** place orders, bypass LiveTradingController,
or invent profitability. Catalog-only UI modules are labeled separately.

ADR alignment: AI/OpenAI remain advisory; Risk + live-trading ENABLE remain
authoritative.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.domain.institutional_trading.ai_scalping.strategies.evaluate import (
    evaluate_all_strategies,
)
from app.domain.institutional_trading.ai_scalping.strategies.orchestrator import (
    orchestrate_strategies,
)
from app.domain.institutional_trading.ai_scalping.strategies.registry import (
    ALL_STRATEGIES,
)

# UI / operator preference modules (frontend AUTO_STRATEGY_MODULES). These are
# SMC *components*, not independent live strategy engines.
CATALOG_ONLY_MODULES: tuple[dict[str, str], ...] = (
    {
        "id": "smart_money_concepts",
        "label": "Smart Money Concepts",
        "status": "component",
        "maps_to": "smc_scalping",
        "note": "UI toggle preference; live path uses smc_scalping profile",
    },
    {
        "id": "liquidity_sweep",
        "label": "Liquidity Sweep",
        "status": "component",
        "maps_to": "smc_scalping / range_mean_reversion",
        "note": "Factor inside SMC/range profiles — not a standalone OMS strategy",
    },
    {
        "id": "bos",
        "label": "BOS",
        "status": "component",
        "maps_to": "smc_scalping / trend_continuation / breakout_scalping",
        "note": "Structure factor — not independently eligible for live submit",
    },
    {
        "id": "choch",
        "label": "CHOCH",
        "status": "component",
        "maps_to": "smc_scalping / range_mean_reversion",
        "note": "Structure factor — not independently eligible for live submit",
    },
    {
        "id": "order_block",
        "label": "Order Block",
        "status": "component",
        "maps_to": "smc_scalping",
        "note": "SMC component weight — not a standalone live strategy",
    },
    {
        "id": "fair_value_gap",
        "label": "Fair Value Gap",
        "status": "component",
        "maps_to": "smc_scalping",
        "note": "SMC component weight — not a standalone live strategy",
    },
)

# Named in product asks but not registered as independent live profiles yet.
NOT_IMPLEMENTED_AS_LIVE_PROFILES: tuple[dict[str, str], ...] = (
    {
        "id": "session_breakout",
        "label": "Session Breakout",
        "status": "catalog_only",
        "note": "No dedicated StrategyDefinition; session gates exist elsewhere",
    },
    {
        "id": "ma_cross",
        "label": "MA Cross",
        "status": "catalog_only",
        "note": "EMA factor exists; no standalone live strategy profile",
    },
    {
        "id": "rsi",
        "label": "RSI",
        "status": "catalog_only",
        "note": "Not a registered live StrategyDefinition",
    },
    {
        "id": "macd",
        "label": "MACD",
        "status": "catalog_only",
        "note": "Not a registered live StrategyDefinition",
    },
    {
        "id": "bollinger_bands",
        "label": "Bollinger Bands",
        "status": "catalog_only",
        "note": "Not a registered live StrategyDefinition",
    },
)

# Align with SOE MAX_QUOTE_AGE_SECONDS — one freshness policy for Gold decisions.
DEFAULT_MAX_QUOTE_AGE_SECONDS = 8.0


@dataclass(frozen=True, slots=True)
class UnifiedGoldDecision:
    """Auditable decision from the Gold unified brain."""

    decision: str  # BUY | SELL | NO_TRADE
    symbol: str
    regime: str
    selected_strategy_id: str | None
    selected_strategy_name: str | None
    confidence: int
    quality: int
    reasons: tuple[str, ...]
    rejected_strategies: tuple[dict[str, Any], ...]
    conflicting: bool
    stale_data: bool
    as_of: str
    authorizes_trade: bool = False
    profitability_claimed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "symbol": self.symbol,
            "regime": self.regime,
            "selected_strategy_id": self.selected_strategy_id,
            "selected_strategy_name": self.selected_strategy_name,
            "confidence": self.confidence,
            "quality": self.quality,
            "reasons": list(self.reasons),
            "rejected_strategies": list(self.rejected_strategies),
            "conflicting": self.conflicting,
            "stale_data": self.stale_data,
            "as_of": self.as_of,
            "authorizes_trade": False,
            "profitability_claimed": False,
            "advisory_note": (
                "Unified brain output is a strategy recommendation only. "
                "Live submit still requires LiveTradingController ENABLED, "
                "Risk Engine pass, and EXECUTION_ENABLED."
            ),
        }


def inventory_strategies() -> dict[str, Any]:
    """Classify live-eligible profiles vs catalog/UI-only modules."""
    live = [
        {
            "id": s.strategy_id,
            "name": s.name,
            "status": "live_eligible_profile",
            "forbid_regimes": list(s.forbid_regimes or ()),
            "require_regimes": list(s.require_regimes or ()),
            "explanation": s.explanation,
            "live_eligible": True,
            "evidence_note": (
                "Eligible for ITE strategy selection after SCALPING_V1 base gates. "
                "Not a profitability guarantee; promotion still requires OOS evidence."
            ),
        }
        for s in ALL_STRATEGIES
    ]
    return {
        "symbol_focus": "XAUUSD",
        "live_eligible_profiles": live,
        "ui_component_modules": list(CATALOG_ONLY_MODULES),
        "catalog_only_not_live_profiles": list(NOT_IMPLEMENTED_AS_LIVE_PROFILES),
        "engine": "ai_scalping.strategies (Gold Unified Brain facade)",
        "duplicate_engines": False,
        "as_of": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _quote_age_seconds(score: dict[str, Any]) -> float | None:
    for key in ("quote_age_seconds", "tick_age_seconds", "data_age_seconds"):
        raw = score.get(key)
        if raw is None:
            continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            continue
    return None


def decide_gold(
    score: dict[str, Any],
    *,
    max_quote_age_seconds: float = DEFAULT_MAX_QUOTE_AGE_SECONDS,
    live_boosts: dict[str, float] | None = None,
) -> UnifiedGoldDecision:
    """Coordinate all live-eligible profiles for one Gold score snapshot.

    Conflict rule: if multiple strategies pass with opposing BUY/SELL → NO_TRADE.
    Stale quote → NO_TRADE. Never sets authorizes_trade.
    Non-Gold symbols are rejected at the analysis boundary.
    """
    from app.domain.institutional_trading.ai_scalping.strategies.cycle_activity import (
        record_cycle_start,
        record_soe_verdict,
        record_strategy_evaluation,
    )
    from app.domain.institutional_trading.ai_scalping.strategies.stats import (
        get_strategy_stats_book,
    )
    from app.domain.trading.gold_only import (
        DisabledAutonomousSymbolError,
        require_gold_trading_symbol,
    )

    raw_symbol = str(score.get("symbol") or "XAUUSD").upper()
    as_of = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    regime = str(score.get("market_regime") or score.get("regime") or "unknown")
    age = _quote_age_seconds(score)

    def _f(key: str) -> float | None:
        raw = score.get(key)
        if raw is None and key == "net_reward_risk":
            raw = score.get("expected_net_rr") or score.get("expected_rr")
        try:
            return float(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None

    def _i(key: str) -> int | None:
        raw = score.get(key)
        try:
            return int(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None

    atr_raw = score.get("atr_pct")
    if atr_raw is None:
        thr = score.get("thresholds")
        if isinstance(thr, dict):
            atr_raw = thr.get("atr_pct")
    try:
        atr_f = float(atr_raw) if atr_raw is not None else None
    except (TypeError, ValueError):
        atr_f = None
    record_cycle_start(
        symbol=raw_symbol,
        quote_age_seconds=age,
        regime=regime,
        atr_pct=atr_f,
        net_reward_risk=_f("net_reward_risk"),
        trade_quality=_i("trade_quality"),
    )
    try:
        symbol = require_gold_trading_symbol(raw_symbol)
    except DisabledAutonomousSymbolError:
        record_soe_verdict(
            decision="NO_TRADE",
            reasons=(f"Non-Gold symbol rejected at analysis boundary: {raw_symbol}",),
        )
        return UnifiedGoldDecision(
            decision="NO_TRADE",
            symbol=raw_symbol,
            regime=regime,
            selected_strategy_id=None,
            selected_strategy_name=None,
            confidence=0,
            quality=0,
            reasons=(f"Non-Gold symbol rejected at analysis boundary: {raw_symbol}",),
            rejected_strategies=(),
            conflicting=False,
            stale_data=False,
            as_of=as_of,
        )

    stale = age is not None and age > float(max_quote_age_seconds)
    if stale:
        record_soe_verdict(
            decision="NO_TRADE",
            reasons=(
                f"Stale market data: quote_age_seconds={age} > {max_quote_age_seconds}",
            ),
            stale_data=True,
        )
        return UnifiedGoldDecision(
            decision="NO_TRADE",
            symbol=symbol,
            regime=regime,
            selected_strategy_id=None,
            selected_strategy_name=None,
            confidence=0,
            quality=0,
            reasons=(
                f"Stale market data: quote_age_seconds={age} > {max_quote_age_seconds}",
            ),
            rejected_strategies=(),
            conflicting=False,
            stale_data=True,
            as_of=as_of,
        )

    gold_score = dict(score)
    gold_score["symbol"] = symbol
    evaluations = evaluate_all_strategies(gold_score, live_boosts=live_boosts)
    book = get_strategy_stats_book()
    for ev in evaluations:
        book.record_evaluation(ev.strategy_id, passed=ev.passed)
        record_strategy_evaluation(
            strategy_id=ev.strategy_id,
            name=ev.name,
            passed=ev.passed,
            direction=ev.direction,
            quality=ev.quality,
            confidence=ev.confidence,
            reject_reason=ev.reject_reason,
        )
    verdict = orchestrate_strategies(
        evaluations,
        live_boosts=live_boosts,
        stats_snapshot=book.snapshot(),
        score=gold_score,
    )
    rejected = tuple(r.to_dict() for r in verdict.rejected)

    if verdict.prefer_no_trade or verdict.selected is None:
        record_soe_verdict(
            decision="NO_TRADE",
            reasons=verdict.reasons
            or ("SOE prefer no trade — no selectable strategy",),
        )
        return UnifiedGoldDecision(
            decision="NO_TRADE",
            symbol=symbol,
            regime=regime,
            selected_strategy_id=None,
            selected_strategy_name=None,
            confidence=0,
            quality=0,
            reasons=verdict.reasons
            or ("SOE prefer no trade — no selectable strategy",),
            rejected_strategies=rejected,
            conflicting=verdict.conflicting,
            stale_data=False,
            as_of=as_of,
        )

    best = verdict.selected
    book.record_accepted(best.strategy_id)
    record_soe_verdict(
        decision=best.direction,
        reasons=verdict.reasons,
        selected_strategy_id=best.strategy_id,
    )
    return UnifiedGoldDecision(
        decision=best.direction,
        symbol=symbol,
        regime=regime,
        selected_strategy_id=best.strategy_id,
        selected_strategy_name=best.name,
        confidence=int(best.confidence),
        quality=int(best.quality),
        reasons=verdict.reasons,
        rejected_strategies=rejected,
        conflicting=False,
        stale_data=False,
        as_of=as_of,
    )
