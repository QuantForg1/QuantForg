"""OrderBlockEngine — orchestrate detect → validate → mitigate → breaker → snapshot.

Why it exists
-------------
Single entry point that loads price/structure/liquidity context, detects and
lifecycles order blocks, and returns an immutable :class:`OrderBlockSnapshot`
plus domain events. Does not trade, call MetaTrader, run AI, or emit signals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.domain.events.base import DomainEvent
from app.domain.events.order_block import (
    BreakerDetected,
    MitigationDetected,
    OrderBlockDetected,
    OrderBlockExpired,
    OrderBlockStateChanged,
    OrderBlockValidated,
)
from app.domain.interfaces.order_block import (
    LiquiditySnapshotPort,
    MarketStructurePort,
    OrderBlockRepositoryPort,
    PriceHistoryPort,
)
from app.domain.market_data.timeframe import Timeframe
from app.domain.order_block.breaker_detector import BreakerDetector
from app.domain.order_block.detector import OrderBlockDetector
from app.domain.order_block.enums import OrderBlockState
from app.domain.order_block.mitigation_detector import MitigationDetector
from app.domain.order_block.models import (
    BreakerBlock,
    MitigationBlock,
    OrderBlock,
    OrderBlockSnapshot,
)
from app.domain.order_block.strength_evaluator import OrderBlockStrengthEvaluator
from app.domain.order_block.validator import OrderBlockValidator
from app.domain.value_objects.identity import SymbolCode


@dataclass(frozen=True, slots=True)
class OrderBlockResult:
    """Engine output: immutable snapshot plus pending domain events."""

    snapshot: OrderBlockSnapshot
    events: tuple[DomainEvent, ...] = ()


@dataclass(frozen=True, slots=True)
class OrderBlockEngine:
    """Orchestrate order-block analysis for one symbol/timeframe."""

    prices: PriceHistoryPort
    structure: MarketStructurePort
    liquidity: LiquiditySnapshotPort | None = None
    repository: OrderBlockRepositoryPort | None = None
    detector: OrderBlockDetector = field(default_factory=OrderBlockDetector)
    validator: OrderBlockValidator = field(default_factory=OrderBlockValidator)
    mitigation: MitigationDetector = field(default_factory=MitigationDetector)
    breakers: BreakerDetector = field(default_factory=BreakerDetector)
    strength: OrderBlockStrengthEvaluator = field(
        default_factory=OrderBlockStrengthEvaluator
    )
    max_age_bars: int = 100
    candle_limit: int = 500

    async def analyze(
        self,
        symbol_code: str | SymbolCode,
        timeframe: Timeframe | str,
        *,
        persist: bool = False,
        as_of: datetime | None = None,
    ) -> OrderBlockResult:
        """Run a full order-block analysis pass and return snapshot + events."""
        code = (
            symbol_code
            if isinstance(symbol_code, SymbolCode)
            else SymbolCode(value=symbol_code)
        )
        tf = (
            timeframe
            if isinstance(timeframe, Timeframe)
            else Timeframe.parse(timeframe)
        )
        moment = as_of or datetime.now(UTC)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)

        candles = await self.prices.get_candles(code, tf, limit=self.candle_limit)
        structure = await self.structure.get_latest_snapshot(code, tf)
        liquidity = None
        if self.liquidity is not None:
            liquidity = await self.liquidity.get_latest_snapshot(code, tf)

        previous: OrderBlockSnapshot | None = None
        if self.repository is not None:
            previous = await self.repository.get_latest_snapshot(code, tf)

        detected = self.detector.detect(candles, structure)
        # Merge with prior non-terminal blocks for continued lifecycle.
        prior_live: tuple[OrderBlock, ...] = ()
        if previous is not None:
            prior_live = tuple(
                b
                for b in previous.order_blocks
                if b.state
                not in {
                    OrderBlockState.EXPIRED,
                    OrderBlockState.BREAKER,
                }
                and b.id not in {d.id for d in detected}
            )

        candidates = prior_live + detected
        validation = self.validator.validate(candidates, candles, as_of=moment)
        blocks = validation.activated + validation.expired

        mit = self.mitigation.detect(
            [b for b in blocks if b.state != OrderBlockState.EXPIRED],
            candles,
        )
        brk = self.breakers.detect(mit.blocks, candles)
        blocks = brk.blocks
        blocks = self._expire_stale(blocks, len(candles), moment)
        blocks = self.strength.evaluate(blocks, candles, liquidity=liquidity)

        # Keep terminal records from this pass + prior breakers/mitigations.
        prior_breakers = previous.breakers if previous else ()
        prior_mits = previous.mitigations if previous else ()
        # Prefer fresh mitigations/breakers; dedupe by id.
        breakers = self._merge_by_id(prior_breakers, brk.breakers)
        mitigations = self._merge_mitigations(prior_mits, mit.mitigations)

        snapshot = OrderBlockSnapshot(
            symbol_code=code,
            timeframe=tf,
            as_of=moment,
            order_blocks=tuple(blocks),
            breakers=breakers,
            mitigations=mitigations,
        )

        events = self._build_events(snapshot, previous, detected, validation.expired)

        if persist and self.repository is not None:
            await self.repository.save_snapshot(snapshot)

        return OrderBlockResult(snapshot=snapshot, events=tuple(events))

    def _expire_stale(
        self,
        blocks: tuple[OrderBlock, ...] | list[OrderBlock],
        series_length: int,
        as_of: datetime,
    ) -> tuple[OrderBlock, ...]:
        result: list[OrderBlock] = []
        last_index = max(series_length - 1, 0)
        for block in blocks:
            if block.state in {
                OrderBlockState.EXPIRED,
                OrderBlockState.BREAKER,
            }:
                result.append(block)
                continue
            age = last_index - block.origin_bar_index
            if age > self.max_age_bars and block.state in {
                OrderBlockState.DETECTED,
                OrderBlockState.VALIDATED,
                OrderBlockState.ACTIVE,
                OrderBlockState.MITIGATED,
            }:
                result.append(block.transition(OrderBlockState.EXPIRED, at=as_of))
            else:
                result.append(block)
        return tuple(result)

    @staticmethod
    def _merge_by_id(
        prior: tuple[BreakerBlock, ...],
        fresh: tuple[BreakerBlock, ...],
    ) -> tuple[BreakerBlock, ...]:
        by_id = {item.id: item for item in prior}
        for item in fresh:
            by_id[item.id] = item
        return tuple(by_id.values())

    @staticmethod
    def _merge_mitigations(
        prior: tuple[MitigationBlock, ...],
        fresh: tuple[MitigationBlock, ...],
    ) -> tuple[MitigationBlock, ...]:
        by_id = {item.id: item for item in prior}
        for item in fresh:
            by_id[item.id] = item
        return tuple(by_id.values())

    def _build_events(
        self,
        snapshot: OrderBlockSnapshot,
        previous: OrderBlockSnapshot | None,
        newly_detected: tuple[OrderBlock, ...],
        expired_from_validation: tuple[OrderBlock, ...],
    ) -> list[DomainEvent]:
        events: list[DomainEvent] = []
        prev_map = (
            {b.id: b for b in previous.order_blocks} if previous is not None else {}
        )
        prev_breaker_ids = {b.id for b in previous.breakers} if previous else set()
        prev_mit_ids = {m.id for m in previous.mitigations} if previous else set()
        detected_ids = {b.id for b in newly_detected}

        for block in snapshot.order_blocks:
            prev = prev_map.get(block.id)
            if block.id in detected_ids and prev is None:
                events.append(
                    OrderBlockDetected(
                        order_block_id=block.id,
                        symbol_code=str(block.symbol_code),
                        timeframe=block.timeframe.value,
                        side=block.side.value,
                        state=block.state.value,
                        low_price=str(block.zone.low_price),
                        high_price=str(block.zone.high_price),
                        occurred_at=block.formed_at,
                    )
                )

            if (prev is None or prev.state != block.state) and (
                prev is not None or block.state != OrderBlockState.DETECTED
            ):
                events.append(
                    OrderBlockStateChanged(
                        order_block_id=block.id,
                        symbol_code=str(block.symbol_code),
                        timeframe=block.timeframe.value,
                        previous_state=(
                            prev.state.value if prev is not None else "none"
                        ),
                        current_state=block.state.value,
                        occurred_at=snapshot.as_of,
                    )
                )

            if block.validated_at is not None and (
                prev is None or prev.validated_at is None
            ):
                score = str(block.quality.score) if block.quality is not None else None
                events.append(
                    OrderBlockValidated(
                        order_block_id=block.id,
                        symbol_code=str(block.symbol_code),
                        timeframe=block.timeframe.value,
                        side=block.side.value,
                        quality_score=score,
                        occurred_at=block.validated_at or snapshot.as_of,
                    )
                )

            if block.state == OrderBlockState.EXPIRED and (
                prev is None or prev.state != OrderBlockState.EXPIRED
            ):
                events.append(
                    OrderBlockExpired(
                        order_block_id=block.id,
                        symbol_code=str(block.symbol_code),
                        timeframe=block.timeframe.value,
                        previous_state=(
                            prev.state.value if prev is not None else "detected"
                        ),
                        occurred_at=snapshot.as_of,
                    )
                )

        for expired in expired_from_validation:
            # Already covered via snapshot loop if present; skip duplicates.
            _ = expired

        for breaker in snapshot.breakers:
            if breaker.id in prev_breaker_ids:
                continue
            events.append(
                BreakerDetected(
                    breaker_id=breaker.id,
                    order_block_id=breaker.order_block.id,
                    symbol_code=str(breaker.symbol_code),
                    timeframe=breaker.timeframe.value,
                    break_price=str(breaker.break_price),
                    occurred_at=breaker.broken_at,
                )
            )

        for mitigation in snapshot.mitigations:
            if mitigation.id in prev_mit_ids:
                continue
            events.append(
                MitigationDetected(
                    mitigation_id=mitigation.id,
                    order_block_id=mitigation.order_block.id,
                    symbol_code=str(mitigation.symbol_code),
                    timeframe=mitigation.timeframe.value,
                    kind=mitigation.kind.value,
                    touch_price=str(mitigation.touch_price),
                    occurred_at=mitigation.mitigated_at,
                )
            )

        return events
