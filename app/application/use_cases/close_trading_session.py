"""CloseTradingSessionUseCase — gracefully end an open session.

Why this use case exists
------------------------
Sessions must be closed deliberately (logout, timeout hand-off). This use
case loads the session, applies the domain close transition, and persists
the terminal state.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.dto.trading_session import (
    CloseTradingSessionCommand,
    TradingSessionDTO,
)
from app.domain.exceptions.base import NotFoundError
from app.domain.interfaces.unit_of_work import UnitOfWorkFactory


@dataclass(frozen=True, slots=True)
class CloseTradingSessionUseCase:
    """Close an existing trading session."""

    uow_factory: UnitOfWorkFactory

    async def execute(self, command: CloseTradingSessionCommand) -> TradingSessionDTO:
        """Close the session if it exists and is still open."""
        async with self.uow_factory() as uow:
            session = await uow.trading_sessions.get_by_id(command.session_id)
            if session is None:
                raise NotFoundError(
                    "Trading session not found",
                    details={"session_id": str(command.session_id)},
                )

            session.close(reason=command.reason)
            await uow.trading_sessions.update(session)
            await uow.commit()
            return TradingSessionDTO.from_entity(session)
