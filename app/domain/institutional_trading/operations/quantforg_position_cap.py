"""Authoritative QuantForg live position capacity.

Does not submit orders, change OMS/Gateway, or weaken Risk/Safety.

Strategy cap counts only positions owned by the existing QuantForg
execution identity (MT5 magic 260720 / comment prefix ite:v1) on the
autonomous gold symbol. Account-wide ticket counts remain observability
and must not consume QuantForg capacity.
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
    """True when the ticket was opened by the QuantForg execution identity."""
    if position_magic(row) == int(magic):
        return True
    comment = position_comment(row)
    return comment.startswith(QUANTFORG_COMMENT_PREFIX) or comment.startswith("FORCE:")


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
    out: list[Any] = []
    for row in rows or ():
        if belongs_to_quantforg(row, magic=magic) and matches_autonomous_symbol(
            row, symbol=symbol
        ):
            out.append(row)
    return out


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
