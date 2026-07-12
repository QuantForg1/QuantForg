"""Application DTOs for the Paper Trading Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.domain.entities.paper import (
    PaperOrder,
    PaperPerformance,
    PaperPortfolio,
    PaperPosition,
    PaperTrade,
)


@dataclass(frozen=True, slots=True)
class PlacePaperOrderCommand:
    user_id: UUID
    symbol: str
    side: str
    order_type: str = "market"
    volume: str = "0.10"
    price: str | None = None
    stop_loss: str | None = None
    take_profit: str | None = None
    client_order_id: str = ""
    reduce_position_id: UUID | None = None
    initial_balance: str = "10000"
    ip_address: str = ""
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class PaperOrderDTO:
    id: UUID
    symbol: str
    side: str
    order_type: str
    volume: str
    status: str
    requested_price: str | None
    fill_price: str | None
    filled_volume: str
    stop_loss: str | None
    take_profit: str | None
    spread: str
    slippage: str
    commission: str
    rejection_reason: str
    position_id: UUID | None
    client_order_id: str
    submitted_at: datetime
    filled_at: datetime | None

    @classmethod
    def from_entity(cls, entity: PaperOrder) -> PaperOrderDTO:
        return cls(
            id=entity.id,
            symbol=entity.symbol,
            side=entity.side.value,
            order_type=entity.order_type.value,
            volume=str(entity.volume),
            status=entity.status.value,
            requested_price=(
                str(entity.requested_price)
                if entity.requested_price is not None
                else None
            ),
            fill_price=(
                str(entity.fill_price) if entity.fill_price is not None else None
            ),
            filled_volume=str(entity.filled_volume),
            stop_loss=(str(entity.stop_loss) if entity.stop_loss is not None else None),
            take_profit=(
                str(entity.take_profit) if entity.take_profit is not None else None
            ),
            spread=str(entity.spread),
            slippage=str(entity.slippage),
            commission=str(entity.commission),
            rejection_reason=entity.rejection_reason,
            position_id=entity.position_id,
            client_order_id=entity.client_order_id,
            submitted_at=entity.submitted_at,
            filled_at=entity.filled_at,
        )


@dataclass(frozen=True, slots=True)
class PaperPositionDTO:
    id: UUID
    symbol: str
    side: str
    status: str
    volume: str
    remaining_volume: str
    entry_price: str
    current_price: str
    stop_loss: str | None
    take_profit: str | None
    floating_pnl: str
    realized_pnl: str
    commission: str
    opened_at: datetime
    closed_at: datetime | None

    @classmethod
    def from_entity(cls, entity: PaperPosition) -> PaperPositionDTO:
        return cls(
            id=entity.id,
            symbol=entity.symbol,
            side=entity.side.value,
            status=entity.status.value,
            volume=str(entity.volume),
            remaining_volume=str(entity.remaining_volume),
            entry_price=str(entity.entry_price),
            current_price=str(entity.current_price),
            stop_loss=(str(entity.stop_loss) if entity.stop_loss is not None else None),
            take_profit=(
                str(entity.take_profit) if entity.take_profit is not None else None
            ),
            floating_pnl=str(entity.floating_pnl),
            realized_pnl=str(entity.realized_pnl),
            commission=str(entity.commission),
            opened_at=entity.opened_at,
            closed_at=entity.closed_at,
        )


@dataclass(frozen=True, slots=True)
class PaperTradeDTO:
    id: UUID
    symbol: str
    side: str
    volume: str
    entry_price: str
    exit_price: str
    pnl: str
    commission: str
    spread: str
    slippage: str
    opened_at: datetime
    closed_at: datetime

    @classmethod
    def from_entity(cls, entity: PaperTrade) -> PaperTradeDTO:
        return cls(
            id=entity.id,
            symbol=entity.symbol,
            side=entity.side.value,
            volume=str(entity.volume),
            entry_price=str(entity.entry_price),
            exit_price=str(entity.exit_price),
            pnl=str(entity.pnl),
            commission=str(entity.commission),
            spread=str(entity.spread),
            slippage=str(entity.slippage),
            opened_at=entity.opened_at,
            closed_at=entity.closed_at,
        )


@dataclass(frozen=True, slots=True)
class PlacePaperOrderDTO:
    order: PaperOrderDTO
    position: PaperPositionDTO | None
    trade: PaperTradeDTO | None
    portfolio: dict[str, object]
    quote: dict[str, object]


@dataclass(frozen=True, slots=True)
class ListPaperPositionsCommand:
    user_id: UUID
    limit: int = 50


@dataclass(frozen=True, slots=True)
class PaperPositionListDTO:
    items: list[PaperPositionDTO] = field(default_factory=list)
    count: int = 0
    portfolio: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PaperHistoryCommand:
    user_id: UUID
    limit: int = 50


@dataclass(frozen=True, slots=True)
class PaperHistoryDTO:
    orders: list[PaperOrderDTO] = field(default_factory=list)
    trades: list[PaperTradeDTO] = field(default_factory=list)
    positions: list[PaperPositionDTO] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class PaperPerformanceCommand:
    user_id: UUID


@dataclass(frozen=True, slots=True)
class PaperPerformanceDTO:
    performance: dict[str, object]
    portfolio: dict[str, object]

    @classmethod
    def from_entities(
        cls, perf: PaperPerformance, portfolio: PaperPortfolio
    ) -> PaperPerformanceDTO:
        return cls(performance=perf.to_dict(), portfolio=portfolio.to_dict())
