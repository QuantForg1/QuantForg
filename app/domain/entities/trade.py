"""Trade aggregate — immutable historical execution record.

Why this entity exists
----------------------
A Trade is a permanent ledger entry of an execution (fill). Once created it
never changes. This preserves an audit-grade history independent of live
Order/Position state. It does not compute strategies or indicators.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Self
from uuid import UUID

from app.domain.entities._guards import require
from app.domain.entities.base import Entity
from app.domain.enums.order import OrderSide
from app.domain.value_objects.market import Price, Quantity
from app.domain.value_objects.money import Money


@dataclass(eq=False, kw_only=True)
class Trade(Entity):
    """Immutable-after-creation execution record.

    Mutating methods intentionally raise — use the factory only.
    ``touch()`` is overridden to protect historical integrity.
    """

    trading_account_id: UUID
    symbol_id: UUID
    side: OrderSide
    quantity: Quantity
    price: Price
    executed_at: datetime
    order_id: UUID | None = None
    position_id: UUID | None = None
    commission: Money | None = None
    swap: Money | None = None
    realized_pnl: Money | None = None
    external_trade_id: str = ""
    _frozen: bool = False

    def __post_init__(self) -> None:
        self._validate_invariants()
        self._frozen = True

    def _validate_invariants(self) -> None:
        require(isinstance(self.quantity, Quantity), "quantity must be a Quantity")
        require(isinstance(self.price, Price), "price must be a Price")
        require(self.executed_at is not None, "executed_at is required")
        currency_refs = [
            m for m in (self.commission, self.swap, self.realized_pnl) if m is not None
        ]
        if len(currency_refs) >= 2:
            base = currency_refs[0].currency
            for money in currency_refs[1:]:
                require(
                    money.currency == base,
                    "commission, swap, and realized_pnl must share currency",
                )

    @classmethod
    def record(
        cls,
        *,
        trading_account_id: UUID,
        symbol_id: UUID,
        side: OrderSide,
        quantity: Quantity | str | int,
        price: Price | str,
        executed_at: datetime | None = None,
        order_id: UUID | None = None,
        position_id: UUID | None = None,
        commission: Money | None = None,
        swap: Money | None = None,
        realized_pnl: Money | None = None,
        external_trade_id: str = "",
        entity_id: UUID | None = None,
    ) -> Self:
        """Factory: append an immutable trade record."""
        qty = quantity if isinstance(quantity, Quantity) else Quantity.of(quantity)
        px = price if isinstance(price, Price) else Price.of(price)
        kwargs: dict[str, object] = {
            "trading_account_id": trading_account_id,
            "symbol_id": symbol_id,
            "side": side,
            "quantity": qty,
            "price": px,
            "executed_at": executed_at or datetime.now(UTC),
            "order_id": order_id,
            "position_id": position_id,
            "commission": commission,
            "swap": swap,
            "realized_pnl": realized_pnl,
            "external_trade_id": external_trade_id.strip(),
            "_frozen": False,
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def touch(self) -> None:
        """Trades are immutable — touch is a no-op that raises if frozen."""
        if self._frozen:
            from app.domain.exceptions.base import ConflictError

            raise ConflictError("Trade records are immutable and cannot be touched")

    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        base.update(
            {
                "trading_account_id": str(self.trading_account_id),
                "symbol_id": str(self.symbol_id),
                "side": self.side.value,
                "quantity": str(self.quantity),
                "price": str(self.price),
                "executed_at": self.executed_at.isoformat(),
                "order_id": str(self.order_id) if self.order_id else None,
                "position_id": str(self.position_id) if self.position_id else None,
                "commission": self.commission.to_dict() if self.commission else None,
                "swap": self.swap.to_dict() if self.swap else None,
                "realized_pnl": (
                    self.realized_pnl.to_dict() if self.realized_pnl else None
                ),
                "external_trade_id": self.external_trade_id,
            }
        )
        return base
