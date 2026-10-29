"""Gateway-side order guard: the last check before MetaTrader5.order_send.

Owner live limits enforced on this Windows host, independent of whatever
Railway sends:

- New entries: Gold only (same rule as the application), SL and TP > 0,
  volume > 0, planned loss at most 9% of live equity, SL on the correct
  side of the live quote, and a unique client_order_id.
- Closes: only an explicit close/partial_close whose ticket exists, whose
  symbol matches that position, and whose volume is positive and not larger
  than the open volume.
- SL/TP modifies: position must be readable, SL and TP stay > 0, SL may only
  tighten, and SL must sit on the correct side of the live quote.
- A position ticket on a new entry is rejected. It is not treated as a close.

A failed account, quote, or position read fails closed. This module never
calls MetaTrader5.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from decimal import Decimal
from typing import Any

from app.domain.institutional_trading.owner_risk_policy import MAX_PLANNED_RISK_PCT
from app.domain.trading.gold_only import is_gold_symbol

# Distinct from 90001 (execution disabled) so callers can tell them apart.
RETCODE_ORDER_GUARD_REJECTED = 90002

CLIENT_ORDER_ID_TTL_SECONDS = 24 * 3600
_CLIENT_ORDER_ID_MAX_TRACKED = 10_000
_VOLUME_EPSILON = Decimal("0.0000001")
_CENTS = Decimal("0.01")

_CLOSE_KINDS = frozenset({"close", "partial_close"})
_SLTP_KINDS = frozenset({"sltp", "modify_sltp"})
_BUY_ACTIONS = frozenset({"buy", "buy_limit", "buy_stop", "0"})
_SELL_ACTIONS = frozenset({"sell", "sell_limit", "sell_stop", "1"})

KIND_ENTRY = "entry"
KIND_CLOSE = "close"
KIND_SLTP = "sltp"
KIND_MODIFY_PENDING = "modify_pending"


class OrderGuardRejected(ValueError):
    """Maps to HTTP 403 with retcode 90002 — never reaches MetaTrader5."""

    retcode: int = RETCODE_ORDER_GUARD_REJECTED

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message

    def as_detail(self) -> dict[str, object]:
        return {
            "ok": False,
            "retcode": self.retcode,
            "code": self.code,
            "comment": f"gateway guard: {self.message}",
            "order_ticket": 0,
            "deal_ticket": 0,
        }


class ClientOrderIdRegistry:
    """Remembers entry ``client_order_id`` values for a TTL (process memory)."""

    def __init__(
        self,
        *,
        ttl_seconds: float = CLIENT_ORDER_ID_TTL_SECONDS,
        max_tracked: int = _CLIENT_ORDER_ID_MAX_TRACKED,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = float(ttl_seconds)
        self._max = int(max_tracked)
        self._clock = clock
        self._seen: OrderedDict[str, float] = OrderedDict()
        self._lock = threading.Lock()

    def claim(self, client_order_id: str) -> bool:
        """True the first time ``client_order_id`` is seen inside the TTL."""
        now = self._clock()
        with self._lock:
            while self._seen:
                oldest_id, seen_at = next(iter(self._seen.items()))
                if now - seen_at <= self._ttl and len(self._seen) < self._max:
                    break
                self._seen.pop(oldest_id)
            if client_order_id in self._seen:
                return False
            self._seen[client_order_id] = now
            return True


_REGISTRY = ClientOrderIdRegistry()


def get_client_order_id_registry() -> ClientOrderIdRegistry:
    return _REGISTRY


def _num(body: dict[str, Any], *keys: str) -> float:
    for key in keys:
        value = body.get(key)
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def _dec(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        number = Decimal(str(value))
    except Exception:
        return None
    if not number.is_finite():
        return None
    return number


def classify_order(body: dict[str, Any]) -> str:
    """entry | close | sltp | modify_pending for an order_send payload.

    A position ticket alone is not a close. Only an explicit close kind is.
    """
    oms_kind = str(body.get("oms_kind") or "").strip().lower()
    action = str(body.get("action") or "").strip().lower()
    if oms_kind in _SLTP_KINDS or action in _SLTP_KINDS:
        return KIND_SLTP
    if oms_kind == KIND_MODIFY_PENDING:
        return KIND_MODIFY_PENDING
    if oms_kind in _CLOSE_KINDS:
        return KIND_CLOSE
    return KIND_ENTRY


def _require_stops(body: dict[str, Any]) -> tuple[Decimal, Decimal]:
    raw_sl = body.get("sl")
    if raw_sl in (None, ""):
        raw_sl = body.get("stop_loss")
    raw_tp = body.get("tp")
    if raw_tp in (None, ""):
        raw_tp = body.get("take_profit")
    sl = _dec(raw_sl)
    tp = _dec(raw_tp)
    if sl is None or sl <= 0:
        raise OrderGuardRejected("GUARD_SL_REQUIRED", "stop loss must be > 0")
    if tp is None or tp <= 0:
        raise OrderGuardRejected("GUARD_TP_REQUIRED", "take profit must be > 0")
    return sl, tp


def _quote_prices(quote: dict[str, Any] | None) -> tuple[Decimal, Decimal]:
    if not isinstance(quote, dict):
        raise OrderGuardRejected(
            "GUARD_QUOTE_UNAVAILABLE", "live quote is required to check the stop"
        )
    bid = _dec(quote.get("bid"))
    ask = _dec(quote.get("ask"))
    if bid is None or ask is None or bid <= 0 or ask <= 0:
        raise OrderGuardRejected(
            "GUARD_QUOTE_UNAVAILABLE", "live bid and ask are required to check the stop"
        )
    return bid, ask


def _entry_side(body: dict[str, Any]) -> str:
    action = str(body.get("action") or "").strip().lower()
    if action in _BUY_ACTIONS:
        return "buy"
    if action in _SELL_ACTIONS:
        return "sell"
    return ""


def _require_sl_side(sl: Decimal, *, side: str, bid: Decimal, ask: Decimal) -> None:
    if side == "buy" and sl >= bid:
        raise OrderGuardRejected(
            "GUARD_SL_WRONG_SIDE", "buy stop loss must be below the live bid"
        )
    if side == "sell" and sl <= ask:
        raise OrderGuardRejected(
            "GUARD_SL_WRONG_SIDE", "sell stop loss must be above the live ask"
        )
    if side not in {"buy", "sell"}:
        raise OrderGuardRejected(
            "GUARD_SL_WRONG_SIDE", "stop side cannot be checked without buy or sell"
        )


def _specs(quote: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(quote, dict):
        return {}
    raw = quote.get("specs")
    return raw if isinstance(raw, dict) else {}


def _planned_loss(
    *,
    volume: Decimal,
    stop_distance: Decimal,
    quote: dict[str, Any] | None,
    contract_size: Decimal | None,
) -> Decimal:
    specs = _specs(quote)
    tick_size = _dec(specs.get("tick_size"))
    tick_value = _dec(specs.get("tick_value"))
    live_cs = _dec(specs.get("contract_size"))
    cs = live_cs if live_cs is not None and live_cs > 0 else contract_size
    if (
        tick_size is not None
        and tick_value is not None
        and tick_size > 0
        and tick_value > 0
    ):
        per_lot = (stop_distance / tick_size) * tick_value
    elif cs is not None and cs > 0:
        per_lot = stop_distance * cs
    else:
        raise OrderGuardRejected(
            "GUARD_RISK_UNAVAILABLE",
            "contract size is required to price the stop",
        )
    if per_lot <= 0 or volume <= 0 or stop_distance <= 0:
        raise OrderGuardRejected(
            "GUARD_RISK_UNAVAILABLE", "planned stop loss cannot be priced"
        )
    return (volume * per_lot).quantize(_CENTS)


def _check_entry(
    body: dict[str, Any],
    registry: ClientOrderIdRegistry,
    *,
    equity: Decimal | None,
    quote: dict[str, Any] | None,
    contract_size: Decimal | None,
) -> None:
    if int(_num(body, "position")) > 0:
        raise OrderGuardRejected(
            "GUARD_ENTRY_POSITION",
            "a new entry must not carry a position ticket",
        )
    symbol = str(body.get("symbol") or "")
    if not is_gold_symbol(symbol):
        raise OrderGuardRejected(
            "GUARD_GOLD_ONLY", f"new entries are Gold only (got {symbol!r})"
        )
    sl, _tp = _require_stops(body)
    volume = _dec(body.get("volume"))
    if volume is None or volume <= 0:
        raise OrderGuardRejected("GUARD_VOLUME", "entry volume must be > 0")
    if equity is None or equity <= 0:
        raise OrderGuardRejected(
            "GUARD_EQUITY_UNAVAILABLE", "live equity is required to price risk"
        )
    bid, ask = _quote_prices(quote)
    side = _entry_side(body)
    _require_sl_side(sl, side=side, bid=bid, ask=ask)
    price = ask if side == "buy" else bid
    loss = _planned_loss(
        volume=volume,
        stop_distance=abs(price - sl),
        quote=quote,
        contract_size=contract_size,
    )
    cap = (equity * MAX_PLANNED_RISK_PCT / Decimal("100")).quantize(_CENTS)
    if loss > cap:
        raise OrderGuardRejected(
            "GUARD_MAX_RISK",
            f"planned loss {loss} exceeds {MAX_PLANNED_RISK_PCT}% of equity ({cap})",
        )
    client_order_id = str(body.get("client_order_id") or "").strip()
    if not client_order_id:
        raise OrderGuardRejected(
            "GUARD_CLIENT_ORDER_ID_REQUIRED", "client_order_id is required"
        )
    # Claimed last, so a rejected entry never burns its id. A broker reject
    # after this claim still consumes the id for this process lifetime.
    if not registry.claim(client_order_id):
        raise OrderGuardRejected(
            "GUARD_DUPLICATE_CLIENT_ORDER_ID",
            f"client_order_id already used: {client_order_id}",
        )


def _positions(
    positions_lookup: Callable[[], list[dict[str, Any]]] | None,
    *,
    code: str,
) -> list[dict[str, Any]]:
    try:
        return list(positions_lookup() if positions_lookup is not None else [])
    except Exception as exc:
        raise OrderGuardRejected(code, f"cannot read positions: {exc}") from exc


def _position_row(
    rows: list[dict[str, Any]], ticket: int, *, code: str
) -> dict[str, Any]:
    current = next((row for row in rows if int(_num(row, "ticket")) == ticket), None)
    if current is None:
        raise OrderGuardRejected(code, f"position {ticket} not found")
    return current


def _check_close(
    body: dict[str, Any],
    positions_lookup: Callable[[], list[dict[str, Any]]] | None,
) -> None:
    symbol = str(body.get("symbol") or "")
    if not is_gold_symbol(symbol):
        raise OrderGuardRejected(
            "GUARD_GOLD_ONLY", f"closes are Gold only (got {symbol!r})"
        )
    ticket = int(_num(body, "position"))
    if ticket <= 0:
        raise OrderGuardRejected(
            "GUARD_CLOSE_TICKET_REQUIRED", "close requires a position ticket"
        )
    volume = _dec(body.get("volume"))
    if volume is None or volume <= 0:
        raise OrderGuardRejected("GUARD_CLOSE_VOLUME", "close volume must be > 0")
    rows = _positions(positions_lookup, code="GUARD_CLOSE_UNVERIFIED")
    current = _position_row(rows, ticket, code="GUARD_CLOSE_UNVERIFIED")
    current_symbol = str(current.get("symbol") or "")
    if not is_gold_symbol(current_symbol):
        raise OrderGuardRejected(
            "GUARD_GOLD_ONLY", f"position {ticket} is not Gold ({current_symbol!r})"
        )
    if current_symbol.strip().upper() != symbol.strip().upper():
        raise OrderGuardRejected(
            "GUARD_CLOSE_SYMBOL",
            f"close symbol {symbol!r} does not match position {current_symbol!r}",
        )
    open_volume = _dec(current.get("volume")) or Decimal("0")
    if volume > open_volume + _VOLUME_EPSILON:
        raise OrderGuardRejected(
            "GUARD_CLOSE_VOLUME",
            f"close volume {volume} exceeds position volume {open_volume}",
        )


def _check_sltp(
    body: dict[str, Any],
    positions_lookup: Callable[[], list[dict[str, Any]]] | None,
    quote: dict[str, Any] | None,
) -> None:
    new_sl, _tp = _require_stops(body)
    ticket = int(_num(body, "position"))
    if ticket <= 0:
        raise OrderGuardRejected(
            "GUARD_SLTP_POSITION_REQUIRED", "SL/TP modify needs a position ticket"
        )
    bid, ask = _quote_prices(quote)
    rows = _positions(positions_lookup, code="GUARD_SLTP_UNVERIFIED")
    current = _position_row(rows, ticket, code="GUARD_SLTP_UNVERIFIED")
    is_buy = int(_num(current, "type")) == 0
    side = "buy" if is_buy else "sell"
    _require_sl_side(new_sl, side=side, bid=bid, ask=ask)
    current_sl = _dec(current.get("sl")) or Decimal("0")
    if current_sl <= 0:
        return
    widens = new_sl < current_sl if is_buy else new_sl > current_sl
    if widens:
        raise OrderGuardRejected(
            "GUARD_SL_WIDEN",
            f"stop loss may only tighten (current {current_sl}, requested {new_sl})",
        )


def enforce_order_guard(
    body: dict[str, Any],
    *,
    positions_lookup: Callable[[], list[dict[str, Any]]] | None = None,
    registry: ClientOrderIdRegistry | None = None,
    equity: Decimal | float | str | None = None,
    quote: dict[str, Any] | None = None,
    contract_size: Decimal | float | str | None = None,
) -> str:
    """Raise ``OrderGuardRejected`` unless ``body`` may reach order_send.

    Returns the order kind on success.
    """
    kind = classify_order(body)
    equity_dec = _dec(equity) if equity is not None else None
    contract_dec = _dec(contract_size) if contract_size is not None else None
    if kind == KIND_ENTRY:
        _check_entry(
            body,
            registry or _REGISTRY,
            equity=equity_dec,
            quote=quote,
            contract_size=contract_dec,
        )
    elif kind == KIND_CLOSE:
        _check_close(body, positions_lookup)
    elif kind == KIND_SLTP:
        _check_sltp(body, positions_lookup, quote)
    elif kind == KIND_MODIFY_PENDING:
        symbol = str(body.get("symbol") or "")
        if not is_gold_symbol(symbol):
            raise OrderGuardRejected(
                "GUARD_GOLD_ONLY", f"pending orders are Gold only (got {symbol!r})"
            )
        sl, _tp = _require_stops(body)
        bid, ask = _quote_prices(quote)
        _require_sl_side(sl, side=_entry_side(body), bid=bid, ask=ask)
    return kind
