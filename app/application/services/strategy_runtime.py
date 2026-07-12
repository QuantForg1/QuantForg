"""Strategy Runtime Engine — orchestrate analysis → decision only. Never order_send."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from app.application.services.mt5_market_data import MT5MarketDataService
from app.application.services.portfolio_sync import PortfolioSyncService
from app.application.services.risk_engine import RiskCheckInput, RiskEngine
from app.domain.entities.mt5_portfolio import AccountSnapshot, MT5Position
from app.domain.entities.risk_engine import RiskEngineConfig
from app.domain.entities.strategy_runtime import (
    AnalysisContext,
    MarketState,
    StrategyEvaluation,
    StrategyRuntimeConfig,
    StrategySignal,
)
from app.domain.enums.risk import PositionSizingMethod, RiskDecision
from app.domain.enums.signal import SignalDirection
from app.domain.enums.strategy import StrategyDecisionType
from app.domain.events.base import DomainEvent
from app.domain.events.strategy import (
    SignalGenerated,
    SignalRejected,
    StrategyBlocked,
    StrategyEvaluated,
)
from app.domain.market_data.timeframe import Timeframe


@dataclass(frozen=True, slots=True)
class StrategyEvaluateInput:
    """Normalized input for one Strategy Runtime evaluation."""

    user_id: UUID
    request_id: str
    symbol: str
    timeframe: str = "m15"
    analysis: AnalysisContext = field(default_factory=AnalysisContext)
    check_risk: bool = True
    requested_lots: Decimal | None = None
    stop_loss_distance: Decimal | None = None
    entry_price: Decimal | None = None
    # Optional offline overrides when MT5 is unavailable (tests)
    equity: Decimal | None = None
    balance: Decimal | None = None
    tick_age_seconds: float | None = None
    candle_count: int | None = None
    last_price: str | None = None
    mt5_connected: bool | None = None
    position_count: int | None = None


@dataclass(frozen=True, slots=True)
class StrategyEvaluateResult:
    """Outcome of a Strategy Runtime evaluation (no execution)."""

    evaluation: StrategyEvaluation
    signal: StrategySignal | None


@dataclass
class StrategyRuntimeService:
    """Orchestrates analysis engines into StrategyDecision — never executes."""

    market_data: MT5MarketDataService | None = None
    portfolio_sync: PortfolioSyncService | None = None
    risk_engine: RiskEngine | None = None
    config: StrategyRuntimeConfig = field(default_factory=StrategyRuntimeConfig)
    _events: list[DomainEvent] = field(default_factory=list, init=False)

    def drain_events(self) -> list[DomainEvent]:
        events = list(self._events)
        self._events.clear()
        return events

    def evaluate(
        self,
        command: StrategyEvaluateInput,
        *,
        account: AccountSnapshot | None = None,
        positions: list[MT5Position] | None = None,
    ) -> StrategyEvaluateResult:
        """Run the Strategy Runtime pipeline.

        1. Collect market state
        2. Validate data freshness
        3. Evaluate strategy preconditions
        4. Generate StrategyDecision (+ optional StrategySignal)
        """
        state = self.collect_market_state(command, account=account, positions=positions)
        fresh_ok, freshness_reasons = self.validate_freshness(state)
        preconditions, reasons, direction, confidence = self.evaluate_preconditions(
            state, fresh_ok=fresh_ok, freshness_reasons=freshness_reasons
        )

        decision = self._decide(preconditions, confidence)
        signal: StrategySignal | None = None
        risk_decision: str | None = None
        risk_score: int | None = None
        evaluation_id = uuid4()

        if (
            decision in {StrategyDecisionType.READY, StrategyDecisionType.WATCH}
            and direction is not SignalDirection.NEUTRAL
        ):
            signal = StrategySignal.create(
                user_id=command.user_id,
                symbol=command.symbol,
                timeframe=command.timeframe,
                direction=direction,
                confidence=confidence,
                reasons=list(reasons),
                evaluation_id=evaluation_id,
            )
            self._events.append(
                SignalGenerated(
                    user_id=command.user_id,
                    signal_id=signal.id,
                    evaluation_id=evaluation_id,
                    symbol=signal.symbol,
                    direction=signal.direction.value,
                    confidence=signal.confidence,
                )
            )

        if (
            decision is StrategyDecisionType.READY
            and command.check_risk
            and self.config.consult_risk_engine
            and signal is not None
            and direction is not SignalDirection.NEUTRAL
        ):
            risk_decision, risk_score, risk_reasons = self._consult_risk(
                command,
                signal=signal,
                account=account,
                positions=positions or [],
                last_price=state.last_price,
            )
            if risk_decision == RiskDecision.REJECT.value:
                signal.reject(reasons=risk_reasons)
                self._events.append(
                    SignalRejected(
                        user_id=command.user_id,
                        signal_id=signal.id,
                        evaluation_id=evaluation_id,
                        symbol=signal.symbol,
                        reasons=tuple(risk_reasons),
                    )
                )
                decision = StrategyDecisionType.BLOCKED
                reasons = [*reasons, *risk_reasons]
                preconditions = {**preconditions, "risk_approved": False}
            else:
                preconditions = {**preconditions, "risk_approved": True}
                if risk_decision == RiskDecision.REDUCE_SIZE.value:
                    reasons = [
                        *reasons,
                        "risk engine suggested REDUCE_SIZE (informational only)",
                    ]

        evaluation = StrategyEvaluation.record(
            user_id=command.user_id,
            request_id=command.request_id,
            symbol=command.symbol,
            timeframe=command.timeframe,
            decision=decision,
            reasons=list(reasons),
            preconditions=preconditions,
            market_state=state.to_dict(),
            signal_id=signal.id if signal is not None else None,
            risk_decision=risk_decision,
            risk_score=risk_score,
            entity_id=evaluation_id,
        )

        self._events.append(
            StrategyEvaluated(
                user_id=command.user_id,
                evaluation_id=evaluation.id,
                request_id=command.request_id,
                symbol=evaluation.symbol,
                timeframe=evaluation.timeframe,
                decision=evaluation.decision.value,
            )
        )
        if decision is StrategyDecisionType.BLOCKED:
            self._events.append(
                StrategyBlocked(
                    user_id=command.user_id,
                    evaluation_id=evaluation.id,
                    request_id=command.request_id,
                    symbol=evaluation.symbol,
                    reasons=tuple(evaluation.reasons),
                )
            )

        return StrategyEvaluateResult(evaluation=evaluation, signal=signal)

    # -- 1. Collect market state ---------------------------------------------

    def collect_market_state(
        self,
        command: StrategyEvaluateInput,
        *,
        account: AccountSnapshot | None = None,
        positions: list[MT5Position] | None = None,
    ) -> MarketState:
        symbol = command.symbol.strip().upper()
        timeframe = command.timeframe.strip().lower()
        now = datetime.now(UTC)

        tick_age = command.tick_age_seconds
        last_price = command.last_price
        candle_count = command.candle_count if command.candle_count is not None else 0
        mt5_connected = (
            bool(command.mt5_connected) if command.mt5_connected is not None else False
        )

        if self.market_data is not None and command.tick_age_seconds is None:
            try:
                tick = self.market_data.latest_tick(symbol)
                tick_age = max(0.0, (now - tick.timestamp).total_seconds())
                last_price = str(tick.mid)
                mt5_connected = True
            except (OSError, RuntimeError, ValueError, AttributeError):
                tick_age = tick_age if tick_age is not None else None

            if command.candle_count is None:
                try:
                    tf = Timeframe.parse(timeframe)
                    candles = self.market_data.historical_candles(symbol, tf, count=50)
                    candle_count = len(candles)
                    if last_price is None and candles:
                        last_price = str(candles[-1].close)
                    mt5_connected = True
                except (OSError, RuntimeError, ValueError, AttributeError):
                    pass

        pos_list = positions if positions is not None else []
        if (
            not pos_list
            and command.position_count is None
            and self.portfolio_sync is not None
        ):
            try:
                pos_list = self.portfolio_sync.list_positions()
            except (OSError, RuntimeError, ValueError):
                pos_list = []

        position_count = (
            command.position_count
            if command.position_count is not None
            else len(pos_list)
        )

        equity: str | None = None
        if command.equity is not None:
            equity = str(command.equity)
        elif account is not None:
            equity = str(account.equity)
        elif self.portfolio_sync is not None:
            try:
                equity = str(self.portfolio_sync.account_snapshot().equity)
            except (OSError, RuntimeError, ValueError):
                equity = None

        fresh, reasons = self._freshness_from_age(tick_age, candle_count)
        return MarketState(
            symbol=symbol,
            timeframe=timeframe,
            tick_age_seconds=tick_age,
            last_price=last_price,
            candle_count=candle_count,
            position_count=position_count,
            equity=equity,
            analysis=command.analysis,
            collected_at=now,
            data_fresh=fresh,
            freshness_reasons=reasons,
            mt5_connected=mt5_connected,
        )

    # -- 2. Validate data freshness ------------------------------------------

    def validate_freshness(self, state: MarketState) -> tuple[bool, tuple[str, ...]]:
        if state.data_fresh:
            return True, ()
        return False, state.freshness_reasons

    def _freshness_from_age(
        self, tick_age: float | None, candle_count: int
    ) -> tuple[bool, tuple[str, ...]]:
        reasons: list[str] = []
        if tick_age is None and candle_count <= 0:
            reasons.append("no market data available")
            return False, tuple(reasons)
        if tick_age is not None and tick_age > self.config.max_tick_age_seconds:
            max_age = self.config.max_tick_age_seconds
            reasons.append(f"tick stale ({tick_age:.0f}s > {max_age:.0f}s)")
            return False, tuple(reasons)
        if candle_count <= 0 and tick_age is None:
            reasons.append("no candles available")
            return False, tuple(reasons)
        return True, ()

    # -- 3. Evaluate strategy preconditions ----------------------------------

    def evaluate_preconditions(
        self,
        state: MarketState,
        *,
        fresh_ok: bool,
        freshness_reasons: tuple[str, ...],
    ) -> tuple[dict[str, bool], list[str], SignalDirection, float]:
        analysis = state.analysis
        reasons: list[str] = []
        preconditions: dict[str, bool] = {
            "data_fresh": fresh_ok,
            "market_open": analysis.market_open,
            "has_structure": analysis.has_structure
            or analysis.structure_bias not in {"", "unknown"},
            "has_liquidity_context": analysis.has_liquidity
            or analysis.liquidity_sweep_bullish
            or analysis.liquidity_sweep_bearish,
            "has_order_block_context": analysis.has_order_blocks
            or analysis.order_block_bullish
            or analysis.order_block_bearish,
            "has_fvg_context": analysis.has_fvgs
            or analysis.fvg_bullish
            or analysis.fvg_bearish,
        }

        if not fresh_ok:
            reasons.extend(freshness_reasons or ("stale market data",))
        if not analysis.market_open:
            reasons.append("market closed")

        bullish_hits = 0
        bearish_hits = 0
        if analysis.structure_bias == "up":
            bullish_hits += 1
            reasons.append("structure bias up")
        elif analysis.structure_bias == "down":
            bearish_hits += 1
            reasons.append("structure bias down")
        elif analysis.structure_bias == "range":
            reasons.append("structure ranging")

        if analysis.liquidity_sweep_bullish:
            bullish_hits += 1
            reasons.append("bullish liquidity sweep")
        if analysis.liquidity_sweep_bearish:
            bearish_hits += 1
            reasons.append("bearish liquidity sweep")
        if analysis.order_block_bullish:
            bullish_hits += 1
            reasons.append("bullish order block")
        if analysis.order_block_bearish:
            bearish_hits += 1
            reasons.append("bearish order block")
        if analysis.fvg_bullish:
            bullish_hits += 1
            reasons.append("bullish fair value gap")
        if analysis.fvg_bearish:
            bearish_hits += 1
            reasons.append("bearish fair value gap")

        if analysis.notes:
            reasons.extend(list(analysis.notes)[:10])

        if bullish_hits > bearish_hits:
            direction = SignalDirection.BUY
            confluence = bullish_hits
        elif bearish_hits > bullish_hits:
            direction = SignalDirection.SELL
            confluence = bearish_hits
        else:
            direction = SignalDirection.NEUTRAL
            confluence = max(bullish_hits, bearish_hits)

        preconditions["confluence_met"] = confluence >= self.config.min_confluence
        preconditions["direction_resolved"] = direction is not SignalDirection.NEUTRAL

        # Confidence scales with confluence (capped at 1.0)
        confidence = min(1.0, confluence * 0.25 + (0.15 if fresh_ok else 0.0))
        if (
            analysis.structure_bias in {"up", "down"}
            and direction is not SignalDirection.NEUTRAL
        ):
            confidence = min(1.0, confidence + 0.10)

        return preconditions, reasons, direction, round(confidence, 4)

    # -- 4. Generate StrategyDecision ----------------------------------------

    def _decide(
        self, preconditions: dict[str, bool], confidence: float
    ) -> StrategyDecisionType:
        if self.config.require_fresh_data and not preconditions.get(
            "data_fresh", False
        ):
            return StrategyDecisionType.BLOCKED
        if not preconditions.get("market_open", True):
            return StrategyDecisionType.BLOCKED
        if (
            preconditions.get("confluence_met", False)
            and preconditions.get("direction_resolved", False)
            and confidence >= self.config.min_ready_confidence
        ):
            return StrategyDecisionType.READY
        if confidence >= self.config.min_watch_confidence and (
            preconditions.get("has_structure", False)
            or preconditions.get("has_liquidity_context", False)
            or preconditions.get("has_order_block_context", False)
            or preconditions.get("has_fvg_context", False)
        ):
            return StrategyDecisionType.WATCH
        return StrategyDecisionType.NO_ACTION

    def _consult_risk(
        self,
        command: StrategyEvaluateInput,
        *,
        signal: StrategySignal,
        account: AccountSnapshot | None,
        positions: list[MT5Position],
        last_price: str | None,
    ) -> tuple[str, int | None, list[str]]:
        engine = self.risk_engine or RiskEngine(config=RiskEngineConfig())
        equity = command.equity
        balance = command.balance
        if account is None:
            eq = equity if equity is not None else Decimal("10000")
            bal = balance if balance is not None else eq
            account = AccountSnapshot(
                login=1,
                balance=bal,
                equity=eq,
                margin=Decimal("0"),
                free_margin=eq,
                margin_level=Decimal("0"),
                profit=Decimal("0"),
                leverage=100,
            )
        entry = command.entry_price
        if entry is None and last_price is not None:
            try:
                entry = Decimal(last_price)
            except ArithmeticError:
                entry = Decimal("1")
        if entry is None:
            entry = Decimal("1")
        stop = command.stop_loss_distance or (entry * Decimal("0.001"))
        lots = command.requested_lots or Decimal("0.10")
        assessment = engine.evaluate(
            RiskCheckInput(
                user_id=command.user_id,
                request_id=f"strategy-{command.request_id}",
                symbol=command.symbol,
                side=signal.direction.value,
                requested_lots=lots,
                stop_loss_distance=stop,
                sizing_method=PositionSizingMethod.PERCENTAGE_RISK,
                entry_price=entry,
            ),
            account=account,
            positions=positions,
        )
        _ = engine.drain_events()
        return (
            assessment.decision.value,
            assessment.risk_score,
            (
                list(assessment.reasons)
                if assessment.decision is RiskDecision.REJECT
                else []
            ),
        )
