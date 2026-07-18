"""Strategy Engine — deterministic plugins + risk gate (never order_send)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.interfaces.strategy_engine import (
    EngineSignalAction,
    OhlcBar,
    StrategyIntention,
    StrategyPort,
    StrategyRiskLimits,
    StrategyRiskPort,
    StrategyRiskVerdict,
    StrategySnapshot,
)
from app.strategies import default_strategy_plugins


@dataclass(frozen=True, slots=True)
class StrategyAllocation:
    strategy_key: str
    weight_pct: float
    symbols: tuple[str, ...]


@dataclass
class DefaultStrategyRisk:
    """Simple deterministic risk interface for the Strategy Engine."""

    def check(
        self,
        intention: StrategyIntention,
        *,
        open_trades: int,
        daily_pnl_pct: float,
        exposure_pct: float,
        limits: StrategyRiskLimits,
        correlation: float | None = None,
    ) -> StrategyRiskVerdict:
        reasons: list[str] = []
        allowed = True
        conf = intention.confidence
        if intention.action in {EngineSignalAction.BUY, EngineSignalAction.SELL}:
            if open_trades >= limits.max_trades:
                allowed = False
                reasons.append(
                    f"Max trades reached ({open_trades}>={limits.max_trades})"
                )
            if daily_pnl_pct <= -abs(limits.daily_loss_pct):
                allowed = False
                reasons.append(
                    "Daily loss limit hit "
                    f"({daily_pnl_pct}% <= -{limits.daily_loss_pct}%)"
                )
            if exposure_pct >= limits.max_exposure_pct:
                allowed = False
                reasons.append(
                    f"Exposure limit ({exposure_pct}% >= {limits.max_exposure_pct}%)"
                )
            if correlation is not None and abs(correlation) > limits.max_correlation:
                allowed = False
                reasons.append(
                    f"Correlation limit (|{correlation}| > {limits.max_correlation})"
                )
            if conf * 100 > limits.max_risk_pct * 50:
                # Soft reduce confidence rather than invent fills
                conf = min(conf, limits.max_risk_pct / 2)
                reasons.append("Confidence capped by max_risk_pct policy")
        if allowed and not reasons:
            reasons.append("Risk checks passed")
        return StrategyRiskVerdict(
            allowed=allowed,
            reasons=tuple(reasons),
            adjusted_confidence=round(conf, 3),
            limits=limits,
        )


@dataclass
class StrategyEngine:
    """Catalog + evaluate deterministic strategies with explainability."""

    plugins: dict[str, StrategyPort] = field(default_factory=dict)
    risk: StrategyRiskPort = field(default_factory=DefaultStrategyRisk)
    allocations: list[StrategyAllocation] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.plugins:
            self.plugins = {p.key: p for p in default_strategy_plugins()}

    def catalog(self) -> list[dict[str, Any]]:
        items = []
        for p in sorted(self.plugins.values(), key=lambda x: x.key):
            items.append(
                {
                    "key": p.key,
                    "name": p.name,
                    "category": p.category,
                    "description": p.description,
                    "default_params": dict(p.default_params),
                }
            )
        return items

    def validate_rules(
        self,
        strategy_key: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        plugin = self.plugins.get(strategy_key)
        if plugin is None:
            return {
                "valid": False,
                "errors": [f"Unknown strategy_key '{strategy_key}'"],
                "strategy_key": strategy_key,
            }
        ok, errors = plugin.validate_params(params or {})
        return {
            "valid": ok,
            "errors": list(errors),
            "strategy_key": strategy_key,
            "params": params or dict(plugin.default_params),
        }

    def run(
        self,
        *,
        strategy_key: str,
        symbol: str,
        timeframe: str,
        bars: list[OhlcBar],
        params: dict[str, Any] | None = None,
        session: str = "unknown",
        market_state: str = "unknown",
        open_trades: int = 0,
        daily_pnl_pct: float = 0.0,
        exposure_pct: float = 0.0,
        correlation: float | None = None,
        limits: StrategyRiskLimits | None = None,
        allocation_weight_pct: float | None = None,
    ) -> dict[str, Any]:
        plugin = self.plugins.get(strategy_key)
        if plugin is None:
            return {
                "ok": False,
                "error": f"Unknown strategy_key '{strategy_key}'",
                "signal": None,
            }
        merged = {**dict(plugin.default_params), **(params or {})}
        ok, errors = plugin.validate_params(merged)
        if not ok:
            return {
                "ok": False,
                "error": "; ".join(errors),
                "signal": None,
                "validation_errors": list(errors),
            }
        if len(bars) < 5:
            return {
                "ok": False,
                "error": "At least 5 OHLC bars required (no fabricated bars)",
                "signal": None,
            }

        snapshot = StrategySnapshot(
            symbol=symbol.strip().upper(),
            timeframe=timeframe,
            bars=tuple(bars),
            params=merged,
            session=session,
            market_state=market_state,
            as_of=bars[-1].time if bars and bars[-1].time else "",
        )
        intention = plugin.evaluate(snapshot)
        risk_limits = limits or StrategyRiskLimits()
        verdict = self.risk.check(
            intention,
            open_trades=open_trades,
            daily_pnl_pct=daily_pnl_pct,
            exposure_pct=exposure_pct,
            limits=risk_limits,
            correlation=correlation,
        )
        action = intention.action.value
        confidence = verdict.adjusted_confidence
        if not verdict.allowed and intention.action in {
            EngineSignalAction.BUY,
            EngineSignalAction.SELL,
            EngineSignalAction.EXIT,
        }:
            action = EngineSignalAction.HOLD.value
            confidence = 0.0

        weight = allocation_weight_pct
        if weight is None:
            for alloc in self.allocations:
                if alloc.strategy_key == strategy_key and (
                    not alloc.symbols or symbol.upper() in alloc.symbols
                ):
                    weight = alloc.weight_pct
                    break

        return {
            "ok": True,
            "strategy_key": strategy_key,
            "symbol": snapshot.symbol,
            "timeframe": timeframe,
            "signal": {
                "action": action,
                "confidence": confidence,
                "timestamp": intention.timestamp,
                "reasons": [e.reason for e in intention.explanations],
                "explanations": [
                    {
                        "reason": e.reason,
                        "indicator": e.indicator,
                        "threshold": e.threshold,
                        "market_context": e.market_context,
                        "value": e.value,
                    }
                    for e in intention.explanations
                ],
            },
            "risk": {
                "allowed": verdict.allowed,
                "reasons": list(verdict.reasons),
                "limits": {
                    "max_risk_pct": risk_limits.max_risk_pct,
                    "max_trades": risk_limits.max_trades,
                    "daily_loss_pct": risk_limits.daily_loss_pct,
                    "max_exposure_pct": risk_limits.max_exposure_pct,
                    "max_correlation": risk_limits.max_correlation,
                },
            },
            "allocation": {
                "strategy_key": strategy_key,
                "weight_pct": weight,
                "symbol": snapshot.symbol,
            },
            "execution_policy": {
                "live_requires": "EXECUTION_ENABLED=true",
                "default_path": "paper_trading",
                "autonomous_trading": False,
            },
            "params": merged,
            "bar_count": len(bars),
            "integrations": {
                "backtest": "POST /backtests/run (existing BacktestEngine)",
                "walkforward": "POST /walkforward/run (existing WalkForwardEngine)",
                "paper": "POST /paper/orders when EXECUTION_ENABLED=false",
                "live": "POST /execution/submit only if EXECUTION_ENABLED=true",
            },
        }

    def set_allocations(self, items: list[StrategyAllocation]) -> list[dict[str, Any]]:
        total = sum(a.weight_pct for a in items)
        if items and abs(total - 100.0) > 0.01 and total > 100.0:
            raise ValueError(f"Allocation weights exceed 100% (got {total})")
        self.allocations = list(items)
        return self.list_allocations()

    def list_allocations(self) -> list[dict[str, Any]]:
        return [
            {
                "strategy_key": a.strategy_key,
                "weight_pct": a.weight_pct,
                "symbols": list(a.symbols),
            }
            for a in self.allocations
        ]

    def portfolio_summary(self) -> dict[str, Any]:
        return {
            "allocations": self.list_allocations(),
            "strategies": [p.key for p in self.plugins.values()],
            "performance": {
                "note": (
                    "Use paper/performance and backtests endpoints; " "no invented PnL"
                ),
                "paper": "GET /paper/performance",
                "backtests": "GET /backtests",
            },
        }
