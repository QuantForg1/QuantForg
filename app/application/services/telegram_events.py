"""Telegram event names and message formatting.

Observability only. Does not submit orders, evaluate risk, or call MT5.
Missing fields are omitted or shown as N/A — never fabricated.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

TELEGRAM_TEST = "TELEGRAM_TEST"
ROBOT_STARTED = "ROBOT_STARTED"
ROBOT_STOPPED = "ROBOT_STOPPED"
MT5_CONNECTED = "MT5_CONNECTED"
MT5_DISCONNECTED = "MT5_DISCONNECTED"
GATEWAY_ONLINE = "GATEWAY_ONLINE"
GATEWAY_OFFLINE = "GATEWAY_OFFLINE"
SIGNAL_GENERATED = "SIGNAL_GENERATED"
SIGNAL_CONFIRMED = "SIGNAL_CONFIRMED"
TRADE_OPENED = "TRADE_OPENED"
TRADE_REJECTED = "TRADE_REJECTED"
SL_CREATED = "SL_CREATED"
SL_UPDATED = "SL_UPDATED"
TP_CREATED = "TP_CREATED"
TP_UPDATED = "TP_UPDATED"
BREAKEVEN_SET = "BREAKEVEN_SET"
TRAILING_STOP_UPDATED = "TRAILING_STOP_UPDATED"
PARTIAL_CLOSE = "PARTIAL_CLOSE"
TAKE_PROFIT = "TAKE_PROFIT"
STOP_LOSS = "STOP_LOSS"
TRADE_CLOSED = "TRADE_CLOSED"
RISK_BLOCKED = "RISK_BLOCKED"
OMS_REJECTED = "OMS_REJECTED"
ORDER_EXECUTION_ERROR = "ORDER_EXECUTION_ERROR"
SYSTEM_ERROR = "SYSTEM_ERROR"

_FILL_RETCODES = frozenset({10008, 10009})
_RISK_ABORT_MARKERS = (
    "DAILY_LOSS",
    "MAX_POSITION",
    "MIN_LOT",
    "MISSING_LOTS",
    "SIZING",
    "KILL_SWITCH",
    "SAFETY_BLOCKED",
    "AUTO_TRADING_BLOCKED",
    "CANARY_POSITION",
    "CANARY_LOT",
    "CANARY_DAILY",
    "SELF_PROTECTION",
)
_OMS_ABORT_MARKERS = ("OMS_FAILURE", "OMS_REJECT")
_EXEC_ABORT_MARKERS = (
    "GATEWAY_FAILURE",
    "MT5_REJECTION",
    "MT5_FAILURE",
    "ORDER_SEND",
    "EXECUTION_DISABLED",
)


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"none", "null", "n/a"}:
        return None
    return text


def _num(value: object, *, treat_zero_missing: bool = False) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    try:
        number = Decimal(text)
    except (InvalidOperation, ValueError):
        return text
    if treat_zero_missing and number == 0:
        return None
    normalized = format(number.normalize(), "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized or "0"


def _pct(value: object) -> str | None:
    number = _num(value)
    if number is None:
        return None
    return f"{number}%"


def _rr(value: object) -> str | None:
    number = _num(value)
    if number is None:
        return None
    return f"1:{number}"


def _side(value: object) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    upper = text.upper()
    if upper in {"BUY", "LONG"}:
        return "BUY"
    if upper in {"SELL", "SHORT"}:
        return "SELL"
    return upper


def _line(label: str, value: object, *, missing: str | None = "N/A") -> str | None:
    text = _clean(value)
    if text is None:
        if missing is None:
            return None
        return f"{label}: {missing}"
    return f"{label}: {text}"


def _join(lines: list[str | None]) -> str:
    return "\n".join(line for line in lines if line)


def format_test_message() -> str:
    return _join(
        [
            "🤖 QUANTFORG TELEGRAM TEST",
            "",
            "Status: CONNECTIVITY CHECK",
            "Trading: NOT AFFECTED",
            "Orders: NONE",
        ]
    )


def format_robot_started(*, telegram_status: str) -> str:
    return _join(
        [
            "🟢 QUANTFORG ROBOT STARTED",
            "",
            "Execution engine: RUNNING",
            "Market scanning: ACTIVE",
            f"Telegram: {telegram_status}",
        ]
    )


def format_robot_stopped(*, reason: str | None) -> str:
    return _join(
        [
            "🔴 QUANTFORG ROBOT STOPPED",
            "",
            "Reason:",
            _clean(reason) or "orchestrator_stopped",
        ]
    )


def format_mt5_connected() -> str:
    return _join(
        [
            "🟢 QUANTFORG MT5 CONNECTED",
            "",
            "Status: CONNECTION RESTORED",
        ]
    )


def format_mt5_disconnected() -> str:
    return _join(
        [
            "🔴 QUANTFORG MT5 DISCONNECTED",
            "",
            "Status: CONNECTION LOST",
        ]
    )


def format_gateway_online() -> str:
    return _join(
        [
            "🟢 QUANTFORG GATEWAY ONLINE",
            "",
            "Status: CONNECTION RESTORED",
        ]
    )


def format_gateway_offline() -> str:
    return _join(
        [
            "🔴 QUANTFORG GATEWAY OFFLINE",
            "",
            "Status: CONNECTION LOST",
        ]
    )


def format_signal(
    *,
    confirmed: bool,
    symbol: str | None,
    direction: str | None,
    opportunity: object = None,
    confidence: object = None,
    entry: object = None,
    stop_loss: object = None,
    take_profit: object = None,
    risk_reward: object = None,
    regime: str | None = None,
) -> str:
    status = "SIGNAL CONFIRMED" if confirmed else "SIGNAL GENERATED"
    emoji = "🟢" if _side(direction) != "SELL" else "🔴"
    return _join(
        [
            f"{emoji} QUANTFORG SIGNAL",
            "",
            _line("Symbol", symbol),
            _line("Direction", _side(direction)),
            "",
            _line("Opportunity", _num(opportunity)),
            _line("Confidence", _pct(confidence)),
            "",
            _line("Entry", _num(entry, treat_zero_missing=True)),
            _line("Stop Loss", _num(stop_loss, treat_zero_missing=True)),
            _line("Take Profit", _num(take_profit, treat_zero_missing=True)),
            "",
            _line("Risk/Reward", _rr(risk_reward)),
            "",
            _line("Regime", regime),
            f"Status: {status}",
        ]
    )


def format_trade_opened(
    *,
    symbol: str | None,
    side: str | None,
    volume: object = None,
    entry: object = None,
    stop_loss: object = None,
    take_profit: object = None,
    ticket: object = None,
) -> str:
    return _join(
        [
            "🚀 QUANTFORG TRADE OPENED",
            "",
            _line("Symbol", symbol),
            _line("Side", _side(side)),
            "",
            _line("Volume", _num(volume, treat_zero_missing=True)),
            _line("Entry", _num(entry, treat_zero_missing=True)),
            "",
            _line("SL", _num(stop_loss, treat_zero_missing=True)),
            _line("TP", _num(take_profit, treat_zero_missing=True)),
            "",
            _line("MT5 Ticket", ticket),
            "",
            "Status: EXECUTED ✅",
        ]
    )


def format_breakeven(
    *,
    symbol: str | None,
    side: str | None,
    entry: object = None,
    previous_sl: object = None,
    new_sl: object = None,
) -> str:
    return _join(
        [
            "🔒 QUANTFORG BREAKEVEN",
            "",
            _line("Symbol", symbol),
            _line("Side", _side(side)),
            "",
            _line("Entry", _num(entry, treat_zero_missing=True)),
            "",
            _line("Previous SL", _num(previous_sl, treat_zero_missing=True)),
            _line("New SL", _num(new_sl, treat_zero_missing=True)),
            "",
            "Status: PROTECTED ✅",
        ]
    )


def format_trailing(
    *,
    symbol: str | None,
    side: str | None,
    previous_sl: object = None,
    new_sl: object = None,
) -> str:
    return _join(
        [
            "🔄 QUANTFORG TRAILING STOP",
            "",
            _line("Symbol", symbol),
            _line("Side", _side(side)),
            "",
            _line("Previous SL", _num(previous_sl, treat_zero_missing=True)),
            _line("New SL", _num(new_sl, treat_zero_missing=True)),
            "",
            "Profit protection: ACTIVE ✅",
        ]
    )


def format_partial_close(
    *,
    symbol: str | None,
    side: str | None,
    volume: object = None,
    ticket: object = None,
) -> str:
    return _join(
        [
            "✂️ QUANTFORG PARTIAL CLOSE",
            "",
            _line("Symbol", symbol),
            _line("Side", _side(side)),
            _line("Volume", _num(volume, treat_zero_missing=True)),
            _line("MT5 Ticket", ticket),
        ]
    )


def format_sl_tp(
    *,
    kind: str,
    symbol: str | None,
    side: str | None,
    previous: object = None,
    new: object = None,
    ticket: object = None,
) -> str:
    title = {
        SL_CREATED: "📌 QUANTFORG SL CREATED",
        SL_UPDATED: "📌 QUANTFORG SL UPDATED",
        TP_CREATED: "🎯 QUANTFORG TP CREATED",
        TP_UPDATED: "🎯 QUANTFORG TP UPDATED",
    }.get(kind, "📌 QUANTFORG LEVEL UPDATE")
    return _join(
        [
            title,
            "",
            _line("Symbol", symbol),
            _line("Side", _side(side)),
            _line("Previous", _num(previous, treat_zero_missing=True), missing=None),
            _line("New", _num(new, treat_zero_missing=True)),
            _line("MT5 Ticket", ticket),
        ]
    )


def format_trade_closed(
    *,
    symbol: str | None,
    side: str | None,
    entry: object = None,
    exit_price: object = None,
    volume: object = None,
    pnl: object = None,
    reason: str | None = None,
    event: str = TRADE_CLOSED,
) -> str:
    if event == TAKE_PROFIT:
        headline = "🟢 QUANTFORG TAKE PROFIT"
        reason_line = "Reason: TAKE PROFIT ✅"
    elif event == STOP_LOSS:
        headline = "🔴 QUANTFORG STOP LOSS"
        reason_line = "Reason: STOP LOSS"
    else:
        headline = "🔴 QUANTFORG TRADE CLOSED"
        reason_line = f"Reason: {_clean(reason) or 'CLOSED'}"
    pnl_text = _clean(pnl)
    if pnl_text is not None and not pnl_text.startswith(("+", "-", "$")):
        try:
            amount = Decimal(pnl_text)
            sign = "+" if amount > 0 else ""
            pnl_text = f"{sign}${format(amount.normalize(), 'f')}"
        except (InvalidOperation, ValueError):
            pass
    return _join(
        [
            headline,
            "",
            _line("Symbol", symbol),
            _line("Side", _side(side)),
            "",
            _line("Entry", _num(entry, treat_zero_missing=True)),
            _line("Exit", _num(exit_price, treat_zero_missing=True)),
            "",
            _line("Volume", _num(volume, treat_zero_missing=True)),
            "",
            _line("P/L", pnl_text),
            "",
            reason_line,
        ]
    )


def format_risk_block(
    *,
    symbol: str | None,
    action: str | None,
    reason: str | None,
) -> str:
    return _join(
        [
            "🛡️ QUANTFORG RISK BLOCK",
            "",
            _line("Symbol", symbol),
            "",
            _line("Action", _side(action) or _clean(action)),
            "",
            "Reason:",
            _clean(reason) or "RISK_REJECTED",
            "",
            "No order submitted.",
            "No MT5 ticket.",
        ]
    )


def format_oms_rejected(
    *,
    symbol: str | None,
    action: str | None,
    reason: str | None,
) -> str:
    return _join(
        [
            "⚠️ QUANTFORG OMS REJECTED",
            "",
            _line("Symbol", symbol),
            "",
            _line("Action", _side(action) or _clean(action)),
            "",
            "Reason:",
            _clean(reason) or "OMS_REJECTED",
            "",
            "Status: NO ORDER",
        ]
    )


def format_execution_error(
    *,
    symbol: str | None,
    action: str | None,
    reason: str | None,
) -> str:
    return _join(
        [
            "⚠️ QUANTFORG ORDER EXECUTION ERROR",
            "",
            _line("Symbol", symbol),
            _line("Action", _side(action) or _clean(action)),
            "",
            "Reason:",
            _clean(reason) or "EXECUTION_ERROR",
            "",
            "Status: NO FILL",
        ]
    )


def format_trade_rejected(
    *,
    symbol: str | None,
    action: str | None,
    reason: str | None,
) -> str:
    return _join(
        [
            "🟡 QUANTFORG SIGNAL REJECTED",
            "",
            _line("Symbol", symbol),
            _line("Action", _side(action) or _clean(action)),
            "",
            "Reason:",
            _clean(reason) or "REJECTED",
            "",
            "Status: NO ORDER",
            "No MT5 ticket.",
        ]
    )


def format_system_error(*, reason: str | None) -> str:
    return _join(
        [
            "🔴 QUANTFORG SYSTEM ERROR",
            "",
            "Reason:",
            _clean(reason) or "UNEXPECTED_EXCEPTION",
            "",
            "Trading loop: CONTINUING",
        ]
    )


def _ai_map(pipeline: Any) -> dict[str, Any]:
    raw = getattr(pipeline, "_last_ai_score", None) if pipeline is not None else None
    if isinstance(raw, dict):
        return dict(raw)
    if raw is None:
        return {}
    to_dict = getattr(raw, "to_dict", None)
    if callable(to_dict):
        data = to_dict()
        return dict(data) if isinstance(data, dict) else {}
    return {}


def _zone_price(zone: Any) -> str | None:
    if zone is None:
        return None
    for attr in ("mid", "low", "high"):
        found = _num(getattr(zone, attr, None), treat_zero_missing=True)
        if found is not None:
            return found
    if isinstance(zone, dict):
        for key in ("mid", "low", "high"):
            found = _num(zone.get(key), treat_zero_missing=True)
            if found is not None:
                return found
    return _num(zone, treat_zero_missing=True)


def _int_ticket(value: object) -> int | None:
    try:
        ticket = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return ticket if ticket > 0 else None


def broker_ticket(cycle: Any, bridge: Any) -> int | None:
    """Return a real MT5 ticket only. Never invents fills."""
    journal = getattr(bridge, "journal_entry", None) if bridge is not None else None
    oms = getattr(bridge, "oms_result", None) if bridge is not None else None
    for src in (
        getattr(cycle, "mt5_ticket", None) if cycle is not None else None,
        getattr(journal, "mt5_ticket", None),
        getattr(oms, "order_ticket", None),
        getattr(journal, "ticket", None),
        getattr(journal, "order_ticket", None),
    ):
        ticket = _int_ticket(src)
        if ticket is not None:
            return ticket
    return None


def broker_deal(bridge: Any) -> int | None:
    journal = getattr(bridge, "journal_entry", None) if bridge is not None else None
    oms = getattr(bridge, "oms_result", None) if bridge is not None else None
    for src in (
        getattr(journal, "mt5_deal", None),
        getattr(oms, "deal_ticket", None),
    ):
        deal = _int_ticket(src)
        if deal is not None:
            return deal
    return None


def _abort(cycle: Any, bridge: Any) -> str:
    raw = getattr(cycle, "abort_reason", None) if cycle is not None else None
    if raw in {None, "", "none", "NONE"}:
        raw = getattr(getattr(bridge, "abort_reason", None), "value", None)
        if raw is None:
            raw = getattr(bridge, "abort_reason", None)
    text = str(raw or "").strip().upper()
    if text in {"NONE", "NULL"}:
        return ""
    return text


def _contains(haystack: str, markers: tuple[str, ...]) -> bool:
    return any(marker in haystack for marker in markers)


def classify_close_event(reason: str | None) -> str:
    """TP/SL only when existing reason text confirms it."""
    text = str(reason or "").upper()
    if any(
        tok in text
        for tok in ("TAKE_PROFIT", "TAKE PROFIT", "TP_HIT", "DEAL_REASON_TP")
    ):
        return TAKE_PROFIT
    if any(
        tok in text
        for tok in ("STOP_LOSS", "STOP LOSS", "SL_HIT", "DEAL_REASON_SL")
    ):
        return STOP_LOSS
    return TRADE_CLOSED


def signal_fingerprint(
    *,
    symbol: str | None,
    direction: str | None,
    entry: object,
    stop_loss: object,
    take_profit: object,
) -> str:
    return "|".join(
        [
            _clean(symbol) or "?",
            _side(direction) or "?",
            _num(entry, treat_zero_missing=True) or "na",
            _num(stop_loss, treat_zero_missing=True) or "na",
            _num(take_profit, treat_zero_missing=True) or "na",
        ]
    )


def classify_cycle_notices(
    *,
    cycle: Any,
    decision: Any = None,
    bridge: Any = None,
    pipeline: Any = None,
) -> list[dict[str, Any]]:
    """Map one finished ITE cycle onto Telegram notices. No trading side effects."""
    abort = _abort(cycle, bridge)
    if abort in {"CYCLE_TIMEOUT"}:
        return []
    if abort == "CYCLE_EXCEPTION":
        return [
            {
                "event": SYSTEM_ERROR,
                "event_id": f"sys:{getattr(cycle, 'detail', '')}",
                "text": format_system_error(reason=getattr(cycle, "detail", None)),
            }
        ]

    outcome = str(getattr(cycle, "cycle_outcome", "") or "").lower()
    if outcome in {"waiting_next_cycle", "no_snapshot"}:
        return []

    ai = _ai_map(pipeline)
    symbol = _clean(
        getattr(decision, "symbol", None)
        or ai.get("symbol")
        or getattr(cycle, "symbol", None)
    )
    direction = _side(
        getattr(getattr(decision, "direction", None), "value", None)
        or getattr(decision, "direction", None)
        or ai.get("direction")
        or getattr(cycle, "decision_action", None)
    )
    action = str(
        getattr(getattr(decision, "action", None), "value", None)
        or getattr(decision, "action", None)
        or getattr(cycle, "decision_action", None)
        or ""
    ).upper()
    signal_action = str(ai.get("signal_action") or "").upper()
    entry = (
        _zone_price(getattr(decision, "entry_zone", None))
        or _num(ai.get("entry"), treat_zero_missing=True)
    )
    stop_loss = (
        _zone_price(getattr(decision, "stop_zone", None))
        or _num(ai.get("stop_loss"), treat_zero_missing=True)
    )
    take_profit = (
        _zone_price(getattr(decision, "target_zone", None))
        or _num(ai.get("take_profit"), treat_zero_missing=True)
    )
    opportunity = ai.get("opportunity_score")
    confidence = (
        getattr(decision, "confidence", None)
        or ai.get("ai_confidence")
        or ai.get("confidence")
    )
    rr = getattr(decision, "estimated_rr", None) or ai.get("expected_rr")
    regime = _clean(ai.get("market_regime") or ai.get("regime"))
    sig_fp = signal_fingerprint(
        symbol=symbol,
        direction=direction,
        entry=entry,
        stop_loss=stop_loss,
        take_profit=take_profit,
    )
    ticket = broker_ticket(cycle, bridge)
    retcode = getattr(cycle, "broker_retcode", None)
    if retcode is None and bridge is not None:
        retcode = getattr(getattr(bridge, "journal_entry", None), "retcode", None)
        if retcode is None:
            retcode = getattr(getattr(bridge, "oms_result", None), "retcode", None)
    volume = getattr(decision, "approved_lots", None)
    if volume is None:
        journal = getattr(bridge, "journal_entry", None) if bridge is not None else None
        volume = getattr(journal, "approved_lots", None)

    notices: list[dict[str, Any]] = []
    generated = signal_action in {"BUY", "SELL"} or (
        bool(ai.get("opportunity_eligible")) and direction in {"BUY", "SELL"}
    )
    confirmed = action in {"BUY", "SELL"}
    if generated:
        notices.append(
            {
                "event": SIGNAL_GENERATED,
                "event_id": f"sig:{sig_fp}",
                "text": format_signal(
                    confirmed=False,
                    symbol=symbol,
                    direction=direction,
                    opportunity=opportunity,
                    confidence=confidence,
                    entry=entry,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    risk_reward=rr,
                    regime=regime,
                ),
            }
        )
    if confirmed:
        notices.append(
            {
                "event": SIGNAL_CONFIRMED,
                "event_id": f"sigconf:{sig_fp}",
                "text": format_signal(
                    confirmed=True,
                    symbol=symbol,
                    direction=direction,
                    opportunity=opportunity,
                    confidence=confidence,
                    entry=entry,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    risk_reward=rr,
                    regime=regime,
                ),
            }
        )

    if ticket is not None:
        notices.append(
            {
                "event": TRADE_OPENED,
                "event_id": f"open:{ticket}",
                "text": format_trade_opened(
                    symbol=symbol,
                    side=direction or action,
                    volume=volume,
                    entry=entry,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    ticket=ticket,
                ),
            }
        )
        if stop_loss is not None:
            notices.append(
                {
                    "event": SL_CREATED,
                    "event_id": f"slc:{ticket}:{stop_loss}",
                    "text": format_sl_tp(
                        kind=SL_CREATED,
                        symbol=symbol,
                        side=direction or action,
                        new=stop_loss,
                        ticket=ticket,
                    ),
                }
            )
        if take_profit is not None:
            notices.append(
                {
                    "event": TP_CREATED,
                    "event_id": f"tpc:{ticket}:{take_profit}",
                    "text": format_sl_tp(
                        kind=TP_CREATED,
                        symbol=symbol,
                        side=direction or action,
                        new=take_profit,
                        ticket=ticket,
                    ),
                }
            )
        return notices

    safety = tuple(getattr(cycle, "safety_failed_reasons", ()) or ())
    safety_text = " ".join(str(item) for item in safety).upper()
    reason = (
        getattr(cycle, "oms_message", None)
        or "; ".join(str(r) for r in getattr(cycle, "decision_reasons", ()) or ())
        or getattr(cycle, "detail", None)
        or abort
        or safety_text
    )
    risk_hit = _contains(abort, _RISK_ABORT_MARKERS) or _contains(
        safety_text, _RISK_ABORT_MARKERS
    )
    if not confirmed and not generated and not risk_hit:
        return notices

    if risk_hit:
        notices.append(
            {
                "event": RISK_BLOCKED,
                "event_id": f"risk:{sig_fp}:{abort or safety_text}",
                "text": format_risk_block(
                    symbol=symbol,
                    action=direction or action,
                    reason=reason,
                ),
            }
        )
        return notices
    if _contains(abort, _OMS_ABORT_MARKERS):
        notices.append(
            {
                "event": OMS_REJECTED,
                "event_id": f"oms:{sig_fp}:{abort}",
                "text": format_oms_rejected(
                    symbol=symbol,
                    action=direction or action,
                    reason=reason,
                ),
            }
        )
        return notices
    if _contains(abort, _EXEC_ABORT_MARKERS):
        notices.append(
            {
                "event": ORDER_EXECUTION_ERROR,
                "event_id": f"exec:{sig_fp}:{abort}",
                "text": format_execution_error(
                    symbol=symbol,
                    action=direction or action,
                    reason=reason,
                ),
            }
        )
        return notices
    if abort and (confirmed or generated):
        notices.append(
            {
                "event": TRADE_REJECTED,
                "event_id": f"rej:{sig_fp}:{abort}",
                "text": format_trade_rejected(
                    symbol=symbol,
                    action=direction or action,
                    reason=reason,
                ),
            }
        )
    return notices


def classify_pme_notices(
    *,
    result: Any,
    current_price: object = None,
) -> list[dict[str, Any]]:
    """Map one PME evaluate result onto Telegram notices after broker success."""
    if result is None:
        return []
    skipped = bool(getattr(result, "skipped", False))
    record = getattr(result, "record", None)
    if skipped or record is None:
        return []
    outcome = str(
        getattr(
            getattr(record, "outcome", None),
            "value",
            getattr(record, "outcome", ""),
        )
        or ""
    ).lower()
    if outcome not in {"success"}:
        return []
    action = str(
        getattr(
            getattr(result, "action", None),
            "value",
            getattr(result, "action", ""),
        )
        or ""
    ).lower()
    position = getattr(result, "position", None)
    oms = getattr(result, "oms_result", None)
    oms_ok = True if oms is None else bool(getattr(oms, "ok", True))
    if not oms_ok:
        return []
    ticket = _int_ticket(
        getattr(record, "ticket", None) or getattr(position, "ticket", None)
    )
    if ticket is None:
        return []
    symbol = _clean(
        getattr(position, "symbol", None) or getattr(record, "symbol", None)
    )
    side = _side(getattr(position, "side", None))
    old_sl = getattr(record, "old_sl", None)
    new_sl = getattr(record, "new_sl", None)
    old_tp = getattr(record, "old_tp", None)
    new_tp = getattr(record, "new_tp", None)
    fingerprint = _clean(getattr(record, "fingerprint", None)) or (
        f"{ticket}:{action}:{new_sl}"
    )
    to_state = str(
        getattr(
            getattr(record, "to_state", None),
            "value",
            getattr(record, "to_state", ""),
        )
        or getattr(getattr(position, "state", None), "value", "")
        or ""
    ).upper()
    notices: list[dict[str, Any]] = []

    if action in {"break_even", "break-even"} and new_sl is not None:
        notices.append(
            {
                "event": BREAKEVEN_SET,
                "event_id": f"be:{fingerprint}",
                "text": format_breakeven(
                    symbol=symbol,
                    side=side,
                    entry=getattr(position, "entry_price", None),
                    previous_sl=old_sl,
                    new_sl=new_sl,
                ),
            }
        )
    elif action in {"trail", "trailing"} and new_sl is not None:
        notices.append(
            {
                "event": TRAILING_STOP_UPDATED,
                "event_id": f"trail:{fingerprint}",
                "text": format_trailing(
                    symbol=symbol,
                    side=side,
                    previous_sl=old_sl,
                    new_sl=new_sl,
                ),
            }
        )
    elif (
        action not in {"break_even", "break-even", "trail", "trailing"}
        and new_sl is not None
        and _num(old_sl) != _num(new_sl)
    ):
        notices.append(
            {
                "event": SL_UPDATED,
                "event_id": f"slu:{fingerprint}",
                "text": format_sl_tp(
                    kind=SL_UPDATED,
                    symbol=symbol,
                    side=side,
                    previous=old_sl,
                    new=new_sl,
                    ticket=ticket,
                ),
            }
        )

    if new_tp is not None and _num(old_tp) != _num(new_tp):
        notices.append(
            {
                "event": TP_UPDATED,
                "event_id": f"tpu:{fingerprint}",
                "text": format_sl_tp(
                    kind=TP_UPDATED,
                    symbol=symbol,
                    side=side,
                    previous=old_tp,
                    new=new_tp,
                    ticket=ticket,
                ),
            }
        )

    if action in {"partial_close", "partial"}:
        notices.append(
            {
                "event": PARTIAL_CLOSE,
                "event_id": f"part:{fingerprint}",
                "text": format_partial_close(
                    symbol=symbol,
                    side=side,
                    volume=getattr(record, "volume", None),
                    ticket=ticket,
                ),
            }
        )

    if to_state in {"EXITED", "CLOSED"}:
        reason = getattr(record, "exit_reason", None) or getattr(record, "reason", None)
        event = classify_close_event(str(reason or ""))
        notices.append(
            {
                "event": event,
                "event_id": f"close:{ticket}:{event}",
                "text": format_trade_closed(
                    symbol=symbol,
                    side=side,
                    entry=getattr(position, "entry_price", None),
                    exit_price=current_price,
                    volume=getattr(position, "initial_volume", None)
                    or getattr(record, "volume", None),
                    pnl=getattr(record, "pnl", None)
                    or getattr(position, "profit", None),
                    reason=str(reason or ""),
                    event=event,
                ),
            }
        )
    return notices
