"""Virtual Broker — simulate order acceptance/fills for paper trading.

Never connects to live execution. Never calls order_send().
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from app.application.services.paper_market_listener import PaperQuote
from app.domain.entities.paper import (
    PaperBrokerAssumptions,
    PaperOrder,
    PaperPortfolio,
    PaperPosition,
    PaperTrade,
)
from app.domain.enums.paper import (
    PaperOrderSide,
    PaperOrderStatus,
    PaperOrderType,
    PaperPositionStatus,
)
from app.domain.events.base import DomainEvent
from app.domain.events.paper import (
    PaperOrderFilled,
    PaperOrderRejected,
    PaperTradeClosed,
    PaperTradeOpened,
)


@dataclass(frozen=True, slots=True)
class VirtualBrokerResult:
    """Outcome of submitting a paper order to the virtual broker."""

    order: PaperOrder
    position: PaperPosition | None
    trade: PaperTrade | None = None
    accepted: bool = False
    filled: bool = False


@dataclass
class VirtualBroker:
    """Simulates order acceptance, fills, slippage, commissions, spread."""

    assumptions: PaperBrokerAssumptions = field(default_factory=PaperBrokerAssumptions)
    _events: list[DomainEvent] = field(default_factory=list, init=False)

    def drain_events(self) -> list[DomainEvent]:
        events = list(self._events)
        self._events.clear()
        return events

    def submit(
        self,
        order: PaperOrder,
        *,
        quote: PaperQuote,
        portfolio: PaperPortfolio,
        reduce_position: PaperPosition | None = None,
    ) -> VirtualBrokerResult:
        """Accept or reject; fill market (and eligible limit/stop) orders."""
        # Volume bounds
        if order.volume < self.assumptions.min_lot:
            return self._reject(
                order, f"volume below min_lot {self.assumptions.min_lot}"
            )
        if order.volume > self.assumptions.max_lot:
            return self._reject(
                order, f"volume above max_lot {self.assumptions.max_lot}"
            )

        # Free margin rough check for opening (not reducing)
        if reduce_position is None:
            notional = order.volume * self.assumptions.contract_size * quote.mid
            required_margin = notional / Decimal(self.assumptions.leverage)
            free = portfolio.equity - portfolio.margin
            if required_margin > free:
                return self._reject(
                    order,
                    f"insufficient free margin (need {required_margin})",
                )

        order.accept()

        if order.order_type is PaperOrderType.MARKET:
            return self._fill_now(
                order,
                quote=quote,
                portfolio=portfolio,
                reduce_position=reduce_position,
            )

        if order.order_type is PaperOrderType.LIMIT:
            if self._limit_triggered(order, quote):
                return self._fill_now(
                    order,
                    quote=quote,
                    portfolio=portfolio,
                    reduce_position=reduce_position,
                )
            return VirtualBrokerResult(order=order, position=None, accepted=True)

        if order.order_type is PaperOrderType.STOP:
            if self._stop_triggered(order, quote):
                return self._fill_now(
                    order,
                    quote=quote,
                    portfolio=portfolio,
                    reduce_position=reduce_position,
                )
            return VirtualBrokerResult(order=order, position=None, accepted=True)

        return self._reject(order, f"unsupported order type {order.order_type}")

    def try_fill_pending(
        self,
        order: PaperOrder,
        *,
        quote: PaperQuote,
        portfolio: PaperPortfolio,
    ) -> VirtualBrokerResult | None:
        """Attempt to fill an accepted pending limit/stop against a new quote."""
        if order.status is not PaperOrderStatus.ACCEPTED:
            return None
        if order.order_type is PaperOrderType.LIMIT and self._limit_triggered(
            order, quote
        ):
            return self._fill_now(order, quote=quote, portfolio=portfolio)
        if order.order_type is PaperOrderType.STOP and self._stop_triggered(
            order, quote
        ):
            return self._fill_now(order, quote=quote, portfolio=portfolio)
        return None

    def _reject(self, order: PaperOrder, reason: str) -> VirtualBrokerResult:
        order.reject(reason=reason)
        self._events.append(
            PaperOrderRejected(
                user_id=order.user_id,
                order_id=order.id,
                symbol=order.symbol,
                reason=reason,
            )
        )
        return VirtualBrokerResult(order=order, position=None, accepted=False)

    def _limit_triggered(self, order: PaperOrder, quote: PaperQuote) -> bool:
        assert order.requested_price is not None
        if order.side is PaperOrderSide.BUY:
            return quote.ask <= order.requested_price
        return quote.bid >= order.requested_price

    def _stop_triggered(self, order: PaperOrder, quote: PaperQuote) -> bool:
        assert order.requested_price is not None
        if order.side is PaperOrderSide.BUY:
            return quote.ask >= order.requested_price
        return quote.bid <= order.requested_price

    def _fill_price(
        self, order: PaperOrder, quote: PaperQuote
    ) -> tuple[Decimal, Decimal, Decimal]:
        half = self.assumptions.spread / Decimal("2")
        slip = self.assumptions.slippage
        if order.side is PaperOrderSide.BUY:
            # Buy at ask + slippage
            base = quote.ask if quote.ask > 0 else quote.mid + half
            price = base + slip
        else:
            base = quote.bid if quote.bid > 0 else quote.mid - half
            price = base - slip
        return price, self.assumptions.spread, slip

    def _fill_now(
        self,
        order: PaperOrder,
        *,
        quote: PaperQuote,
        portfolio: PaperPortfolio,
        reduce_position: PaperPosition | None = None,
    ) -> VirtualBrokerResult:
        fill_price, spread, slip = self._fill_price(order, quote)
        commission = self.assumptions.commission_per_lot * order.volume
        now = datetime.now(UTC)

        if reduce_position is not None:
            close_vol = min(order.volume, reduce_position.remaining_volume)
            pnl = reduce_position.close_partial(
                close_volume=close_vol,
                exit_price=fill_price,
                contract_size=self.assumptions.contract_size,
                commission=commission,
                at=now,
            )
            portfolio.apply_realized(pnl, fee=commission)
            order.fill(
                fill_price=fill_price,
                filled_volume=close_vol,
                spread=spread,
                slippage=slip,
                commission=commission,
                position_id=reduce_position.id,
                at=now,
            )
            trade = PaperTrade.record(
                user_id=order.user_id,
                symbol=order.symbol,
                side=reduce_position.side,
                volume=close_vol,
                entry_price=reduce_position.entry_price,
                exit_price=fill_price,
                pnl=pnl - commission,
                commission=commission,
                spread=spread,
                slippage=slip,
                position_id=reduce_position.id,
                order_id=order.id,
                opened_at=reduce_position.opened_at,
                closed_at=now,
            )
            self._events.append(
                PaperOrderFilled(
                    user_id=order.user_id,
                    order_id=order.id,
                    symbol=order.symbol,
                    fill_price=str(fill_price),
                    filled_volume=str(close_vol),
                )
            )
            self._events.append(
                PaperTradeClosed(
                    user_id=order.user_id,
                    position_id=reduce_position.id,
                    symbol=order.symbol,
                    volume=str(close_vol),
                    pnl=str(pnl - commission),
                    fully_closed=(reduce_position.status is PaperPositionStatus.CLOSED),
                )
            )
            return VirtualBrokerResult(
                order=order,
                position=reduce_position,
                trade=trade,
                accepted=True,
                filled=True,
            )

        position = PaperPosition.open_position(
            user_id=order.user_id,
            symbol=order.symbol,
            side=order.side,
            volume=order.volume,
            entry_price=fill_price,
            stop_loss=order.stop_loss,
            take_profit=order.take_profit,
            commission=commission,
            order_id=order.id,
            opened_at=now,
            entity_id=uuid4(),
        )
        portfolio.debit_commission(commission)
        order.fill(
            fill_price=fill_price,
            filled_volume=order.volume,
            spread=spread,
            slippage=slip,
            commission=commission,
            position_id=position.id,
            at=now,
        )
        self._events.append(
            PaperOrderFilled(
                user_id=order.user_id,
                order_id=order.id,
                symbol=order.symbol,
                fill_price=str(fill_price),
                filled_volume=str(order.volume),
            )
        )
        self._events.append(
            PaperTradeOpened(
                user_id=order.user_id,
                position_id=position.id,
                order_id=order.id,
                symbol=order.symbol,
                side=order.side.value,
                volume=str(order.volume),
                entry_price=str(fill_price),
            )
        )
        return VirtualBrokerResult(
            order=order,
            position=position,
            accepted=True,
            filled=True,
        )
