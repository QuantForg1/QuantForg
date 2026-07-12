"""MT5 portfolio / position domain models — read-only sync snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Self
from uuid import UUID

from app.domain.entities._guards import require
from app.domain.entities.base import Entity


@dataclass(frozen=True, slots=True)
class MT5Position:
    """Open MT5 position snapshot (ticket-based, read-only)."""

    ticket: int
    symbol: str
    side: str  # buy | sell
    volume: Decimal
    open_price: Decimal
    current_price: Decimal = Decimal("0")
    stop_loss: Decimal = Decimal("0")
    take_profit: Decimal = Decimal("0")
    profit: Decimal = Decimal("0")
    swap: Decimal = Decimal("0")
    magic: int = 0
    comment: str = ""
    opened_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(self, "side", self.side.strip().lower())
        object.__setattr__(self, "comment", self.comment.strip()[:64])
        require(self.ticket > 0, "ticket must be > 0")
        require(len(self.symbol) > 0, "symbol is required")
        require(self.side in {"buy", "sell"}, "side must be buy or sell")
        require(self.volume > 0, "volume must be > 0")

    def to_dict(self) -> dict[str, object]:
        return {
            "ticket": self.ticket,
            "symbol": self.symbol,
            "side": self.side,
            "volume": str(self.volume),
            "open_price": str(self.open_price),
            "current_price": str(self.current_price),
            "stop_loss": str(self.stop_loss),
            "take_profit": str(self.take_profit),
            "profit": str(self.profit),
            "swap": str(self.swap),
            "magic": self.magic,
            "comment": self.comment,
            "opened_at": self.opened_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class MT5PendingOrder:
    """Pending MT5 order snapshot (read-only)."""

    ticket: int
    symbol: str
    side: str
    order_type: str  # buy_limit | sell_limit | buy_stop | sell_stop | ...
    volume: Decimal
    price: Decimal
    stop_loss: Decimal = Decimal("0")
    take_profit: Decimal = Decimal("0")
    magic: int = 0
    comment: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(self, "side", self.side.strip().lower())
        object.__setattr__(self, "order_type", self.order_type.strip().lower())
        object.__setattr__(self, "comment", self.comment.strip()[:64])
        require(self.ticket > 0, "ticket must be > 0")
        require(len(self.symbol) > 0, "symbol is required")
        require(self.volume > 0, "volume must be > 0")

    def to_dict(self) -> dict[str, object]:
        return {
            "ticket": self.ticket,
            "symbol": self.symbol,
            "side": self.side,
            "order_type": self.order_type,
            "volume": str(self.volume),
            "price": str(self.price),
            "stop_loss": str(self.stop_loss),
            "take_profit": str(self.take_profit),
            "magic": self.magic,
            "comment": self.comment,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class MT5HistoryOrder:
    """Historical MT5 order (read-only cache)."""

    ticket: int
    symbol: str
    side: str
    order_type: str
    volume: Decimal
    price: Decimal
    state: str = "filled"  # filled | cancelled | expired | rejected
    profit: Decimal = Decimal("0")
    time_setup: datetime = field(default_factory=lambda: datetime.now(UTC))
    time_done: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(self, "side", self.side.strip().lower())
        object.__setattr__(self, "order_type", self.order_type.strip().lower())
        object.__setattr__(self, "state", self.state.strip().lower())
        require(self.ticket > 0, "ticket must be > 0")

    def to_dict(self) -> dict[str, object]:
        return {
            "ticket": self.ticket,
            "symbol": self.symbol,
            "side": self.side,
            "order_type": self.order_type,
            "volume": str(self.volume),
            "price": str(self.price),
            "state": self.state,
            "profit": str(self.profit),
            "time_setup": self.time_setup.isoformat(),
            "time_done": self.time_done.isoformat() if self.time_done else None,
        }


@dataclass(frozen=True, slots=True)
class MT5Deal:
    """Historical MT5 deal / fill (read-only cache)."""

    ticket: int
    order_ticket: int
    symbol: str
    side: str
    volume: Decimal
    price: Decimal
    profit: Decimal = Decimal("0")
    commission: Decimal = Decimal("0")
    swap: Decimal = Decimal("0")
    deal_type: str = "deal"  # entry_in | entry_out | ...
    time: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(self, "side", self.side.strip().lower())
        object.__setattr__(self, "deal_type", self.deal_type.strip().lower())
        require(self.ticket > 0, "ticket must be > 0")
        require(len(self.symbol) > 0, "symbol is required")

    def to_dict(self) -> dict[str, object]:
        return {
            "ticket": self.ticket,
            "order_ticket": self.order_ticket,
            "symbol": self.symbol,
            "side": self.side,
            "volume": str(self.volume),
            "price": str(self.price),
            "profit": str(self.profit),
            "commission": str(self.commission),
            "swap": str(self.swap),
            "deal_type": self.deal_type,
            "time": self.time.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    """Account equity/margin snapshot for portfolio sync."""

    login: int
    balance: Decimal
    equity: Decimal
    margin: Decimal
    free_margin: Decimal
    margin_level: Decimal
    profit: Decimal
    leverage: int
    currency: str = "USD"
    server: str = ""

    def __post_init__(self) -> None:
        require(self.login > 0, "login must be > 0")
        require(self.leverage >= 1, "leverage must be >= 1")
        object.__setattr__(self, "currency", self.currency.strip().upper() or "USD")
        object.__setattr__(self, "server", self.server.strip())

    def to_dict(self) -> dict[str, object]:
        return {
            "login": self.login,
            "balance": str(self.balance),
            "equity": str(self.equity),
            "margin": str(self.margin),
            "free_margin": str(self.free_margin),
            "margin_level": str(self.margin_level),
            "profit": str(self.profit),
            "leverage": self.leverage,
            "currency": self.currency,
            "server": self.server,
        }


@dataclass(frozen=True, slots=True)
class PortfolioState:
    """In-memory portfolio view after a sync (not an Entity)."""

    account: AccountSnapshot
    positions: tuple[MT5Position, ...] = ()
    pending_orders: tuple[MT5PendingOrder, ...] = ()
    history_orders: tuple[MT5HistoryOrder, ...] = ()
    history_deals: tuple[MT5Deal, ...] = ()
    synced_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, object]:
        return {
            "account": self.account.to_dict(),
            "positions": [p.to_dict() for p in self.positions],
            "pending_orders": [o.to_dict() for o in self.pending_orders],
            "history_orders": [o.to_dict() for o in self.history_orders],
            "history_deals": [d.to_dict() for d in self.history_deals],
            "synced_at": self.synced_at.isoformat(),
            "position_count": len(self.positions),
            "pending_order_count": len(self.pending_orders),
        }


@dataclass(eq=False, kw_only=True)
class PortfolioSyncRecord(Entity):
    """Persisted portfolio sync snapshot metadata (cache only)."""

    user_id: UUID
    login: int
    balance: Decimal
    equity: Decimal
    margin: Decimal
    free_margin: Decimal
    margin_level: Decimal
    profit: Decimal
    leverage: int
    position_count: int = 0
    pending_order_count: int = 0
    history_order_count: int = 0
    history_deal_count: int = 0
    snapshot: dict[str, object] = field(default_factory=dict)
    synced_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        require(self.login > 0, "login must be > 0")
        require(self.position_count >= 0, "position_count must be >= 0")

    @classmethod
    def from_state(
        cls,
        *,
        user_id: UUID,
        state: PortfolioState,
        entity_id: UUID | None = None,
    ) -> Self:
        kwargs: dict[str, object] = {
            "user_id": user_id,
            "login": state.account.login,
            "balance": state.account.balance,
            "equity": state.account.equity,
            "margin": state.account.margin,
            "free_margin": state.account.free_margin,
            "margin_level": state.account.margin_level,
            "profit": state.account.profit,
            "leverage": state.account.leverage,
            "position_count": len(state.positions),
            "pending_order_count": len(state.pending_orders),
            "history_order_count": len(state.history_orders),
            "history_deal_count": len(state.history_deals),
            "snapshot": state.to_dict(),
            "synced_at": state.synced_at,
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        base.update(
            {
                "user_id": str(self.user_id),
                "login": self.login,
                "balance": str(self.balance),
                "equity": str(self.equity),
                "margin": str(self.margin),
                "free_margin": str(self.free_margin),
                "margin_level": str(self.margin_level),
                "profit": str(self.profit),
                "leverage": self.leverage,
                "position_count": self.position_count,
                "pending_order_count": self.pending_order_count,
                "history_order_count": self.history_order_count,
                "history_deal_count": self.history_deal_count,
                "snapshot": dict(self.snapshot),
                "synced_at": self.synced_at.isoformat(),
            }
        )
        return base
