"""Signal aggregate — market direction suggestion metadata.

Why this entity exists
----------------------
A Signal is a time-bounded suggestion (direction, confidence, source) that
may later be consumed by application workflows. This entity stores and
validates signal *records*. It does **not** generate signals, run AI, or
implement strategy logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Self
from uuid import UUID

from app.domain.entities._guards import require, require_state
from app.domain.entities.base import Entity
from app.domain.enums.signal import SignalDirection, SignalSource, SignalStatus
from app.domain.value_objects.confidence import Confidence
from app.domain.value_objects.market import Price


@dataclass(eq=False, kw_only=True)
class Signal(Entity):
    """Rich domain model for a trading signal record."""

    symbol_id: UUID
    direction: SignalDirection
    source: SignalSource = SignalSource.MANUAL
    status: SignalStatus = SignalStatus.PENDING
    confidence: Confidence | None = None
    entry_price: Price | None = None
    stop_loss: Price | None = None
    take_profit: Price | None = None
    strategy_metadata_id: UUID | None = None
    trading_account_id: UUID | None = None
    generated_at: datetime | None = None
    expires_at: datetime | None = None
    consumed_at: datetime | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if self.generated_at is None:
            self.generated_at = self.created_at
        self._validate_invariants()

    def _validate_invariants(self) -> None:
        if self.expires_at is not None and self.generated_at is not None:
            require(
                self.expires_at > self.generated_at,
                "expires_at must be after generated_at",
            )
        if self.status == SignalStatus.CONSUMED:
            require(
                self.consumed_at is not None,
                "Consumed signals must record consumed_at",
            )

    @classmethod
    def create(
        cls,
        *,
        symbol_id: UUID,
        direction: SignalDirection,
        source: SignalSource = SignalSource.MANUAL,
        confidence: Confidence | str | None = None,
        entry_price: Price | str | None = None,
        stop_loss: Price | str | None = None,
        take_profit: Price | str | None = None,
        strategy_metadata_id: UUID | None = None,
        trading_account_id: UUID | None = None,
        generated_at: datetime | None = None,
        expires_at: datetime | None = None,
        notes: str = "",
        entity_id: UUID | None = None,
    ) -> Self:
        """Factory: create a PENDING signal record."""
        conf = None
        if confidence is not None:
            conf = (
                confidence
                if isinstance(confidence, Confidence)
                else Confidence.of(confidence)
            )
        entry = (
            None
            if entry_price is None
            else (
                entry_price if isinstance(entry_price, Price) else Price.of(entry_price)
            )
        )
        sl = (
            None
            if stop_loss is None
            else (stop_loss if isinstance(stop_loss, Price) else Price.of(stop_loss))
        )
        tp = (
            None
            if take_profit is None
            else (
                take_profit if isinstance(take_profit, Price) else Price.of(take_profit)
            )
        )
        now = generated_at or datetime.now(UTC)
        kwargs: dict[str, object] = {
            "symbol_id": symbol_id,
            "direction": direction,
            "source": source,
            "status": SignalStatus.PENDING,
            "confidence": conf,
            "entry_price": entry,
            "stop_loss": sl,
            "take_profit": tp,
            "strategy_metadata_id": strategy_metadata_id,
            "trading_account_id": trading_account_id,
            "generated_at": now,
            "expires_at": expires_at,
            "notes": notes.strip(),
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def activate(self) -> None:
        """Make the signal available for consumption."""
        require_state(
            self.status == SignalStatus.PENDING,
            "Only pending signals can be activated",
            status=self.status.value,
        )
        self.status = SignalStatus.ACTIVE
        self.touch()

    def consume(self) -> None:
        """Mark the signal as consumed by a downstream workflow."""
        require_state(
            self.status == SignalStatus.ACTIVE,
            "Only active signals can be consumed",
            status=self.status.value,
        )
        self.status = SignalStatus.CONSUMED
        self.consumed_at = datetime.now(UTC)
        self.touch()

    def cancel(self) -> None:
        """Cancel a non-terminal signal."""
        require_state(
            self.status in {SignalStatus.PENDING, SignalStatus.ACTIVE},
            "Signal cannot be cancelled in its current status",
            status=self.status.value,
        )
        self.status = SignalStatus.CANCELLED
        self.touch()

    def expire(self, *, at: datetime | None = None) -> None:
        """Expire the signal when its validity window has passed."""
        moment = at or datetime.now(UTC)
        require_state(
            self.status in {SignalStatus.PENDING, SignalStatus.ACTIVE},
            "Signal cannot expire in its current status",
            status=self.status.value,
        )
        require(
            self.expires_at is not None and moment >= self.expires_at,
            "Cannot expire before expires_at",
        )
        self.status = SignalStatus.EXPIRED
        self.touch()

    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        base.update(
            {
                "symbol_id": str(self.symbol_id),
                "direction": self.direction.value,
                "source": self.source.value,
                "status": self.status.value,
                "confidence": str(self.confidence) if self.confidence else None,
                "entry_price": str(self.entry_price) if self.entry_price else None,
                "stop_loss": str(self.stop_loss) if self.stop_loss else None,
                "take_profit": str(self.take_profit) if self.take_profit else None,
                "strategy_metadata_id": (
                    str(self.strategy_metadata_id)
                    if self.strategy_metadata_id
                    else None
                ),
                "trading_account_id": (
                    str(self.trading_account_id) if self.trading_account_id else None
                ),
                "generated_at": (
                    self.generated_at.isoformat() if self.generated_at else None
                ),
                "expires_at": self.expires_at.isoformat() if self.expires_at else None,
                "consumed_at": (
                    self.consumed_at.isoformat() if self.consumed_at else None
                ),
                "notes": self.notes,
            }
        )
        return base
