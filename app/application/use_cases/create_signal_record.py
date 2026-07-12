"""CreateSignalRecordUseCase — persist a signal metadata record.

Why this use case exists
------------------------
Signals are stored as domain records (direction, confidence, expiry) for
later consumption. This use case validates the symbol exists and is
tradable, then creates the Signal aggregate. It does **not** generate
signals, run AI, or execute strategies.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.dto.signal import CreateSignalRecordCommand, SignalDTO
from app.domain.entities.signal import Signal
from app.domain.exceptions.base import NotFoundError, ValidationError
from app.domain.interfaces.unit_of_work import UnitOfWorkFactory


@dataclass(frozen=True, slots=True)
class CreateSignalRecordUseCase:
    """Create and optionally activate a signal record."""

    uow_factory: UnitOfWorkFactory

    async def execute(self, command: CreateSignalRecordCommand) -> SignalDTO:
        """Persist a new signal record against a known symbol."""
        async with self.uow_factory() as uow:
            symbol = await uow.symbols.get_by_id(command.symbol_id)
            if symbol is None:
                raise NotFoundError(
                    "Symbol not found",
                    details={"symbol_id": str(command.symbol_id)},
                )
            if not symbol.is_tradable:
                raise ValidationError(
                    "Symbol is not tradable",
                    details={
                        "symbol_id": str(symbol.id),
                        "status": symbol.status.value,
                    },
                )

            if command.trading_account_id is not None:
                account = await uow.trading_accounts.get_by_id(
                    command.trading_account_id
                )
                if account is None:
                    raise NotFoundError(
                        "Trading account not found",
                        details={
                            "trading_account_id": str(command.trading_account_id),
                        },
                    )

            signal = Signal.create(
                symbol_id=command.symbol_id,
                direction=command.direction,
                source=command.source,
                confidence=command.confidence,
                entry_price=command.entry_price,
                stop_loss=command.stop_loss,
                take_profit=command.take_profit,
                strategy_metadata_id=command.strategy_metadata_id,
                trading_account_id=command.trading_account_id,
                expires_at=command.expires_at,
                notes=command.notes,
            )
            if command.activate:
                signal.activate()

            await uow.signals.add(signal)
            await uow.commit()
            return SignalDTO.from_entity(signal)
