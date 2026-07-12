"""Walk-Forward Validation Engine — IS backtest + OOS validation only.

Never enables EXECUTION_ENABLED. Never calls order_send(). Never live trades.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from app.application.services.backtest_engine import (
    BacktestBarInput,
    BacktestEngine,
    BacktestResult,
    BacktestRunInput,
)
from app.application.services.rolling_windows import RollingWindowScheduler
from app.application.services.strategy_runtime import StrategyRuntimeService
from app.application.services.walkforward_robustness import RobustnessEngine
from app.domain.entities.backtest import BacktestAssumptions
from app.domain.entities.strategy_runtime import StrategyRuntimeConfig
from app.domain.entities.walkforward import (
    FoldMetrics,
    FoldResult,
    WalkForwardPromotionRules,
    WalkForwardRun,
    WalkForwardWindow,
    WalkForwardWindowConfig,
)
from app.domain.enums.walkforward import PromotionDecision
from app.domain.events.base import DomainEvent
from app.domain.events.walkforward import (
    WalkForwardFinished,
    WalkForwardFoldCompleted,
    WalkForwardStarted,
)

# Deterministic candidate parameter sets for IS "optimization" (not AI).
_PARAM_GRID: tuple[dict[str, str], ...] = (
    {
        "lot_size": "0.05",
        "stop_loss_distance": "0.0015",
        "take_profit_distance": "0.0030",
    },
    {
        "lot_size": "0.10",
        "stop_loss_distance": "0.0020",
        "take_profit_distance": "0.0040",
    },
    {
        "lot_size": "0.10",
        "stop_loss_distance": "0.0025",
        "take_profit_distance": "0.0050",
    },
)


@dataclass(frozen=True, slots=True)
class WalkForwardRunInput:
    user_id: UUID
    request_id: str
    symbol: str
    timeframe: str = "m15"
    initial_balance: Decimal = Decimal("10000")
    bars: tuple[BacktestBarInput, ...] = ()
    window_config: WalkForwardWindowConfig = field(
        default_factory=WalkForwardWindowConfig
    )
    assumptions: BacktestAssumptions = field(default_factory=BacktestAssumptions)
    promotion_rules: WalkForwardPromotionRules = field(
        default_factory=WalkForwardPromotionRules
    )
    optimize_params: bool = True
    auto_analysis: bool = True


@dataclass(frozen=True, slots=True)
class WalkForwardResult:
    run: WalkForwardRun
    folds: tuple[FoldResult, ...]


@dataclass
class WalkForwardEngine:
    """Deterministic walk-forward validation orchestrator."""

    backtest_engine: BacktestEngine
    window_scheduler: RollingWindowScheduler = field(
        default_factory=RollingWindowScheduler
    )
    robustness_engine: RobustnessEngine = field(default_factory=RobustnessEngine)
    _events: list[DomainEvent] = field(default_factory=list, init=False)

    def drain_events(self) -> list[DomainEvent]:
        events = list(self._events)
        self._events.clear()
        return events

    def run(self, command: WalkForwardRunInput) -> WalkForwardResult:
        run = WalkForwardRun.create(
            user_id=command.user_id,
            request_id=command.request_id,
            symbol=command.symbol,
            timeframe=command.timeframe,
            window_config=command.window_config,
            bar_count=len(command.bars),
        )
        run.mark_running()
        self._events.append(
            WalkForwardStarted(
                user_id=command.user_id,
                run_id=run.id,
                request_id=command.request_id,
                symbol=run.symbol,
            )
        )
        try:
            return self._execute(run, command)
        except (ValueError, ArithmeticError, TypeError, KeyError) as exc:
            run.mark_failed(message=str(exc))
            self._events.append(
                WalkForwardFinished(
                    user_id=command.user_id,
                    run_id=run.id,
                    request_id=command.request_id,
                    status=run.status.value,
                    promotion=None,
                    fold_count=0,
                )
            )
            return WalkForwardResult(run=run, folds=())

    def _execute(
        self, run: WalkForwardRun, command: WalkForwardRunInput
    ) -> WalkForwardResult:
        windows = self.window_scheduler.build(
            bar_count=len(command.bars),
            config=command.window_config,
        )
        if not windows:
            raise ValueError("no walk-forward windows produced")

        folds: list[FoldResult] = []
        combined_equity: list[dict[str, object]] = []

        for window in windows:
            fold = self._run_fold(command, window)
            folds.append(fold)
            # Combined equity: concatenate OOS equity only (validation focus)
            for point in fold.oos_equity:
                combined_equity.append(
                    {**point, "fold_index": window.index, "segment": "oos"}
                )
            self._events.append(
                WalkForwardFoldCompleted(
                    user_id=command.user_id,
                    run_id=run.id,
                    fold_index=window.index,
                    oos_return_pct=str(fold.oos_metrics.total_return_pct),
                )
            )

        aggregated_is = self._aggregate([f.is_metrics for f in folds])
        # Aggregate OOS metrics only for promotion decisions
        aggregated_oos = self._aggregate([f.oos_metrics for f in folds])
        robustness = self.robustness_engine.compute(folds)
        promotion = self._decide_promotion(
            robustness=robustness,
            avg_oos=aggregated_oos.total_return_pct,
            rules=command.promotion_rules,
        )

        run.mark_completed(
            promotion=promotion,
            folds=folds,
            aggregated_is=aggregated_is,
            aggregated_oos=aggregated_oos,
            robustness=robustness,
            combined_equity=combined_equity,
        )
        self._events.append(
            WalkForwardFinished(
                user_id=command.user_id,
                run_id=run.id,
                request_id=command.request_id,
                status=run.status.value,
                promotion=promotion.value,
                fold_count=len(folds),
            )
        )
        return WalkForwardResult(run=run, folds=tuple(folds))

    def _run_fold(
        self, command: WalkForwardRunInput, window: WalkForwardWindow
    ) -> FoldResult:
        is_bars = command.bars[window.is_start : window.is_end]
        oos_bars = command.bars[window.oos_start : window.oos_end]

        if command.optimize_params:
            selected, is_result = self._optimize_is(command, is_bars, window.index)
        else:
            selected = {
                "lot_size": str(command.assumptions.lot_size),
                "stop_loss_distance": str(command.assumptions.stop_loss_distance),
                "take_profit_distance": str(command.assumptions.take_profit_distance),
            }
            is_result = self._backtest_segment(
                command,
                bars=is_bars,
                params=selected,
                request_suffix=f"is-{window.index}",
            )

        oos_result = self._backtest_segment(
            command,
            bars=oos_bars,
            params=selected,
            request_suffix=f"oos-{window.index}",
        )
        _ = self.backtest_engine.drain_events()

        return FoldResult(
            window=window,
            is_metrics=self._to_fold_metrics(is_result.run.metrics),
            oos_metrics=self._to_fold_metrics(oos_result.run.metrics),
            selected_params=selected,
            is_equity=tuple(is_result.run.equity_curve),
            oos_equity=tuple(oos_result.run.equity_curve),
        )

    def _optimize_is(
        self,
        command: WalkForwardRunInput,
        is_bars: tuple[BacktestBarInput, ...],
        fold_index: int,
    ) -> tuple[dict[str, str], BacktestResult]:
        best_params = dict(_PARAM_GRID[0])
        best_return = Decimal("-999999")
        best_result: BacktestResult | None = None
        for params in _PARAM_GRID:
            result = self._backtest_segment(
                command,
                bars=is_bars,
                params=params,
                request_suffix=f"is-opt-{fold_index}-{params['lot_size']}",
            )
            ret = Decimal(str(result.run.metrics.get("total_return_pct", "0")))
            if ret > best_return:
                best_return = ret
                best_params = dict(params)
                best_result = result
        assert best_result is not None
        return best_params, best_result

    def _backtest_segment(
        self,
        command: WalkForwardRunInput,
        *,
        bars: tuple[BacktestBarInput, ...],
        params: dict[str, str],
        request_suffix: str,
    ) -> BacktestResult:
        assumptions = BacktestAssumptions(
            spread=command.assumptions.spread,
            slippage=command.assumptions.slippage,
            fee_per_lot=command.assumptions.fee_per_lot,
            lot_size=Decimal(params["lot_size"]),
            stop_loss_distance=Decimal(params["stop_loss_distance"]),
            take_profit_distance=Decimal(params["take_profit_distance"]),
            contract_size=command.assumptions.contract_size,
            leverage=command.assumptions.leverage,
        )
        # Fresh strategy runtime per segment to avoid cross-talk
        engine = self.backtest_engine
        if engine.strategy_runtime is None:
            engine.strategy_runtime = StrategyRuntimeService(
                config=StrategyRuntimeConfig(consult_risk_engine=True)
            )
        return engine.run(
            BacktestRunInput(
                user_id=command.user_id,
                request_id=f"{command.request_id}-{request_suffix}",
                symbol=command.symbol,
                timeframe=command.timeframe,
                initial_balance=command.initial_balance,
                bars=bars,
                assumptions=assumptions,
                auto_analysis=command.auto_analysis,
                consult_execution_safety=False,
            )
        )

    def _to_fold_metrics(self, metrics: dict[str, object]) -> FoldMetrics:
        return FoldMetrics.from_dict(metrics)

    def _aggregate(self, rows: list[FoldMetrics]) -> FoldMetrics:
        if not rows:
            return FoldMetrics()
        n = Decimal(len(rows))
        avg_return = sum((r.total_return_pct for r in rows), Decimal("0")) / n
        avg_dd = sum((r.max_drawdown_pct for r in rows), Decimal("0")) / n
        avg_wr = sum((r.win_rate for r in rows), Decimal("0")) / n
        avg_exp = sum((r.expectancy for r in rows), Decimal("0")) / n
        trades = sum(r.trade_count for r in rows)
        pfs = [r.profit_factor for r in rows if r.profit_factor is not None]
        sharpes = [r.sharpe_ratio for r in rows if r.sharpe_ratio is not None]
        return FoldMetrics(
            total_return_pct=avg_return.quantize(Decimal("0.0001")),
            max_drawdown_pct=avg_dd.quantize(Decimal("0.0001")),
            win_rate=avg_wr.quantize(Decimal("0.0001")),
            profit_factor=(
                (sum(pfs, Decimal("0")) / Decimal(len(pfs))).quantize(Decimal("0.0001"))
                if pfs
                else None
            ),
            expectancy=avg_exp.quantize(Decimal("0.0001")),
            sharpe_ratio=(
                (sum(sharpes, Decimal("0")) / Decimal(len(sharpes))).quantize(
                    Decimal("0.0001")
                )
                if sharpes
                else None
            ),
            trade_count=trades,
        )

    def _decide_promotion(
        self,
        *,
        robustness: object,
        avg_oos: Decimal,
        rules: WalkForwardPromotionRules,
    ) -> PromotionDecision:
        from app.domain.entities.walkforward import RobustnessReport

        assert isinstance(robustness, RobustnessReport)
        # Reject first
        if (
            robustness.robustness_score < rules.max_robustness_reject
            or robustness.overfitting_score >= rules.min_overfitting_reject
            or robustness.consistency_score <= rules.max_consistency_reject
        ):
            return PromotionDecision.REJECT

        oos_ok = (not rules.require_positive_avg_oos) or avg_oos > 0
        if (
            robustness.robustness_score >= rules.min_robustness_promote
            and robustness.overfitting_score <= rules.max_overfitting_promote
            and robustness.consistency_score >= rules.min_consistency_promote
            and oos_ok
        ):
            return PromotionDecision.PROMOTE_TO_PAPER

        return PromotionDecision.NEEDS_REWORK
