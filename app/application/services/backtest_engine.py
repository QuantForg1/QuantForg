"""Backtest Simulation Engine — replay Strategy Runtime + Risk + Safety offline.

Never connects to a live broker. Never calls order_send().
Never enables EXECUTION_ENABLED.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID, uuid4

from app.application.services.backtest_metrics import MetricsEngine
from app.application.services.execution_safety import ExecutionSafetyService
from app.application.services.historical_replay import (
    HistoricalReplayEngine,
    ReplayBar,
)
from app.application.services.risk_engine import RiskEngine
from app.application.services.strategy_runtime import (
    StrategyEvaluateInput,
    StrategyRuntimeService,
)
from app.domain.entities.backtest import (
    BacktestAssumptions,
    BacktestRun,
    EquityPoint,
    SimulatedTrade,
    VirtualPortfolio,
)
from app.domain.entities.mt5_order import OrderIntent
from app.domain.entities.strategy_runtime import (
    AnalysisContext,
    StrategyRuntimeConfig,
)
from app.domain.enums.backtest import (
    ReplayMode,
    SimulatedExitReason,
    SimulatedTradeSide,
    SimulatedTradeStatus,
)
from app.domain.enums.order import OrderSide, OrderType
from app.domain.enums.signal import SignalDirection
from app.domain.enums.strategy import StrategyDecisionType
from app.domain.events.backtest import (
    BacktestFinished,
    BacktestStarted,
    MetricUpdated,
    TradeSimulated,
)
from app.domain.events.base import DomainEvent
from app.domain.value_objects.mt5_order import LotSize, Slippage


@dataclass(frozen=True, slots=True)
class BacktestBarInput:
    """One OHLC bar supplied to a backtest run (never from live broker send)."""

    open_time: str
    open: str
    high: str
    low: str
    close: str
    volume: str = "0"
    close_time: str | None = None


@dataclass(frozen=True, slots=True)
class BacktestRunInput:
    """Normalized input for one offline backtest."""

    user_id: UUID
    request_id: str
    symbol: str
    timeframe: str = "m15"
    initial_balance: Decimal = Decimal("10000")
    bars: tuple[BacktestBarInput, ...] = ()
    ticks: tuple[dict[str, object], ...] = ()
    replay_mode: ReplayMode = ReplayMode.CANDLE
    assumptions: BacktestAssumptions = field(default_factory=BacktestAssumptions)
    auto_analysis: bool = True
    analysis: AnalysisContext = field(default_factory=AnalysisContext)
    max_open_trades: int = 1
    consult_execution_safety: bool = True


@dataclass(frozen=True, slots=True)
class BacktestResult:
    run: BacktestRun
    trades: tuple[SimulatedTrade, ...]
    equity_curve: tuple[EquityPoint, ...]


@dataclass
class BacktestEngine:
    """Deterministic event-driven backtesting orchestrator (offline only)."""

    strategy_runtime: StrategyRuntimeService | None = None
    risk_engine: RiskEngine | None = None
    execution_safety: ExecutionSafetyService | None = None
    metrics_engine: MetricsEngine = field(default_factory=MetricsEngine)
    _events: list[DomainEvent] = field(default_factory=list, init=False)

    def drain_events(self) -> list[DomainEvent]:
        events = list(self._events)
        self._events.clear()
        return events

    def run(self, command: BacktestRunInput) -> BacktestResult:
        """Execute a full backtest: replay → simulate → metrics."""
        run = BacktestRun.create(
            user_id=command.user_id,
            request_id=command.request_id,
            symbol=command.symbol,
            timeframe=command.timeframe,
            initial_balance=command.initial_balance,
            replay_mode=command.replay_mode,
            assumptions={
                "spread": str(command.assumptions.spread),
                "slippage": str(command.assumptions.slippage),
                "fee_per_lot": str(command.assumptions.fee_per_lot),
                "lot_size": str(command.assumptions.lot_size),
                "stop_loss_distance": str(command.assumptions.stop_loss_distance),
                "take_profit_distance": str(command.assumptions.take_profit_distance),
                "contract_size": str(command.assumptions.contract_size),
                "leverage": command.assumptions.leverage,
            },
            bar_count=len(command.bars) if command.bars else len(command.ticks),
        )
        run.mark_running()
        self._events.append(
            BacktestStarted(
                user_id=command.user_id,
                backtest_id=run.id,
                request_id=command.request_id,
                symbol=run.symbol,
            )
        )

        try:
            return self._execute(run, command)
        except (ValueError, ArithmeticError, TypeError, KeyError) as exc:
            run.mark_failed(message=str(exc))
            self._events.append(
                BacktestFinished(
                    user_id=command.user_id,
                    backtest_id=run.id,
                    request_id=command.request_id,
                    status=run.status.value,
                    trade_count=0,
                )
            )
            return BacktestResult(run=run, trades=(), equity_curve=())

    def _execute(self, run: BacktestRun, command: BacktestRunInput) -> BacktestResult:
        replay = HistoricalReplayEngine(mode=command.replay_mode)
        if command.replay_mode is ReplayMode.TICK and command.ticks:
            replay.load_raw_bars([dict(t) for t in command.ticks], mode=ReplayMode.TICK)
        else:
            rows: list[dict[str, object]] = [
                {
                    "open_time": b.open_time,
                    "close_time": b.close_time or b.open_time,
                    "open": b.open,
                    "high": b.high,
                    "low": b.low,
                    "close": b.close,
                    "volume": b.volume,
                    "timestamp": b.close_time or b.open_time,
                }
                for b in command.bars
            ]
            replay.load_raw_bars(rows, mode=ReplayMode.CANDLE)

        replay.start()
        # Expose pause/resume/step/speed controls on the run snapshot
        replay.resume()

        portfolio = VirtualPortfolio.create(initial_balance=command.initial_balance)
        trades: list[SimulatedTrade] = []
        equity_curve: list[EquityPoint] = []
        assumptions = command.assumptions
        streak = 0
        last_bias = "unknown"

        strategy = self.strategy_runtime or StrategyRuntimeService(
            config=StrategyRuntimeConfig(
                consult_risk_engine=True,
                require_fresh_data=True,
            ),
            risk_engine=self.risk_engine,
        )

        while True:
            bar = replay.step_forward()
            if bar is None:
                break

            # 1) Manage open trades (SL/TP) against bar range
            self._manage_open_trades(
                trades,
                bar=bar,
                portfolio=portfolio,
                assumptions=assumptions,
                user_id=command.user_id,
                backtest_id=run.id,
            )

            # 2) Mark-to-market
            floating, margin = self._floating_and_margin(
                trades, mark=bar.close, assumptions=assumptions
            )
            portfolio.mark_to_market(floating, margin=margin)
            dd = Decimal("0")
            if portfolio.peak_equity > 0:
                dd = (
                    (portfolio.peak_equity - portfolio.equity)
                    / portfolio.peak_equity
                    * Decimal("100")
                )
            equity_curve.append(
                EquityPoint(
                    timestamp=bar.timestamp,
                    equity=portfolio.equity,
                    balance=portfolio.balance,
                    drawdown_pct=dd,
                    bar_index=bar.index,
                )
            )

            open_count = sum(1 for t in trades if t.status is SimulatedTradeStatus.OPEN)
            if open_count >= command.max_open_trades:
                continue

            # 3) Strategy Runtime (offline overrides — no MT5 / no broker)
            analysis = (
                self._auto_analysis(bar, streak=streak, last_bias=last_bias)
                if command.auto_analysis
                else command.analysis
            )
            bias = analysis.structure_bias
            if bias in {"up", "down"}:
                if bias == last_bias:
                    streak += 1
                else:
                    streak = 1
                    last_bias = bias
            else:
                streak = 0
                last_bias = "unknown"

            result = strategy.evaluate(
                StrategyEvaluateInput(
                    user_id=command.user_id,
                    request_id=f"{command.request_id}-bar-{bar.index}",
                    symbol=command.symbol,
                    timeframe=command.timeframe,
                    analysis=analysis,
                    check_risk=True,
                    requested_lots=assumptions.lot_size,
                    stop_loss_distance=assumptions.stop_loss_distance,
                    entry_price=bar.close,
                    equity=portfolio.equity,
                    balance=portfolio.balance,
                    tick_age_seconds=0.0,
                    candle_count=bar.index + 1,
                    last_price=str(bar.close),
                    mt5_connected=False,
                    position_count=open_count,
                )
            )
            _ = strategy.drain_events()

            if result.evaluation.decision is not StrategyDecisionType.READY:
                continue
            if result.signal is None or result.signal.rejected:
                continue
            if result.signal.direction is SignalDirection.NEUTRAL:
                continue

            side = (
                SimulatedTradeSide.BUY
                if result.signal.direction is SignalDirection.BUY
                else SimulatedTradeSide.SELL
            )

            # 4) Execution Safety policy (offline) — decisions only
            if command.consult_execution_safety and self.execution_safety is not None:
                intent = OrderIntent(
                    symbol=command.symbol,
                    side=(
                        OrderSide.BUY
                        if side is SimulatedTradeSide.BUY
                        else OrderSide.SELL
                    ),
                    order_type=OrderType.MARKET,
                    volume=LotSize.of(str(assumptions.lot_size)),
                    slippage=Slippage.of(10),
                )
                ok, reasons, _warnings, _checks = self.execution_safety.evaluate_policy(
                    intent,
                    login=1,
                    spread=assumptions.spread,
                    leverage=Decimal(assumptions.leverage),
                    now=bar.timestamp,
                )
                if not ok:
                    continue
                _ = reasons

            # 5) Simulated fill (never order_send)
            trade = self._open_simulated(
                backtest_id=run.id,
                user_id=command.user_id,
                symbol=command.symbol,
                side=side,
                bar=bar,
                assumptions=assumptions,
            )
            trades.append(trade)
            portfolio.apply_realized(Decimal("0"), fee=trade.fees)

        # Close any remaining open trades at last mark
        if equity_curve:
            last = equity_curve[-1]
            last_bar = ReplayBar(
                timestamp=last.timestamp,
                open=last.equity,  # unused for exit price path
                high=last.equity,
                low=last.equity,
                close=Decimal(
                    str(
                        next(
                            (
                                t.entry_price
                                for t in reversed(trades)
                                if t.status is SimulatedTradeStatus.OPEN
                            ),
                            last.equity,
                        )
                    )
                ),
                index=last.bar_index,
            )
            # Prefer last replayed close from bars list
            if replay.bars:
                last_bar = replay.bars[-1]
            self._close_all_open(
                trades,
                bar=last_bar,
                portfolio=portfolio,
                assumptions=assumptions,
                user_id=command.user_id,
                backtest_id=run.id,
                reason=SimulatedExitReason.END_OF_DATA,
            )
            floating, margin = self._floating_and_margin(
                trades, mark=last_bar.close, assumptions=assumptions
            )
            portfolio.mark_to_market(floating, margin=margin)
            dd = Decimal("0")
            if portfolio.peak_equity > 0:
                dd = (
                    (portfolio.peak_equity - portfolio.equity)
                    / portfolio.peak_equity
                    * Decimal("100")
                )
            equity_curve.append(
                EquityPoint(
                    timestamp=last_bar.timestamp,
                    equity=portfolio.equity,
                    balance=portfolio.balance,
                    drawdown_pct=dd,
                    bar_index=last_bar.index,
                )
            )

        metrics = self.metrics_engine.compute(
            trades=trades,
            equity_curve=equity_curve,
            initial_balance=command.initial_balance,
        )
        self._events.append(
            MetricUpdated(
                user_id=command.user_id,
                backtest_id=run.id,
                total_return_pct=str(metrics.total_return_pct),
                max_drawdown_pct=str(metrics.max_drawdown_pct),
            )
        )
        run.mark_completed(
            metrics=metrics,
            equity_curve=equity_curve,
            portfolio=portfolio,
            trade_count=sum(
                1 for t in trades if t.status is SimulatedTradeStatus.CLOSED
            ),
            replay_state=replay.controller.to_dict(),
        )
        self._events.append(
            BacktestFinished(
                user_id=command.user_id,
                backtest_id=run.id,
                request_id=command.request_id,
                status=run.status.value,
                trade_count=run.trade_count,
            )
        )
        return BacktestResult(
            run=run,
            trades=tuple(trades),
            equity_curve=tuple(equity_curve),
        )

    # -- helpers -------------------------------------------------------------

    def _auto_analysis(
        self, bar: ReplayBar, *, streak: int, last_bias: str
    ) -> AnalysisContext:
        if bar.close > bar.open:
            bias = "up"
            bullish = True
            bearish = False
        elif bar.close < bar.open:
            bias = "down"
            bullish = False
            bearish = True
        else:
            return AnalysisContext(
                market_open=True,
                session="backtest",
                structure_bias="range",
                has_structure=True,
            )
        # Build confluence after a short streak so READY can fire deterministically
        strong = (streak >= 1 and bias == last_bias) or streak == 0
        return AnalysisContext(
            market_open=True,
            session="backtest",
            structure_bias=bias,
            liquidity_sweep_bullish=bullish and strong,
            liquidity_sweep_bearish=bearish and strong,
            order_block_bullish=bullish and strong,
            order_block_bearish=bearish and strong,
            fvg_bullish=bullish and strong,
            fvg_bearish=bearish and strong,
            has_structure=True,
            has_liquidity=strong,
            has_order_blocks=strong,
            has_fvgs=strong,
            notes=("auto_analysis",),
        )

    def _open_simulated(
        self,
        *,
        backtest_id: UUID,
        user_id: UUID,
        symbol: str,
        side: SimulatedTradeSide,
        bar: ReplayBar,
        assumptions: BacktestAssumptions,
    ) -> SimulatedTrade:
        half_spread = assumptions.spread / Decimal("2")
        slip = assumptions.slippage
        if side is SimulatedTradeSide.BUY:
            entry = bar.close + half_spread + slip
            stop = entry - assumptions.stop_loss_distance
            take = entry + assumptions.take_profit_distance
        else:
            entry = bar.close - half_spread - slip
            stop = entry + assumptions.stop_loss_distance
            take = entry - assumptions.take_profit_distance
        fees = assumptions.fee_per_lot * assumptions.lot_size
        trade = SimulatedTrade.open_trade(
            backtest_id=backtest_id,
            symbol=symbol,
            side=side,
            volume=assumptions.lot_size,
            entry_price=entry,
            stop_loss=stop,
            take_profit=take,
            spread=assumptions.spread,
            slippage=assumptions.slippage,
            fees=fees,
            opened_at=bar.timestamp,
            bar_index=bar.index,
            entity_id=uuid4(),
        )
        self._events.append(
            TradeSimulated(
                user_id=user_id,
                backtest_id=backtest_id,
                trade_id=trade.id,
                symbol=symbol,
                side=side.value,
                action="opened",
            )
        )
        return trade

    def _manage_open_trades(
        self,
        trades: list[SimulatedTrade],
        *,
        bar: ReplayBar,
        portfolio: VirtualPortfolio,
        assumptions: BacktestAssumptions,
        user_id: UUID,
        backtest_id: UUID,
    ) -> None:
        for trade in trades:
            if trade.status is not SimulatedTradeStatus.OPEN:
                continue
            hit_sl = False
            hit_tp = False
            exit_price = bar.close
            if trade.side is SimulatedTradeSide.BUY:
                if trade.stop_loss is not None and bar.low <= trade.stop_loss:
                    hit_sl = True
                    exit_price = trade.stop_loss
                elif trade.take_profit is not None and bar.high >= trade.take_profit:
                    hit_tp = True
                    exit_price = trade.take_profit
            else:
                if trade.stop_loss is not None and bar.high >= trade.stop_loss:
                    hit_sl = True
                    exit_price = trade.stop_loss
                elif trade.take_profit is not None and bar.low <= trade.take_profit:
                    hit_tp = True
                    exit_price = trade.take_profit
            if not hit_sl and not hit_tp:
                continue
            reason = (
                SimulatedExitReason.STOP_LOSS
                if hit_sl
                else SimulatedExitReason.TAKE_PROFIT
            )
            self._close_trade(
                trade,
                exit_price=exit_price,
                bar=bar,
                portfolio=portfolio,
                assumptions=assumptions,
                user_id=user_id,
                backtest_id=backtest_id,
                reason=reason,
            )

    def _close_all_open(
        self,
        trades: list[SimulatedTrade],
        *,
        bar: ReplayBar,
        portfolio: VirtualPortfolio,
        assumptions: BacktestAssumptions,
        user_id: UUID,
        backtest_id: UUID,
        reason: SimulatedExitReason,
    ) -> None:
        for trade in trades:
            if trade.status is SimulatedTradeStatus.OPEN:
                self._close_trade(
                    trade,
                    exit_price=bar.close,
                    bar=bar,
                    portfolio=portfolio,
                    assumptions=assumptions,
                    user_id=user_id,
                    backtest_id=backtest_id,
                    reason=reason,
                )

    def _close_trade(
        self,
        trade: SimulatedTrade,
        *,
        exit_price: Decimal,
        bar: ReplayBar,
        portfolio: VirtualPortfolio,
        assumptions: BacktestAssumptions,
        user_id: UUID,
        backtest_id: UUID,
        reason: SimulatedExitReason,
    ) -> None:
        pnl = trade.unrealized_pnl(exit_price, contract_size=assumptions.contract_size)
        exit_fee = assumptions.fee_per_lot * trade.volume
        trade.close(
            exit_price=exit_price,
            pnl=pnl,
            exit_reason=reason,
            closed_at=bar.timestamp,
            bar_index=bar.index,
            extra_fees=exit_fee,
        )
        portfolio.apply_realized(pnl, fee=exit_fee)
        self._events.append(
            TradeSimulated(
                user_id=user_id,
                backtest_id=backtest_id,
                trade_id=trade.id,
                symbol=trade.symbol,
                side=trade.side.value,
                action="closed",
            )
        )

    def _floating_and_margin(
        self,
        trades: list[SimulatedTrade],
        *,
        mark: Decimal,
        assumptions: BacktestAssumptions,
    ) -> tuple[Decimal, Decimal]:
        floating = Decimal("0")
        margin = Decimal("0")
        for trade in trades:
            if trade.status is not SimulatedTradeStatus.OPEN:
                continue
            floating += trade.unrealized_pnl(
                mark, contract_size=assumptions.contract_size
            )
            notional = trade.volume * assumptions.contract_size * mark
            margin += notional / Decimal(assumptions.leverage)
        return floating, margin
