"""Gateway-side order guard: the last check before MetaTrader5.order_send.

Enforced on this Windows host, independent of whatever Railway sends:

- New entries: XAUUSD only, protective SL/TP on the correct side of the live
  quote, 0 < volume <= 0.01, planned loss at or under 9% of live equity, no
  second Gold position, no working Gold pending order, and a unique
  ``client_order_id``.
- Closes / partial closes: an explicit close kind, a ticket that is open, the
  same Gold symbol, and a volume that does not exceed the open volume.
- SL/TP modifies: SL and TP stay > 0 and the SL may only tighten. When the
  current position cannot be read, the modify is rejected (fail closed).

``MT5_GATEWAY_EXECUTION_ENABLED`` still gates every mutation before this runs.
A missing quote, equity read, or position read rejects the entry. This module
never invents a stop.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from decimal import Decimal
from typing import Any

from app.domain.institutional_trading.owner_live_limits import max_planned_risk_usd
from app.domain.trading.gold_only import is_gold_symbol

# Distinct from 90001 (execution disabled) so callers can tell them apart.
RETCODE_ORDER_GUARD_REJECTED = 90002

OWNER_MAX_ENTRY_VOLUME = 0.01
_CENTS = Decimal("0.01")
CLIENT_ORDER_ID_TTL_SECONDS = 24 * 3600
_CLIENT_ORDER_ID_MAX_TRACKED = 10_000
_VOLUME_EPSILON = 1e-9

_CLOSE_KINDS = frozenset({"close", "partial_close"})
_SLTP_KINDS = frozenset({"sltp", "modify_sltp"})

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


def classify_order(body: dict[str, Any]) -> str:
    """entry | close | sltp | modify_pending for an order_send payload.

    A position ticket without an explicit close kind is not a close. Treating
    it as one skipped the entry checks and could hedge or close the wrong trade.
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


def _require_stops(body: dict[str, Any]) -> tuple[float, float]:
    sl = _num(body, "sl", "stop_loss")
    tp = _num(body, "tp", "take_profit")
    if sl <= 0:
        raise OrderGuardRejected("GUARD_SL_REQUIRED", "stop loss must be > 0")
    if tp <= 0:
        raise OrderGuardRejected("GUARD_TP_REQUIRED", "take profit must be > 0")
    return sl, tp


def _norm_symbol(symbol: str) -> str:
    return "".join(ch for ch in str(symbol or "").upper() if ch.isalnum())


def _side(body: dict[str, Any]) -> str:
    action = str(body.get("action") or "").strip().lower()
    if action.startswith("buy"):
        return "BUY"
    if action.startswith("sell"):
        return "SELL"
    return ""


def _decimal(value: object) -> Decimal | None:
    try:
        parsed = Decimal(str(value))
    except Exception:
        return None
    if not parsed.is_finite():
        return None
    return parsed


def _read_positions(
    positions_lookup: Callable[[], list[dict[str, Any]]] | None,
    *,
    code: str,
) -> list[dict[str, Any]]:
    if positions_lookup is None:
        raise OrderGuardRejected(code, "open positions could not be read")
    try:
        return list(positions_lookup())
    except OrderGuardRejected:
        raise
    except Exception:
        raise OrderGuardRejected(code, "open positions could not be read") from None


def _planned_loss_usd(
    *,
    volume: Decimal,
    price: Decimal,
    stop: Decimal,
    quote: dict[str, Any],
) -> Decimal:
    specs = quote.get("specs") if isinstance(quote.get("specs"), dict) else {}
    tick_size = _decimal((specs or {}).get("tick_size"))
    tick_value = _decimal((specs or {}).get("tick_value"))
    contract = _decimal((specs or {}).get("contract_size"))
    distance = abs(price - stop)
    if (
        tick_size is not None
        and tick_value is not None
        and tick_size > 0
        and tick_value > 0
    ):
        return (volume * (distance / tick_size) * tick_value).quantize(_CENTS)
    if contract is not None and contract > 0:
        return (volume * distance * contract).quantize(_CENTS)
    raise OrderGuardRejected(
        "GUARD_RISK_UNAVAILABLE", "planned loss cannot be priced from the live quote"
    )


def _check_entry(
    body: dict[str, Any],
    registry: ClientOrderIdRegistry,
    *,
    positions_lookup: Callable[[], list[dict[str, Any]]] | None,
    equity: Decimal | None,
    quote: dict[str, Any] | None,
    orders_lookup: Callable[[], list[dict[str, Any]]] | None = None,
) -> None:
    if int(_num(body, "position")) > 0:
        raise OrderGuardRejected(
            "GUARD_ENTRY_POSITION",
            "a new entry cannot carry a position ticket",
        )
    symbol = str(body.get("symbol") or "")
    if not is_gold_symbol(symbol):
        raise OrderGuardRejected(
            "GUARD_GOLD_ONLY", f"new entries are XAUUSD only (got {symbol!r})"
        )
    sl, _tp = _require_stops(body)
    volume = _num(body, "volume")
    if volume <= 0 or volume > OWNER_MAX_ENTRY_VOLUME + _VOLUME_EPSILON:
        raise OrderGuardRejected(
            "GUARD_MAX_LOT",
            f"entry volume must be > 0 and <= {OWNER_MAX_ENTRY_VOLUME} (got {volume})",
        )
    rows = _read_positions(positions_lookup, code="GUARD_POSITIONS_UNVERIFIED")
    for row in rows:
        if _num(row, "volume") <= 0:
            continue
        if is_gold_symbol(str(row.get("symbol") or row.get("code") or "")):
            raise OrderGuardRejected(
                "GUARD_HEDGE",
                "an open Gold position already exists; a second entry is blocked",
            )
    if orders_lookup is not None:
        try:
            pending = list(orders_lookup())
        except OrderGuardRejected:
            raise
        except Exception:
            raise OrderGuardRejected(
                "GUARD_ORDERS_UNVERIFIED",
                "pending orders could not be read",
            ) from None
        for row in pending:
            pending_volume = _num(row, "volume_current")
            if pending_volume <= 0:
                pending_volume = _num(row, "volume")
            if pending_volume <= 0:
                continue
            if is_gold_symbol(str(row.get("symbol") or row.get("code") or "")):
                raise OrderGuardRejected(
                    "GUARD_PENDING_EXPOSURE",
                    "a working Gold order already uses the entry budget",
                )
    if equity is None or equity <= 0:
        raise OrderGuardRejected(
            "GUARD_EQUITY_UNAVAILABLE", "live equity is required before sizing"
        )
    if not isinstance(quote, dict):
        raise OrderGuardRejected(
            "GUARD_QUOTE_UNAVAILABLE", "a live quote is required before sizing"
        )
    bid = _decimal(quote.get("bid"))
    ask = _decimal(quote.get("ask"))
    if bid is None or ask is None or bid <= 0 or ask <= 0 or ask < bid:
        raise OrderGuardRejected(
            "GUARD_QUOTE_UNAVAILABLE", "the live quote has no usable bid and ask"
        )
    side = _side(body)
    stop = Decimal(str(sl))
    if side == "BUY":
        if not (stop < bid):
            raise OrderGuardRejected(
                "GUARD_SL_WRONG_SIDE", "BUY stop loss must be below the live bid"
            )
        reference = ask
    elif side == "SELL":
        if not (stop > ask):
            raise OrderGuardRejected(
                "GUARD_SL_WRONG_SIDE", "SELL stop loss must be above the live ask"
            )
        reference = bid
    else:
        raise OrderGuardRejected("GUARD_SIDE", "entry side must be buy or sell")
    loss = _planned_loss_usd(
        volume=Decimal(str(volume)), price=reference, stop=stop, quote=quote
    )
    cap = max_planned_risk_usd(equity)
    if loss > cap:
        raise OrderGuardRejected(
            "GUARD_MAX_RISK",
            f"planned loss {loss} exceeds 9% of equity ({cap})",
        )
    client_order_id = str(body.get("client_order_id") or "").strip()
    if not client_order_id:
        raise OrderGuardRejected(
            "GUARD_CLIENT_ORDER_ID_REQUIRED", "client_order_id is required"
        )
    # Claimed last, so a rejected entry never burns its id.
    if not registry.claim(client_order_id):
        raise OrderGuardRejected(
            "GUARD_DUPLICATE_CLIENT_ORDER_ID",
            f"client_order_id already used: {client_order_id}",
        )


def _check_close(
    body: dict[str, Any],
    positions_lookup: Callable[[], list[dict[str, Any]]] | None,
) -> None:
    ticket = int(_num(body, "position"))
    if ticket <= 0:
        raise OrderGuardRejected(
            "GUARD_CLOSE_TICKET_REQUIRED", "a close needs the open position ticket"
        )
    rows = _read_positions(positions_lookup, code="GUARD_CLOSE_UNVERIFIED")
    current = next((row for row in rows if int(_num(row, "ticket")) == ticket), None)
    if current is None:
        raise OrderGuardRejected(
            "GUARD_CLOSE_UNVERIFIED", f"position {ticket} is not open"
        )
    requested = _norm_symbol(str(body.get("symbol") or ""))
    opened = _norm_symbol(str(current.get("symbol") or current.get("code") or ""))
    if not requested or not opened or requested != opened:
        raise OrderGuardRejected(
            "GUARD_CLOSE_SYMBOL", "close symbol must match the open position"
        )
    if not is_gold_symbol(requested):
        raise OrderGuardRejected(
            "GUARD_GOLD_ONLY", "closes are limited to the open XAUUSD position"
        )
    volume = _num(body, "volume")
    opened_volume = _num(current, "volume")
    if volume <= 0 or volume > opened_volume + _VOLUME_EPSILON:
        raise OrderGuardRejected(
            "GUARD_CLOSE_VOLUME",
            f"close volume must be > 0 and <= open volume {opened_volume}",
        )


def _check_sltp(
    body: dict[str, Any],
    positions_lookup: Callable[[], list[dict[str, Any]]] | None,
) -> None:
    new_sl, _ = _require_stops(body)
    ticket = int(_num(body, "position"))
    if ticket <= 0:
        raise OrderGuardRejected(
            "GUARD_SLTP_POSITION_REQUIRED", "SL/TP modify needs a position ticket"
        )
    try:
        rows = list(positions_lookup() if positions_lookup is not None else [])
    except Exception as exc:  # any lookup failure fails closed
        raise OrderGuardRejected(
            "GUARD_SLTP_UNVERIFIED", f"cannot read position {ticket}: {exc}"
        ) from exc
    current = next((r for r in rows if int(_num(r, "ticket")) == ticket), None)
    if current is None:
        raise OrderGuardRejected(
            "GUARD_SLTP_UNVERIFIED", f"position {ticket} not found"
        )
    current_sl = _num(current, "sl")
    if current_sl <= 0:
        # No broker SL yet: setting one only reduces risk.
        return
    is_buy = int(_num(current, "type")) == 0
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
    equity: Decimal | None = None,
    quote: dict[str, Any] | None = None,
    orders_lookup: Callable[[], list[dict[str, Any]]] | None = None,
) -> str:
    """Raise ``OrderGuardRejected`` unless ``body`` may reach order_send.

    Returns the order kind on success. Entries require live equity, a live
    quote, and a position read. Those are never invented here.
    """
    kind = classify_order(body)
    if kind == KIND_ENTRY:
        _check_entry(
            body,
            registry or _REGISTRY,
            positions_lookup=positions_lookup,
            equity=equity,
            quote=quote,
            orders_lookup=orders_lookup,
        )
    elif kind == KIND_CLOSE:
        _check_close(body, positions_lookup)
    elif kind == KIND_SLTP:
        _check_sltp(body, positions_lookup)
    elif kind == KIND_MODIFY_PENDING:
        symbol = str(body.get("symbol") or "")
        if not is_gold_symbol(symbol):
            raise OrderGuardRejected(
                "GUARD_GOLD_ONLY", f"pending orders are Gold only (got {symbol!r})"
            )
        _require_stops(body)
    return kind
