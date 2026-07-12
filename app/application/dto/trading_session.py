"""Trading session application DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.entities.trading_session import TradingSession


@dataclass(frozen=True, slots=True)
class OpenTradingSessionCommand:
    """Input for OpenTradingSessionUseCase."""

    trading_account_id: UUID
    user_id: UUID
    client_label: str = ""


@dataclass(frozen=True, slots=True)
class CloseTradingSessionCommand:
    """Input for CloseTradingSessionUseCase."""

    session_id: UUID
    reason: str = ""


@dataclass(frozen=True, slots=True)
class TradingSessionDTO:
    """Trading session representation for the presentation layer."""

    id: UUID
    trading_account_id: UUID
    user_id: UUID
    status: str
    started_at: str | None
    ended_at: str | None
    client_label: str
    termination_reason: str

    @classmethod
    def from_entity(cls, session: TradingSession) -> TradingSessionDTO:
        return cls(
            id=session.id,
            trading_account_id=session.trading_account_id,
            user_id=session.user_id,
            status=session.status.value,
            started_at=session.started_at.isoformat() if session.started_at else None,
            ended_at=session.ended_at.isoformat() if session.ended_at else None,
            client_label=session.client_label,
            termination_reason=session.termination_reason,
        )
