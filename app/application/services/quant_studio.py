"""Quant Studio application service — research workspace, never order_send."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

from app.application.services.backtest_engine import (
    BacktestBarInput,
    BacktestEngine,
    BacktestRunInput,
)
from app.application.services.mt5_market_data import MT5MarketDataService
from app.application.services.portfolio_sync import PortfolioSyncService
from app.application.services.walkforward_engine import (
    WalkForwardEngine,
    WalkForwardRunInput,
)
from app.application.use_cases.mt5 import GetMT5StatusUseCase
from app.domain.entities.backtest import BacktestAssumptions
from app.domain.entities.walkforward import WalkForwardWindowConfig
from app.domain.market_data.timeframe import Timeframe
from app.domain.portfolio_intelligence.statistics import correlation_matrix
from app.domain.portfolio_intelligence.taxonomy import (
    classify_currency,
    classify_sector,
)
from app.domain.quant_studio.analytics import build_professional_analytics
from app.domain.quant_studio.marketplace import get_marketplace_store
from app.domain.quant_studio.monte_carlo import run_monte_carlo
from app.domain.quant_studio.optimizer import suggest_optimizations
from app.domain.quant_studio.strategy_review import review_strategy
from app.domain.quant_studio.visual_builder import BLOCK_CATALOG, compile_strategy_graph
from app.domain.quant_studio.walkforward import summarize_walkforward_stability
from app.infrastructure.intelligence.runtime import TtlCache
from core.config.settings import get_settings

_WORKSPACE_CACHE = TtlCache(ttl_seconds=20.0, max_items=64)


def _security_flags() -> dict[str, Any]:
    settings = get_settings()
    return {
        "advisory_only": True,
        "autonomous_trading": False,
        "never_submits_orders": True,
        "never_bypasses_execution_enabled": True,
        "never_modifies_broker_state": True,
        "execution_enabled": bool(getattr(settings, "execution_enabled", False)),
    }


def _dec(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True, slots=True)
class QuantStudioService:
    status: GetMT5StatusUseCase
    market_data: MT5MarketDataService
    portfolio_sync: PortfolioSyncService

    async def workspace(self, *, user_id: UUID) -> dict[str, Any]:
        cache_key = f"qs:ws:{user_id}"
        cached = _WORKSPACE_CACHE.get(cache_key)
        if cached is not None:
            return cast("dict[str, Any]", cached)

        st = await self.status.execute(user_id=user_id)
        market = get_marketplace_store()
        strategies = market.list_for_user(user_id)
        payload = {
            "status": "available" if st.connected else "degraded",
            "module": "quant_studio",
            "version": "3.0",
            **_security_flags(),
            "broker": {
                "connected": st.connected,
                "status": st.status,
                "latency_ms": st.latency_ms,
            },
            "modules": [
                "visual_strategy_builder",
                "backtest_studio",
                "walk_forward",
                "monte_carlo",
                "ai_strategy_review",
                "ai_optimizer",
                "strategy_marketplace",
                "professional_analytics",
                "portfolio_lab",
                "live_strategy_monitor",
            ],
            "block_catalog": BLOCK_CATALOG,
            "marketplace_count": len(strategies),
            "marketplace_preview": strategies[:8],
            "data_policy": {
                "mock": False,
                "sources": [
                    "mt5_candles",
                    "backtest_engine",
                    "walkforward_engine",
                    "portfolio",
                ],
            },
        }
        _WORKSPACE_CACHE.set(cache_key, payload)
        return payload

    def compile_graph(self, graph: dict[str, Any]) -> dict[str, Any]:
        return {**compile_strategy_graph(graph), **_security_flags()}

    async def run_backtest_studio(
        self,
        *,
        user_id: UUID,
        symbol: str,
        timeframe: str = "H1",
        count: int = 300,
        initial_balance: str = "10000",
        assumptions: dict[str, Any] | None = None,
        graph: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        st = await self.status.execute(user_id=user_id)
        if not st.connected:
            return {
                "status": "unavailable",
                "reason": "MT5 session not connected — cannot load live OHLC",
                **_security_flags(),
            }

        compiled = (
            compile_strategy_graph(graph)
            if graph
            else {"status": "skipped", "assumptions": {}}
        )
        merged = dict(compiled.get("assumptions") or {})
        if assumptions:
            merged.update({k: str(v) for k, v in assumptions.items()})

        bars = self._load_bars(symbol, timeframe, count)
        if len(bars) < 30:
            return {
                "status": "unavailable",
                "reason": "Insufficient live MT5 candles for backtest",
                "bar_count": len(bars),
                **_security_flags(),
            }

        bt_assumptions = BacktestAssumptions(
            spread=Decimal(str(merged.get("spread", "0.00010"))),
            slippage=Decimal(str(merged.get("slippage", "0.00005"))),
            fee_per_lot=Decimal(str(merged.get("fee_per_lot", "7"))),
            lot_size=Decimal(str(merged.get("lot_size", "0.10"))),
            stop_loss_distance=Decimal(str(merged.get("stop_loss_distance", "0.0020"))),
            take_profit_distance=Decimal(
                str(merged.get("take_profit_distance", "0.0040"))
            ),
        )

        engine = BacktestEngine()
        result = engine.run(
            BacktestRunInput(
                user_id=user_id,
                request_id=f"qs-bt-{uuid4().hex[:12]}",
                symbol=symbol.strip().upper(),
                timeframe=timeframe,
                initial_balance=Decimal(initial_balance),
                bars=tuple(bars),
                assumptions=bt_assumptions,
                auto_analysis=True,
            )
        )
        run = result.run
        metrics = dict(run.metrics or {})

        equity = [
            {
                "timestamp": p.timestamp.isoformat() if p.timestamp else None,
                "equity": float(p.equity),
                "drawdown_pct": float(p.drawdown_pct),
            }
            for p in result.equity_curve
        ]
        trades = [
            {
                "id": str(t.id),
                "symbol": t.symbol,
                "side": t.side.value if hasattr(t.side, "value") else str(t.side),
                "pnl": float(t.pnl),
                "entry_price": float(t.entry_price),
                "exit_price": float(t.exit_price) if t.exit_price is not None else None,
                "stop_loss": float(t.stop_loss) if t.stop_loss is not None else None,
                "take_profit": (
                    float(t.take_profit) if t.take_profit is not None else None
                ),
                "opened_at": t.opened_at.isoformat() if t.opened_at else None,
                "closed_at": t.closed_at.isoformat() if t.closed_at else None,
                "exit_reason": (
                    t.exit_reason.value
                    if t.exit_reason is not None and hasattr(t.exit_reason, "value")
                    else (str(t.exit_reason) if t.exit_reason else None)
                ),
            }
            for t in result.trades
        ]
        analytics = build_professional_analytics(equity_curve=equity, trades=trades)
        pnls = [
            pnl
            for t in trades
            if t.get("closed_at") and (pnl := _dec(t["pnl"])) is not None
        ]
        mc = run_monte_carlo(pnls, initial_equity=float(initial_balance))
        review = review_strategy(
            metrics=metrics, assumptions=merged, graph_summary=compiled
        )
        optimize = suggest_optimizations(
            metrics=metrics,
            assumptions=merged,
            symbol=symbol,
            timeframe=timeframe,
        )

        return {
            "status": "available" if run.status.value != "failed" else "failed",
            "run_id": str(run.id),
            "symbol": run.symbol,
            "timeframe": run.timeframe,
            "bar_count": len(bars),
            "metrics": metrics,
            "equity_curve": equity,
            "trades": trades,
            "analytics": analytics,
            "monte_carlo": mc,
            "ai_review": review,
            "ai_optimizer": optimize,
            "compiled_graph": compiled,
            "assumptions": merged,
            "error_message": run.error_message or "",
            "data_source": "mt5_candles|backtest_engine",
            **_security_flags(),
        }

    async def run_walkforward_studio(
        self,
        *,
        user_id: UUID,
        symbol: str,
        timeframe: str = "H1",
        count: int = 400,
        in_sample_bars: int = 120,
        out_of_sample_bars: int = 40,
        step_bars: int = 40,
    ) -> dict[str, Any]:
        st = await self.status.execute(user_id=user_id)
        if not st.connected:
            return {
                "status": "unavailable",
                "reason": "MT5 session not connected",
                **_security_flags(),
            }
        bars = self._load_bars(symbol, timeframe, count)
        if len(bars) < in_sample_bars + out_of_sample_bars:
            return {
                "status": "unavailable",
                "reason": "Insufficient live candles for walk-forward windows",
                "bar_count": len(bars),
                **_security_flags(),
            }

        engine = WalkForwardEngine(backtest_engine=BacktestEngine())
        result = engine.run(
            WalkForwardRunInput(
                user_id=user_id,
                request_id=f"qs-wf-{uuid4().hex[:12]}",
                symbol=symbol.strip().upper(),
                timeframe=timeframe,
                bars=tuple(bars),
                window_config=WalkForwardWindowConfig(
                    in_sample_bars=in_sample_bars,
                    out_of_sample_bars=out_of_sample_bars,
                    step_bars=step_bars,
                    anchored=False,
                ),
                optimize_params=True,
                auto_analysis=True,
            )
        )
        run = result.run
        folds_out = self._serialize_folds(result)
        stability = summarize_walkforward_stability(folds_out)

        promo = run.promotion.value if run.promotion is not None else None
        return {
            "status": "available",
            "run_id": str(run.id),
            "symbol": run.symbol,
            "timeframe": run.timeframe,
            "bar_count": len(bars),
            "folds": folds_out,
            "stability": stability,
            "promotion": promo,
            "aggregated": {
                "is": dict(run.aggregated_is or {}),
                "oos": dict(run.aggregated_oos or {}),
            },
            "robustness": dict(run.robustness or {}),
            "data_source": "mt5_candles|walkforward_engine",
            **_security_flags(),
        }

    async def portfolio_lab(self, *, user_id: UUID) -> dict[str, Any]:
        st = await self.status.execute(user_id=user_id)
        if not st.connected:
            return {
                "status": "unavailable",
                "reason": "MT5 session not connected",
                **_security_flags(),
            }
        try:
            snap = self.portfolio_sync.account_snapshot()
            positions = self.portfolio_sync.list_positions()
        except Exception as exc:
            return {
                "status": "unavailable",
                "reason": str(exc),
                **_security_flags(),
            }

        sectors: dict[str, float] = {}
        currencies: dict[str, float] = {}
        exposures: list[dict[str, Any]] = []
        symbols: list[str] = []
        for p in positions:
            vol = _dec(p.volume) or 0.0
            sym = p.symbol
            symbols.append(sym)
            sector = classify_sector(sym)
            ccy = classify_currency(sym)
            sectors[sector] = sectors.get(sector, 0.0) + abs(vol)
            currencies[ccy] = currencies.get(ccy, 0.0) + abs(vol)
            exposures.append(
                {
                    "symbol": sym,
                    "volume": vol,
                    "profit": _dec(getattr(p, "profit", 0)),
                    "sector": sector,
                    "currency": ccy,
                }
            )

        # Correlation from live closes when possible
        close_map: dict[str, list[float]] = {}
        for sym in sorted(set(symbols))[:8]:
            candles = self._load_candle_dicts(sym, "H1", 60)
            if len(candles) >= 10:
                close_map[sym] = [float(c["close"]) for c in candles]
        corr: dict[str, Any]
        if len(close_map) >= 2:
            labels, matrix, _notes = correlation_matrix(close_map)
            corr = {"status": "available", "labels": labels, "matrix": matrix}
        else:
            corr = {
                "status": "unavailable",
                "reason": "Need ≥2 open symbols with OHLC for correlation",
            }

        equity = _dec(snap.equity) or 0.0
        balance = _dec(snap.balance) or 0.0
        return {
            "status": "available",
            "account": {
                "equity": equity,
                "balance": balance,
                "margin": _dec(snap.margin),
                "free_margin": _dec(snap.free_margin),
                "leverage": snap.leverage,
            },
            "exposure": exposures,
            "sector_allocation": [
                {"sector": k, "weight": v} for k, v in sorted(sectors.items())
            ],
            "currency_allocation": [
                {"currency": k, "weight": v} for k, v in sorted(currencies.items())
            ],
            "correlation": corr,
            "volatility": {
                "note": "Per-symbol ATR not aggregated here — use Backtest Studio risk",
            },
            "risk": {
                "open_positions": len(positions),
                "floating_pnl": sum(_dec(e.get("profit")) or 0 for e in exposures),
            },
            "data_source": "mt5_positions|mt5_candles",
            **_security_flags(),
        }

    async def live_monitor(self, *, user_id: UUID) -> dict[str, Any]:
        st = await self.status.execute(user_id=user_id)
        positions: list[dict[str, Any]] = []
        if st.connected:
            try:
                for p in self.portfolio_sync.list_positions():
                    positions.append(
                        {
                            "ticket": p.ticket,
                            "symbol": p.symbol,
                            "volume": _dec(p.volume),
                            "profit": _dec(getattr(p, "profit", 0)),
                            "side": getattr(p, "side", None)
                            or str(getattr(p, "type", "")),
                        }
                    )
            except Exception:
                positions = []

        alerts: list[str] = []
        if not st.connected:
            alerts.append("Broker disconnected — live monitor degraded")
        loss_pos = [p for p in positions if (p.get("profit") or 0) < 0]
        if len(loss_pos) >= 3:
            alerts.append(f"{len(loss_pos)} positions currently underwater")
        floating = sum(p.get("profit") or 0 for p in positions)

        return {
            "status": "available" if st.connected else "degraded",
            "broker": {"connected": st.connected, "latency_ms": st.latency_ms},
            "performance": {
                "open_positions": len(positions),
                "floating_pnl": floating,
            },
            "signals": {
                "note": (
                    "Signal feed from locked Strategy Engine not duplicated — "
                    "open positions summarized only"
                ),
                "count": 0,
            },
            "execution_quality": {
                "latency_ms": st.latency_ms,
                "note": "Use Execution Intelligence for full attempt analytics",
            },
            "risk": {
                "open_risk_positions": len(positions),
                "underwater": len(loss_pos),
            },
            "alerts": alerts,
            "positions": positions,
            "data_source": "mt5_positions|mt5_status",
            **_security_flags(),
        }

    # --- marketplace -----------------------------------------------------

    def marketplace_list(self, user_id: UUID) -> dict[str, Any]:
        items = get_marketplace_store().list_for_user(user_id)
        return {"status": "available", "items": items, **_security_flags()}

    def marketplace_save(
        self,
        *,
        user_id: UUID,
        name: str,
        graph: dict[str, Any],
        assumptions: dict[str, Any] | None = None,
        notes: str = "",
        strategy_id: str | None = None,
    ) -> dict[str, Any]:
        return {
            **get_marketplace_store().save(
                user_id=user_id,
                name=name,
                graph=graph,
                assumptions=assumptions,
                notes=notes,
                strategy_id=strategy_id,
            ),
            **_security_flags(),
        }

    def marketplace_action(
        self,
        *,
        user_id: UUID,
        action: str,
        strategy_id: str,
        other_id: str | None = None,
        favorited: bool = True,
        published: bool = True,
    ) -> dict[str, Any]:
        store = get_marketplace_store()
        if action == "clone":
            return {
                **store.clone(user_id=user_id, strategy_id=strategy_id),
                **_security_flags(),
            }
        if action == "publish":
            return {
                **store.publish(
                    user_id=user_id, strategy_id=strategy_id, published=published
                ),
                **_security_flags(),
            }
        if action == "favorite":
            return {
                **store.favorite(
                    user_id=user_id, strategy_id=strategy_id, favorited=favorited
                ),
                **_security_flags(),
            }
        if action == "compare" and other_id:
            return {**store.compare(strategy_id, other_id), **_security_flags()}
        if action == "get":
            item = store.get(strategy_id)
            if not item:
                return {
                    "status": "unavailable",
                    "reason": "Not found",
                    **_security_flags(),
                }
            return {"status": "available", "strategy": item, **_security_flags()}
        return {
            "status": "unavailable",
            "reason": f"Unknown action {action}",
            **_security_flags(),
        }

    # --- helpers ---------------------------------------------------------

    def _load_bars(
        self, symbol: str, timeframe: str, count: int
    ) -> list[BacktestBarInput]:
        candles = self._load_candle_dicts(symbol, timeframe, count)
        out: list[BacktestBarInput] = []
        for c in candles:
            out.append(
                BacktestBarInput(
                    open_time=str(c["open_time"]),
                    open=str(c["open"]),
                    high=str(c["high"]),
                    low=str(c["low"]),
                    close=str(c["close"]),
                    volume=str(c.get("volume") or "0"),
                    close_time=c.get("close_time"),
                )
            )
        return out

    def _load_candle_dicts(
        self, symbol: str, timeframe: str, count: int
    ) -> list[dict[str, Any]]:
        try:
            tf = Timeframe.parse(timeframe)
        except Exception:
            tf = Timeframe.H1
        try:
            rates = self.market_data.historical_candles(
                symbol.strip().upper(), tf, count=count, start_pos=0
            )
        except Exception:
            return []
        rows: list[dict[str, Any]] = []
        for r in rates:
            ot = r.open_time.isoformat() if r.open_time else None
            rows.append(
                {
                    "open_time": ot,
                    "close_time": ot,
                    "open": str(r.open),
                    "high": str(r.high),
                    "low": str(r.low),
                    "close": str(r.close),
                    "volume": str(r.tick_volume),
                }
            )
        rows.sort(key=lambda x: str(x.get("open_time") or ""))
        return rows

    def _serialize_folds(self, result: Any) -> list[dict[str, Any]]:
        folds: list[dict[str, Any]] = []
        for idx, fr in enumerate(getattr(result, "folds", ()) or ()):
            is_m = getattr(fr, "is_metrics", None)
            oos_m = getattr(fr, "oos_metrics", None)
            is_pf = (
                float(is_m.profit_factor)
                if is_m and is_m.profit_factor is not None
                else None
            )
            oos_pf = (
                float(oos_m.profit_factor)
                if oos_m and oos_m.profit_factor is not None
                else None
            )
            folds.append(
                {
                    "index": idx,
                    "is_profit_factor": is_pf,
                    "oos_profit_factor": oos_pf,
                    "selected_params": dict(getattr(fr, "selected_params", {}) or {}),
                }
            )
        # Fallback: folds already serialized on run
        if not folds:
            for idx, fr in enumerate(getattr(result.run, "folds", None) or []):
                if isinstance(fr, dict):
                    is_m = fr.get("is_metrics") or {}
                    oos_m = fr.get("oos_metrics") or {}
                    folds.append(
                        {
                            "index": idx,
                            "is_profit_factor": _dec(
                                is_m.get("profit_factor")
                                if isinstance(is_m, dict)
                                else None
                            ),
                            "oos_profit_factor": _dec(
                                oos_m.get("profit_factor")
                                if isinstance(oos_m, dict)
                                else None
                            ),
                        }
                    )
        return folds
