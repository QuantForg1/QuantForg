"""Paper Trading domain models — live quotes, simulated fills only."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Self
from uuid import UUID

from app.domain.entities._guards import require
from app.domain.entities.base import Entity
from app.domain.enums.paper import (
    PaperOrderSide,
    PaperOrderStatus,
    PaperOrderType,
    PaperPositionStatus,
)


@dataclass(frozen=True, slots=True)
class PaperBrokerAssumptions:
    """Virtual broker cost model (never live broker quotes for fills)."""

    spread: Decimal = Decimal("0.00010")
    slippage: Decimal = Decimal("0.00005")
    commission_per_lot: Decimal = Decimal("7")
    contract_size: Decimal = Decimal("100000")
    leverage: int = 100
    min_lot: Decimal = Decimal("0.01")
    max_lot: Decimal = Decimal("10")

    def __post_init__(self) -> None:
        require(self.spread >= 0, "spread must be >= 0")
        require(self.slippage >= 0, "slippage must be >= 0")
        require(self.commission_per_lot >= 0, "commission_per_lot must be >= 0")
        require(self.contract_size > 0, "contract_size must be > 0")
        require(self.leverage > 0, "leverage must be > 0")
        require(self.min_lot > 0, "min_lot must be > 0")
        require(self.max_lot >= self.min_lot, "max_lot must be >= min_lot")

    def to_dict(self) -> dict[str, object]:
        return {
            "spread": str(self.spread),
            "slippage": str(self.slippage),
            "commission_per_lot": str(self.commission_per_lot),
            "contract_size": str(self.contract_size),
            "leverage": self.leverage,
            "min_lot": str(self.min_lot),
            "max_lot": str(self.max_lot),
        }


@dataclass
class PaperPortfolio:
    """Paper account state — never a live broker account."""

    user_id: UUID
    initial_balance: Decimal
    balance: Decimal
    equity: Decimal
    floating_pnl: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    margin: Decimal = Decimal("0")
    peak_equity: Decimal = Decimal("0")
    max_drawdown_pct: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        require(self.initial_balance > 0, "initial_balance must be > 0")
        if self.peak_equity <= 0:
            self.peak_equity = self.equity

    @classmethod
    def create(cls, *, user_id: UUID, initial_balance: Decimal) -> Self:
        return cls(
            user_id=user_id,
            initial_balance=initial_balance,
            balance=initial_balance,
            equity=initial_balance,
            peak_equity=initial_balance,
        )

    def mark_to_market(self, floating: Decimal, *, margin: Decimal) -> None:
        self.floating_pnl = floating
        self.margin = margin
        self.equity = self.balance + floating
        if self.equity > self.peak_equity:
            self.peak_equity = self.equity
        if self.peak_equity > 0:
            dd = (self.peak_equity - self.equity) / self.peak_equity * Decimal("100")
            if dd > self.max_drawdown_pct:
                self.max_drawdown_pct = dd

    def apply_realized(self, pnl: Decimal, *, fee: Decimal) -> None:
        net = pnl - fee
        self.realized_pnl += net
        self.balance += net
        self.equity = self.balance + self.floating_pnl
        if self.equity > self.peak_equity:
            self.peak_equity = self.equity

    def debit_commission(self, fee: Decimal) -> None:
        self.balance -= fee
        self.equity = self.balance + self.floating_pnl

    def to_dict(self) -> dict[str, object]:
        free = self.equity - self.margin
        return {
            "user_id": str(self.user_id),
            "initial_balance": str(self.initial_balance),
            "balance": str(self.balance),
            "equity": str(self.equity),
            "floating_pnl": str(self.floating_pnl),
            "realized_pnl": str(self.realized_pnl),
            "margin": str(self.margin),
            "free_margin": str(free),
            "peak_equity": str(self.peak_equity),
            "max_drawdown_pct": str(self.max_drawdown_pct),
        }


@dataclass(eq=False, kw_only=True)
class PaperOrder(Entity):
    """Paper order — accepted/filled by Virtual Broker only."""

    user_id: UUID
    symbol: str
    side: PaperOrderSide
    order_type: PaperOrderType
    volume: Decimal
    status: PaperOrderStatus
    requested_price: Decimal | None = None
    fill_price: Decimal | None = None
    filled_volume: Decimal = Decimal("0")
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    spread: Decimal = Decimal("0")
    slippage: Decimal = Decimal("0")
    commission: Decimal = Decimal("0")
    rejection_reason: str = ""
    position_id: UUID | None = None
    client_order_id: str = ""
    submitted_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    filled_at: datetime | None = None

    def __post_init__(self) -> None:
        self.symbol = self.symbol.strip().upper()
        self.client_order_id = self.client_order_id.strip()
        require(len(self.symbol) > 0, "symbol is required")
        require(self.volume > 0, "volume must be > 0")
        if self.order_type is not PaperOrderType.MARKET:
            require(
                self.requested_price is not None and self.requested_price > 0,
                "limit/stop orders require requested_price",
            )

    @classmethod
    def create(
        cls,
        *,
        user_id: UUID,
        symbol: str,
        side: PaperOrderSide,
        order_type: PaperOrderType,
        volume: Decimal,
        requested_price: Decimal | None = None,
        stop_loss: Decimal | None = None,
        take_profit: Decimal | None = None,
        client_order_id: str = "",
        entity_id: UUID | None = None,
    ) -> Self:
        kwargs: dict[str, object] = {
            "user_id": user_id,
            "symbol": symbol,
            "side": side,
            "order_type": order_type,
            "volume": volume,
            "status": PaperOrderStatus.PENDING,
            "requested_price": requested_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "client_order_id": client_order_id,
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def accept(self) -> None:
        require(
            self.status is PaperOrderStatus.PENDING,
            "only pending orders can be accepted",
        )
        self.status = PaperOrderStatus.ACCEPTED
        self.touch()

    def reject(self, *, reason: str) -> None:
        require(
            self.status in {PaperOrderStatus.PENDING, PaperOrderStatus.ACCEPTED},
            "order cannot be rejected in current status",
        )
        self.status = PaperOrderStatus.REJECTED
        self.rejection_reason = reason.strip()[:500]
        self.touch()

    def fill(
        self,
        *,
        fill_price: Decimal,
        filled_volume: Decimal,
        spread: Decimal,
        slippage: Decimal,
        commission: Decimal,
        position_id: UUID,
        at: datetime | None = None,
    ) -> None:
        require(
            self.status
            in {
                PaperOrderStatus.PENDING,
                PaperOrderStatus.ACCEPTED,
                PaperOrderStatus.PARTIALLY_FILLED,
            },
            "order cannot be filled in current status",
        )
        require(filled_volume > 0, "filled_volume must be > 0")
        self.fill_price = fill_price
        self.filled_volume += filled_volume
        self.spread = spread
        self.slippage = slippage
        self.commission += commission
        self.position_id = position_id
        self.filled_at = at or datetime.now(UTC)
        if self.filled_volume >= self.volume:
            self.status = PaperOrderStatus.FILLED
        else:
            self.status = PaperOrderStatus.PARTIALLY_FILLED
        self.touch()

    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        base.update(
            {
                "user_id": str(self.user_id),
                "symbol": self.symbol,
                "side": self.side.value,
                "order_type": self.order_type.value,
                "volume": str(self.volume),
                "status": self.status.value,
                "requested_price": (
                    str(self.requested_price)
                    if self.requested_price is not None
                    else None
                ),
                "fill_price": (
                    str(self.fill_price) if self.fill_price is not None else None
                ),
                "filled_volume": str(self.filled_volume),
                "stop_loss": (
                    str(self.stop_loss) if self.stop_loss is not None else None
                ),
                "take_profit": (
                    str(self.take_profit) if self.take_profit is not None else None
                ),
                "spread": str(self.spread),
                "slippage": str(self.slippage),
                "commission": str(self.commission),
                "rejection_reason": self.rejection_reason,
                "position_id": (str(self.position_id) if self.position_id else None),
                "client_order_id": self.client_order_id,
                "submitted_at": self.submitted_at.isoformat(),
                "filled_at": (self.filled_at.isoformat() if self.filled_at else None),
            }
        )
        return base


@dataclass(eq=False, kw_only=True)
class PaperPosition(Entity):
    """Paper position lifecycle — opened / partially closed / closed."""

    user_id: UUID
    symbol: str
    side: PaperOrderSide
    status: PaperPositionStatus
    volume: Decimal
    remaining_volume: Decimal
    entry_price: Decimal
    current_price: Decimal
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    floating_pnl: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    commission: Decimal = Decimal("0")
    opened_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    closed_at: datetime | None = None
    order_id: UUID | None = None

    def __post_init__(self) -> None:
        self.symbol = self.symbol.strip().upper()
        require(len(self.symbol) > 0, "symbol is required")
        require(self.volume > 0, "volume must be > 0")
        require(self.remaining_volume >= 0, "remaining_volume must be >= 0")
        require(self.entry_price > 0, "entry_price must be > 0")

    @classmethod
    def open_position(
        cls,
        *,
        user_id: UUID,
        symbol: str,
        side: PaperOrderSide,
        volume: Decimal,
        entry_price: Decimal,
        stop_loss: Decimal | None = None,
        take_profit: Decimal | None = None,
        commission: Decimal = Decimal("0"),
        order_id: UUID | None = None,
        opened_at: datetime | None = None,
        entity_id: UUID | None = None,
    ) -> Self:
        kwargs: dict[str, object] = {
            "user_id": user_id,
            "symbol": symbol,
            "side": side,
            "status": PaperPositionStatus.OPENED,
            "volume": volume,
            "remaining_volume": volume,
            "entry_price": entry_price,
            "current_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "commission": commission,
            "order_id": order_id,
            "opened_at": opened_at or datetime.now(UTC),
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def mark(self, price: Decimal, *, contract_size: Decimal) -> Decimal:
        self.current_price = price
        direction = Decimal("1") if self.side is PaperOrderSide.BUY else Decimal("-1")
        self.floating_pnl = (
            (price - self.entry_price)
            * direction
            * self.remaining_volume
            * contract_size
        )
        self.touch()
        return self.floating_pnl

    def close_partial(
        self,
        *,
        close_volume: Decimal,
        exit_price: Decimal,
        contract_size: Decimal,
        commission: Decimal = Decimal("0"),
        at: datetime | None = None,
    ) -> Decimal:
        require(
            self.status
            in {PaperPositionStatus.OPENED, PaperPositionStatus.PARTIALLY_CLOSED},
            "position is not open",
        )
        require(
            Decimal("0") < close_volume <= self.remaining_volume,
            "invalid close_volume",
        )
        direction = Decimal("1") if self.side is PaperOrderSide.BUY else Decimal("-1")
        pnl = (exit_price - self.entry_price) * direction * close_volume * contract_size
        self.remaining_volume -= close_volume
        self.realized_pnl += pnl - commission
        self.commission += commission
        self.current_price = exit_price
        if self.remaining_volume == 0:
            self.status = PaperPositionStatus.CLOSED
            self.floating_pnl = Decimal("0")
            self.closed_at = at or datetime.now(UTC)
        else:
            self.status = PaperPositionStatus.PARTIALLY_CLOSED
            self.mark(exit_price, contract_size=contract_size)
        self.touch()
        return pnl

    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        base.update(
            {
                "user_id": str(self.user_id),
                "symbol": self.symbol,
                "side": self.side.value,
                "status": self.status.value,
                "volume": str(self.volume),
                "remaining_volume": str(self.remaining_volume),
                "entry_price": str(self.entry_price),
                "current_price": str(self.current_price),
                "stop_loss": (
                    str(self.stop_loss) if self.stop_loss is not None else None
                ),
                "take_profit": (
                    str(self.take_profit) if self.take_profit is not None else None
                ),
                "floating_pnl": str(self.floating_pnl),
                "realized_pnl": str(self.realized_pnl),
                "commission": str(self.commission),
                "opened_at": self.opened_at.isoformat(),
                "closed_at": (self.closed_at.isoformat() if self.closed_at else None),
                "order_id": str(self.order_id) if self.order_id else None,
            }
        )
        return base


@dataclass(eq=False, kw_only=True)
class PaperTrade(Entity):
    """Closed (or partial) paper trade record for history / performance."""

    user_id: UUID
    symbol: str
    side: PaperOrderSide
    volume: Decimal
    entry_price: Decimal
    exit_price: Decimal
    pnl: Decimal
    commission: Decimal = Decimal("0")
    spread: Decimal = Decimal("0")
    slippage: Decimal = Decimal("0")
    position_id: UUID | None = None
    order_id: UUID | None = None
    opened_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    closed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self.symbol = self.symbol.strip().upper()
        require(len(self.symbol) > 0, "symbol is required")
        require(self.volume > 0, "volume must be > 0")

    @classmethod
    def record(
        cls,
        *,
        user_id: UUID,
        symbol: str,
        side: PaperOrderSide,
        volume: Decimal,
        entry_price: Decimal,
        exit_price: Decimal,
        pnl: Decimal,
        commission: Decimal = Decimal("0"),
        spread: Decimal = Decimal("0"),
        slippage: Decimal = Decimal("0"),
        position_id: UUID | None = None,
        order_id: UUID | None = None,
        opened_at: datetime | None = None,
        closed_at: datetime | None = None,
        entity_id: UUID | None = None,
    ) -> Self:
        kwargs: dict[str, object] = {
            "user_id": user_id,
            "symbol": symbol,
            "side": side,
            "volume": volume,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pnl": pnl,
            "commission": commission,
            "spread": spread,
            "slippage": slippage,
            "position_id": position_id,
            "order_id": order_id,
            "opened_at": opened_at or datetime.now(UTC),
            "closed_at": closed_at or datetime.now(UTC),
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        base.update(
            {
                "user_id": str(self.user_id),
                "symbol": self.symbol,
                "side": self.side.value,
                "volume": str(self.volume),
                "entry_price": str(self.entry_price),
                "exit_price": str(self.exit_price),
                "pnl": str(self.pnl),
                "commission": str(self.commission),
                "spread": str(self.spread),
                "slippage": str(self.slippage),
                "position_id": (str(self.position_id) if self.position_id else None),
                "order_id": str(self.order_id) if self.order_id else None,
                "opened_at": self.opened_at.isoformat(),
                "closed_at": self.closed_at.isoformat(),
            }
        )
        return base


@dataclass(frozen=True, slots=True)
class PaperPerformance:
    """Aggregated paper trading performance snapshot."""

    balance: Decimal
    equity: Decimal
    realized_pnl: Decimal
    floating_pnl: Decimal
    max_drawdown_pct: Decimal
    total_trades: int
    win_count: int
    loss_count: int
    win_rate: Decimal
    profit_factor: Decimal | None
    expectancy: Decimal

    def to_dict(self) -> dict[str, object]:
        return {
            "balance": str(self.balance),
            "equity": str(self.equity),
            "realized_pnl": str(self.realized_pnl),
            "floating_pnl": str(self.floating_pnl),
            "max_drawdown_pct": str(self.max_drawdown_pct),
            "total_trades": self.total_trades,
            "win_count": self.win_count,
            "loss_count": self.loss_count,
            "win_rate": str(self.win_rate),
            "profit_factor": (
                str(self.profit_factor) if self.profit_factor is not None else None
            ),
            "expectancy": str(self.expectancy),
        }
