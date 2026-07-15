"""Quant Research Lab application service — analysis only, never order_send."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
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
from app.domain.decision_engine.paper_tracker import get_paper_tracker
from app.domain.entities.backtest import BacktestAssumptions
from app.domain.entities.walkforward import WalkForwardWindowConfig
from app.domain.market_context.engine import MarketContextEngine
from app.domain.market_data.timeframe import Timeframe
from app.domain.portfolio_intelligence.statistics import correlation_matrix
from app.domain.quant_ai.market_structure import analyze_symbol_structure
from app.domain.quant_studio.monte_carlo import run_monte_carlo
from app.domain.quant_studio.strategy_review import review_strategy
from app.domain.quant_studio.walkforward import summarize_walkforward_stability
from app.domain.research_lab import (
    build_research_report,
    classify_regime,
    compare_strategies,
    get_research_store,
    get_strategy,
    list_strategy_library,
    pick_dashboard_leaders,
    sandbox_parameters,
    strategy_regime_fit,
    to_backtest_assumptions,
)
from app.infrastructure.intelligence.runtime import TtlCache
from core.config.settings import get_settings

_DASH_CACHE = TtlCache(ttl_seconds=25.0, max_items=64)


def _security() -> dict[str, Any]:
    settings = get_settings()
    return {
        "advisory_only": True,
        "autonomous_trading": False,
        "never_submits_orders": True,
        "never_bypasses_execution_enabled": True,
        "never_modifies_broker_state": True,
        "never_changes_positions": True,
        "execution_enabled": bool(getattr(settings, "execution_enabled", False)),
        "promises_profit": False,
        "decision_engine_gatekeeper": True,
    }


def _dec(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True, slots=True)
class ResearchLabService:
    status: GetMT5StatusUseCase
    market_data: MT5MarketDataService
    portfolio_sync: PortfolioSyncService
    market_context: MarketContextEngine

    async def dashboard(
        self, *, user_id: UUID, symbol: str = "EURUSD"
    ) -> dict[str, Any]:
        code = symbol.strip().upper() or "EURUSD"
        cache_key = f"rl:dash:{user_id}:{code}"
        cached = _DASH_CACHE.get(cache_key)
        if cached is not None:
            return dict(cached)

        st = await self.status.execute(user_id=user_id)
        store = get_research_store()
        library = list_strategy_library()
        runs = store.list_runs(user_id, limit=40)
        comparison = compare_strategies(runs)
        leaders = pick_dashboard_leaders(comparison)
        regime = await self._regime(
            user_id=user_id, symbol=code, connected=st.connected
        )
        fits = [
            strategy_regime_fit(s, regime)
            for s in library
            if regime.get("status") == "available"
        ]
        paper = self.paper_performance(user_id=user_id)
        eligibility = store.list_eligibility(user_id)

        payload = {
            "status": "available" if st.connected else "degraded",
            "module": "research_lab",
            "version": "5.0",
            "symbol": code,
            "broker": {
                "connected": st.connected,
                "status": st.status,
                "latency_ms": st.latency_ms,
            },
            "library_count": len(library),
            "library_preview": library[:6],
            "research_dashboard": leaders,
            "regime": regime,
            "regime_fits": fits[:12],
            "comparison_preview": comparison,
            "paper": paper,
            "promotion_pipeline": {
                "criteria": store.get_criteria(),
                "eligibility": eligibility,
                "note": (
                    "Eligible strategies may be evaluated by Decision Engine "
                    "— DE remains gatekeeper"
                ),
            },
            "modules": [
                "strategy_library",
                "strategy_comparison",
                "validation_center",
                "research_dashboard",
                "market_regime_detection",
                "parameter_laboratory",
                "paper_performance",
                "ai_research_review",
                "research_reports",
                "promotion_pipeline",
            ],
            "data_policy": {
                "mock": False,
                "sources": [
                    "mt5_candles",
                    "backtest_engine",
                    "walkforward_engine",
                    "monte_carlo",
                    "paper_tracker",
                    "portfolio",
                ],
            },
            **_security(),
        }
        _DASH_CACHE.set(cache_key, payload)
        return payload

    def strategy_library(self) -> dict[str, Any]:
        items = list_strategy_library()
        return {
            "status": "available",
            "items": items,
            "count": len(items),
            **_security(),
        }

    async def validate_strategy(
        self,
        *,
        user_id: UUID,
        strategy_key: str,
        symbol: str = "EURUSD",
        timeframe: str = "H1",
        count: int = 300,
        initial_balance: str = "10000",
        parameter_overrides: dict[str, Any] | None = None,
        run_walkforward: bool = True,
        run_monte_carlo_flag: bool = True,
        save_run: bool = True,
    ) -> dict[str, Any]:
        """Side-by-side Validation Center: backtest / WF / MC / paper."""
        strategy = get_strategy(strategy_key)
        if strategy is None:
            return {
                "status": "unavailable",
                "reason": f"Unknown strategy '{strategy_key}'",
                **_security(),
            }
        if not strategy.get("engine_plugin"):
            return {
                "status": "unavailable",
                "reason": (
                    f"{strategy.get('name')} is a research archetype — "
                    "no executable OHLC plugin yet. Compare via catalog + "
                    "regime fit only."
                ),
                "strategy": strategy,
                **_security(),
            }

        st = await self.status.execute(user_id=user_id)
        if not st.connected:
            return {
                "status": "unavailable",
                "reason": "MT5 session not connected — cannot load historical OHLC",
                "strategy": strategy,
                **_security(),
            }

        sandbox = sandbox_parameters(parameter_overrides)
        get_research_store().save_sandbox(user_id, sandbox)
        assumptions = to_backtest_assumptions(sandbox)
        code = symbol.strip().upper()

        bars = self._load_bars(code, timeframe, count)
        if len(bars) < 30:
            return {
                "status": "unavailable",
                "reason": "Insufficient live MT5 candles for validation",
                "bar_count": len(bars),
                "strategy": strategy,
                **_security(),
            }

        bt_assumptions = BacktestAssumptions(
            spread=Decimal("0.00010"),
            slippage=Decimal("0.00005"),
            fee_per_lot=Decimal("7"),
            lot_size=Decimal(str(assumptions.get("lot_size", "0.10"))),
            stop_loss_distance=Decimal(str(assumptions["stop_loss_distance"])),
            take_profit_distance=Decimal(str(assumptions["take_profit_distance"])),
        )

        engine = BacktestEngine()
        result = engine.run(
            BacktestRunInput(
                user_id=user_id,
                request_id=f"rl-bt-{uuid4().hex[:12]}",
                symbol=code,
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
                "pnl": float(t.pnl),
                "closed_at": t.closed_at.isoformat() if t.closed_at else None,
            }
            for t in result.trades
        ]
        pnls: list[float] = []
        for t in trades:
            if t.get("closed_at") is None:
                continue
            pnl = _dec(t.get("pnl"))
            if pnl is not None:
                pnls.append(pnl)
        mc = (
            run_monte_carlo(pnls, initial_equity=float(initial_balance))
            if run_monte_carlo_flag
            else {"status": "skipped"}
        )

        walkforward: dict[str, Any] = {"status": "skipped"}
        stability: dict[str, Any] = {}
        if run_walkforward and len(bars) >= 160:
            wf_engine = WalkForwardEngine(backtest_engine=BacktestEngine())
            wf_result = wf_engine.run(
                WalkForwardRunInput(
                    user_id=user_id,
                    request_id=f"rl-wf-{uuid4().hex[:12]}",
                    symbol=code,
                    timeframe=timeframe,
                    bars=tuple(bars),
                    window_config=WalkForwardWindowConfig(
                        in_sample_bars=120,
                        out_of_sample_bars=40,
                        step_bars=40,
                        anchored=False,
                    ),
                    optimize_params=True,
                    auto_analysis=True,
                )
            )
            folds = self._serialize_folds(wf_result)
            stability = summarize_walkforward_stability(folds)
            walkforward = {
                "status": "available",
                "run_id": str(wf_result.run.id),
                "folds": folds,
                "stability": stability,
                "aggregated": {
                    "is": dict(wf_result.run.aggregated_is or {}),
                    "oos": dict(wf_result.run.aggregated_oos or {}),
                },
                "data_source": "mt5_candles|walkforward_engine",
            }

        regime = await self._regime(user_id=user_id, symbol=code, connected=True)
        fit = strategy_regime_fit(strategy, regime)
        review = review_strategy(
            metrics=metrics,
            assumptions=assumptions,
            fold_stability=stability or None,
        )
        paper = self.paper_performance(user_id=user_id)

        validation = {
            "backtest": {
                "status": "available" if run.status.value != "failed" else "failed",
                "run_id": str(run.id),
                "metrics": metrics,
                "equity_curve": equity,
                "trade_count": len(trades),
                "error_message": run.error_message or "",
                "data_source": "mt5_candles|backtest_engine",
            },
            "walkforward": walkforward,
            "monte_carlo": mc,
            "paper": paper,
        }

        store = get_research_store()
        promotion = store.evaluate_promotion(
            {
                "metrics": metrics,
                "stability": stability,
            }
        )
        exposure = self._exposure_note(user_id)
        correlation = await self._correlation_for_symbol(code)

        saved = None
        if save_run:
            saved = store.save_run(
                user_id=user_id,
                run={
                    "strategy_key": strategy_key,
                    "name": strategy.get("name"),
                    "symbol": code,
                    "timeframe": timeframe,
                    "metrics": metrics,
                    "stability": stability,
                    "regime_fit": fit,
                    "exposure": exposure,
                    "correlation": correlation,
                    "sandbox": {
                        "overrides_applied": sandbox.get("overrides_applied"),
                        "production_defaults_unchanged": True,
                    },
                    "promotion": promotion,
                    "ai_review": review,
                },
            )

        report = build_research_report(
            strategy=strategy,
            metrics=metrics,
            regime=regime,
            review=review,
            validation={
                "backtest_status": validation["backtest"]["status"],
                "walkforward_status": walkforward.get("status"),
                "monte_carlo_status": mc.get("status"),
                "equity_curve": equity[:40],
            },
            promotion=promotion,
        )

        return {
            "status": "available",
            "strategy": strategy,
            "symbol": code,
            "timeframe": timeframe,
            "bar_count": len(bars),
            "parameter_sandbox": sandbox,
            "validation": validation,
            "regime": regime,
            "regime_fit": fit,
            "ai_research_review": review,
            "promotion": promotion,
            "report": report,
            "saved_run": saved,
            **_security(),
        }

    def compare(self, *, user_id: UUID) -> dict[str, Any]:
        runs = get_research_store().list_runs(user_id, limit=80)
        comparison = compare_strategies(runs)
        leaders = pick_dashboard_leaders(comparison)
        return {
            **comparison,
            "research_dashboard": leaders,
            **_security(),
        }

    def parameter_lab(
        self, *, user_id: UUID, overrides: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        sandbox = sandbox_parameters(overrides)
        get_research_store().save_sandbox(user_id, sandbox)
        return {**sandbox, **_security()}

    def get_parameters(self, *, user_id: UUID) -> dict[str, Any]:
        store = get_research_store()
        existing = store.get_sandbox(user_id)
        if existing:
            return {**existing, **_security()}
        return {**sandbox_parameters(None), **_security()}

    def paper_performance(self, *, user_id: UUID) -> dict[str, Any]:
        """Daily / weekly / monthly / annual from Decision Engine paper tracker only."""
        tracker = get_paper_tracker()
        base = tracker.reports(user_id)
        rows = tracker.list_for_user(user_id, limit=5000)
        now = datetime.now(UTC)
        cut = now - timedelta(days=365)

        annual_rows: list[dict[str, Any]] = []
        for r in rows:
            try:
                ts = datetime.fromisoformat(str(r["created_at"]).replace("Z", "+00:00"))
            except ValueError:
                continue
            if ts >= cut:
                annual_rows.append(r)

        ideas = [r for r in annual_rows if r.get("decision") == "TRADE_IDEA"]
        waits = [r for r in annual_rows if r.get("decision") == "WAIT"]
        pnls = [
            float(r["simulated_pnl"])
            for r in ideas
            if r.get("simulated_pnl") is not None
        ]
        annual = {
            "period": "annual",
            "signals": len(annual_rows),
            "trade_ideas": len(ideas),
            "waits": len(waits),
            "wait_ratio": (
                round(len(waits) / len(annual_rows), 4) if annual_rows else None
            ),
            "realized_sim_pnl": round(sum(pnls), 4) if pnls else 0.0,
        }
        return {
            "status": base.get("status", "available"),
            "daily": base.get("daily"),
            "weekly": base.get("weekly"),
            "monthly": base.get("monthly"),
            "annual": annual,
            "aggregate": tracker.performance(user_id),
            "data_source": "decision_engine_paper_tracker",
            "note": "Paper results only — no fabricated fills",
            **_security(),
        }

    def promotion_criteria(
        self, *, updates: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        store = get_research_store()
        criteria = store.set_criteria(updates) if updates else store.get_criteria()
        return {
            "status": "available",
            "criteria": criteria,
            "note": (
                "Criteria gate Research Lab eligibility only — "
                "Decision Engine unchanged"
            ),
            **_security(),
        }

    def promote(
        self,
        *,
        user_id: UUID,
        strategy_key: str,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        store = get_research_store()
        strategy = get_strategy(strategy_key)
        if strategy is None:
            return {
                "status": "unavailable",
                "reason": "Unknown strategy",
                **_security(),
            }

        runs = store.list_runs(user_id, limit=200)
        target = None
        if run_id:
            target = next((r for r in runs if r.get("run_id") == run_id), None)
        else:
            candidates = [r for r in runs if r.get("strategy_key") == strategy_key]
            target = candidates[0] if candidates else None

        if target is None:
            return {
                "status": "unavailable",
                "reason": "No research run to evaluate for promotion",
                "strategy": strategy,
                **_security(),
            }

        evaluation = store.evaluate_promotion(target)
        row = store.set_eligibility(
            user_id=user_id,
            strategy_key=strategy_key,
            eligible=bool(evaluation["eligible_for_decision_engine"]),
            evidence={
                "run_id": target.get("run_id"),
                "metrics": target.get("metrics"),
                "stability": target.get("stability"),
                "evaluation": evaluation,
            },
        )
        return {
            "status": "available",
            "strategy": strategy,
            "evaluation": evaluation,
            "eligibility": row,
            "decision_engine_untouched": True,
            "forwarded_to_decision_engine": False,
            **_security(),
        }

    def report(
        self, *, user_id: UUID, strategy_key: str | None = None
    ) -> dict[str, Any]:
        store = get_research_store()
        runs = store.list_runs(user_id, limit=50)
        if strategy_key:
            runs = [r for r in runs if r.get("strategy_key") == strategy_key]
        if not runs:
            return {
                "status": "unavailable",
                "reason": "No research runs available for report",
                **_security(),
            }
        latest = runs[0]
        strategy = get_strategy(str(latest.get("strategy_key") or "")) or {
            "key": latest.get("strategy_key"),
            "name": latest.get("name"),
        }
        report = build_research_report(
            strategy=strategy,
            metrics=dict(latest.get("metrics") or {}),
            regime=None,
            review=dict(latest.get("ai_review") or {}),
            validation={"saved_run_id": latest.get("run_id")},
            promotion=dict(latest.get("promotion") or {}),
        )
        return {**report, **_security()}

    async def regime_snapshot(
        self, *, user_id: UUID, symbol: str = "EURUSD"
    ) -> dict[str, Any]:
        st = await self.status.execute(user_id=user_id)
        regime = await self._regime(
            user_id=user_id, symbol=symbol.strip().upper(), connected=st.connected
        )
        fits = [
            strategy_regime_fit(s, regime)
            for s in list_strategy_library()
            if regime.get("status") == "available"
        ]
        return {
            "status": regime.get("status"),
            "regime": regime,
            "fits": fits,
            **_security(),
        }

    # --- helpers ---------------------------------------------------------

    async def _regime(
        self, *, user_id: UUID, symbol: str, connected: bool
    ) -> dict[str, Any]:
        _ = user_id
        if not connected:
            return {
                "status": "unavailable",
                "reason": "MT5 not connected",
                "regimes": [],
            }
        try:
            ctx = self.market_context.build("FX", symbol_code=symbol)
            session = ctx.session.value
        except Exception:
            session = None
            ctx = None

        candles = self._load_candle_dicts(symbol, "H1", 220)
        if len(candles) < 30:
            return {
                "status": "unavailable",
                "reason": "Insufficient OHLC for regime classification",
                "regimes": [],
            }
        bid = ask = None
        try:
            tick = self.market_data.latest_tick(symbol)
            bid, ask = float(tick.bid), float(tick.ask)
        except Exception:
            bid = None
            ask = None
        structure = analyze_symbol_structure(
            symbol=symbol,
            candles=candles,
            bid=bid,
            ask=ask,
            session=session,
        )
        news_risk = None
        market_ctx = {"session": session}
        if ctx is not None:
            market_ctx["liquidity"] = str(ctx.liquidity_level.value)
        return classify_regime(
            structure=structure,
            market_context=market_ctx,
            news_risk=news_risk,
        )

    def _exposure_note(self, user_id: UUID) -> dict[str, Any]:
        _ = user_id
        try:
            positions = self.portfolio_sync.list_positions()
            return {
                "status": "available",
                "open_positions": len(positions),
                "note": "Live portfolio exposure snapshot — not strategy-simulated",
            }
        except Exception as exc:
            return {"status": "unavailable", "reason": str(exc)}

    async def _correlation_for_symbol(self, symbol: str) -> dict[str, Any]:
        peers = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]
        if symbol not in peers:
            peers = [symbol, *peers][:4]
        close_map: dict[str, list[float]] = {}
        for sym in peers:
            candles = self._load_candle_dicts(sym, "H1", 60)
            if len(candles) >= 10:
                close_map[sym] = [float(c["close"]) for c in candles]
        if len(close_map) < 2:
            return {
                "status": "unavailable",
                "reason": "Need ≥2 symbols with OHLC for correlation",
            }
        labels, matrix, _notes = correlation_matrix(close_map)
        return {"status": "available", "labels": labels, "matrix": matrix}

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
        return folds
