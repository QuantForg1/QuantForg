"""Order aggregate — intent to buy or sell a quantity of a symbol.

Why this entity exists
----------------------
An Order captures the *intent* and lifecycle of a trade instruction
(type, side, quantity, limits, status). State transitions enforce business
invariants. This is **not** an order-matching engine and contains no
broker routing or MetaTrader submission logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Self
from uuid import UUID

from app.domain.entities._guards import require, require_state
from app.domain.entities.base import Entity
from app.domain.enums.order import OrderSide, OrderStatus, OrderType, TimeInForce
from app.domain.value_objects.market import Price, Quantity

_TERMINAL_STATUSES = frozenset(
    {
        OrderStatus.FILLED,
        OrderStatus.CANCELLED,
        OrderStatus.REJECTED,
        OrderStatus.EXPIRED,
    }
)

_ALLOWED_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.PENDING: frozenset(
        {
            OrderStatus.ACCEPTED,
            OrderStatus.REJECTED,
            OrderStatus.CANCELLED,
            OrderStatus.EXPIRED,
        }
    ),
    OrderStatus.ACCEPTED: frozenset(
        {
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.EXPIRED,
            OrderStatus.REJECTED,
        }
    ),
    OrderStatus.PARTIALLY_FILLED: frozenset(
        {
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.EXPIRED,
        }
    ),
}


@dataclass(eq=False, kw_only=True)
class Order(Entity):
    """Rich domain model for an order."""

    trading_account_id: UUID
    symbol_id: UUID
    order_type: OrderType
    side: OrderSide
    quantity: Quantity
    status: OrderStatus = OrderStatus.PENDING
    time_in_force: TimeInForce = TimeInForce.GTC
    limit_price: Price | None = None
    stop_price: Price | None = None
    stop_loss: Price | None = None
    take_profit: Price | None = None
    filled_quantity: Quantity | None = None
    average_fill_price: Price | None = None
    submitted_at: datetime | None = None
    closed_at: datetime | None = None
    client_order_id: str = ""
    rejection_reason: str = ""

    def __post_init__(self) -> None:
        self._validate_invariants()

    def _validate_invariants(self) -> None:
        require(isinstance(self.quantity, Quantity), "quantity must be a Quantity")
        if self.order_type in {OrderType.LIMIT, OrderType.STOP_LIMIT}:
            require(
                self.limit_price is not None,
                f"{self.order_type.value} orders require limit_price",
            )
        if self.order_type in {OrderType.STOP, OrderType.STOP_LIMIT}:
            require(
                self.stop_price is not None,
                f"{self.order_type.value} orders require stop_price",
            )
        if self.order_type == OrderType.MARKET:
            require(
                self.limit_price is None and self.stop_price is None,
                "Market orders must not carry limit_price or stop_price",
            )
        if self.filled_quantity is not None:
            require(
                self.filled_quantity.value <= self.quantity.value,
                "filled_quantity cannot exceed order quantity",
            )
        if self.status in _TERMINAL_STATUSES:
            require(
                self.closed_at is not None,
                "Terminal orders must record closed_at",
                status=self.status.value,
            )

    @classmethod
    def create(
        cls,
        *,
        trading_account_id: UUID,
        symbol_id: UUID,
        order_type: OrderType,
        side: OrderSide,
        quantity: Quantity | str | int,
        time_in_force: TimeInForce = TimeInForce.GTC,
        limit_price: Price | str | None = None,
        stop_price: Price | str | None = None,
        stop_loss: Price | str | None = None,
        take_profit: Price | str | None = None,
        client_order_id: str = "",
        entity_id: UUID | None = None,
    ) -> Self:
        """Factory: create a PENDING order with validated parameters."""
        qty = quantity if isinstance(quantity, Quantity) else Quantity.of(quantity)
        limit = (
            None
            if limit_price is None
            else (
                limit_price if isinstance(limit_price, Price) else Price.of(limit_price)
            )
        )
        stop = (
            None
            if stop_price is None
            else (stop_price if isinstance(stop_price, Price) else Price.of(stop_price))
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
        kwargs: dict[str, object] = {
            "trading_account_id": trading_account_id,
            "symbol_id": symbol_id,
            "order_type": order_type,
            "side": side,
            "quantity": qty,
            "status": OrderStatus.PENDING,
            "time_in_force": time_in_force,
            "limit_price": limit,
            "stop_price": stop,
            "stop_loss": sl,
            "take_profit": tp,
            "submitted_at": datetime.now(UTC),
            "client_order_id": client_order_id.strip(),
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def _transition(self, new_status: OrderStatus) -> None:
        allowed = _ALLOWED_TRANSITIONS.get(self.status, frozenset())
        require_state(
            new_status in allowed,
            f"Illegal order transition {self.status.value} → {new_status.value}",
            from_status=self.status.value,
            to_status=new_status.value,
        )
        self.status = new_status
        if new_status in _TERMINAL_STATUSES:
            self.closed_at = datetime.now(UTC)
        self.touch()

    def accept(self) -> None:
        """Broker / venue accepted the order."""
        self._transition(OrderStatus.ACCEPTED)

    def reject(self, *, reason: str) -> None:
        """Reject the order with a reason."""
        require(bool(reason.strip()), "Rejection reason is required")
        self.rejection_reason = reason.strip()
        self._transition(OrderStatus.REJECTED)
        self._validate_invariants()

    def cancel(self) -> None:
        """Cancel a non-terminal order."""
        self._transition(OrderStatus.CANCELLED)
        self._validate_invariants()

    def expire(self) -> None:
        """Expire the order per time-in-force rules."""
        self._transition(OrderStatus.EXPIRED)
        self._validate_invariants()

    def record_fill(
        self,
        *,
        fill_quantity: Quantity | str | int,
        fill_price: Price | str,
    ) -> None:
        """Record a (partial) fill. Does not execute market matching."""
        require_state(
            self.status
            in {
                OrderStatus.ACCEPTED,
                OrderStatus.PARTIALLY_FILLED,
                OrderStatus.PENDING,
            },
            "Cannot fill an order in the current status",
            status=self.status.value,
        )
        if self.status == OrderStatus.PENDING:
            self._transition(OrderStatus.ACCEPTED)

        qty = (
            fill_quantity
            if isinstance(fill_quantity, Quantity)
            else Quantity.of(fill_quantity)
        )
        price = fill_price if isinstance(fill_price, Price) else Price.of(fill_price)

        current_filled = (
            self.filled_quantity.value if self.filled_quantity is not None else 0
        )
        from decimal import Decimal

        new_filled = Decimal(str(current_filled)) + qty.value
        require(
            new_filled <= self.quantity.value,
            "Fill would exceed order quantity",
            order_qty=str(self.quantity.value),
            filled=str(new_filled),
        )
        self.filled_quantity = Quantity(value=new_filled)
        self.average_fill_price = price

        if new_filled == self.quantity.value:
            self._transition(OrderStatus.FILLED)
        else:
            if self.status != OrderStatus.PARTIALLY_FILLED:
                self._transition(OrderStatus.PARTIALLY_FILLED)
            else:
                self.touch()
        self._validate_invariants()

    @property
    def is_open(self) -> bool:
        return self.status not in _TERMINAL_STATUSES

    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        base.update(
            {
                "trading_account_id": str(self.trading_account_id),
                "symbol_id": str(self.symbol_id),
                "order_type": self.order_type.value,
                "side": self.side.value,
                "quantity": str(self.quantity),
                "status": self.status.value,
                "time_in_force": self.time_in_force.value,
                "limit_price": str(self.limit_price) if self.limit_price else None,
                "stop_price": str(self.stop_price) if self.stop_price else None,
                "stop_loss": str(self.stop_loss) if self.stop_loss else None,
                "take_profit": str(self.take_profit) if self.take_profit else None,
                "filled_quantity": (
                    str(self.filled_quantity) if self.filled_quantity else None
                ),
                "average_fill_price": (
                    str(self.average_fill_price) if self.average_fill_price else None
                ),
                "submitted_at": (
                    self.submitted_at.isoformat() if self.submitted_at else None
                ),
                "closed_at": self.closed_at.isoformat() if self.closed_at else None,
                "client_order_id": self.client_order_id,
                "rejection_reason": self.rejection_reason,
            }
        )
        return base
