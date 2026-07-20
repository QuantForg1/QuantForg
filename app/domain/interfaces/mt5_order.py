"""MT5 order-check / calc result types (validation layer — no order_send)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.entities.mt5_order import TradeRequest

# Common MT5 trade retcodes used by the mock / validation layer.
RETCODE_DONE = 10009
RETCODE_INVALID_VOLUME = 10014
RETCODE_INVALID_STOPS = 10016
RETCODE_INVALID_PRICE = 10015
RETCODE_NO_MONEY = 10019
RETCODE_MARKET_CLOSED = 10018
RETCODE_TRADE_DISABLED = 10017
RETCODE_INVALID = 10013


@dataclass(frozen=True, slots=True)
class MT5OrderCheckResult:
    """Result of ``order_check`` — never implies a live fill."""

    retcode: int
    comment: str
    request: TradeRequest
    balance: Decimal = Decimal("0")
    equity: Decimal = Decimal("0")
    margin: Decimal = Decimal("0")
    margin_free: Decimal = Decimal("0")
    profit: Decimal = Decimal("0")

    @property
    def ok(self) -> bool:
        return self.retcode in {0, RETCODE_DONE}

    def to_dict(self) -> dict[str, object]:
        return {
            "retcode": self.retcode,
            "comment": self.comment,
            "ok": self.ok,
            "balance": str(self.balance),
            "equity": str(self.equity),
            "margin": str(self.margin),
            "margin_free": str(self.margin_free),
            "profit": str(self.profit),
            "request": self.request.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class MT5MarginResult:
    """Result of ``order_calc_margin``."""

    margin: Decimal
    retcode: int = RETCODE_DONE
    comment: str = "done"

    def to_dict(self) -> dict[str, object]:
        return {
            "margin": str(self.margin),
            "retcode": self.retcode,
            "comment": self.comment,
        }


@dataclass(frozen=True, slots=True)
class MT5ProfitResult:
    """Result of ``order_calc_profit``."""

    profit: Decimal
    retcode: int = RETCODE_DONE
    comment: str = "done"

    def to_dict(self) -> dict[str, object]:
        return {
            "profit": str(self.profit),
            "retcode": self.retcode,
            "comment": self.comment,
        }


@dataclass(frozen=True, slots=True)
class MT5OrderSendResult:
    """Adapter-internal send result — mapped to domain before leaving infra."""

    retcode: int
    comment: str
    order_ticket: int = 0
    deal_ticket: int = 0
    volume: Decimal = Decimal("0")
    price: Decimal = Decimal("0")
    request: TradeRequest | None = None

    @property
    def ok(self) -> bool:
        return self.retcode in {0, RETCODE_DONE, 10008}

    def to_dict(self) -> dict[str, object]:
        return {
            "retcode": self.retcode,
            "comment": self.comment,
            "ok": self.ok,
            "order_ticket": self.order_ticket,
            "deal_ticket": self.deal_ticket,
            "volume": str(self.volume),
            "price": str(self.price),
            "request": self.request.to_dict() if self.request else None,
        }
