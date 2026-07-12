"""Position aggregate — open market exposure on a symbol.

Why this entity exists
----------------------
A Position represents current exposure (side, quantity, open price, protective
stops). Lifecycle methods open/close/reduce quantity. It does **not**
calculate P&L, margin, or run liquidation logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Self
from uuid import UUID

from app.domain.entities._guards import require, require_state
from app.domain.entities.base import Entity
from app.domain.enums.position import PositionSide, PositionStatus
from app.domain.value_objects.market import Price, Quantity


@dataclass(eq=False, kw_only=True)
class Position(Entity):
    """Rich domain model for a trading position."""

    trading_account_id: UUID
    symbol_id: UUID
    side: PositionSide
    quantity: Quantity
    open_price: Price
    status: PositionStatus = PositionStatus.OPEN
    stop_loss: Price | None = None
    take_profit: Price | None = None
    opened_at: datetime | None = None
    closed_at: datetime | None = None
    close_price: Price | None = None
    opening_order_id: UUID | None = None

    def __post_init__(self) -> None:
        if self.opened_at is None:
            self.opened_at = self.created_at
        self._validate_invariants()

    def _validate_invariants(self) -> None:
        require(isinstance(self.quantity, Quantity), "quantity must be a Quantity")
        require(isinstance(self.open_price, Price), "open_price must be a Price")
        if self.status == PositionStatus.CLOSED:
            require(
                self.closed_at is not None, "Closed positions must record closed_at"
            )
            require(
                self.close_price is not None, "Closed positions must record close_price"
            )

    @classmethod
    def open(
        cls,
        *,
        trading_account_id: UUID,
        symbol_id: UUID,
        side: PositionSide,
        quantity: Quantity | str | int,
        open_price: Price | str,
        stop_loss: Price | str | None = None,
        take_profit: Price | str | None = None,
        opening_order_id: UUID | None = None,
        opened_at: datetime | None = None,
        entity_id: UUID | None = None,
    ) -> Self:
        """Factory: open a new position."""
        qty = quantity if isinstance(quantity, Quantity) else Quantity.of(quantity)
        price = open_price if isinstance(open_price, Price) else Price.of(open_price)
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
        kwargs: dict[str, object] = {
            "trading_account_id": trading_account_id,
            "symbol_id": symbol_id,
            "side": side,
            "quantity": qty,
            "open_price": price,
            "status": PositionStatus.OPEN,
            "stop_loss": sl,
            "take_profit": tp,
            "opened_at": opened_at or datetime.now(UTC),
            "opening_order_id": opening_order_id,
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def update_protective_orders(
        self,
        *,
        stop_loss: Price | str | None = None,
        take_profit: Price | str | None = None,
    ) -> None:
        """Update stop-loss / take-profit levels on an open position."""
        require_state(
            self.status in {PositionStatus.OPEN, PositionStatus.PARTIALLY_CLOSED},
            "Cannot update protective orders on a closed position",
            status=self.status.value,
        )
        if stop_loss is not None:
            self.stop_loss = (
                stop_loss if isinstance(stop_loss, Price) else Price.of(stop_loss)
            )
        if take_profit is not None:
            self.take_profit = (
                take_profit if isinstance(take_profit, Price) else Price.of(take_profit)
            )
        self.touch()

    def reduce(
        self,
        *,
        quantity: Quantity | str | int,
        close_price: Price | str,
    ) -> None:
        """Partially reduce position quantity."""
        require_state(
            self.status in {PositionStatus.OPEN, PositionStatus.PARTIALLY_CLOSED},
            "Cannot reduce a closed position",
            status=self.status.value,
        )
        qty = quantity if isinstance(quantity, Quantity) else Quantity.of(quantity)
        price = close_price if isinstance(close_price, Price) else Price.of(close_price)
        require(
            qty.value < self.quantity.value,
            "Partial reduce quantity must be less than position quantity; "
            "use close() for a full close",
            reduce=str(qty.value),
            position=str(self.quantity.value),
        )
        remaining = self.quantity.value - qty.value
        self.quantity = Quantity(value=remaining)
        self.close_price = price
        self.status = PositionStatus.PARTIALLY_CLOSED
        self.touch()
        self._validate_invariants()

    def close(self, *, close_price: Price | str) -> None:
        """Fully close the position."""
        require_state(
            self.status in {PositionStatus.OPEN, PositionStatus.PARTIALLY_CLOSED},
            "Position is already closed",
            status=self.status.value,
        )
        self.close_price = (
            close_price if isinstance(close_price, Price) else Price.of(close_price)
        )
        self.status = PositionStatus.CLOSED
        self.closed_at = datetime.now(UTC)
        self.touch()
        self._validate_invariants()

    @property
    def is_open(self) -> bool:
        return self.status != PositionStatus.CLOSED

    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        base.update(
            {
                "trading_account_id": str(self.trading_account_id),
                "symbol_id": str(self.symbol_id),
                "side": self.side.value,
                "quantity": str(self.quantity),
                "open_price": str(self.open_price),
                "status": self.status.value,
                "stop_loss": str(self.stop_loss) if self.stop_loss else None,
                "take_profit": str(self.take_profit) if self.take_profit else None,
                "opened_at": self.opened_at.isoformat() if self.opened_at else None,
                "closed_at": self.closed_at.isoformat() if self.closed_at else None,
                "close_price": str(self.close_price) if self.close_price else None,
                "opening_order_id": (
                    str(self.opening_order_id) if self.opening_order_id else None
                ),
            }
        )
        return base
