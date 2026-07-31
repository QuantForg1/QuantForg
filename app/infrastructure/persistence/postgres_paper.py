"""Postgres persistence for Paper Trading Engine."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text

from app.domain.entities.paper import (
    PaperOrder,
    PaperPortfolio,
    PaperPosition,
    PaperTrade,
)
from app.domain.enums.paper import (
    PaperOrderSide,
    PaperOrderStatus,
    PaperOrderType,
    PaperPositionStatus,
)
from app.infrastructure.persistence.postgres_common import (
    PostgresUnitOfWorkBase,
    as_json,
    json_dict,
    parse_datetime,
    parse_datetime_optional,
    parse_decimal,
    parse_decimal_optional,
    parse_uuid,
    parse_uuid_optional,
)
from core.database.session import DatabaseManager


def portfolio_from_dict(user_id: UUID, data: dict[str, object]) -> PaperPortfolio:
    """Helper for reconstructing portfolio from persisted snapshot."""
    return PaperPortfolio(
        user_id=user_id,
        initial_balance=Decimal(str(data.get("initial_balance", "10000"))),
        balance=Decimal(str(data.get("balance", "10000"))),
        equity=Decimal(str(data.get("equity", "10000"))),
        floating_pnl=Decimal(str(data.get("floating_pnl", "0"))),
        realized_pnl=Decimal(str(data.get("realized_pnl", "0"))),
        margin=Decimal(str(data.get("margin", "0"))),
        peak_equity=Decimal(str(data.get("peak_equity", data.get("equity", "10000")))),
        max_drawdown_pct=Decimal(str(data.get("max_drawdown_pct", "0"))),
    )


def _portfolio_from_row(row: Any) -> PaperPortfolio:
    return PaperPortfolio(
        user_id=parse_uuid(row["user_id"]),
        initial_balance=parse_decimal(row["initial_balance"]),
        balance=parse_decimal(row["balance"]),
        equity=parse_decimal(row["equity"]),
        floating_pnl=parse_decimal(row["floating_pnl"], "0"),
        realized_pnl=parse_decimal(row["realized_pnl"], "0"),
        margin=parse_decimal(row["margin"], "0"),
        peak_equity=parse_decimal(row["peak_equity"]),
        max_drawdown_pct=parse_decimal(row["max_drawdown_pct"], "0"),
    )


def _order_from_row(row: Any) -> PaperOrder:
    created = parse_datetime(row["created_at"])
    return PaperOrder(
        id=parse_uuid(row["id"]),
        user_id=parse_uuid(row["user_id"]),
        symbol=str(row["symbol"]),
        side=PaperOrderSide(str(row["side"])),
        order_type=PaperOrderType(str(row["order_type"])),
        volume=parse_decimal(row["volume"]),
        status=PaperOrderStatus(str(row["status"])),
        requested_price=parse_decimal_optional(row["requested_price"]),
        fill_price=parse_decimal_optional(row["fill_price"]),
        filled_volume=parse_decimal(row["filled_volume"], "0"),
        stop_loss=parse_decimal_optional(row["stop_loss"]),
        take_profit=parse_decimal_optional(row["take_profit"]),
        spread=parse_decimal(row["spread"], "0"),
        slippage=parse_decimal(row["slippage"], "0"),
        commission=parse_decimal(row["commission"], "0"),
        rejection_reason=str(row["rejection_reason"] or ""),
        position_id=parse_uuid_optional(row["position_id"]),
        client_order_id=str(row["client_order_id"] or ""),
        submitted_at=parse_datetime(row["submitted_at"]),
        filled_at=parse_datetime_optional(row["filled_at"]),
        created_at=created,
        updated_at=created,
    )


def _position_from_row(row: Any) -> PaperPosition:
    return PaperPosition(
        id=parse_uuid(row["id"]),
        user_id=parse_uuid(row["user_id"]),
        symbol=str(row["symbol"]),
        side=PaperOrderSide(str(row["side"])),
        status=PaperPositionStatus(str(row["status"])),
        volume=parse_decimal(row["volume"]),
        remaining_volume=parse_decimal(row["remaining_volume"]),
        entry_price=parse_decimal(row["entry_price"]),
        current_price=parse_decimal(row["current_price"]),
        stop_loss=parse_decimal_optional(row["stop_loss"]),
        take_profit=parse_decimal_optional(row["take_profit"]),
        floating_pnl=parse_decimal(row["floating_pnl"], "0"),
        realized_pnl=parse_decimal(row["realized_pnl"], "0"),
        commission=parse_decimal(row["commission"], "0"),
        order_id=parse_uuid_optional(row["order_id"]),
        opened_at=parse_datetime(row["opened_at"]),
        closed_at=parse_datetime_optional(row["closed_at"]),
        created_at=parse_datetime(row["created_at"]),
        updated_at=parse_datetime(row["updated_at"]),
    )


def _trade_from_row(row: Any) -> PaperTrade:
    created = parse_datetime(row["created_at"])
    return PaperTrade(
        id=parse_uuid(row["id"]),
        user_id=parse_uuid(row["user_id"]),
        symbol=str(row["symbol"]),
        side=PaperOrderSide(str(row["side"])),
        volume=parse_decimal(row["volume"]),
        entry_price=parse_decimal(row["entry_price"]),
        exit_price=parse_decimal(row["exit_price"]),
        pnl=parse_decimal(row["pnl"]),
        commission=parse_decimal(row["commission"], "0"),
        spread=parse_decimal(row["spread"], "0"),
        slippage=parse_decimal(row["slippage"], "0"),
        position_id=parse_uuid_optional(row["position_id"]),
        order_id=parse_uuid_optional(row["order_id"]),
        opened_at=parse_datetime(row["opened_at"]),
        closed_at=parse_datetime(row["closed_at"]),
        created_at=created,
        updated_at=created,
    )


class PostgresPaperPortfolioRepository:
    def __init__(self, uow: PostgresPaperUnitOfWork) -> None:
        self._uow = uow

    async def get(self, user_id: UUID) -> PaperPortfolio | None:
        session = self._uow._require_session()
        result = await session.execute(
            text("SELECT * FROM paper_portfolios WHERE user_id = :user_id"),
            {"user_id": str(user_id)},
        )
        row = result.mappings().first()
        return _portfolio_from_row(row) if row else None

    async def save(self, portfolio: PaperPortfolio) -> PaperPortfolio:
        session = self._uow._require_session()
        await session.execute(
            text("""
                INSERT INTO paper_portfolios (
                    id, user_id, initial_balance, balance, equity, floating_pnl,
                    realized_pnl, margin, peak_equity, max_drawdown_pct, snapshot
                ) VALUES (
                    :id, :user_id, :initial_balance, :balance, :equity,
                    :floating_pnl, :realized_pnl, :margin, :peak_equity,
                    :max_drawdown_pct, CAST(:snapshot AS jsonb)
                )
                ON CONFLICT (user_id) DO UPDATE SET
                    initial_balance = EXCLUDED.initial_balance,
                    balance = EXCLUDED.balance,
                    equity = EXCLUDED.equity,
                    floating_pnl = EXCLUDED.floating_pnl,
                    realized_pnl = EXCLUDED.realized_pnl,
                    margin = EXCLUDED.margin,
                    peak_equity = EXCLUDED.peak_equity,
                    max_drawdown_pct = EXCLUDED.max_drawdown_pct,
                    snapshot = EXCLUDED.snapshot,
                    updated_at = timezone('utc', now())
                """),
            {
                "id": str(uuid4()),
                "user_id": str(portfolio.user_id),
                "initial_balance": str(portfolio.initial_balance),
                "balance": str(portfolio.balance),
                "equity": str(portfolio.equity),
                "floating_pnl": str(portfolio.floating_pnl),
                "realized_pnl": str(portfolio.realized_pnl),
                "margin": str(portfolio.margin),
                "peak_equity": str(portfolio.peak_equity),
                "max_drawdown_pct": str(portfolio.max_drawdown_pct),
                "snapshot": as_json(portfolio.to_dict()),
            },
        )
        return portfolio


class PostgresPaperOrderRepository:
    def __init__(self, uow: PostgresPaperUnitOfWork) -> None:
        self._uow = uow

    async def add(self, order: PaperOrder) -> PaperOrder:
        session = self._uow._require_session()
        await session.execute(
            text("""
                INSERT INTO paper_orders (
                    id, user_id, symbol, side, order_type, volume, status,
                    requested_price, fill_price, filled_volume, stop_loss,
                    take_profit, spread, slippage, commission, rejection_reason,
                    position_id, client_order_id, submitted_at, filled_at, created_at
                ) VALUES (
                    :id, :user_id, :symbol, :side, :order_type, :volume, :status,
                    :requested_price, :fill_price, :filled_volume, :stop_loss,
                    :take_profit, :spread, :slippage, :commission, :rejection_reason,
                    :position_id, :client_order_id, :submitted_at, :filled_at,
                    :created_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    symbol = EXCLUDED.symbol,
                    side = EXCLUDED.side,
                    order_type = EXCLUDED.order_type,
                    volume = EXCLUDED.volume,
                    status = EXCLUDED.status,
                    requested_price = EXCLUDED.requested_price,
                    fill_price = EXCLUDED.fill_price,
                    filled_volume = EXCLUDED.filled_volume,
                    stop_loss = EXCLUDED.stop_loss,
                    take_profit = EXCLUDED.take_profit,
                    spread = EXCLUDED.spread,
                    slippage = EXCLUDED.slippage,
                    commission = EXCLUDED.commission,
                    rejection_reason = EXCLUDED.rejection_reason,
                    position_id = EXCLUDED.position_id,
                    client_order_id = EXCLUDED.client_order_id,
                    submitted_at = EXCLUDED.submitted_at,
                    filled_at = EXCLUDED.filled_at
                """),
            {
                "id": str(order.id),
                "user_id": str(order.user_id),
                "symbol": order.symbol,
                "side": order.side.value,
                "order_type": order.order_type.value,
                "volume": str(order.volume),
                "status": order.status.value,
                "requested_price": (
                    str(order.requested_price)
                    if order.requested_price is not None
                    else None
                ),
                "fill_price": (
                    str(order.fill_price) if order.fill_price is not None else None
                ),
                "filled_volume": str(order.filled_volume),
                "stop_loss": (
                    str(order.stop_loss) if order.stop_loss is not None else None
                ),
                "take_profit": (
                    str(order.take_profit) if order.take_profit is not None else None
                ),
                "spread": str(order.spread),
                "slippage": str(order.slippage),
                "commission": str(order.commission),
                "rejection_reason": order.rejection_reason,
                "position_id": str(order.position_id) if order.position_id else None,
                "client_order_id": order.client_order_id,
                "submitted_at": order.submitted_at,
                "filled_at": order.filled_at,
                "created_at": order.created_at,
            },
        )
        return order

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 100
    ) -> list[PaperOrder]:
        session = self._uow._require_session()
        result = await session.execute(
            text("""
                SELECT * FROM paper_orders
                WHERE user_id = :user_id
                ORDER BY submitted_at DESC
                LIMIT :limit
                """),
            {"user_id": str(user_id), "limit": limit},
        )
        return [_order_from_row(r) for r in result.mappings().all()]

    async def list_pending(self, user_id: UUID) -> list[PaperOrder]:
        session = self._uow._require_session()
        result = await session.execute(
            text("""
                SELECT * FROM paper_orders
                WHERE user_id = :user_id AND status = :status
                ORDER BY submitted_at ASC
                """),
            {
                "user_id": str(user_id),
                "status": PaperOrderStatus.ACCEPTED.value,
            },
        )
        return [_order_from_row(r) for r in result.mappings().all()]


class PostgresPaperPositionRepository:
    def __init__(self, uow: PostgresPaperUnitOfWork) -> None:
        self._uow = uow

    async def add(self, position: PaperPosition) -> PaperPosition:
        return await self.save(position)

    async def save(self, position: PaperPosition) -> PaperPosition:
        session = self._uow._require_session()
        await session.execute(
            text("""
                INSERT INTO paper_positions (
                    id, user_id, symbol, side, status, volume, remaining_volume,
                    entry_price, current_price, stop_loss, take_profit,
                    floating_pnl, realized_pnl, commission, order_id,
                    opened_at, closed_at, created_at, updated_at
                ) VALUES (
                    :id, :user_id, :symbol, :side, :status, :volume,
                    :remaining_volume, :entry_price, :current_price, :stop_loss,
                    :take_profit, :floating_pnl, :realized_pnl, :commission,
                    :order_id, :opened_at, :closed_at, :created_at, :updated_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    symbol = EXCLUDED.symbol,
                    side = EXCLUDED.side,
                    status = EXCLUDED.status,
                    volume = EXCLUDED.volume,
                    remaining_volume = EXCLUDED.remaining_volume,
                    entry_price = EXCLUDED.entry_price,
                    current_price = EXCLUDED.current_price,
                    stop_loss = EXCLUDED.stop_loss,
                    take_profit = EXCLUDED.take_profit,
                    floating_pnl = EXCLUDED.floating_pnl,
                    realized_pnl = EXCLUDED.realized_pnl,
                    commission = EXCLUDED.commission,
                    order_id = EXCLUDED.order_id,
                    opened_at = EXCLUDED.opened_at,
                    closed_at = EXCLUDED.closed_at,
                    updated_at = EXCLUDED.updated_at
                """),
            {
                "id": str(position.id),
                "user_id": str(position.user_id),
                "symbol": position.symbol,
                "side": position.side.value,
                "status": position.status.value,
                "volume": str(position.volume),
                "remaining_volume": str(position.remaining_volume),
                "entry_price": str(position.entry_price),
                "current_price": str(position.current_price),
                "stop_loss": (
                    str(position.stop_loss) if position.stop_loss is not None else None
                ),
                "take_profit": (
                    str(position.take_profit)
                    if position.take_profit is not None
                    else None
                ),
                "floating_pnl": str(position.floating_pnl),
                "realized_pnl": str(position.realized_pnl),
                "commission": str(position.commission),
                "order_id": str(position.order_id) if position.order_id else None,
                "opened_at": position.opened_at,
                "closed_at": position.closed_at,
                "created_at": position.created_at,
                "updated_at": position.updated_at,
            },
        )
        return position

    async def get(self, position_id: UUID) -> PaperPosition | None:
        session = self._uow._require_session()
        result = await session.execute(
            text("SELECT * FROM paper_positions WHERE id = :id"),
            {"id": str(position_id)},
        )
        row = result.mappings().first()
        return _position_from_row(row) if row else None

    async def list_open(self, user_id: UUID) -> list[PaperPosition]:
        session = self._uow._require_session()
        result = await session.execute(
            text("""
                SELECT * FROM paper_positions
                WHERE user_id = :user_id
                  AND status IN ('opened', 'partially_closed')
                ORDER BY opened_at DESC
                """),
            {"user_id": str(user_id)},
        )
        return [_position_from_row(r) for r in result.mappings().all()]

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 100
    ) -> list[PaperPosition]:
        session = self._uow._require_session()
        result = await session.execute(
            text("""
                SELECT * FROM paper_positions
                WHERE user_id = :user_id
                ORDER BY opened_at DESC
                LIMIT :limit
                """),
            {"user_id": str(user_id), "limit": limit},
        )
        return [_position_from_row(r) for r in result.mappings().all()]


class PostgresPaperTradeRepository:
    def __init__(self, uow: PostgresPaperUnitOfWork) -> None:
        self._uow = uow

    async def add(self, trade: PaperTrade) -> PaperTrade:
        session = self._uow._require_session()
        await session.execute(
            text("""
                INSERT INTO paper_trades (
                    id, user_id, symbol, side, volume, entry_price, exit_price,
                    pnl, commission, spread, slippage, position_id, order_id,
                    opened_at, closed_at, created_at
                ) VALUES (
                    :id, :user_id, :symbol, :side, :volume, :entry_price,
                    :exit_price, :pnl, :commission, :spread, :slippage,
                    :position_id, :order_id, :opened_at, :closed_at, :created_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    symbol = EXCLUDED.symbol,
                    side = EXCLUDED.side,
                    volume = EXCLUDED.volume,
                    entry_price = EXCLUDED.entry_price,
                    exit_price = EXCLUDED.exit_price,
                    pnl = EXCLUDED.pnl,
                    commission = EXCLUDED.commission,
                    spread = EXCLUDED.spread,
                    slippage = EXCLUDED.slippage,
                    position_id = EXCLUDED.position_id,
                    order_id = EXCLUDED.order_id,
                    opened_at = EXCLUDED.opened_at,
                    closed_at = EXCLUDED.closed_at
                """),
            {
                "id": str(trade.id),
                "user_id": str(trade.user_id),
                "symbol": trade.symbol,
                "side": trade.side.value,
                "volume": str(trade.volume),
                "entry_price": str(trade.entry_price),
                "exit_price": str(trade.exit_price),
                "pnl": str(trade.pnl),
                "commission": str(trade.commission),
                "spread": str(trade.spread),
                "slippage": str(trade.slippage),
                "position_id": str(trade.position_id) if trade.position_id else None,
                "order_id": str(trade.order_id) if trade.order_id else None,
                "opened_at": trade.opened_at,
                "closed_at": trade.closed_at,
                "created_at": trade.created_at,
            },
        )
        return trade

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 100
    ) -> list[PaperTrade]:
        session = self._uow._require_session()
        result = await session.execute(
            text("""
                SELECT * FROM paper_trades
                WHERE user_id = :user_id
                ORDER BY closed_at DESC
                LIMIT :limit
                """),
            {"user_id": str(user_id), "limit": limit},
        )
        return [_trade_from_row(r) for r in result.mappings().all()]


class PostgresPaperPerformanceRepository:
    def __init__(self, uow: PostgresPaperUnitOfWork) -> None:
        self._uow = uow

    async def save(self, user_id: UUID, payload: dict[str, object]) -> None:
        session = self._uow._require_session()
        await session.execute(
            text("""
                INSERT INTO paper_performance (id, user_id, payload)
                VALUES (:id, :user_id, CAST(:payload AS jsonb))
                ON CONFLICT (user_id) DO UPDATE SET
                    payload = EXCLUDED.payload,
                    recorded_at = timezone('utc', now()),
                    updated_at = timezone('utc', now())
                """),
            {
                "id": str(uuid4()),
                "user_id": str(user_id),
                "payload": as_json(payload),
            },
        )

    async def get(self, user_id: UUID) -> dict[str, object] | None:
        session = self._uow._require_session()
        result = await session.execute(
            text("SELECT payload FROM paper_performance WHERE user_id = :user_id"),
            {"user_id": str(user_id)},
        )
        row = result.mappings().first()
        if row is None:
            return None
        return json_dict(row["payload"])


class PostgresPaperUnitOfWork(PostgresUnitOfWorkBase):
    def __init__(self, database: DatabaseManager) -> None:
        super().__init__(database)
        self.portfolios = PostgresPaperPortfolioRepository(self)
        self.orders = PostgresPaperOrderRepository(self)
        self.positions = PostgresPaperPositionRepository(self)
        self.trades = PostgresPaperTradeRepository(self)
        self.performance = PostgresPaperPerformanceRepository(self)


class PostgresPaperUnitOfWorkFactory:
    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    def __call__(self) -> PostgresPaperUnitOfWork:
        return PostgresPaperUnitOfWork(self._database)
