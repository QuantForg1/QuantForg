"""Canonical MT5 order_send request/response operator logs.

Never swallow broker retcodes or comments. Print the full request and
response around every live MetaTrader5.order_send call.
"""

from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

_SEND_OK = frozenset({0, 10008, 10009})


def _side_of(action: Any) -> str:
    raw = str(action or "").strip().lower()
    if "sell" in raw:
        return "SELL"
    if "buy" in raw:
        return "BUY"
    return raw.upper() or "UNKNOWN"


def format_mt5_order_send_request(
    *,
    symbol: Any,
    side: Any,
    volume: Any,
    price: Any,
    stop_loss: Any,
    take_profit: Any,
) -> str:
    return (
        "MT5 order_send()\n"
        "Request:\n"
        f"- symbol: {symbol}\n"
        f"- side: {_side_of(side)}\n"
        f"- volume: {volume}\n"
        f"- price: {price}\n"
        f"- SL: {stop_loss}\n"
        f"- TP: {take_profit}"
    )


def format_mt5_order_send_response(
    *,
    retcode: Any,
    comment: Any,
    deal: Any = None,
    order: Any = None,
    ticket: Any = None,
) -> str:
    return (
        "Response:\n"
        f"- retcode: {retcode}\n"
        f"- comment: {comment if comment not in (None, '') else '(empty)'}\n"
        f"- deal: {deal if deal not in (None, 0, '0') else 0}\n"
        f"- order: {order if order not in (None, 0, '0') else 0}\n"
        f"- ticket: {ticket if ticket not in (None, 0, '0') else 0}"
    )


def log_mt5_order_send_exchange(
    *,
    symbol: Any,
    side: Any,
    volume: Any,
    price: Any,
    stop_loss: Any,
    take_profit: Any,
    retcode: Any,
    comment: Any,
    deal: Any = None,
    order: Any = None,
    ticket: Any = None,
) -> None:
    """Print request + response + ORDER ACCEPTED / ORDER REJECTED."""
    req = format_mt5_order_send_request(
        symbol=symbol,
        side=side,
        volume=volume,
        price=price,
        stop_loss=stop_loss,
        take_profit=take_profit,
    )
    logger.warning(req)

    order_n = int(order or 0)
    deal_n = int(deal or 0)
    ticket_n = int(ticket or 0) or order_n or deal_n
    resp = format_mt5_order_send_response(
        retcode=retcode,
        comment=comment,
        deal=deal_n,
        order=order_n,
        ticket=ticket_n,
    )
    logger.warning(resp)

    try:
        code = int(retcode)
    except (TypeError, ValueError):
        code = -1
    comment_txt = str(comment or "").strip() or "(empty)"
    if code in _SEND_OK:
        logger.warning(
            "ORDER ACCEPTED\n"
            "Position Opened\n"
            f"retcode: {code}\n"
            f"comment: {comment_txt}\n"
            f"deal: {deal_n}\n"
            f"order: {order_n}\n"
            f"ticket: {ticket_n}"
        )
    else:
        logger.error(
            "ORDER REJECTED\n"
            f"retcode: {code}\n"
            f"comment: {comment_txt}\n"
            f"deal: {deal_n}\n"
            f"order: {order_n}\n"
            f"ticket: {ticket_n}"
        )
