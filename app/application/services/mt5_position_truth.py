"""MT5 position truth — force-sync open counts before execution gates.

MT5 (gateway positions_get / adapter list_positions) is the source of truth.
Never block Auto Trading solely on a stale internal/cache count.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from app.domain.institutional_trading.decision_models import AccountRiskState
from app.domain.trading.gold_only import GOLD_SYMBOL, is_gold_symbol
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class PositionTruthSync:
    """Result of one Force Sync Positions operation."""

    mt5_positions: int
    internal_positions: int
    repaired: bool
    symbol: str
    tickets: tuple[int, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "mt5_positions": self.mt5_positions,
            "internal_positions": self.internal_positions,
            "repaired": self.repaired,
            "symbol": self.symbol,
            "tickets": list(self.tickets),
        }


def _invalidate_adapter_position_cache(mt5_adapter: Any) -> None:
    """Clear gateway/client position caches so the next read hits MT5."""
    client = getattr(mt5_adapter, "client", None) or getattr(
        mt5_adapter, "_client", None
    )
    if client is None:
        return
    invalidate = getattr(client, "invalidate_positions_cache", None)
    if callable(invalidate):
        invalidate()
        return
    clear = getattr(client, "_clear_data_caches", None)
    if callable(clear):
        clear()
        return
    if hasattr(client, "_positions_cache"):
        client._positions_cache = None
        client._positions_cache_at = 0.0


def _ticket_of(row: Any) -> int:
    try:
        return int(getattr(row, "ticket", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _count_all_positions(rows: list[Any] | None) -> tuple[int, tuple[int, ...]]:
    """Account-level open count — every live MT5 ticket (multi-symbol desk)."""
    tickets = [_ticket_of(p) for p in rows or []]
    tickets = [t for t in tickets if t > 0]
    return len(tickets), tuple(tickets)


def _count_symbol_positions(
    rows: list[Any] | None, *, symbol: str
) -> tuple[int, tuple[int, ...]]:
    target = (symbol or GOLD_SYMBOL).strip().upper()
    tickets: list[int] = []
    for p in rows or []:
        sym = str(getattr(p, "symbol", "") or "").strip().upper()
        if target == GOLD_SYMBOL:
            if not is_gold_symbol(sym):
                continue
        elif sym != target:
            continue
        t = _ticket_of(p)
        if t > 0:
            tickets.append(t)
    return len(tickets), tuple(tickets)


def _internal_engine_count(position_engine: Any | None, *, symbol: str) -> int:
    if position_engine is None:
        return 0
    positions = getattr(position_engine, "_positions", None)
    if not isinstance(positions, dict):
        return 0
    target = (symbol or GOLD_SYMBOL).strip().upper()
    n = 0
    for pos in positions.values():
        sym = str(getattr(pos, "symbol", "") or "").strip().upper()
        if target == GOLD_SYMBOL:
            if is_gold_symbol(sym) or not sym:
                n += 1
        elif sym == target or not sym:
            n += 1
    return n


def _repair_internal_engine(
    position_engine: Any | None,
    *,
    live_tickets: set[int],
    symbol: str | None = None,
) -> int:
    """Drop managed tickets that no longer exist on MT5. Returns removed count.

    Symbol-scoped repair never drops tickets for other symbols.
    """
    if position_engine is None:
        return 0
    drop = getattr(position_engine, "drop_missing_tickets", None)
    if callable(drop):
        try:
            return int(drop(live_tickets, symbol=symbol) or 0)
        except TypeError:
            # Older engines without symbol kwarg — fall through carefully
            if symbol is None:
                return int(drop(live_tickets) or 0)
    positions = getattr(position_engine, "_positions", None)
    if not isinstance(positions, dict):
        return 0
    target = (symbol or "").strip().upper() or None
    lock = getattr(position_engine, "_lock", None)
    removed = 0
    stale: list[int] = []
    for ticket, pos in list(positions.items()):
        if target is not None:
            sym = str(getattr(pos, "symbol", "") or "").strip().upper()
            if target == GOLD_SYMBOL:
                if sym and not is_gold_symbol(sym):
                    continue
            elif sym and sym != target:
                continue
        if int(ticket) not in live_tickets:
            stale.append(int(ticket))
    if lock is not None:
        with lock:
            for ticket in stale:
                if positions.pop(ticket, None) is not None:
                    removed += 1
                    logger.warning(
                        "Position Closed",
                        ticket=ticket,
                        reason="missing_from_mt5_book",
                        symbol=target or "",
                    )
    else:
        for ticket in stale:
            if positions.pop(ticket, None) is not None:
                removed += 1
                logger.warning(
                    "Position Closed",
                    ticket=ticket,
                    reason="missing_from_mt5_book",
                    symbol=target or "",
                )
    return removed


def force_sync_positions(
    mt5_adapter: Any,
    *,
    symbol: str = GOLD_SYMBOL,
    internal_positions: int | None = None,
    position_engine: Any | None = None,
) -> PositionTruthSync:
    """Force Sync Positions — MT5 is authoritative.

    Clears adapter caches, re-queries live positions, logs both counts, and
    repairs internal PME state when it disagrees with MT5.
    """
    sym = (symbol or GOLD_SYMBOL).strip().upper() or GOLD_SYMBOL
    engine_count = _internal_engine_count(position_engine, symbol=sym)
    prior_internal = (
        int(internal_positions) if internal_positions is not None else engine_count
    )

    _invalidate_adapter_position_cache(mt5_adapter)
    rows = list(mt5_adapter.list_positions() or [])
    # Account gate uses ALL open tickets. Symbol filter is only for PME repair
    # scope — never report "MT5 positions: 0" while another symbol is live.
    mt5_count, tickets = _count_all_positions(rows)
    sym_count, sym_tickets = _count_symbol_positions(rows, symbol=sym)

    logger.warning("MT5 positions: %s", mt5_count)
    logger.warning("Internal positions: %s", prior_internal)
    if sym_count != mt5_count:
        logger.warning(
            "MT5 positions symbol_scope",
            symbol=sym,
            count=sym_count,
            tickets=list(sym_tickets),
            account_count=mt5_count,
        )

    repaired = False
    if mt5_count != prior_internal or (
        position_engine is not None and engine_count != sym_count
    ):
        removed = _repair_internal_engine(
            position_engine,
            live_tickets=set(sym_tickets),
            symbol=sym,
        )
        repaired = True
        logger.warning(
            "position_truth_repaired",
            mt5_positions=mt5_count,
            symbol_positions=sym_count,
            internal_positions=prior_internal,
            engine_positions_before=engine_count,
            removed_stale=removed,
            tickets=list(tickets),
            symbol_tickets=list(sym_tickets),
            symbol=sym,
        )

    return PositionTruthSync(
        mt5_positions=mt5_count,
        internal_positions=prior_internal,
        repaired=repaired,
        symbol=sym,
        tickets=tickets,
    )


def apply_mt5_position_truth(
    account: AccountRiskState,
    sync: PositionTruthSync,
) -> AccountRiskState:
    """Rewrite AccountRiskState open count from MT5 truth."""
    return replace(
        account,
        open_positions=int(sync.mt5_positions),
        already_in_trade=bool(sync.mt5_positions > 0),
    )
