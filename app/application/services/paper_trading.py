"""Paper Trading Engine — live market data, simulated execution only.

Never enables EXECUTION_ENABLED. Never calls order_send().
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from app.application.services.paper_market_listener import (
    PaperMarketListener,
    PaperQuote,
)
from app.application.services.virtual_broker import VirtualBroker, VirtualBrokerResult
from app.domain.entities.paper import (
    PaperOrder,
    PaperPerformance,
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


@dataclass(frozen=True, slots=True)
class PlacePaperOrderInput:
    user_id: UUID
    symbol: str
    side: str
    order_type: str = "market"
    volume: Decimal = Decimal("0.10")
    price: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    client_order_id: str = ""
    reduce_position_id: UUID | None = None
    initial_balance: Decimal = Decimal("10000")


@dataclass(frozen=True, slots=True)
class PlacePaperOrderResult:
    order: PaperOrder
    position: PaperPosition | None
    trade: PaperTrade | None
    portfolio: PaperPortfolio
    quote: PaperQuote


@dataclass
class PaperTradingEngine:
    """Orchestrates paper orders against live MT5 quotes via Virtual Broker."""

    market_listener: PaperMarketListener
    broker: VirtualBroker = field(default_factory=VirtualBroker)
    _events: list[DomainEvent] = field(default_factory=list, init=False)
    # In-process portfolios keyed by user (also persisted via UoW)
    _portfolios: dict[UUID, PaperPortfolio] = field(default_factory=dict, init=False)

    def drain_events(self) -> list[DomainEvent]:
        events = list(self._events)
        self._events.clear()
        events.extend(self.broker.drain_events())
        return events

    def get_or_create_portfolio(
        self,
        user_id: UUID,
        *,
        initial_balance: Decimal = Decimal("10000"),
        existing: PaperPortfolio | None = None,
    ) -> PaperPortfolio:
        if existing is not None:
            self._portfolios[user_id] = existing
            return existing
        if user_id in self._portfolios:
            return self._portfolios[user_id]
        portfolio = PaperPortfolio.create(
            user_id=user_id, initial_balance=initial_balance
        )
        self._portfolios[user_id] = portfolio
        return portfolio

    def place_order(
        self,
        command: PlacePaperOrderInput,
        *,
        portfolio: PaperPortfolio | None = None,
        positions: list[PaperPosition] | None = None,
        pending_orders: list[PaperOrder] | None = None,
    ) -> PlacePaperOrderResult:
        """Place a paper order using the latest MT5 quote (simulated fill)."""
        side = PaperOrderSide(command.side.strip().lower())
        order_type = PaperOrderType(command.order_type.strip().lower())
        port = self.get_or_create_portfolio(
            command.user_id,
            initial_balance=command.initial_balance,
            existing=portfolio,
        )

        # Refresh market data: tick + symbol update
        self.market_listener.symbol_update(command.symbol)
        quote = self.market_listener.latest_tick(command.symbol)
        _ = self.market_listener.latest_candle(command.symbol)

        # Mark open positions to market before margin checks
        open_positions = [
            p
            for p in (positions or [])
            if p.status
            in {PaperPositionStatus.OPENED, PaperPositionStatus.PARTIALLY_CLOSED}
        ]
        self._mark_positions(open_positions, quote=quote, portfolio=port)

        # Try fill any pending limit/stop for this user/symbol first
        for pending in pending_orders or []:
            if pending.symbol != command.symbol.strip().upper():
                continue
            if pending.status is not PaperOrderStatus.ACCEPTED:
                continue
            filled = self.broker.try_fill_pending(pending, quote=quote, portfolio=port)
            if filled is not None and filled.filled:
                self._events.extend(self.broker.drain_events())

        order = PaperOrder.create(
            user_id=command.user_id,
            symbol=command.symbol,
            side=side,
            order_type=order_type,
            volume=command.volume,
            requested_price=command.price,
            stop_loss=command.stop_loss,
            take_profit=command.take_profit,
            client_order_id=command.client_order_id,
        )

        reduce: PaperPosition | None = None
        if command.reduce_position_id is not None:
            for pos in open_positions:
                if pos.id == command.reduce_position_id:
                    reduce = pos
                    break
            if reduce is None:
                order.reject(reason="reduce_position_id not found or not open")
                self._events.extend(self.broker.drain_events())
                from app.domain.events.paper import PaperOrderRejected

                self._events.append(
                    PaperOrderRejected(
                        user_id=command.user_id,
                        order_id=order.id,
                        symbol=order.symbol,
                        reason=order.rejection_reason,
                    )
                )
                return PlacePaperOrderResult(
                    order=order,
                    position=None,
                    trade=None,
                    portfolio=port,
                    quote=quote,
                )

        result: VirtualBrokerResult = self.broker.submit(
            order,
            quote=quote,
            portfolio=port,
            reduce_position=reduce,
        )
        self._events.extend(self.broker.drain_events())

        # Re-mark after fill
        if (
            result.position is not None
            and result.position.status is not PaperPositionStatus.CLOSED
            and result.position not in open_positions
        ):
            open_positions.append(result.position)
        self._mark_positions(open_positions, quote=quote, portfolio=port)

        return PlacePaperOrderResult(
            order=result.order,
            position=result.position,
            trade=result.trade,
            portfolio=port,
            quote=quote,
        )

    def refresh_positions(
        self,
        *,
        user_id: UUID,
        positions: list[PaperPosition],
        portfolio: PaperPortfolio,
        symbol: str | None = None,
    ) -> tuple[list[PaperPosition], PaperPortfolio, PaperQuote | None]:
        """Mark positions to latest MT5 quotes and update portfolio."""
        quote: PaperQuote | None = None
        symbols = {p.symbol for p in positions}
        if symbol:
            symbols.add(symbol.strip().upper())
        for sym in symbols:
            quote = self.market_listener.latest_tick(sym)
            for pos in positions:
                if pos.symbol == sym and pos.status in {
                    PaperPositionStatus.OPENED,
                    PaperPositionStatus.PARTIALLY_CLOSED,
                }:
                    # SL/TP auto-close against tick
                    self._check_sl_tp(pos, quote=quote, portfolio=portfolio)
        open_left = [
            p
            for p in positions
            if p.status
            in {PaperPositionStatus.OPENED, PaperPositionStatus.PARTIALLY_CLOSED}
        ]
        if quote is not None:
            self._mark_positions(open_left, quote=quote, portfolio=portfolio)
        elif open_left:
            # Mark with last known current prices
            floating = sum((p.floating_pnl for p in open_left), Decimal("0"))
            margin = self._margin_for(open_left)
            portfolio.mark_to_market(floating, margin=margin)
        self._portfolios[user_id] = portfolio
        return positions, portfolio, quote

    def compute_performance(
        self,
        *,
        portfolio: PaperPortfolio,
        trades: list[PaperTrade],
    ) -> PaperPerformance:
        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl < 0]
        total = len(trades)
        win_count = len(wins)
        loss_count = len(losses)
        win_rate = (
            Decimal(win_count) / Decimal(total) * Decimal("100")
            if total
            else Decimal("0")
        )
        gross_profit = sum((t.pnl for t in wins), Decimal("0"))
        gross_loss = abs(sum((t.pnl for t in losses), Decimal("0")))
        pf: Decimal | None
        if gross_loss > 0:
            pf = (gross_profit / gross_loss).quantize(Decimal("0.0001"))
        elif gross_profit > 0:
            pf = Decimal("999")
        else:
            pf = None
        expectancy = (
            (sum((t.pnl for t in trades), Decimal("0")) / Decimal(total)).quantize(
                Decimal("0.0001")
            )
            if total
            else Decimal("0")
        )
        return PaperPerformance(
            balance=portfolio.balance,
            equity=portfolio.equity,
            realized_pnl=portfolio.realized_pnl,
            floating_pnl=portfolio.floating_pnl,
            max_drawdown_pct=portfolio.max_drawdown_pct,
            total_trades=total,
            win_count=win_count,
            loss_count=loss_count,
            win_rate=win_rate.quantize(Decimal("0.0001")),
            profit_factor=pf,
            expectancy=expectancy,
        )

    def _mark_positions(
        self,
        positions: list[PaperPosition],
        *,
        quote: PaperQuote,
        portfolio: PaperPortfolio,
    ) -> None:
        floating = Decimal("0")
        for pos in positions:
            if pos.status not in {
                PaperPositionStatus.OPENED,
                PaperPositionStatus.PARTIALLY_CLOSED,
            }:
                continue
            if pos.symbol == quote.symbol:
                mark = quote.bid if pos.side is PaperOrderSide.BUY else quote.ask
                floating += pos.mark(
                    mark, contract_size=self.broker.assumptions.contract_size
                )
            else:
                floating += pos.floating_pnl
        margin = self._margin_for(positions)
        portfolio.mark_to_market(floating, margin=margin)

    def _margin_for(self, positions: list[PaperPosition]) -> Decimal:
        margin = Decimal("0")
        lev = Decimal(self.broker.assumptions.leverage)
        cs = self.broker.assumptions.contract_size
        for pos in positions:
            if pos.status not in {
                PaperPositionStatus.OPENED,
                PaperPositionStatus.PARTIALLY_CLOSED,
            }:
                continue
            notional = pos.remaining_volume * cs * pos.current_price
            margin += notional / lev
        return margin

    def _check_sl_tp(
        self,
        pos: PaperPosition,
        *,
        quote: PaperQuote,
        portfolio: PaperPortfolio,
    ) -> PaperTrade | None:
        if pos.symbol != quote.symbol:
            return None
        if pos.status not in {
            PaperPositionStatus.OPENED,
            PaperPositionStatus.PARTIALLY_CLOSED,
        }:
            return None
        hit_sl = False
        hit_tp = False
        exit_price = quote.mid
        if pos.side is PaperOrderSide.BUY:
            mark = quote.bid
            if pos.stop_loss is not None and mark <= pos.stop_loss:
                hit_sl = True
                exit_price = pos.stop_loss
            elif pos.take_profit is not None and mark >= pos.take_profit:
                hit_tp = True
                exit_price = pos.take_profit
        else:
            mark = quote.ask
            if pos.stop_loss is not None and mark >= pos.stop_loss:
                hit_sl = True
                exit_price = pos.stop_loss
            elif pos.take_profit is not None and mark <= pos.take_profit:
                hit_tp = True
                exit_price = pos.take_profit
        if not hit_sl and not hit_tp:
            return None
        vol = pos.remaining_volume
        commission = self.broker.assumptions.commission_per_lot * vol
        pnl = pos.close_partial(
            close_volume=vol,
            exit_price=exit_price,
            contract_size=self.broker.assumptions.contract_size,
            commission=commission,
        )
        portfolio.apply_realized(pnl, fee=commission)
        trade = PaperTrade.record(
            user_id=pos.user_id,
            symbol=pos.symbol,
            side=pos.side,
            volume=vol,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            pnl=pnl - commission,
            commission=commission,
            position_id=pos.id,
            opened_at=pos.opened_at,
        )
        from app.domain.events.paper import PaperTradeClosed

        self._events.append(
            PaperTradeClosed(
                user_id=pos.user_id,
                position_id=pos.id,
                symbol=pos.symbol,
                volume=str(vol),
                pnl=str(pnl - commission),
                fully_closed=True,
            )
        )
        return trade
