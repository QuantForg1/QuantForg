"""Connect M1 decisions to the existing submit path. Flags stay off.

When ``QUANTFORG_M1_MICRO_SCALPING`` is off this function returns before it
reads the adapter, the book, or the submit port. The primary strategy cycle
is unchanged. Live submission also requires ``QUANTFORG_M1_MICRO_LIVE_SUBMIT``
and the caller's execution switch. This module never invents a stop or a
signal, and it never closes a position that M1 did not open.

An opposite primary direction submits nothing. The same direction submits
at most once, through the guarded port already used by the primary.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from app.domain.institutional_trading.m1_micro.config import (
    m1_live_submit_enabled,
    m1_micro_enabled,
)
from app.domain.institutional_trading.m1_micro.engine import evaluate_m1
from app.domain.institutional_trading.m1_micro.signals import Bar
from app.domain.institutional_trading.operations.min_lot_feasibility import (
    entry_book_exposure,
)
from app.domain.institutional_trading.operations.quantforg_position_cap import (
    QUANTFORG_MAGIC,
)
from app.domain.institutional_trading.owner_live_limits import (
    OWNER_MAX_LOT,
    max_aggregate_risk_usd,
    max_planned_risk_usd,
    planned_risk_usd,
    resolve_entry_commission,
    reward_risk_after_spread,
)
from app.domain.institutional_trading.runtime_policy import active_min_reward_risk
from app.domain.institutional_trading.unified_decision import (
    NormalizedSignal,
    resolve_unified,
)
from app.domain.trading.gold_only import is_gold_symbol

_HUNDRED = Decimal("100")


def consider_m1_complement(
    *,
    adapter: Any,
    account: Any,
    snapshot: Any,
    execution_enabled: bool,
    primary_forwarded: bool,
    submit_market: Any = None,
    close_position: Any = None,
    user_id: UUID | None = None,
    login: int | None = None,
    primary_direction: str | None = None,
    primary_owns_order: bool = False,
    primary_invalidation: Decimal | None = None,
    primary_confidence: Decimal | None = None,
    primary_holding_period: str = "",
) -> dict[str, Any] | None:
    """Evaluate one M1 complement. ``None`` means the flag is off.

    A returned note is diagnostic. It is not broker confirmation. ``submitted``
    is true only after the existing submit port was called. The broker ticket,
    when present, is copied from that port's result.
    """
    if not m1_micro_enabled():
        return None
    symbol = str(getattr(snapshot, "symbol", "") or "").strip()
    note: dict[str, Any] = {
        "enabled": True,
        "live_submit": m1_live_submit_enabled(),
        "execution_enabled": bool(execution_enabled),
        "symbol": symbol,
        "action": "none",
        "reason": "",
        "submitted": False,
        "commission_known": False,
        "entry_valid": False,
    }
    if not is_gold_symbol(symbol):
        note["reason"] = "not_gold"
        return note
    bars = _m1_bars(adapter, symbol)
    if bars is None:
        note["reason"] = "m1_bars_unavailable"
        return note
    bid, ask = _quote(adapter, symbol)
    if bid is None or ask is None or bid <= 0 or ask <= 0 or ask < bid:
        note["reason"] = "quote_unusable"
        return note
    equity = _equity(account)
    positions, positions_ok = _positions(adapter)
    if not positions_ok or equity is None or equity <= 0:
        note["reason"] = "open_planned_risk_unmeasured"
        note["action"] = "none"
        decision = evaluate_m1(
            bars,
            bid=bid,
            ask=ask,
            higher_timeframe_bias=_bias(snapshot),
            open_risk_known=False,
        )
        note["action"] = decision.action
        note["reason"] = decision.reason
        return note
    book = entry_book_exposure(
        positions,
        contract_size_for=_contract,
    )
    note["external_positions"] = list(book.external_tickets)
    if book.blocked:
        note["reason"] = book.reason
        note["open_risk_known"] = False
        return note
    open_pct = (book.measured_usd / equity * _HUNDRED) if equity > 0 else _HUNDRED
    m1_open = _m1_position(positions)
    thesis_open = m1_open is not None
    decision = evaluate_m1(
        bars,
        bid=bid,
        ask=ask,
        higher_timeframe_bias=_bias(snapshot),
        open_positions=len(positions),
        open_planned_risk_pct=open_pct,
        open_risk_known=True,
        planned_risk_pct=Decimal("0"),
        last_signal_id=_comment_signal(m1_open),
        thesis_open=thesis_open,
        side_open=_side(m1_open),
        invalidation=_stop_of(m1_open),
        target_open=_target_of(m1_open),
        slippage_points=Decimal("0.05"),
        commission_points=Decimal("0"),
    )
    note["action"] = decision.action
    note["reason"] = decision.reason
    note["setup"] = decision.setup
    note["signal_id"] = decision.signal_id
    note["stop"] = str(decision.stop) if decision.stop is not None else None
    note["target"] = str(decision.target) if decision.target is not None else None
    note["estimated_cost"] = str(decision.cost)
    if decision.action == "exit":
        _maybe_close(
            note,
            position=m1_open,
            execution_enabled=execution_enabled,
            close_position=close_position,
            user_id=user_id,
            login=login,
            symbol=symbol,
        )
        return note
    if decision.action not in {"buy", "sell"}:
        return note
    if decision.stop is None or decision.target is None or decision.stop <= 0:
        note["reason"] = "stop_missing"
        return note
    entry = ask if decision.action == "buy" else bid
    if decision.action == "buy" and decision.stop >= bid:
        note["reason"] = "stop_wrong_side"
        return note
    if decision.action == "sell" and decision.stop <= ask:
        note["reason"] = "stop_wrong_side"
        return note
    spread = ask - bid
    stop_distance = abs(entry - decision.stop)
    # Same formula OMS enforces. Stop-only dollars can sit under the cap
    # while stop plus spread, rounded up, does not. Do not shrink the stop.
    fee = resolve_entry_commission(symbol, None)
    if fee is None or fee < 0:
        note["reason"] = (
            "OWNER_COMMISSION_UNKNOWN" if fee is None else "OWNER_COMMISSION_INVALID"
        )
        return note
    risk = planned_risk_usd(
        stop_distance=stop_distance,
        spread=spread,
        contract_size=_contract(symbol),
        volume=OWNER_MAX_LOT,
        commission=fee,
    )
    trade_cap = max_planned_risk_usd(equity)
    book_cap = max_aggregate_risk_usd(equity)
    remaining = book_cap - book.measured_usd
    note["planned_risk_usd"] = str(risk)
    note["remaining_risk_usd"] = str(remaining)
    note["commission_usd"] = format(fee, "f")
    if risk <= 0 or trade_cap <= 0 or risk > trade_cap or risk > remaining:
        note["reason"] = "combined_planned_risk_above_cap"
        return note
    risk_pct = risk / equity * _HUNDRED
    if risk_pct + open_pct > (book_cap / equity * _HUNDRED):
        note["reason"] = "combined_planned_risk_above_cap"
        return note
    note["entry_valid"] = True
    if _coordinated_elsewhere(
        note,
        decision=decision,
        primary_direction=primary_direction,
        primary_forwarded=primary_forwarded,
        primary_owns_order=primary_owns_order,
        primary_invalidation=primary_invalidation,
        primary_confidence=primary_confidence,
        primary_holding_period=primary_holding_period,
    ):
        return note
    if (
        not m1_live_submit_enabled()
        or not execution_enabled
        or primary_forwarded
        or submit_market is None
        or user_id is None
    ):
        note["reason"] = decision.reason
        note["submit_withheld"] = (
            "primary_cycle_already_forwarded"
            if primary_forwarded
            else "live_submit_not_authorized"
        )
        return note
    target_distance = abs(decision.target - entry)
    rr = reward_risk_after_spread(
        tp_distance=target_distance,
        stop_distance=stop_distance,
        spread=spread,
    )
    # The measured M1 target stays as detected. A target that does not clear
    # the owner reward:risk floor is withheld. It is not stretched.
    if rr is None or rr < active_min_reward_risk():
        note["submit_withheld"] = "OWNER_MIN_RR"
        return note
    _submit_entry(
        note,
        submit_market=submit_market,
        user_id=user_id,
        login=login,
        symbol=symbol,
        decision=decision,
    )
    return note


def _coordinated_elsewhere(
    note: dict[str, Any],
    *,
    decision: Any,
    primary_direction: str | None,
    primary_forwarded: bool,
    primary_owns_order: bool,
    primary_invalidation: Decimal | None,
    primary_confidence: Decimal | None,
    primary_holding_period: str,
) -> bool:
    """True when this M1 entry must not be submitted.

    Opposite directions wait. The primary keeps a same-direction entry when
    it already owns the cycle. A blocked primary leaves that one entry to M1.
    """
    primary = None
    if str(primary_direction or "").strip():
        primary = NormalizedSignal(
            source="primary",
            direction=str(primary_direction),
            confidence=primary_confidence,
            timeframe="primary",
            invalidation=primary_invalidation,
            holding_period=primary_holding_period,
            direction_counts_without_stop=True,
        )
    plan = resolve_unified(
        primary,
        NormalizedSignal(
            source="m1",
            direction=str(decision.action),
            confidence=None,
            timeframe="M1",
            invalidation=decision.stop,
            holding_period="m1",
        ),
        primary_executable=bool(primary_owns_order or primary_forwarded),
    )
    note["unified"] = plan.to_dict()
    if plan.submit_m1:
        return False
    if plan.reason == "direction_conflict":
        note["reason"] = "direction_conflict"
        note["submit_withheld"] = (
            "primary_cycle_already_forwarded"
            if primary_forwarded
            else "direction_conflict"
        )
        return True
    if primary_forwarded or primary_owns_order:
        note["reason"] = decision.reason
        note["submit_withheld"] = (
            "primary_cycle_already_forwarded"
            if primary_forwarded
            else "primary_owns_order"
        )
        return True
    note["reason"] = str(plan.reason or decision.reason)
    note["submit_withheld"] = str(plan.reason or "unified_decision")
    return True


def _submit_entry(
    note: dict[str, Any],
    *,
    submit_market: Any,
    user_id: UUID,
    login: int | None,
    symbol: str,
    decision: Any,
) -> None:
    from app.application.services.institutional_execution_engine import (
        parse_order_intent,
    )

    request_id = f"m1-{decision.signal_id}"[:64]
    intent = parse_order_intent(
        symbol=symbol,
        side=str(decision.action),
        order_type="market",
        volume=str(OWNER_MAX_LOT),
        stop_loss=str(decision.stop),
        take_profit=str(decision.target),
        magic=int(QUANTFORG_MAGIC),
        comment=f"m1:{decision.signal_id}"[:31],
    )
    result = submit_market(
        user_id=user_id,
        request_id=request_id,
        intent=intent,
        connected=True,
        login=login if isinstance(login, int) and login > 0 else None,
    )
    note["submitted"] = True
    note["request_id"] = request_id
    note["broker_outcome"] = str(getattr(result, "outcome", "") or "")
    note["broker_retcode"] = getattr(result, "retcode", None)
    ticket = getattr(result, "order_ticket", None) or getattr(
        result, "deal_ticket", None
    )
    note["broker_ticket"] = int(ticket) if ticket else None
    note["broker_message"] = str(getattr(result, "message", "") or "")[:300]


def _maybe_close(
    note: dict[str, Any],
    *,
    position: Any,
    execution_enabled: bool,
    close_position: Any,
    user_id: UUID | None,
    login: int | None,
    symbol: str,
) -> None:
    if position is None:
        note["reason"] = "exit_without_m1_position"
        return
    if (
        not m1_live_submit_enabled()
        or not execution_enabled
        or close_position is None
        or user_id is None
    ):
        note["submit_withheld"] = "live_submit_not_authorized"
        return
    ticket = int(getattr(position, "ticket", 0) or 0)
    volume = getattr(position, "volume", None)
    if ticket <= 0 or volume is None:
        note["reason"] = "exit_unverified"
        return
    side = _side(position)
    close_side = "sell" if side == "buy" else "buy"
    result = close_position(
        user_id=user_id,
        request_id=f"m1-exit-{ticket}"[:64],
        symbol=symbol,
        side=close_side,
        position=ticket,
        volume=Decimal(str(volume)),
        comment="m1:exit"[:31],
        connected=True,
        login=login if isinstance(login, int) and login > 0 else None,
    )
    note["submitted"] = True
    note["broker_outcome"] = str(getattr(result, "outcome", "") or "")
    note["broker_retcode"] = getattr(result, "retcode", None)
    ticket_out = getattr(result, "order_ticket", None) or getattr(
        result, "deal_ticket", None
    )
    note["broker_ticket"] = int(ticket_out) if ticket_out else None


def _m1_bars(adapter: Any, symbol: str) -> list[Bar] | None:
    try:
        from app.domain.market_data.timeframe import Timeframe

        rates = adapter.copy_rates_from_pos(symbol, Timeframe.M1, 0, 40)
    except Exception:
        return None
    bars: list[Bar] = []
    for row in rates or []:
        try:
            bars.append(
                Bar(
                    open=_dec(_field(row, "open")),
                    high=_dec(_field(row, "high")),
                    low=_dec(_field(row, "low")),
                    close=_dec(_field(row, "close")),
                )
            )
        except Exception:
            return None
    return bars or None


def _quote(adapter: Any, symbol: str) -> tuple[Decimal | None, Decimal | None]:
    try:
        tick = adapter.latest_tick(symbol)
    except Exception:
        return None, None
    if tick is None:
        return None, None
    try:
        return _dec(getattr(tick, "bid", None)), _dec(getattr(tick, "ask", None))
    except Exception:
        return None, None


def _positions(adapter: Any) -> tuple[list[Any], bool]:
    try:
        return list(adapter.list_positions() or []), True
    except Exception:
        return [], False


def _equity(account: Any) -> Decimal | None:
    try:
        value = Decimal(str(getattr(account, "equity", None)))
    except Exception:
        return None
    return value if value > 0 else None


def _contract(symbol: str) -> Decimal:
    from app.domain.entities.risk_engine import contract_size_for_symbol

    size = contract_size_for_symbol(symbol, default=Decimal("100"))
    return size if size > 0 else Decimal("100")


def _bias(snapshot: Any) -> str:
    trend = getattr(snapshot, "trend", None)
    if trend is None:
        return "flat"
    effective = getattr(trend, "effective_bias", None)
    direction = effective() if callable(effective) else effective
    if direction is None:
        direction = getattr(trend, "trade_bias", None) or getattr(
            trend, "macro_bias", None
        )
    value = str(getattr(direction, "value", direction) or "").strip().lower()
    if value in {"up", "bullish", "buy"}:
        return "up"
    if value in {"down", "bearish", "sell"}:
        return "down"
    return "flat"


def _m1_position(positions: list[Any]) -> Any | None:
    for pos in positions:
        if str(getattr(pos, "comment", "") or "").startswith("m1:"):
            return pos
    return None


def _comment_signal(pos: Any) -> str:
    if pos is None:
        return ""
    comment = str(getattr(pos, "comment", "") or "")
    return comment[3:64] if comment.startswith("m1:") else ""


def _side(pos: Any) -> str:
    if pos is None:
        return ""
    return str(getattr(pos, "side", "") or "").strip().lower()


def _stop_of(pos: Any) -> Decimal | None:
    if pos is None:
        return None
    try:
        value = Decimal(str(getattr(pos, "stop_loss", None)))
    except Exception:
        return None
    return value if value > 0 else None


def _target_of(pos: Any) -> Decimal | None:
    if pos is None:
        return None
    try:
        value = Decimal(str(getattr(pos, "take_profit", None)))
    except Exception:
        return None
    return value if value > 0 else None


def _field(row: Any, name: str) -> Any:
    if isinstance(row, dict):
        return row.get(name)
    return getattr(row, name)


def _dec(value: Any) -> Decimal:
    if hasattr(value, "value"):
        value = value.value
    return Decimal(str(value))
