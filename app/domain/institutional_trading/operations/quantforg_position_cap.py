"""Authoritative QuantForg live position capacity.

Does not submit orders, change OMS/Gateway, or weaken Risk/Safety.

Strategy cap, same-symbol duplicate, and PME management count only
positions owned by the QuantForg execution identity:

    magic == 260720 AND canonical gold (XAUUSD_i)

magic=0 is always manual. Comment prefix (ite:v1) must not promote a
manual ticket. Account-wide ticket counts remain observability and must
not consume QuantForg strategy capacity.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.domain.trading.gold_only import (
    CANONICAL_GOLD_BROKER_DISPLAY,
    is_gold_symbol,
)

# Existing production identity — ExecutionBridgeConfig.magic / PME magic.
QUANTFORG_MAGIC = 260720
QUANTFORG_COMMENT_PREFIX = "ite:v1"

OWNER_QUANTFORG = "QUANTFORG"
OWNER_MANUAL = "MANUAL"
OWNER_OTHER_EA = "OTHER_EA"
OWNER_UNKNOWN = "UNKNOWN"


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def position_magic(row: Any) -> int:
    try:
        return int(_row_get(row, "magic", 0) or 0)
    except (TypeError, ValueError):
        return 0


def position_symbol(row: Any) -> str:
    return str(_row_get(row, "symbol", "") or "").strip()


def position_comment(row: Any) -> str:
    return str(_row_get(row, "comment", "") or "").strip()


def belongs_to_quantforg(
    row: Any,
    *,
    magic: int = QUANTFORG_MAGIC,
) -> bool:
    """True when MT5 magic is the QuantForg execution identity.

    magic=0 is always manual/unrelated — comment prefix must not promote it.
    """
    return position_magic(row) == int(magic)


def classify_position_owner(
    row: Any,
    *,
    magic: int = QUANTFORG_MAGIC,
) -> str:
    mid = position_magic(row)
    if mid == int(magic):
        if matches_autonomous_symbol(row):
            return OWNER_QUANTFORG
        return OWNER_UNKNOWN
    if mid == 0:
        return OWNER_MANUAL
    return OWNER_OTHER_EA


def is_quantforg_owned_position(
    row: Any,
    *,
    magic: int = QUANTFORG_MAGIC,
    symbol: str | None = None,
) -> bool:
    """Authoritative QuantForg strategy ownership for Gold autonomous execution."""
    return belongs_to_quantforg(row, magic=magic) and matches_autonomous_symbol(
        row, symbol=symbol
    )


def ownership_observability(
    row: Any,
    *,
    magic: int = QUANTFORG_MAGIC,
    symbol: str | None = None,
) -> dict[str, Any]:
    owner = classify_position_owner(row, magic=magic)
    owned = is_quantforg_owned_position(row, magic=magic, symbol=symbol)
    return {
        "position_owner": owner,
        "quantforg_owned": owned,
        "is_manual": owner == OWNER_MANUAL,
        "is_same_symbol": matches_autonomous_symbol(row, symbol=symbol),
        "consumes_quantforg_capacity": owned,
        "managed_by_pme": owned,
        "magic": position_magic(row),
        "symbol": position_symbol(row),
    }


def quantforg_open_symbols(
    rows: list[Any] | tuple[Any, ...] | None,
    *,
    magic: int = QUANTFORG_MAGIC,
    symbol: str | None = None,
) -> set[str]:
    out: set[str] = set()
    for row in rows or ():
        if not is_quantforg_owned_position(row, magic=magic, symbol=symbol):
            continue
        sym = position_symbol(row).upper()
        if sym:
            out.add(sym)
    return out


def is_quantforg_same_symbol_open(
    candidate_symbol: str | None,
    open_syms: set[str] | list[str] | tuple[str, ...],
) -> bool:
    """True when a QuantForg-owned ticket already occupies this symbol."""
    cand = (candidate_symbol or "").strip().upper()
    if not cand:
        return False
    owned = {str(s).strip().upper() for s in open_syms if str(s).strip()}
    if cand in owned:
        return True
    return is_gold_symbol(cand) and any(is_gold_symbol(s) for s in owned)


def purge_non_quantforg_from_engine(
    engine: Any | None,
    *,
    magic: int = QUANTFORG_MAGIC,
    symbol: str | None = None,
) -> int:
    """Drop manual/other-EA tickets from PME. Never mutates broker tickets."""
    if engine is None:
        return 0
    positions = getattr(engine, "_positions", None)
    if not isinstance(positions, dict):
        return 0
    from core.logging import get_logger

    logger = get_logger(__name__)
    lock = getattr(engine, "_lock", None)
    stale: list[int] = []
    for ticket, pos in list(positions.items()):
        if symbol is not None and not matches_autonomous_symbol(pos, symbol=symbol):
            continue
        if is_quantforg_owned_position(pos, magic=magic, symbol=symbol):
            continue
        stale.append(int(ticket))

    def _drop() -> int:
        n = 0
        for ticket in stale:
            pos = positions.pop(ticket, None)
            if pos is None:
                continue
            n += 1
            obs = ownership_observability(pos, magic=magic, symbol=symbol)
            logger.warning(
                "pme_dropped_non_owned",
                ticket=ticket,
                reason="NOT_QUANTFORG_OWNED",
                **obs,
            )
        return n

    if lock is not None:
        with lock:
            return _drop()
    return _drop()


def matches_autonomous_symbol(
    row: Any,
    *,
    symbol: str | None = None,
) -> bool:
    """Gold-only cap matches catalogue gold, never an unrelated desk."""
    pos = position_symbol(row)
    requested = (symbol or CANONICAL_GOLD_BROKER_DISPLAY).strip()
    if is_gold_symbol(requested) or not requested:
        return is_gold_symbol(pos)
    return pos.upper() == requested.upper()


def filter_quantforg_positions(
    rows: list[Any] | tuple[Any, ...] | None,
    *,
    symbol: str | None = None,
    magic: int = QUANTFORG_MAGIC,
) -> list[Any]:
    return [
        row
        for row in rows or ()
        if is_quantforg_owned_position(row, magic=magic, symbol=symbol)
    ]


def engine_position_rows(engine: Any | None) -> list[Any]:
    if engine is None:
        return []
    positions = getattr(engine, "_positions", None)
    if not isinstance(positions, dict):
        return []
    return list(positions.values())


def same_symbol_ownership_facts(
    rows: list[Any] | tuple[Any, ...] | None,
    *,
    candidate_symbol: str | None = None,
    magic: int = QUANTFORG_MAGIC,
) -> dict[str, Any]:
    """Scanner/capacity observability — strategy vs account vs manual."""
    cand = (candidate_symbol or CANONICAL_GOLD_BROKER_DISPLAY).strip().upper()
    qf = 0
    account = 0
    manual_same = 0
    for row in rows or ():
        account += 1
        owned = is_quantforg_owned_position(row, magic=magic, symbol=candidate_symbol)
        same = matches_autonomous_symbol(row, symbol=candidate_symbol)
        if owned:
            qf += 1
        elif classify_position_owner(row, magic=magic) == OWNER_MANUAL and same:
            manual_same += 1
    qf_syms = quantforg_open_symbols(rows, magic=magic, symbol=candidate_symbol)
    already = is_quantforg_same_symbol_open(cand, qf_syms)
    if already:
        reason = "QUANTFORG_SAME_SYMBOL_OPEN"
        capacity_reason = "QUANTFORG_OWNED_CONSUMES_CAPACITY"
    elif manual_same > 0:
        reason = "MANUAL_SAME_SYMBOL_PRESENT"
        capacity_reason = "MANUAL_DOES_NOT_CONSUME_QUANTFORG_CAPACITY"
    else:
        reason = "NO_QUANTFORG_SAME_SYMBOL"
        capacity_reason = "QUANTFORG_CAPACITY_AVAILABLE"
    return {
        "candidate_symbol": cand,
        "quantforg_open_count": qf,
        "account_open_count": account,
        "manual_same_symbol_count": manual_same,
        "already_open": already,
        "already_open_reason": reason,
        "capacity_reason": capacity_reason,
        "candidate_allowed": not already,
        "quantforg_open_symbols": sorted(qf_syms),
    }


def count_quantforg_positions(
    rows: list[Any] | tuple[Any, ...] | None,
    *,
    symbol: str = CANONICAL_GOLD_BROKER_DISPLAY,
    execution_identity: int = QUANTFORG_MAGIC,
) -> int:
    """Live QuantForg strategy count for XAUUSD_i (existing magic identity)."""
    return len(
        filter_quantforg_positions(
            rows, symbol=symbol, magic=execution_identity
        )
    )


def count_account_positions(rows: list[Any] | tuple[Any, ...] | None) -> int:
    n = 0
    for row in rows or ():
        try:
            ticket = int(_row_get(row, "ticket", 0) or 0)
        except (TypeError, ValueError):
            ticket = 0
        if ticket > 0:
            n += 1
    return n


def live_strategy_max_open(ite_config: Any | None) -> int:
    """Authoritative live cap: ITE / scalping config. Never invent a new number."""
    raw = getattr(ite_config, "max_open_trades", None)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 1
    mode = str(getattr(ite_config, "trading_mode", "") or "").strip().lower()
    if mode == "scalping":
        from app.domain.institutional_trading.ai_scalping.profiles.scalping_v1 import (
            align_live_scalp_cap,
        )

        return align_live_scalp_cap(value, trading_mode="scalping")
    return max(1, value)


def capacity_available(*, current_count: int, configured_max: int) -> bool:
    return int(current_count) < max(1, int(configured_max))


def book_facts_from_positions(
    rows: list[Any] | tuple[Any, ...] | None,
) -> tuple[tuple[str, ...], tuple[Any, ...]]:
    from decimal import Decimal

    directions: list[str] = []
    entries: list[Decimal] = []
    for row in rows or ():
        side = str(_row_get(row, "side", "") or "").strip().upper()
        if side in {"BUY", "SELL"}:
            directions.append(side)
        try:
            entry_px = Decimal(str(_row_get(row, "open_price", 0) or 0))
        except Exception:
            entry_px = Decimal("0")
        if entry_px > 0:
            entries.append(entry_px)
    return tuple(directions), tuple(entries)


@dataclass(frozen=True, slots=True)
class QuantForgPositionSnapshot:
    """Same-cycle position facts for the strategy cap vs account observability."""

    as_of: str
    symbol: str
    magic: int
    quantforg_count: int
    account_count: int
    configured_max: int
    capacity_available: bool
    tickets: tuple[int, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "as_of": self.as_of,
            "symbol": self.symbol,
            "execution_identity": self.magic,
            "quantforg_count": self.quantforg_count,
            "account_count": self.account_count,
            "configured_max": self.configured_max,
            "capacity_available": self.capacity_available,
            "tickets": list(self.tickets),
            "source": "quantforg_position_cap",
        }


def snapshot_quantforg_positions(
    rows: list[Any] | tuple[Any, ...] | None,
    *,
    symbol: str = CANONICAL_GOLD_BROKER_DISPLAY,
    execution_identity: int = QUANTFORG_MAGIC,
    configured_max: int = 1,
    as_of: datetime | None = None,
) -> QuantForgPositionSnapshot:
    owned = filter_quantforg_positions(
        rows, symbol=symbol, magic=execution_identity
    )
    tickets: list[int] = []
    for row in owned:
        try:
            ticket = int(_row_get(row, "ticket", 0) or 0)
        except (TypeError, ValueError):
            ticket = 0
        if ticket > 0:
            tickets.append(ticket)
    count = len(owned)
    cap = max(1, int(configured_max))
    stamp = as_of or datetime.now(UTC)
    as_of_s = stamp.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return QuantForgPositionSnapshot(
        as_of=as_of_s,
        symbol=symbol,
        magic=execution_identity,
        quantforg_count=count,
        account_count=count_account_positions(rows),
        configured_max=cap,
        capacity_available=capacity_available(
            current_count=count, configured_max=cap
        ),
        tickets=tuple(tickets),
    )
