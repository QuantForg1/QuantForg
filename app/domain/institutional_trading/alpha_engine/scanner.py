"""Multi-symbol AI scanner — score & rank every cycle."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.domain.institutional_trading.alpha_engine.config import (
    DEFAULT_ALPHA_CONFIG,
    InstitutionalAlphaConfig,
)
from app.domain.institutional_trading.alpha_engine.correlation import (
    CorrelationDecision,
    may_open_with_correlation,
)
from app.domain.institutional_trading.alpha_engine.ranking import (
    SymbolOpportunity,
    rank_opportunities,
    score_opportunity,
    top_executable,
)
from app.domain.institutional_trading.alpha_engine.risk_allocation import (
    RiskAllocation,
    allocate_risk_pct,
    get_smart_recovery,
    min_score_with_recovery,
)
from app.domain.institutional_trading.ai_scalping.session_intelligence import (
    assess_session,
)
from app.domain.institutional_trading.ai_scalping.spread_intelligence import (
    assess_spread,
)


@dataclass(frozen=True, slots=True)
class SymbolMarketFacts:
    """Lightweight per-symbol facts for ranking (caller-supplied; never invented)."""

    symbol: str
    mid: Decimal | None = None
    spread: Decimal | None = None
    atr: Decimal | None = None
    session: str = "off_hours"
    trend_strength: int = 50
    momentum: int = 50
    liquidity: int = 50
    volatility: int = 50
    ai_confidence: int = 50
    expected_rr: Decimal = Decimal("1.5")
    direction: str = "NONE"
    reasons: tuple[str, ...] = ()


@dataclass
class AlphaScanResult:
    as_of: str
    opportunities: list[SymbolOpportunity]
    selected: list[SymbolOpportunity]
    correlation_blocks: list[dict[str, Any]] = field(default_factory=list)
    risk_allocations: dict[str, dict[str, Any]] = field(default_factory=dict)
    recovery: dict[str, Any] = field(default_factory=dict)
    portfolio_risk_pct: float = 0.0
    config_version: str = DEFAULT_ALPHA_CONFIG.version

    def to_dict(self) -> dict[str, Any]:
        return {
            "as_of": self.as_of,
            "opportunities": [o.to_dict() for o in self.opportunities],
            "selected": [o.to_dict() for o in self.selected],
            "correlation_blocks": list(self.correlation_blocks),
            "risk_allocations": dict(self.risk_allocations),
            "recovery": dict(self.recovery),
            "portfolio_risk_pct": self.portfolio_risk_pct,
            "config_version": self.config_version,
        }


def scan_universe(
    facts: list[SymbolMarketFacts],
    *,
    open_symbols: tuple[str, ...] | list[str] = (),
    daily_risk_used_pct: Decimal = Decimal("0"),
    account_exposure_pct: Decimal = Decimal("0"),
    drawdown_pct: Decimal = Decimal("0"),
    config: InstitutionalAlphaConfig | None = None,
) -> AlphaScanResult:
    """Score every symbol, rank, apply correlation + recovery filters."""
    cfg = config or DEFAULT_ALPHA_CONFIG
    scored: list[SymbolOpportunity] = []
    for f in facts:
        session = assess_session(f.session)
        spread_a = assess_spread(f.spread)
        # Soft-blend session / spread into provided confidence
        conf = max(0, min(100, f.ai_confidence - session.confidence_penalty - spread_a.confidence_penalty))
        opp = score_opportunity(
            symbol=f.symbol,
            ai_confidence=conf,
            trend_strength=f.trend_strength,
            momentum=f.momentum,
            liquidity=f.liquidity,
            volatility=f.volatility,
            spread_score=spread_a.score,
            expected_rr=f.expected_rr,
            session_score=session.stars * 20,
            direction=f.direction,
            reasons=f.reasons + (session.reason, spread_a.reason),
            config=cfg,
        )
        scored.append(opp)

    ranked = rank_opportunities(scored, config=cfg)
    min_score = min_score_with_recovery(config=cfg)
    correlation_blocks: list[dict[str, Any]] = []
    selected: list[SymbolOpportunity] = []
    risk_map: dict[str, dict[str, Any]] = {}

    for cand in ranked:
        if cand.opportunity_score < min_score or cand.direction not in {"BUY", "SELL"}:
            continue
        corr: CorrelationDecision = may_open_with_correlation(
            candidate_symbol=cand.symbol,
            open_symbols=list(open_symbols) + [s.symbol for s in selected],
            config=cfg,
        )
        if not corr.allow:
            correlation_blocks.append(
                {"symbol": cand.symbol, **corr.to_dict()}
            )
            continue
        alloc: RiskAllocation = allocate_risk_pct(
            cand.opportunity_score,
            daily_risk_used_pct=daily_risk_used_pct,
            account_exposure_pct=account_exposure_pct,
            drawdown_pct=drawdown_pct,
            config=cfg,
        )
        risk_map[cand.symbol] = alloc.to_dict()
        if alloc.risk_pct <= 0:
            continue
        selected.append(cand)
        if len(selected) >= max(1, cfg.execute_top_n):
            break

    # If nothing passed filters, still expose top_executable for observability
    if not selected:
        selected = top_executable(ranked, config=cfg)[:0]

    recovery = get_smart_recovery().snapshot()
    return AlphaScanResult(
        as_of=datetime.now(UTC).isoformat(),
        opportunities=ranked,
        selected=selected,
        correlation_blocks=correlation_blocks,
        risk_allocations=risk_map,
        recovery=dict(recovery),
        portfolio_risk_pct=float(account_exposure_pct),
        config_version=cfg.version,
    )
