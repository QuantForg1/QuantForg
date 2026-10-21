"""Gateway-side order guard: the last check before MetaTrader5.order_send.

Owner live limits (2026-10-20) enforced on this Windows host, independent of
whatever Railway sends:

- New entries: Gold only, SL > 0, TP > 0, 0 < volume <= 0.01, and a unique
  ``client_order_id`` (replays of the same id are rejected).
- Closes / partial closes: always allowed (they only reduce risk).
- SL/TP modifies: SL and TP stay > 0 and the SL may only tighten. When the
  current position cannot be read, the modify is rejected (fail closed).

``MT5_GATEWAY_EXECUTION_ENABLED`` still gates every mutation before this runs.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

from services.mt5_gateway.symbol_resolve import desk_code

# Distinct from 90001 (execution disabled) so callers can tell them apart.
RETCODE_ORDER_GUARD_REJECTED = 90002

OWNER_MAX_ENTRY_VOLUME = 0.01
CLIENT_ORDER_ID_TTL_SECONDS = 24 * 3600
_CLIENT_ORDER_ID_MAX_TRACKED = 10_000
_VOLUME_EPSILON = 1e-9

_GOLD_DESK_CODES = frozenset({"XAUUSD", "GOLD", "XAUUSDM"})
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
    """entry | close | sltp | modify_pending for an order_send payload."""
    oms_kind = str(body.get("oms_kind") or "").strip().lower()
    action = str(body.get("action") or "").strip().lower()
    if oms_kind in _SLTP_KINDS or action in _SLTP_KINDS:
        return KIND_SLTP
    if oms_kind == KIND_MODIFY_PENDING:
        return KIND_MODIFY_PENDING
    if oms_kind in _CLOSE_KINDS or int(_num(body, "position")) > 0:
        # A deal against an existing position ticket closes / reduces it.
        return KIND_CLOSE
    return KIND_ENTRY


def is_gold_symbol(symbol: str) -> bool:
    desk = desk_code(symbol)
    return desk in _GOLD_DESK_CODES or desk.startswith("XAU")


def _require_stops(body: dict[str, Any]) -> tuple[float, float]:
    sl = _num(body, "sl", "stop_loss")
    tp = _num(body, "tp", "take_profit")
    if sl <= 0:
        raise OrderGuardRejected("GUARD_SL_REQUIRED", "stop loss must be > 0")
    if tp <= 0:
        raise OrderGuardRejected("GUARD_TP_REQUIRED", "take profit must be > 0")
    return sl, tp


def _check_entry(body: dict[str, Any], registry: ClientOrderIdRegistry) -> None:
    symbol = str(body.get("symbol") or "")
    if not is_gold_symbol(symbol):
        raise OrderGuardRejected(
            "GUARD_GOLD_ONLY", f"new entries are Gold only (got {symbol!r})"
        )
    _require_stops(body)
    volume = _num(body, "volume")
    if volume <= 0 or volume > OWNER_MAX_ENTRY_VOLUME + _VOLUME_EPSILON:
        raise OrderGuardRejected(
            "GUARD_MAX_LOT",
            f"entry volume must be > 0 and <= {OWNER_MAX_ENTRY_VOLUME} (got {volume})",
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
) -> str:
    """Raise ``OrderGuardRejected`` unless ``body`` may reach order_send.

    Returns the order kind on success.
    """
    kind = classify_order(body)
    if kind == KIND_ENTRY:
        _check_entry(body, registry or _REGISTRY)
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
