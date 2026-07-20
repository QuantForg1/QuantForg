"""Simulation OMS ports — fills in-process; never calls MT5 order_send."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.domain.entities.mt5_order import OrderIntent
from app.domain.institutional_trading.execution.models import OmsSubmitResult
from app.domain.institutional_trading.management.models import OmsManageResult


@dataclass
class SimulationBook:
    """In-memory book for simulated positions."""

    next_ticket: int = 1000
    positions: dict[int, dict[str, Any]] = field(default_factory=dict)
    pending_entry: dict[str, Any] | None = None  # fill at next bar open
    last_fill_price: Decimal | None = None
    events: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SimulationOmsPort:
    """Implements OmsSubmitPort + OmsManagePort for research simulation."""

    book: SimulationBook = field(default_factory=SimulationBook)
    spread: Decimal = Decimal("0.30")
    slippage: Decimal = Decimal("0.05")
    next_open: Decimal | None = None  # set by engine each bar

    def set_bar_open(self, price: Decimal) -> None:
        self.next_open = price
        self._fill_pending()

    def _fill_pending(self) -> None:
        if not self.book.pending_entry or self.next_open is None:
            return
        pending = self.book.pending_entry
        side = pending["side"]
        px = self.next_open
        if side == "buy":
            px = px + self.spread / Decimal("2") + self.slippage
        else:
            px = px - self.spread / Decimal("2") - self.slippage
        ticket = self.book.next_ticket
        self.book.next_ticket += 1
        self.book.positions[ticket] = {
            "ticket": ticket,
            "symbol": pending["symbol"],
            "side": side,
            "volume": pending["volume"],
            "open_price": px,
            "stop_loss": pending.get("stop_loss"),
            "take_profit": pending.get("take_profit"),
            "comment": pending.get("comment", ""),
            "magic": pending.get("magic", 0),
        }
        self.book.last_fill_price = px
        self.book.events.append({"type": "fill", "ticket": ticket, "price": str(px)})
        self.book.pending_entry = None

    def submit_market(
        self,
        *,
        user_id: UUID,
        request_id: str,
        intent: OrderIntent,
        connected: bool,
        login: int | None,
    ) -> OmsSubmitResult:
        # Queue for next_bar_open fill (approved ITE model)
        self.book.pending_entry = {
            "symbol": intent.symbol,
            "side": intent.side.value,
            "volume": intent.volume.value,
            "stop_loss": intent.stop_loss.value if intent.stop_loss else None,
            "take_profit": intent.take_profit.value if intent.take_profit else None,
            "comment": intent.comment,
            "magic": intent.magic.value,
            "request_id": request_id,
        }
        # If next_open already known (same-bar sync tests), fill immediately
        if self.next_open is not None:
            self._fill_pending()
            pos = next(reversed(self.book.positions.values()), None)
            ticket = pos["ticket"] if pos else None
            return OmsSubmitResult(
                outcome="success",
                message="simulation fill (next_bar_open)",
                retcode=10009,
                order_ticket=ticket,
                deal_ticket=ticket,
                oms_status="success",
                gateway_status="simulation",
                latency_ms=0.0,
                retryable=False,
            )
        return OmsSubmitResult(
            outcome="success",
            message="simulation queued for next bar open",
            retcode=10009,
            order_ticket=None,
            deal_ticket=None,
            oms_status="queued",
            gateway_status="simulation",
            latency_ms=0.0,
            retryable=False,
        )

    def modify_sltp(
        self,
        *,
        user_id: UUID,
        request_id: str,
        symbol: str,
        side: str,
        position: int,
        stop_loss: Decimal,
        take_profit: Decimal | None,
        comment: str,
        connected: bool,
        login: int | None,
    ) -> OmsManageResult:
        pos = self.book.positions.get(position)
        if not pos:
            return OmsManageResult(
                outcome="failed",
                message="position not found",
                retcode=10013,
                oms_status="failed",
                gateway_status="simulation",
            )
        pos["stop_loss"] = stop_loss
        if take_profit is not None:
            pos["take_profit"] = take_profit
        self.book.events.append(
            {"type": "sltp", "ticket": position, "sl": str(stop_loss), "comment": comment}
        )
        return OmsManageResult(
            outcome="success",
            message="simulation SLTP",
            retcode=10009,
            oms_status="success",
            gateway_status="simulation",
        )

    def partial_close(
        self,
        *,
        user_id: UUID,
        request_id: str,
        symbol: str,
        side: str,
        position: int,
        volume: Decimal,
        comment: str,
        connected: bool,
        login: int | None,
    ) -> OmsManageResult:
        pos = self.book.positions.get(position)
        if not pos:
            return OmsManageResult(
                outcome="failed", message="position not found", retcode=10013
            )
        pos["volume"] = (Decimal(str(pos["volume"])) - volume).quantize(Decimal("0.01"))
        self.book.events.append(
            {"type": "partial", "ticket": position, "volume": str(volume)}
        )
        return OmsManageResult(
            outcome="success",
            message="simulation partial",
            retcode=10009,
            oms_status="success",
            gateway_status="simulation",
        )

    def close_position(
        self,
        *,
        user_id: UUID,
        request_id: str,
        symbol: str,
        side: str,
        position: int,
        volume: Decimal,
        comment: str,
        connected: bool,
        login: int | None,
    ) -> OmsManageResult:
        if position in self.book.positions:
            del self.book.positions[position]
            self.book.events.append({"type": "close", "ticket": position})
        return OmsManageResult(
            outcome="success",
            message="simulation close",
            retcode=10009,
            oms_status="success",
            gateway_status="simulation",
        )
