"""MT5 position truth — force-sync open counts before execution gates.

MT5 (gateway positions_get / adapter list_positions) is the source of truth.
Never block Auto Trading solely on a stale internal/cache count.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from app.domain.institutional_trading.decision_models import AccountRiskState
from app.domain.institutional_trading.operations.quantforg_position_cap import (
    QUANTFORG_MAGIC,
    count_quantforg_positions,
    filter_quantforg_positions,
    purge_non_quantforg_from_engine,
)
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
    quantforg_positions: int = 0
    quantforg_tickets: tuple[int, ...] = ()
    rows: tuple[Any, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "mt5_positions": self.mt5_positions,
            "internal_positions": self.internal_positions,
            "repaired": self.repaired,
            "symbol": self.symbol,
            "tickets": list(self.tickets),
            "quantforg_positions": self.quantforg_positions,
            "quantforg_tickets": list(self.quantforg_tickets),
            "account_positions": self.mt5_positions,
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
    return count_quantforg_positions(
        list(positions.values()),
        symbol=symbol,
        execution_identity=QUANTFORG_MAGIC,
    )


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
    fresh: bool = True,
) -> PositionTruthSync:
    """Force Sync Positions — MT5 is authoritative.

    Clears adapter caches when ``fresh=True`` (pre-OMS / max-open recheck).
    Same-cycle decision reads pass ``fresh=False`` to reuse the cycle snapshot.
    """
    sym = (symbol or GOLD_SYMBOL).strip().upper() or GOLD_SYMBOL
    engine_count = _internal_engine_count(position_engine, symbol=sym)
    prior_internal = (
        int(internal_positions) if internal_positions is not None else engine_count
    )

    if fresh:
        _invalidate_adapter_position_cache(mt5_adapter)
    rows = list(mt5_adapter.list_positions() or [])
    # Account ticket count is observability / PME repair context.
    # QuantForg strategy cap uses identity + autonomous symbol only.
    mt5_count, tickets = _count_all_positions(rows)
    sym_count, sym_tickets = _count_symbol_positions(rows, symbol=sym)
    qf_rows = filter_quantforg_positions(rows, symbol=sym, magic=QUANTFORG_MAGIC)
    qf_count = count_quantforg_positions(
        rows, symbol=sym, execution_identity=QUANTFORG_MAGIC
    )
    qf_tickets = tuple(
        t
        for t in (_ticket_of(p) for p in qf_rows)
        if t > 0
    )
    purged = purge_non_quantforg_from_engine(position_engine, symbol=sym)
    engine_count = _internal_engine_count(position_engine, symbol=sym)

    logger.warning("MT5 positions: %s", mt5_count)
    logger.warning("Internal positions: %s", prior_internal)
    logger.warning(
        "quantforg_position_cap",
        symbol=sym,
        quantforg_positions=qf_count,
        account_positions=mt5_count,
        magic=QUANTFORG_MAGIC,
        pme_purged_non_owned=purged,
    )
    if sym_count != mt5_count:
        logger.warning(
            "MT5 positions symbol_scope",
            symbol=sym,
            count=sym_count,
            tickets=list(sym_tickets),
            account_count=mt5_count,
        )

    repaired = False
    removed = 0
    if position_engine is not None:
        removed = _repair_internal_engine(
            position_engine,
            live_tickets=set(qf_tickets),
            symbol=sym,
        )
    if (
        mt5_count != prior_internal
        or purged > 0
        or removed > 0
        or (position_engine is not None and engine_count != qf_count)
    ):
        repaired = True
        logger.warning(
            "position_truth_repaired",
            mt5_positions=mt5_count,
            symbol_positions=sym_count,
            quantforg_positions=qf_count,
            internal_positions=prior_internal,
            engine_positions_before=engine_count,
            removed_stale=removed,
            pme_purged_non_owned=purged,
            tickets=list(tickets),
            symbol_tickets=list(sym_tickets),
            quantforg_tickets=list(qf_tickets),
            symbol=sym,
        )

    return PositionTruthSync(
        mt5_positions=mt5_count,
        internal_positions=prior_internal,
        repaired=repaired,
        symbol=sym,
        tickets=tickets,
        quantforg_positions=qf_count,
        quantforg_tickets=qf_tickets,
        rows=tuple(rows),
    )


def apply_mt5_position_truth(
    account: AccountRiskState,
    sync: PositionTruthSync,
) -> AccountRiskState:
    """Rewrite strategy cap from QuantForg identity — not the account book."""
    qf_n = int(getattr(sync, "quantforg_positions", 0) or 0)
    acct_n = int(getattr(sync, "mt5_positions", 0) or 0)
    return replace(
        account,
        open_positions=qf_n,
        already_in_trade=bool(qf_n > 0),
        account_open_positions=acct_n,
    )
