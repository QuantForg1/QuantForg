"""MT5 order validation service — prepare and check only, never order_send."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from uuid import UUID

from app.domain.entities.mt5_order import (
    OrderConstraints,
    OrderIntent,
    TradeRequest,
    TradeValidation,
)
from app.domain.enums.order import OrderSide, OrderType
from app.domain.execution_engine.reasons import humanize_reason, humanize_reasons
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
from app.domain.value_objects.mt5_order import LotSize
from app.infrastructure.brokers.mt5.adapter import MT5Adapter


def _align_volume(volume: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        return volume
    steps = (volume / step).quantize(Decimal("1"), rounding=ROUND_DOWN)
    return (steps * step).normalize()


def _filling_label(mode: int, *, execution_mode: str = "") -> str:
    parts: list[str] = []
    if mode & 1:
        parts.append("FOK")
    if mode & 2:
        parts.append("IOC")
    if mode & 4:
        parts.append("RETURN")
    if parts:
        return "+".join(parts)
    # No SYMBOL_FILLING_* bits — Market/Exchange typically require RETURN.
    if (execution_mode or "").lower() in {"market", "exchange"}:
        return "RETURN (exec default)"
    return "FOK/IOC/RETURN (probe)"


@dataclass
class MT5OrderValidationService:
    """Build and validate MT5 trade requests without executing them."""

    adapter: MT5Adapter
    _last_check: MT5OrderCheckResult | None = field(default=None, init=False)

    def constraints_for(self, symbol: str) -> OrderConstraints:
        """Load live broker constraints from MT5 — never invent lot/stops rules."""
        info = self.adapter.symbol_info(symbol)
        min_vol = Decimal(str(getattr(info, "volume_min", None) or "0.01"))
        max_vol = Decimal(str(getattr(info, "volume_max", None) or "100"))
        step = Decimal(str(getattr(info, "volume_step", None) or "0.01"))
        if min_vol <= 0:
            min_vol = step if step > 0 else Decimal("0.01")
        if max_vol < min_vol:
            max_vol = min_vol
        if step <= 0:
            step = Decimal("0.01")
        trade_mode = str(getattr(info, "trade_mode", "full") or "full")
        trade_allowed = bool(
            getattr(info, "trade_allowed", trade_mode not in {"disabled", "0"})
        )
        market_open = bool(getattr(info, "market_open", True))
        return OrderConstraints(
            symbol=info.code,
            min_volume=min_vol,
            max_volume=max_vol,
            volume_step=step,
            stops_level=int(getattr(info, "stops_level", 0) or 0),
            freeze_level=int(getattr(info, "freeze_level", 0) or 0),
            trade_allowed=trade_allowed and trade_mode != "disabled",
            market_open=market_open,
            digits=int(info.digits),
            point=Decimal(str(info.point)),
            contract_size=Decimal(str(info.contract_size)),
            filling_mode=int(getattr(info, "filling_mode", 0) or 0),
            execution_mode=str(getattr(info, "execution_mode", "market") or "market"),
            trade_mode=trade_mode,
            visible=bool(getattr(info, "visible", True)),
            margin_calc_mode=str(getattr(info, "margin_calc_mode", "") or ""),
        )

    def normalize_intent(self, intent: OrderIntent) -> tuple[OrderIntent, list[str]]:
        """Safely round lot to volume_step and clamp to broker min/max."""
        notes: list[str] = []
        constraints = self.constraints_for(intent.symbol)
        raw = intent.volume.value
        aligned = _align_volume(raw, constraints.volume_step)
        if aligned < constraints.min_volume:
            aligned = constraints.min_volume
        if aligned > constraints.max_volume:
            aligned = _align_volume(constraints.max_volume, constraints.volume_step)
            if aligned > constraints.max_volume:
                aligned = constraints.max_volume
        if aligned != raw:
            notes.append(
                f"Lot size normalized from {raw} to {aligned} "
                f"(step {constraints.volume_step})."
            )
        if aligned == raw:
            return intent, notes
        return (
            OrderIntent(
                symbol=intent.symbol,
                side=intent.side,
                order_type=intent.order_type,
                volume=LotSize.of(str(aligned)),
                price=intent.price,
                stop_loss=intent.stop_loss,
                take_profit=intent.take_profit,
                slippage=intent.slippage,
                magic=intent.magic,
                comment=intent.comment,
                position=intent.position,
                order_ticket=intent.order_ticket,
                oms_kind=intent.oms_kind,
            ),
            notes,
        )

    def build_order_request(self, intent: OrderIntent) -> TradeRequest:
        normalized, _ = self.normalize_intent(intent)
        intent = normalized
        oms = intent.oms_kind
        if oms in {"sltp", "modify_sltp"}:
            return TradeRequest(
                symbol=intent.symbol,
                action="sltp",
                volume=intent.volume.value,
                price=Decimal("0"),
                stop_loss=(
                    intent.stop_loss.value if intent.stop_loss else Decimal("0")
                ),
                take_profit=(
                    intent.take_profit.value if intent.take_profit else Decimal("0")
                ),
                deviation=intent.slippage.value,
                magic=intent.magic.value,
                comment=intent.comment or "quantforg-sltp",
                position=int(intent.position or 0),
                order_ticket=int(intent.order_ticket or 0),
                oms_kind="sltp",
            )
        if oms == "modify_pending":
            return TradeRequest(
                symbol=intent.symbol,
                action="buy_limit",  # placeholder; gateway uses TRADE_ACTION_MODIFY
                volume=intent.volume.value,
                price=intent.price or Decimal("0"),
                stop_loss=(
                    intent.stop_loss.value if intent.stop_loss else Decimal("0")
                ),
                take_profit=(
                    intent.take_profit.value if intent.take_profit else Decimal("0")
                ),
                deviation=intent.slippage.value,
                magic=intent.magic.value,
                comment=intent.comment or "quantforg-mod",
                position=0,
                order_ticket=int(intent.order_ticket or 0),
                oms_kind="modify_pending",
            )

        tick = self.adapter.latest_tick(intent.symbol)
        constraints = self.constraints_for(intent.symbol)
        digits = max(0, int(constraints.digits))
        if intent.order_type is OrderType.MARKET:
            # BUY uses ASK, SELL uses BID — never mid / stale client price.
            raw = tick.ask if intent.side is OrderSide.BUY else tick.bid
            quant = Decimal(1).scaleb(-digits)
            price = Decimal(str(raw)).quantize(quant, rounding=ROUND_HALF_UP)
        else:
            raw_price = intent.price if intent.price is not None else tick.mid
            quant = Decimal(1).scaleb(-digits)
            price = Decimal(str(raw_price)).quantize(quant, rounding=ROUND_HALF_UP)

        action = self._action_for(intent)
        # Select filling from symbol_info.filling_mode — never hardcode IOC.
        if constraints.filling_mode & 2:
            filling = "ioc"
        elif constraints.filling_mode & 1:
            filling = "fok"
        elif constraints.filling_mode & 4 or (
            constraints.execution_mode or ""
        ).lower() in {"market", "exchange"}:
            filling = "return"
        else:
            filling = "fok"

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
            type_filling=filling,
            type_time="gtc",
            position=int(intent.position or 0),
            order_ticket=int(intent.order_ticket or 0),
            oms_kind=oms
            or (
                "close"
                if intent.position > 0 and intent.order_type is OrderType.MARKET
                else ""
            ),
        )

    def validate_symbol(
        self, intent: OrderIntent, constraints: OrderConstraints
    ) -> tuple[bool, str]:
        if intent.symbol != constraints.symbol:
            return False, "symbol mismatch"
        if not constraints.visible:
            return False, f"Symbol {constraints.symbol} is not visible in Market Watch."
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
            return (
                False,
                f"Lot size below minimum {constraints.min_volume}.",
            )
        if volume > constraints.max_volume:
            return (
                False,
                f"Lot size above maximum {constraints.max_volume}.",
            )
        aligned = _align_volume(volume, constraints.volume_step)
        if aligned != volume:
            return (
                False,
                f"Lot size must be {constraints.volume_step} increments "
                f"(got {volume}).",
            )
        return True, "volume ok"

    def validate_stops(
        self,
        intent: OrderIntent,
        constraints: OrderConstraints,
        *,
        entry_price: Decimal,
    ) -> tuple[bool, str]:
        if intent.oms_kind in {"sltp", "modify_sltp"} and entry_price <= 0:
            tick = self.adapter.latest_tick(intent.symbol)
            entry_price = tick.bid if intent.side is OrderSide.SELL else tick.ask
        min_distance = constraints.point * Decimal(constraints.stops_level)
        if intent.stop_loss is not None and intent.stop_loss.value > 0:
            dist = abs(entry_price - intent.stop_loss.value)
            if constraints.stops_level > 0 and dist < min_distance:
                return (
                    False,
                    f"Stop loss too close — broker stop level is "
                    f"{constraints.stops_level} points.",
                )
            if intent.side is OrderSide.BUY and intent.stop_loss.value >= entry_price:
                return False, "Buy stop loss must be below entry price."
            if intent.side is OrderSide.SELL and intent.stop_loss.value <= entry_price:
                return False, "Sell stop loss must be above entry price."
        if intent.take_profit is not None and intent.take_profit.value > 0:
            dist = abs(intent.take_profit.value - entry_price)
            if constraints.stops_level > 0 and dist < min_distance:
                return (
                    False,
                    f"Take profit too close — broker stop level is "
                    f"{constraints.stops_level} points.",
                )
            if intent.side is OrderSide.BUY and intent.take_profit.value <= entry_price:
                return False, "Buy take profit must be above entry price."
            if (
                intent.side is OrderSide.SELL
                and intent.take_profit.value >= entry_price
            ):
                return False, "Sell take profit must be below entry price."
        return True, "stops ok"

    def validate_margin(
        self, request: TradeRequest, *, free_margin: Decimal
    ) -> tuple[bool, str, MT5MarginResult]:
        if request.oms_kind in {"sltp", "modify_sltp"}:
            return (
                True,
                "margin ok",
                MT5MarginResult(
                    margin=Decimal("0"), retcode=RETCODE_DONE, comment="sltp"
                ),
            )
        margin_res = self.adapter.order_calc_margin(request)
        if margin_res.margin > free_margin:
            return False, "Insufficient free margin.", margin_res
        return True, "margin ok", margin_res

    def validate_market_state(self, constraints: OrderConstraints) -> tuple[bool, str]:
        if not constraints.trade_allowed or constraints.trade_mode in {
            "disabled",
            "closeonly",
        }:
            if constraints.trade_mode == "closeonly":
                return False, "Symbol is close-only — new entries are blocked."
            return False, "Trading is disabled for this symbol."
        if not constraints.market_open:
            return False, "Market is closed."
        return True, "market open"

    def validate_order(self, intent: OrderIntent) -> TradeValidation:
        """Full validation pipeline + MT5 order_check (no order_send)."""
        dummy_user = UUID(int=0)
        messages: list[str] = []
        checks: dict[str, bool] = {}
        rejection_component = ""

        try:
            intent, norm_notes = self.normalize_intent(intent)
            messages.extend(norm_notes)
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
                messages=[humanize_reason(f"symbol lookup failed: {exc}")],
                checks={"symbol": False},
            )

        ok_sym, msg_sym = self.validate_symbol(intent, constraints)
        checks["symbol"] = ok_sym
        messages.append(msg_sym)
        if not ok_sym and not rejection_component:
            rejection_component = "validation.symbol"

        ok_vol, msg_vol = self.validate_volume(intent, constraints)
        checks["volume"] = ok_vol
        messages.append(msg_vol)
        if not ok_vol and not rejection_component:
            rejection_component = "validation.volume"

        ok_mkt, msg_mkt = self.validate_market_state(constraints)
        is_manage = intent.oms_kind in {
            "sltp",
            "modify_sltp",
            "close",
            "partial_close",
        } or (intent.position > 0 and intent.order_type is OrderType.MARKET)
        if is_manage and constraints.trade_mode == "closeonly":
            ok_mkt, msg_mkt = True, "close-only — manage allowed"
        elif is_manage and intent.oms_kind in {"sltp", "modify_sltp"}:
            ok_mkt, msg_mkt = True, "SL/TP manage allowed"
        checks["market_state"] = ok_mkt
        messages.append(msg_mkt)
        if not ok_mkt and not rejection_component:
            rejection_component = "validation.market"

        request = self.build_order_request(intent)
        ok_stops, msg_stops = self.validate_stops(
            intent, constraints, entry_price=request.price
        )
        checks["stops"] = ok_stops
        messages.append(msg_stops)
        if not ok_stops and not rejection_component:
            rejection_component = "validation.stops"

        account = self.adapter.account_info()
        free = getattr(account, "free_margin", None)
        if free is None:
            free = getattr(account, "margin_free", None)
        if free is None:
            free = account.equity
        ok_margin, msg_margin, margin_res = self.validate_margin(
            request, free_margin=Decimal(str(free))
        )
        checks["margin"] = ok_margin
        messages.append(msg_margin)
        if not ok_margin and not rejection_component:
            rejection_component = "validation.margin"

        check_res = self.adapter.order_check(request)
        self._last_check = check_res
        checks["order_check"] = check_res.ok
        mt5_msg = check_res.comment.strip() or "no comment"
        messages.append(f"MT5 order_check: {mt5_msg} (retcode {check_res.retcode})")
        if not check_res.ok and not rejection_component:
            rejection_component = "mt5.order_check"

        profit_res = (
            MT5ProfitResult(profit=Decimal("0"), retcode=RETCODE_DONE, comment="sltp")
            if request.oms_kind in {"sltp", "modify_sltp"}
            else self.adapter.order_calc_profit(request)
        )
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

        primary: list[str] = []
        if not ok_vol:
            primary.append(humanize_reason(msg_vol))
        if not ok_stops:
            primary.append(humanize_reason(msg_stops))
        if not ok_margin:
            primary.append(humanize_reason(msg_margin))
        if not ok_mkt:
            primary.append(humanize_reason(msg_mkt))
        if not ok_sym:
            primary.append(humanize_reason(msg_sym))
        if not check_res.ok:
            # Prefer exact MT5 comment when present
            primary.append(
                humanize_reason(mt5_msg)
                if mt5_msg and mt5_msg.lower() != "done"
                else humanize_reason(f"order_check retcode {check_res.retcode}")
            )
        human_messages = primary + [
            h for h in humanize_reasons(messages) if h not in primary
        ]

        snapshot = request.to_dict()
        snapshot["constraints"] = constraints.to_dict()
        snapshot["rejection_component"] = rejection_component
        snapshot["filling_modes"] = _filling_label(
            constraints.filling_mode, execution_mode=constraints.execution_mode
        )
        snapshot["normalized_volume"] = str(intent.volume.value)
        snapshot["order_check_retcode"] = check_res.retcode
        snapshot["order_check_comment"] = check_res.comment

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
            messages=human_messages,
            checks=checks,
            request_snapshot=snapshot,
        )

    def calculate(
        self, intent: OrderIntent
    ) -> tuple[TradeRequest, MT5MarginResult, MT5ProfitResult]:
        intent, _ = self.normalize_intent(intent)
        request = self.build_order_request(intent)
        if request.oms_kind in {"sltp", "modify_sltp"}:
            return (
                request,
                MT5MarginResult(
                    margin=Decimal("0"), retcode=RETCODE_DONE, comment="sltp"
                ),
                MT5ProfitResult(
                    profit=Decimal("0"), retcode=RETCODE_DONE, comment="sltp"
                ),
            )
        margin = self.adapter.order_calc_margin(request)
        profit = self.adapter.order_calc_profit(request)
        return request, margin, profit

    @staticmethod
    def _action_for(intent: OrderIntent) -> str:
        if intent.oms_kind in {"sltp", "modify_sltp"}:
            return "sltp"
        if intent.order_type is OrderType.MARKET:
            return "buy" if intent.side is OrderSide.BUY else "sell"
        if intent.order_type is OrderType.LIMIT:
            return "buy_limit" if intent.side is OrderSide.BUY else "sell_limit"
        if intent.order_type is OrderType.STOP:
            return "buy_stop" if intent.side is OrderSide.BUY else "sell_stop"
        return "buy_stop" if intent.side is OrderSide.BUY else "sell_stop"
