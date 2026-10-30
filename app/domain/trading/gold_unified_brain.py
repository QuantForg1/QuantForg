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
from app.domain.institutional_trading.ai_scalping.strategies.registry import (
    ALL_STRATEGIES,
)
from app.domain.institutional_trading.ai_scalping.strategies.select import (
    best_strategy_for_symbol,
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

DEFAULT_MAX_QUOTE_AGE_SECONDS = 30.0


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
    from app.domain.trading.gold_only import (
        DisabledAutonomousSymbolError,
        require_gold_trading_symbol,
    )

    raw_symbol = str(score.get("symbol") or "XAUUSD").upper()
    as_of = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    regime = str(score.get("market_regime") or score.get("regime") or "unknown")
    try:
        symbol = require_gold_trading_symbol(raw_symbol)
    except DisabledAutonomousSymbolError:
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

    age = _quote_age_seconds(score)
    stale = age is not None and age > float(max_quote_age_seconds)
    if stale:
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
    passed = [e for e in evaluations if e.passed]
    rejected = [
        {
            "strategy_id": e.strategy_id,
            "name": e.name,
            "reject_reason": e.reject_reason,
            "quality": e.quality,
            "confidence": e.confidence,
        }
        for e in evaluations
        if not e.passed
    ]

    if not passed:
        return UnifiedGoldDecision(
            decision="NO_TRADE",
            symbol=symbol,
            regime=regime,
            selected_strategy_id=None,
            selected_strategy_name=None,
            confidence=0,
            quality=0,
            reasons=("No live-eligible strategy passed filters / base gates",),
            rejected_strategies=tuple(rejected),
            conflicting=False,
            stale_data=False,
            as_of=as_of,
        )

    directions = {e.direction for e in passed if e.direction in {"BUY", "SELL"}}
    if len(directions) > 1:
        return UnifiedGoldDecision(
            decision="NO_TRADE",
            symbol=symbol,
            regime=regime,
            selected_strategy_id=None,
            selected_strategy_name=None,
            confidence=0,
            quality=0,
            reasons=(
                "Conflicting strategy directions: "
                + ", ".join(f"{e.strategy_id}={e.direction}" for e in passed),
            ),
            rejected_strategies=tuple(rejected),
            conflicting=True,
            stale_data=False,
            as_of=as_of,
        )

    best = best_strategy_for_symbol(passed)
    if best is None:
        return UnifiedGoldDecision(
            decision="NO_TRADE",
            symbol=symbol,
            regime=regime,
            selected_strategy_id=None,
            selected_strategy_name=None,
            confidence=0,
            quality=0,
            reasons=("Strategy selection produced no winner",),
            rejected_strategies=tuple(rejected),
            conflicting=False,
            stale_data=False,
            as_of=as_of,
        )

    superseded = [
        f"superseded:{e.strategy_id}(q={e.quality})"
        for e in passed
        if e.strategy_id != best.strategy_id
    ]
    reasons = (
        f"Selected {best.strategy_id} direction={best.direction} "
        f"quality={best.quality} confidence={best.confidence}",
        *superseded,
        best.explanation,
    )
    return UnifiedGoldDecision(
        decision=best.direction,
        symbol=symbol,
        regime=regime,
        selected_strategy_id=best.strategy_id,
        selected_strategy_name=best.name,
        confidence=int(best.confidence),
        quality=int(best.quality),
        reasons=tuple(reasons),
        rejected_strategies=tuple(rejected),
        conflicting=False,
        stale_data=False,
        as_of=as_of,
    )
