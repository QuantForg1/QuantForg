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
    live_capacity_tickets,
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
    # False when positions_get failed / returned None — callers must not treat
    # empty rows as a flat book and must not invent closes.
    reliable: bool = True

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
            "reliable": self.reliable,
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


def _collect_missing_tickets(
    position_engine: Any | None,
    *,
    live_tickets: set[int],
    symbol: str | None = None,
) -> list[int]:
    """List managed tickets absent from the live MT5 book (no mutation)."""
    if position_engine is None:
        return []
    positions = getattr(position_engine, "_positions", None)
    if not isinstance(positions, dict):
        return []
    live = {int(t) for t in live_tickets}
    target = (symbol or "").strip().upper() or None
    stale: list[int] = []
    lock = getattr(position_engine, "_lock", None)

    def _scan() -> None:
        for ticket, pos in list(positions.items()):
            if target is not None:
                sym = str(getattr(pos, "symbol", "") or "").strip().upper()
                if target == GOLD_SYMBOL:
                    if sym and not is_gold_symbol(sym):
                        continue
                elif sym and sym != target:
                    continue
            if int(ticket) not in live:
                stale.append(int(ticket))

    if lock is not None:
        with lock:
            _scan()
    else:
        _scan()
    return stale


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


# Fill-lifecycle evidence (not invented): LIVE executes for these tickets were
# tagged strategy_id=trend_continuation before broker SL. Used only to restore
# attribution bindings when reconciling broker-confirmed exits after the
# missing_from_mt5_book analytics gap. Exit prices/PnL still come from deals.
_HISTORICAL_FILL_STRATEGY_BINDINGS: dict[int, str] = {
    683675942: "trend_continuation",
    683682967: "trend_continuation",
}


def _strategy_hints_for_tickets(tickets: list[int]) -> dict[int, str]:
    """Resolve fill-time strategy IDs before bindings are cleared on close."""
    hints: dict[int, str] = {}
    if not tickets:
        return hints
    try:
        from app.domain.institutional_trading.ai_scalping.strategies import (
            attribution_store as _attr_mod,
        )

        store = _attr_mod.get_strategy_attribution_store()
        for ticket in tickets:
            pid = int(ticket)
            if pid <= 0:
                continue
            bound = store.resolve(ticket=pid, position_id=pid)
            sid = str(getattr(bound, "strategy_id", "") or "").strip()
            if sid:
                hints[pid] = sid
    except Exception:
        logger.exception("close_attribution_strategy_hint_resolve_failed")
    return hints


def _attribute_stale_tickets(
    *,
    stale_tickets: list[int],
    mt5_adapter: Any,
    history_deals: list[Any] | tuple[Any, ...] | None = None,
) -> list[dict[str, Any]]:
    """Propagate broker-confirmed exits into SOE/telemetry analytics (idempotent)."""
    try:
        from app.application.services.close_attribution import (
            attribute_missing_tickets,
            get_close_attribution_ledger,
            load_history_deals_safe,
            reconcile_historical_closes,
            reconcile_pending_closes,
        )

        ledger = get_close_attribution_ledger()
        need_historical = [
            pid
            for pid in _HISTORICAL_FILL_STRATEGY_BINDINGS
            if not ledger.already_recorded(pid)
        ]
        need_history = (
            bool(stale_tickets) or bool(ledger.pending_ids()) or bool(need_historical)
        )
        if not need_history and history_deals is None:
            return []

        deals: list[Any]
        if history_deals is not None:
            deals = list(history_deals)
            hist_ok = True
        else:
            hist_ok, deals = load_history_deals_safe(mt5_adapter)
        results: list[dict[str, Any]] = []
        # Capture strategy bindings before record_closed clears them.
        hint_tickets = list(
            {int(t) for t in list(stale_tickets) + list(ledger.pending_ids()) if int(t)}
        )
        strategy_hints = _strategy_hints_for_tickets(hint_tickets)
        if stale_tickets:
            results.extend(
                attribute_missing_tickets(
                    tickets=stale_tickets,
                    deals=deals if hist_ok else [],
                    strategy_hints=strategy_hints,
                    source="missing_from_mt5_book",
                    ledger=ledger,
                )
            )
        # Retry pending + one-time historical backfill for owner-identified gaps.
        if hist_ok and deals:
            if ledger.pending_ids():
                results.extend(
                    reconcile_pending_closes(
                        deals=deals,
                        strategy_hints=strategy_hints,
                        ledger=ledger,
                    )
                )
            if need_historical:
                results.extend(
                    reconcile_historical_closes(
                        position_ids=need_historical,
                        deals=deals,
                        strategy_bindings={
                            pid: _HISTORICAL_FILL_STRATEGY_BINDINGS[pid]
                            for pid in need_historical
                        },
                        ledger=ledger,
                    )
                )
        return results
    except Exception:
        logger.exception("close_attribution_stale_hook_failed")
        return []


def force_sync_positions(
    mt5_adapter: Any,
    *,
    symbol: str = GOLD_SYMBOL,
    internal_positions: int | None = None,
    position_engine: Any | None = None,
    fresh: bool = True,
    history_deals: list[Any] | tuple[Any, ...] | None = None,
) -> PositionTruthSync:
    """Force Sync Positions — MT5 is authoritative.

    Clears adapter caches when ``fresh=True`` (pre-OMS / max-open recheck).
    Same-cycle decision reads pass ``fresh=False`` to reuse the cycle snapshot.

    Analytics: tickets absent from a **successful** positions fetch are attributed
    only after broker history confirms an exit deal. Failed / unreliable fetches
    never drop managed tickets and never invent closes.
    """
    sym = (symbol or GOLD_SYMBOL).strip().upper() or GOLD_SYMBOL
    engine_count = _internal_engine_count(position_engine, symbol=sym)
    prior_internal = (
        int(internal_positions) if internal_positions is not None else engine_count
    )

    if fresh:
        _invalidate_adapter_position_cache(mt5_adapter)

    fetch_ok = True
    fetch_error: str | None = None
    try:
        raw_rows = mt5_adapter.list_positions()
        if raw_rows is None:
            # None ≠ empty book — treat as incomplete snapshot (gateway glitch).
            fetch_ok = False
            fetch_error = "positions_snapshot_none"
            rows: list[Any] = []
        else:
            rows = list(raw_rows)
    except Exception as exc:
        fetch_ok = False
        fetch_error = str(exc) or type(exc).__name__
        rows = []
        logger.exception(
            "mt5_positions_fetch_failed_skip_repair",
            symbol=sym,
            error=fetch_error,
        )

    if not fetch_ok:
        logger.warning(
            "position_truth_fetch_unreliable",
            symbol=sym,
            error=fetch_error,
            internal_positions=prior_internal,
            action="skip_drop_and_attribution",
        )
        return PositionTruthSync(
            mt5_positions=prior_internal,
            internal_positions=prior_internal,
            repaired=False,
            symbol=sym,
            tickets=(),
            quantforg_positions=prior_internal,
            quantforg_tickets=(),
            rows=(),
            reliable=False,
        )

    # Account ticket count is observability / PME repair context.
    # QuantForg strategy cap uses identity + autonomous symbol only.
    mt5_count, tickets = _count_all_positions(rows)
    sym_count, sym_tickets = _count_symbol_positions(rows, symbol=sym)
    qf_tickets = live_capacity_tickets(
        rows, symbol=sym, execution_identity=QUANTFORG_MAGIC
    )
    qf_count = len(qf_tickets)
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
        stale = _collect_missing_tickets(
            position_engine,
            live_tickets=set(qf_tickets),
            symbol=sym,
        )
        # Always attempt attribution/pending/historical reconcile on a reliable
        # fetch — even when there are no stale PME rows (backfill path).
        _attribute_stale_tickets(
            stale_tickets=stale,
            mt5_adapter=mt5_adapter,
            history_deals=history_deals,
        )
        removed = _repair_internal_engine(
            position_engine,
            live_tickets=set(qf_tickets),
            symbol=sym,
        )
    else:
        # No PME — still allow historical/pending analytics when history is present.
        _attribute_stale_tickets(
            stale_tickets=[],
            mt5_adapter=mt5_adapter,
            history_deals=history_deals,
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


def candidate_position_truth_symbol(symbol: str | None) -> str:
    """Resolve symbol scope for candidate add-on / position-truth sync.

    Gold keeps the caller's spelling, including unsuffixed ``XAUUSD``.
    Non-gold keeps the candidate spelling. Never coerce FX/crypto/index
    to gold, and never invent an ``XAUUSD_i`` suffix.
    """
    from app.domain.trading.gold_only import (
        GOLD_SYMBOL,
        canonical_gold_execution_symbol,
        display_autonomous_symbol,
        is_gold_symbol,
    )

    raw = (symbol or "").strip()
    if not raw:
        return GOLD_SYMBOL
    if is_gold_symbol(raw):
        return canonical_gold_execution_symbol(raw)
    return display_autonomous_symbol(raw)


def apply_mt5_position_truth(
    account: AccountRiskState,
    sync: PositionTruthSync,
) -> AccountRiskState:
    """Rewrite same-symbol QuantForg open count from sync — not the account book.

    Always refreshes ``open_directions`` / ``open_entries`` from ``sync.rows``
    filtered to ``sync.symbol`` so a Gold (or other-desk) QF count cannot leave
    ``open_positions > 0`` with empty book facts on an independent candidate.
    Global ``account_open_positions`` remains the full MT5 book count.

    Unreliable syncs (gateway timeout / None snapshot) leave ``account`` unchanged.
    """
    if not bool(getattr(sync, "reliable", True)):
        return account

    from app.domain.institutional_trading.operations.quantforg_position_cap import (
        book_facts_from_positions,
        filter_quantforg_positions,
    )

    qf_n = int(getattr(sync, "quantforg_positions", 0) or 0)
    acct_n = int(getattr(sync, "mt5_positions", 0) or 0)
    sym = str(getattr(sync, "symbol", "") or "")
    rows = list(getattr(sync, "rows", ()) or ())
    owned = filter_quantforg_positions(rows, symbol=sym or None)
    dirs, entries = book_facts_from_positions(owned)
    if qf_n <= 0:
        dirs, entries = (), ()
    return replace(
        account,
        open_positions=qf_n,
        already_in_trade=bool(qf_n > 0),
        account_open_positions=acct_n,
        open_directions=tuple(dirs),
        open_entries=tuple(entries),
    )
