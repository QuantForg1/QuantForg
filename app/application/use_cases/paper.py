"""Paper Trading use cases — live quotes, simulated fills. Never order_send."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.application.dto.audit import RecordAuditEventCommand
from app.application.dto.paper import (
    ListPaperPositionsCommand,
    PaperHistoryCommand,
    PaperHistoryDTO,
    PaperOrderDTO,
    PaperPerformanceCommand,
    PaperPerformanceDTO,
    PaperPositionDTO,
    PaperPositionListDTO,
    PaperTradeDTO,
    PlacePaperOrderCommand,
    PlacePaperOrderDTO,
)
from app.application.services.paper_trading import (
    PaperTradingEngine,
    PlacePaperOrderInput,
)
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.enums.audit import AuditAction, AuditOutcome
from app.domain.enums.paper import PaperOrderStatus, PaperPositionStatus
from app.domain.exceptions.base import ValidationError
from app.domain.interfaces.mt5_client import MT5LoginRequest
from app.infrastructure.brokers.mt5 import MT5Adapter


@dataclass(frozen=True, slots=True)
class PlacePaperOrderUseCase:
    paper_uow_factory: Any
    mt5_uow_factory: Any
    engine: PaperTradingEngine
    mt5_adapter: MT5Adapter | None
    audit: RecordAuditEventUseCase

    async def execute(self, command: PlacePaperOrderCommand) -> PlacePaperOrderDTO:
        try:
            side = command.side.strip().lower()
            if side not in {"buy", "sell"}:
                raise ValueError("side must be buy or sell")
            order_type = command.order_type.strip().lower()
            if order_type not in {"market", "limit", "stop"}:
                raise ValueError("order_type must be market, limit, or stop")
            volume = Decimal(command.volume)
            price = Decimal(command.price) if command.price else None
            sl = Decimal(command.stop_loss) if command.stop_loss else None
            tp = Decimal(command.take_profit) if command.take_profit else None
            initial = Decimal(command.initial_balance)
        except (ValueError, ArithmeticError) as exc:
            raise ValidationError(
                "Invalid paper order input",
                details={"error": str(exc)},
            ) from exc

        await self._ensure_mt5_connected(command.user_id)

        async with self.paper_uow_factory() as uow:
            portfolio = await uow.portfolios.get(command.user_id)
            positions = await uow.positions.list_open(command.user_id)
            pending = await uow.orders.list_pending(command.user_id)

            result = self.engine.place_order(
                PlacePaperOrderInput(
                    user_id=command.user_id,
                    symbol=command.symbol,
                    side=side,
                    order_type=order_type,
                    volume=volume,
                    price=price,
                    stop_loss=sl,
                    take_profit=tp,
                    client_order_id=command.client_order_id,
                    reduce_position_id=command.reduce_position_id,
                    initial_balance=initial,
                ),
                portfolio=portfolio,
                positions=positions,
                pending_orders=pending,
            )
            _ = self.engine.drain_events()

            await uow.portfolios.save(result.portfolio)
            await uow.orders.add(result.order)
            if result.position is not None:
                existing = await uow.positions.get(result.position.id)
                if existing is None:
                    await uow.positions.add(result.position)
                else:
                    await uow.positions.save(result.position)
            if result.trade is not None:
                await uow.trades.add(result.trade)
            # Persist performance snapshot
            trades = await uow.trades.list_for_user(command.user_id, limit=500)
            perf = self.engine.compute_performance(
                portfolio=result.portfolio, trades=trades
            )
            await uow.performance.save(command.user_id, perf.to_dict())
            await uow.commit()

        outcome = (
            AuditOutcome.SUCCESS
            if result.order.status
            in {
                PaperOrderStatus.FILLED,
                PaperOrderStatus.ACCEPTED,
                PaperOrderStatus.PARTIALLY_FILLED,
            }
            else AuditOutcome.DENIED
        )
        await self.audit.execute(
            RecordAuditEventCommand(
                actor_user_id=command.user_id,
                action=AuditAction.SUBMIT,
                outcome=outcome,
                resource_type="paper_order",
                resource_id=result.order.id,
                ip_address=command.ip_address,
                user_agent=command.user_agent,
                metadata={
                    "status": result.order.status.value,
                    "symbol": result.order.symbol,
                    "side": result.order.side.value,
                },
            )
        )
        return PlacePaperOrderDTO(
            order=PaperOrderDTO.from_entity(result.order),
            position=(
                PaperPositionDTO.from_entity(result.position)
                if result.position
                else None
            ),
            trade=(PaperTradeDTO.from_entity(result.trade) if result.trade else None),
            portfolio=result.portfolio.to_dict(),
            quote=result.quote.to_dict(),
        )

    async def _ensure_mt5_connected(self, user_id: UUID) -> None:
        """Ensure Mock MT5 client is connected for live quote reads."""
        _ = user_id
        _ = self.mt5_uow_factory
        await _ensure_connected(self.mt5_adapter)


@dataclass(frozen=True, slots=True)
class ListPaperPositionsUseCase:
    paper_uow_factory: Any
    engine: PaperTradingEngine
    mt5_adapter: MT5Adapter | None

    async def execute(self, command: ListPaperPositionsCommand) -> PaperPositionListDTO:
        await _ensure_connected(self.mt5_adapter)
        async with self.paper_uow_factory() as uow:
            portfolio = await uow.portfolios.get(command.user_id)
            if portfolio is None:
                return PaperPositionListDTO(items=[], count=0, portfolio={})
            positions = await uow.positions.list_open(command.user_id)
            positions, portfolio, _quote = self.engine.refresh_positions(
                user_id=command.user_id,
                positions=positions,
                portfolio=portfolio,
            )
            for pos in positions:
                await uow.positions.save(pos)
            await uow.portfolios.save(portfolio)
            await uow.commit()
        items = [
            PaperPositionDTO.from_entity(p)
            for p in positions
            if p.status
            in {PaperPositionStatus.OPENED, PaperPositionStatus.PARTIALLY_CLOSED}
        ][: command.limit]
        return PaperPositionListDTO(
            items=items, count=len(items), portfolio=portfolio.to_dict()
        )


@dataclass(frozen=True, slots=True)
class GetPaperHistoryUseCase:
    paper_uow_factory: Any

    async def execute(self, command: PaperHistoryCommand) -> PaperHistoryDTO:
        limit = max(1, min(command.limit, 200))
        async with self.paper_uow_factory() as uow:
            orders = await uow.orders.list_for_user(command.user_id, limit=limit)
            trades = await uow.trades.list_for_user(command.user_id, limit=limit)
            positions = await uow.positions.list_for_user(command.user_id, limit=limit)
        return PaperHistoryDTO(
            orders=[PaperOrderDTO.from_entity(o) for o in orders],
            trades=[PaperTradeDTO.from_entity(t) for t in trades],
            positions=[PaperPositionDTO.from_entity(p) for p in positions],
        )


@dataclass(frozen=True, slots=True)
class GetPaperPerformanceUseCase:
    paper_uow_factory: Any
    engine: PaperTradingEngine
    mt5_adapter: MT5Adapter | None

    async def execute(self, command: PaperPerformanceCommand) -> PaperPerformanceDTO:
        await _ensure_connected(self.mt5_adapter)
        async with self.paper_uow_factory() as uow:
            portfolio = await uow.portfolios.get(command.user_id)
            if portfolio is None:
                from app.domain.entities.paper import PaperPortfolio

                portfolio = PaperPortfolio.create(
                    user_id=command.user_id, initial_balance=Decimal("10000")
                )
                await uow.portfolios.save(portfolio)
            positions = await uow.positions.list_open(command.user_id)
            positions, portfolio, _ = self.engine.refresh_positions(
                user_id=command.user_id,
                positions=positions,
                portfolio=portfolio,
            )
            for pos in positions:
                await uow.positions.save(pos)
            trades = await uow.trades.list_for_user(command.user_id, limit=500)
            perf = self.engine.compute_performance(portfolio=portfolio, trades=trades)
            await uow.portfolios.save(portfolio)
            await uow.performance.save(command.user_id, perf.to_dict())
            await uow.commit()
        return PaperPerformanceDTO.from_entities(perf, portfolio)


async def _ensure_connected(adapter: MT5Adapter | None) -> None:
    if adapter is None:
        return
    try:
        if adapter.client.is_connected:
            return
        # Mock-only paper credentials (never a live broker secret)
        mock_password = "paper"  # noqa: S105
        adapter.login(MT5LoginRequest(login=1, password=mock_password, server="Paper"))
    except (OSError, RuntimeError, AttributeError, ValueError, TypeError):
        pass
