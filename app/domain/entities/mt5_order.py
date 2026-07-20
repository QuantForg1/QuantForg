"""MT5 order-validation domain models — prepare/check only, never send."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Self
from uuid import UUID

from app.domain.entities._guards import require
from app.domain.entities.base import Entity
from app.domain.enums.order import OrderSide, OrderType
from app.domain.value_objects.mt5_order import (
    LotSize,
    MagicNumber,
    Slippage,
    StopLoss,
    TakeProfit,
)


@dataclass(frozen=True, slots=True)
class OrderConstraints:
    """Symbol trading constraints used during validation — sourced from MT5."""

    symbol: str
    min_volume: Decimal = Decimal("0.01")
    max_volume: Decimal = Decimal("100")
    volume_step: Decimal = Decimal("0.01")
    stops_level: int = 0
    freeze_level: int = 0
    trade_allowed: bool = True
    market_open: bool = True
    digits: int = 5
    point: Decimal = Decimal("0.00001")
    contract_size: Decimal = Decimal("100000")
    margin_rate: Decimal = Decimal("0.01")
    filling_mode: int = 0
    execution_mode: str = "market"
    trade_mode: str = "full"
    visible: bool = True
    margin_calc_mode: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        require(len(self.symbol) > 0, "symbol is required")
        require(self.min_volume > 0, "min_volume must be > 0")
        require(self.max_volume >= self.min_volume, "max_volume must be >= min_volume")
        require(self.volume_step > 0, "volume_step must be > 0")

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "min_volume": str(self.min_volume),
            "max_volume": str(self.max_volume),
            "volume_step": str(self.volume_step),
            "stops_level": self.stops_level,
            "freeze_level": self.freeze_level,
            "trade_allowed": self.trade_allowed,
            "market_open": self.market_open,
            "digits": self.digits,
            "point": str(self.point),
            "contract_size": str(self.contract_size),
            "margin_rate": str(self.margin_rate),
            "filling_mode": self.filling_mode,
            "execution_mode": self.execution_mode,
            "trade_mode": self.trade_mode,
            "visible": self.visible,
            "margin_calc_mode": self.margin_calc_mode,
        }


@dataclass(frozen=True, slots=True)
class OrderIntent:
    """User intent to trade — validated before any broker check."""

    symbol: str
    side: OrderSide
    order_type: OrderType
    volume: LotSize
    price: Decimal | None = None
    stop_loss: StopLoss | None = None
    take_profit: TakeProfit | None = None
    slippage: Slippage = field(default_factory=lambda: Slippage.of(10))
    magic: MagicNumber = field(default_factory=lambda: MagicNumber.of(0))
    comment: str = ""
    position: int = 0
    order_ticket: int = 0
    oms_kind: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(self, "comment", self.comment.strip()[:64])
        object.__setattr__(self, "oms_kind", (self.oms_kind or "").strip().lower())
        require(len(self.symbol) > 0, "symbol is required")
        if self.order_type is not OrderType.MARKET and self.oms_kind not in {
            "sltp",
            "modify_sltp",
        }:
            require(
                self.price is not None and self.price > 0,
                "pending orders require a positive price",
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "volume": str(self.volume.value),
            "price": str(self.price) if self.price is not None else None,
            "stop_loss": str(self.stop_loss.value) if self.stop_loss else None,
            "take_profit": str(self.take_profit.value) if self.take_profit else None,
            "slippage": self.slippage.value,
            "magic": self.magic.value,
            "comment": self.comment,
            "position": self.position,
            "order_ticket": self.order_ticket,
            "oms_kind": self.oms_kind,
        }


@dataclass(frozen=True, slots=True)
class TradeRequest:
    """Normalized MT5 trade request payload."""

    symbol: str
    action: str  # buy | sell | buy_limit | sell_limit | buy_stop | sell_stop | sltp
    volume: Decimal
    price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    deviation: int
    magic: int
    comment: str = ""
    type_filling: str = "ioc"
    type_time: str = "gtc"
    position: int = 0
    order_ticket: int = 0
    oms_kind: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "action": self.action,
            "volume": str(self.volume),
            "price": str(self.price),
            "sl": str(self.stop_loss),
            "tp": str(self.take_profit),
            "deviation": self.deviation,
            "magic": self.magic,
            "comment": self.comment,
            "type_filling": self.type_filling,
            "type_time": self.type_time,
            "position": self.position,
            "order_ticket": self.order_ticket,
            "oms_kind": self.oms_kind,
        }


@dataclass(eq=False, kw_only=True)
class TradeValidation(Entity):
    """Persisted validation outcome — history only, no credentials."""

    user_id: UUID
    symbol: str
    side: str
    order_type: str
    volume: Decimal
    valid: bool
    retcode: int = 0
    expected_margin: Decimal = Decimal("0")
    estimated_profit: Decimal = Decimal("0")
    messages: list[str] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)
    request_snapshot: dict[str, object] = field(default_factory=dict)
    validated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self.symbol = self.symbol.strip().upper()
        require(len(self.symbol) > 0, "symbol is required")
        self.messages = [m.strip()[:500] for m in self.messages if m.strip()][:50]

    @classmethod
    def record(
        cls,
        *,
        user_id: UUID,
        symbol: str,
        side: str,
        order_type: str,
        volume: Decimal,
        valid: bool,
        retcode: int = 0,
        expected_margin: Decimal = Decimal("0"),
        estimated_profit: Decimal = Decimal("0"),
        messages: list[str] | None = None,
        checks: dict[str, bool] | None = None,
        request_snapshot: dict[str, object] | None = None,
        entity_id: UUID | None = None,
    ) -> Self:
        kwargs: dict[str, object] = {
            "user_id": user_id,
            "symbol": symbol,
            "side": side,
            "order_type": order_type,
            "volume": volume,
            "valid": valid,
            "retcode": retcode,
            "expected_margin": expected_margin,
            "estimated_profit": estimated_profit,
            "messages": list(messages or []),
            "checks": dict(checks or {}),
            "request_snapshot": dict(request_snapshot or {}),
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
                "side": self.side,
                "order_type": self.order_type,
                "volume": str(self.volume),
                "valid": self.valid,
                "retcode": self.retcode,
                "expected_margin": str(self.expected_margin),
                "estimated_profit": str(self.estimated_profit),
                "messages": list(self.messages),
                "checks": dict(self.checks),
                "request_snapshot": dict(self.request_snapshot),
                "validated_at": self.validated_at.isoformat(),
            }
        )
        return base
