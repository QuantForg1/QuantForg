"""Signal application DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.entities.signal import Signal
from app.domain.enums.signal import SignalDirection, SignalSource


@dataclass(frozen=True, slots=True)
class CreateSignalRecordCommand:
    """Input for CreateSignalRecordUseCase.

    Creates a signal *record* only — does not generate or evaluate signals.
    """

    symbol_id: UUID
    direction: SignalDirection
    source: SignalSource = SignalSource.MANUAL
    confidence: str | None = None
    entry_price: str | None = None
    stop_loss: str | None = None
    take_profit: str | None = None
    strategy_metadata_id: UUID | None = None
    trading_account_id: UUID | None = None
    expires_at: datetime | None = None
    notes: str = ""
    activate: bool = True


@dataclass(frozen=True, slots=True)
class SignalDTO:
    """Signal record representation for the presentation layer."""

    id: UUID
    symbol_id: UUID
    direction: str
    source: str
    status: str
    confidence: str | None
    entry_price: str | None
    expires_at: str | None
    notes: str

    @classmethod
    def from_entity(cls, signal: Signal) -> SignalDTO:
        return cls(
            id=signal.id,
            symbol_id=signal.symbol_id,
            direction=signal.direction.value,
            source=signal.source.value,
            status=signal.status.value,
            confidence=str(signal.confidence) if signal.confidence else None,
            entry_price=str(signal.entry_price) if signal.entry_price else None,
            expires_at=signal.expires_at.isoformat() if signal.expires_at else None,
            notes=signal.notes,
        )
