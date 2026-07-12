"""MT5 order validation service — prepare and check only, never order_send."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_DOWN, Decimal

from app.domain.entities.mt5_order import (
    OrderConstraints,
    OrderIntent,
    TradeRequest,
    TradeValidation,
)
from app.domain.enums.order import OrderSide, OrderType
from app.domain.interfaces.mt5_order import (
    RETCODE_DONE,
    RETCODE_INVALID,
    RETCODE_INVALID_STOPS,
    RETCODE_INVALID_VOLUME,
    RETCODE_MARKET_CLOSED,
    RETCODE_NO_MONEY,
    RETCODE_TRADE_DISABLED,
    MT5MarginResult,
    MT5OrderCheckResult,
    MT5ProfitResult,
)
from app.infrastructure.brokers.mt5.adapter import MT5Adapter


@dataclass
class MT5OrderValidationService:
    """Build and validate MT5 trade requests without executing them."""

    adapter: MT5Adapter
    _last_check: MT5OrderCheckResult | None = field(default=None, init=False)

    def constraints_for(self, symbol: str) -> OrderConstraints:
        info = self.adapter.symbol_info(symbol)
        # Mock defaults tuned per digits
        min_vol = Decimal("0.01")
        max_vol = Decimal("100")
        step = Decimal("0.01")
        if info.digits <= 2:
            min_vol = Decimal("0.01")
            step = Decimal("0.01")
        return OrderConstraints(
            symbol=info.code,
            min_volume=min_vol,
            max_volume=max_vol,
            volume_step=step,
            stops_level=10,
            freeze_level=0,
            trade_allowed=info.trade_mode != "disabled",
            market_open=True,
            digits=info.digits,
            point=info.point,
            contract_size=info.contract_size,
        )

    def build_order_request(self, intent: OrderIntent) -> TradeRequest:
        tick = self.adapter.latest_tick(intent.symbol)
        if intent.order_type is OrderType.MARKET:
            price = tick.ask if intent.side is OrderSide.BUY else tick.bid
        else:
            price = intent.price if intent.price is not None else tick.mid

        action = self._action_for(intent)
        return TradeRequest(
            symbol=intent.symbol,
            action=action,
            volume=intent.volume.value,
            price=price,
            stop_loss=(intent.stop_loss.value if intent.stop_loss else Decimal("0")),
            take_profit=(
                intent.take_profit.value if intent.take_profit else Decimal("0")
            ),
            deviation=intent.slippage.value,
            magic=intent.magic.value,
            comment=intent.comment or "quantforg-validate",
        )

    def validate_symbol(
        self, intent: OrderIntent, constraints: OrderConstraints
    ) -> tuple[bool, str]:
        if intent.symbol != constraints.symbol:
            return False, "symbol mismatch"
        try:
            self.adapter.symbol_info(intent.symbol)
        except (OSError, RuntimeError, ValueError) as exc:
            return False, f"unknown symbol: {exc}"
        return True, "symbol ok"

    def validate_volume(
        self, intent: OrderIntent, constraints: OrderConstraints
    ) -> tuple[bool, str]:
        volume = intent.volume.value
        if volume < constraints.min_volume:
            return False, f"volume below min {constraints.min_volume}"
        if volume > constraints.max_volume:
            return False, f"volume above max {constraints.max_volume}"
        # Step alignment
        steps = (volume / constraints.volume_step).quantize(
            Decimal("1"), rounding=ROUND_DOWN
        )
        aligned = steps * constraints.volume_step
        if aligned != volume:
            return False, f"volume must align to step {constraints.volume_step}"
        return True, "volume ok"

    def validate_stops(
        self,
        intent: OrderIntent,
        constraints: OrderConstraints,
        *,
        entry_price: Decimal,
    ) -> tuple[bool, str]:
        min_distance = constraints.point * Decimal(constraints.stops_level)
        if intent.stop_loss is not None and intent.stop_loss.value > 0:
            dist = abs(entry_price - intent.stop_loss.value)
            if dist < min_distance:
                return False, "stop loss too close to price"
            if intent.side is OrderSide.BUY and intent.stop_loss.value >= entry_price:
                return False, "buy stop loss must be below entry"
            if intent.side is OrderSide.SELL and intent.stop_loss.value <= entry_price:
                return False, "sell stop loss must be above entry"
        if intent.take_profit is not None and intent.take_profit.value > 0:
            dist = abs(intent.take_profit.value - entry_price)
            if dist < min_distance:
                return False, "take profit too close to price"
            if intent.side is OrderSide.BUY and intent.take_profit.value <= entry_price:
                return False, "buy take profit must be above entry"
            if (
                intent.side is OrderSide.SELL
                and intent.take_profit.value >= entry_price
            ):
                return False, "sell take profit must be below entry"
        return True, "stops ok"

    def validate_margin(
        self, request: TradeRequest, *, free_margin: Decimal
    ) -> tuple[bool, str, MT5MarginResult]:
        margin_res = self.adapter.order_calc_margin(request)
        if margin_res.margin > free_margin:
            return False, "insufficient free margin", margin_res
        return True, "margin ok", margin_res

    def validate_market_state(self, constraints: OrderConstraints) -> tuple[bool, str]:
        if not constraints.trade_allowed:
            return False, "trading disabled for symbol"
        if not constraints.market_open:
            return False, "market closed"
        return True, "market open"

    def validate_order(self, intent: OrderIntent) -> TradeValidation:
        """Full validation pipeline + MT5 order_check (no order_send)."""
        from uuid import UUID

        # Placeholder user_id — callers overwrite via use case persistence
        dummy_user = UUID(int=0)
        messages: list[str] = []
        checks: dict[str, bool] = {}

        try:
            constraints = self.constraints_for(intent.symbol)
        except (OSError, RuntimeError, ValueError) as exc:
            return TradeValidation.record(
                user_id=dummy_user,
                symbol=intent.symbol,
                side=intent.side.value,
                order_type=intent.order_type.value,
                volume=intent.volume.value,
                valid=False,
                retcode=RETCODE_INVALID,
                messages=[f"symbol lookup failed: {exc}"],
                checks={"symbol": False},
            )

        ok_sym, msg_sym = self.validate_symbol(intent, constraints)
        checks["symbol"] = ok_sym
        messages.append(msg_sym)

        ok_vol, msg_vol = self.validate_volume(intent, constraints)
        checks["volume"] = ok_vol
        messages.append(msg_vol)

        ok_mkt, msg_mkt = self.validate_market_state(constraints)
        checks["market_state"] = ok_mkt
        messages.append(msg_mkt)

        request = self.build_order_request(intent)
        ok_stops, msg_stops = self.validate_stops(
            intent, constraints, entry_price=request.price
        )
        checks["stops"] = ok_stops
        messages.append(msg_stops)

        account = self.adapter.account_info()
        free = account.equity  # simplified free margin proxy
        ok_margin, msg_margin, margin_res = self.validate_margin(
            request, free_margin=free
        )
        checks["margin"] = ok_margin
        messages.append(msg_margin)

        check_res = self.adapter.order_check(request)
        self._last_check = check_res
        checks["order_check"] = check_res.ok
        messages.append(f"order_check: {check_res.comment} ({check_res.retcode})")

        profit_res = self.adapter.order_calc_profit(request)
        valid = all(checks.values()) and check_res.ok

        retcode = check_res.retcode
        if not ok_vol:
            retcode = RETCODE_INVALID_VOLUME
        elif not ok_stops:
            retcode = RETCODE_INVALID_STOPS
        elif not ok_margin:
            retcode = RETCODE_NO_MONEY
        elif not ok_mkt:
            retcode = (
                RETCODE_MARKET_CLOSED
                if not constraints.market_open
                else RETCODE_TRADE_DISABLED
            )
        elif valid:
            retcode = RETCODE_DONE

        return TradeValidation.record(
            user_id=dummy_user,
            symbol=intent.symbol,
            side=intent.side.value,
            order_type=intent.order_type.value,
            volume=intent.volume.value,
            valid=valid,
            retcode=retcode,
            expected_margin=margin_res.margin,
            estimated_profit=profit_res.profit,
            messages=messages,
            checks=checks,
            request_snapshot=request.to_dict(),
        )

    def calculate(
        self, intent: OrderIntent
    ) -> tuple[TradeRequest, MT5MarginResult, MT5ProfitResult]:
        request = self.build_order_request(intent)
        margin = self.adapter.order_calc_margin(request)
        profit = self.adapter.order_calc_profit(request)
        return request, margin, profit

    @staticmethod
    def _action_for(intent: OrderIntent) -> str:
        if intent.order_type is OrderType.MARKET:
            return "buy" if intent.side is OrderSide.BUY else "sell"
        if intent.order_type is OrderType.LIMIT:
            return "buy_limit" if intent.side is OrderSide.BUY else "sell_limit"
        if intent.order_type is OrderType.STOP:
            return "buy_stop" if intent.side is OrderSide.BUY else "sell_stop"
        # STOP_LIMIT treated as stop for mock mapping
        return "buy_stop" if intent.side is OrderSide.BUY else "sell_stop"
