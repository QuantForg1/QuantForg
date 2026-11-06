"""Durable SELL-cascade anchors — Postgres, account-aware, fail-closed.

Mirrors ``buy_cascade_anchor_store`` so SELL re-entry after a broker-confirmed
losing SELL cannot silently bypass protection. Process memory is only a cache.
A restart reloads ``status='active'`` rows before a new SELL is allowed. If the
table cannot be read, new SELL entries are blocked. BUY and position
management do not use this store.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from threading import RLock
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

PROTECTION_UNAVAILABLE = "SELL_CASCADE_PROTECTION_UNAVAILABLE"

_LOCK = RLock()
_CACHE: dict[tuple[str, int], dict[str, Any]] = {}
_DURABLE: dict[tuple[str, int], dict[str, Any]] = {}
_KNOWN: set[tuple[str, int]] = set()
_LOADED = False
_TRUSTED = True
_FORCED_DOWN = False
_LIVE_LOGIN: int | None = None

_CREATE = """
CREATE TABLE IF NOT EXISTS public.sell_cascade_anchor (
    symbol TEXT NOT NULL,
    position_id BIGINT NOT NULL,
    entry_price NUMERIC NOT NULL,
    closed_at TIMESTAMPTZ NOT NULL,
    net_pnl NUMERIC NOT NULL,
    close_outcome TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    release_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (symbol, position_id)
)
"""

_LOCKDOWN = """
DO $lock$
BEGIN
  EXECUTE 'ALTER TABLE public.sell_cascade_anchor ENABLE ROW LEVEL SECURITY';
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    EXECUTE 'REVOKE ALL ON TABLE public.sell_cascade_anchor FROM anon';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    EXECUTE 'REVOKE ALL ON TABLE public.sell_cascade_anchor FROM authenticated';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
    EXECUTE 'GRANT ALL ON TABLE public.sell_cascade_anchor TO service_role';
  END IF;
END
$lock$;
"""

_INSERT = """
INSERT INTO public.sell_cascade_anchor (
    symbol, position_id, entry_price, closed_at, net_pnl, close_outcome, status,
    broker_login
) VALUES ($1, $2, $3, $4, $5, $6, 'active', $7)
ON CONFLICT (symbol, position_id) DO NOTHING
"""

_ADD_LOGIN = """
ALTER TABLE public.sell_cascade_anchor
ADD COLUMN IF NOT EXISTS broker_login BIGINT
"""

_SELECT_ACTIVE = """
SELECT symbol, position_id, entry_price, closed_at, net_pnl, close_outcome, status,
       broker_login, created_at, updated_at
FROM public.sell_cascade_anchor
WHERE status = 'active'
"""

_RELEASE = """
UPDATE public.sell_cascade_anchor
SET status = $3, release_reason = $3, updated_at = NOW()
WHERE symbol = $1 AND position_id = $2 AND status = 'active'
"""


@dataclass(frozen=True, slots=True)
class SellCascadeAnchor:
    symbol: str
    position_id: int
    entry_price: Decimal
    closed_at: datetime
    net_pnl: Decimal
    close_outcome: str
    status: str
    broker_login: int | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> SellCascadeAnchor:
        closed = row.get("closed_at")
        if not isinstance(closed, datetime):
            closed = datetime.now(UTC)
        if closed.tzinfo is None:
            closed = closed.replace(tzinfo=UTC)
        return cls(
            symbol=str(row.get("symbol") or "").upper(),
            position_id=int(row.get("position_id") or 0),
            entry_price=Decimal(str(row.get("entry_price"))),
            closed_at=closed,
            net_pnl=Decimal(str(row.get("net_pnl") or 0)),
            close_outcome=str(row.get("close_outcome") or ""),
            status=str(row.get("status") or "active"),
            broker_login=(
                int(row["broker_login"])
                if row.get("broker_login") not in (None, "")
                else None
            ),
        )


def reset_sell_cascade_store_for_tests() -> None:
    global _LOADED, _TRUSTED, _FORCED_DOWN, _LIVE_LOGIN
    with _LOCK:
        _CACHE.clear()
        _DURABLE.clear()
        _KNOWN.clear()
        _LOADED = False
        _TRUSTED = True
        _FORCED_DOWN = False
        _LIVE_LOGIN = None


def force_sell_cascade_store_unavailable_for_tests(down: bool) -> None:
    global _FORCED_DOWN, _TRUSTED, _LOADED
    with _LOCK:
        _FORCED_DOWN = down
        _TRUSTED = not down
        if not down:
            _LOADED = False


def forget_process_cache_for_tests() -> None:
    global _LOADED
    with _LOCK:
        _CACHE.clear()
        _LOADED = False


def _testing() -> bool:
    return bool(os.environ.get("PYTEST_CURRENT_TEST"))


def _key(symbol: str) -> str:
    raw = (symbol or "").strip().upper()
    if not raw:
        return raw
    try:
        from app.domain.trading.gold_only import GOLD_SYMBOL, is_gold_symbol

        if is_gold_symbol(raw):
            return GOLD_SYMBOL
    except Exception:
        return raw
    return raw


def _use_postgres() -> bool:
    if _testing() or _FORCED_DOWN:
        return False
    from app.infrastructure.persistence.direct_postgres import (
        direct_postgres_available,
    )

    return direct_postgres_available()


def _ensure_schema() -> None:
    from app.infrastructure.persistence.direct_postgres import execute

    execute(_CREATE)
    execute(_ADD_LOGIN)
    execute(_LOCKDOWN)


def _cache_put(anchor: SellCascadeAnchor) -> None:
    payload = {
        "symbol": anchor.symbol,
        "position_id": anchor.position_id,
        "entry_price": anchor.entry_price,
        "closed_at": anchor.closed_at,
        "net_pnl": anchor.net_pnl,
        "close_outcome": anchor.close_outcome,
        "status": anchor.status,
        "broker_login": anchor.broker_login,
    }
    _CACHE[(anchor.symbol, anchor.position_id)] = payload
    _DURABLE[(anchor.symbol, anchor.position_id)] = dict(payload)
    _KNOWN.add((anchor.symbol, anchor.position_id))


def load_active_anchors() -> tuple[list[SellCascadeAnchor], bool]:
    """Return ``(active, trusted)``. Untrusted blocks new SELL entries."""
    global _LOADED, _TRUSTED
    with _LOCK:
        if _FORCED_DOWN:
            _TRUSTED = False
            _LOADED = True
            return [], False
        if _testing():
            _TRUSTED = True
            _LOADED = True
            _CACHE.clear()
            _CACHE.update({key: dict(row) for key, row in _DURABLE.items()})
            rows = [
                SellCascadeAnchor.from_row(r)
                for r in _CACHE.values()
                if r["status"] == "active"
            ]
            return rows, True
        if not _use_postgres():
            _TRUSTED = False
            _LOADED = True
            logger.warning(
                "sell_cascade_store_untrusted", reason="postgres_unavailable"
            )
            return [], False
    try:
        _ensure_schema()
        from app.infrastructure.persistence.direct_postgres import fetch

        fetched = fetch(_SELECT_ACTIVE)
    except Exception as exc:
        with _LOCK:
            _TRUSTED = False
            _LOADED = True
        logger.warning("sell_cascade_load_failed", error_type=type(exc).__name__)
        return [], False
    anchors = [SellCascadeAnchor.from_row(dict(row)) for row in fetched]
    with _LOCK:
        _CACHE.clear()
        for anchor in anchors:
            _cache_put(anchor)
        _LOADED = True
        _TRUSTED = True
    logger.warning(
        "sell_cascade_anchors_restored",
        count=len(anchors),
        symbols=sorted({a.symbol for a in anchors}),
    )
    return anchors, True


def _symbol_active(symbol: str) -> tuple[list[SellCascadeAnchor], bool]:
    anchors, trusted = load_active_anchors() if not _LOADED else _cached_active()
    if not trusted:
        return [], False
    key = _key(symbol)
    return [a for a in anchors if a.symbol == key], True


def active_anchors(symbol: str) -> tuple[list[SellCascadeAnchor], bool]:
    rows, trusted = _symbol_active(symbol)
    if not trusted or _LIVE_LOGIN is None:
        return rows, trusted
    return [
        row
        for row in rows
        if row.broker_login is None or row.broker_login == _LIVE_LOGIN
    ], True


def active_sell_anchor(symbol: str) -> tuple[SellCascadeAnchor | None, bool]:
    """Compatibility helper used by scoring — binding = lowest failed SELL."""
    rows, trusted = active_anchors(symbol)
    if not trusted:
        return None, False
    if not rows:
        return None, True
    return min(rows, key=lambda row: row.entry_price), True


def _cached_active() -> tuple[list[SellCascadeAnchor], bool]:
    with _LOCK:
        if not _TRUSTED:
            return [], False
        rows = [
            SellCascadeAnchor.from_row(r)
            for r in _CACHE.values()
            if r["status"] == "active"
        ]
        return rows, True


def record_losing_sell_close(
    *,
    symbol: str,
    position_id: int,
    entry_price: Decimal | float | str | None,
    net_pnl: Decimal | float | str | None,
    closed_at: datetime | None = None,
    close_outcome: str = "",
    direction: str = "SELL",
    fully_closed: bool = False,
    broker_login: int | None = None,
) -> str:
    """Idempotent. Only a broker-confirmed full losing SELL creates an anchor."""
    side = str(direction or "").strip().upper()
    if side != "SELL":
        return "ignored_not_sell"
    if not fully_closed:
        return "ignored_partial"
    if _FORCED_DOWN or (not _testing() and not _use_postgres()):
        logger.warning("sell_cascade_record_untrusted", symbol=_key(symbol))
        return "untrusted"
    try:
        pnl = Decimal(str(net_pnl))
    except Exception:
        return "ignored_unconfirmed"
    if pnl >= 0:
        _release_symbol(_key(symbol), "released_win")
        return "ignored_win"
    try:
        pid = int(position_id)
        entry = Decimal(str(entry_price))
    except Exception:
        return "ignored_unconfirmed"
    if pid <= 0 or entry <= 0:
        return "ignored_unconfirmed"
    key = _key(symbol)
    if not key:
        return "ignored_unconfirmed"
    moment = closed_at or datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    login = int(broker_login) if broker_login else _LIVE_LOGIN
    anchor = SellCascadeAnchor(
        symbol=key,
        position_id=pid,
        entry_price=entry,
        closed_at=moment,
        net_pnl=pnl,
        close_outcome=str(close_outcome or "")[:120],
        status="active",
        broker_login=login,
    )
    with _LOCK:
        if not _LOADED:
            load_active_anchors()
        existing = _DURABLE.get((key, pid))
        if existing is not None:
            return "duplicate"
        _cache_put(anchor)
    if not _testing() and _use_postgres():
        try:
            _ensure_schema()
            from app.infrastructure.persistence.direct_postgres import execute

            execute(
                _INSERT,
                key,
                pid,
                entry,
                moment,
                pnl,
                anchor.close_outcome,
                anchor.broker_login,
            )
        except Exception as exc:
            with _LOCK:
                _CACHE.pop((key, pid), None)
                _DURABLE.pop((key, pid), None)
                _KNOWN.discard((key, pid))
                global _TRUSTED
                _TRUSTED = False
            logger.warning("sell_cascade_record_failed", error_type=type(exc).__name__)
            return "untrusted"
    logger.warning(
        "sell_cascade_anchor_created",
        symbol=key,
        position_id=pid,
        entry_price=str(entry),
        net_pnl=str(pnl),
        broker_login=login,
    )
    return "created"


def _mark_released(symbol: str, position_id: int, reason: str) -> None:
    global _TRUSTED
    row = _CACHE.get((symbol, position_id))
    durable = _DURABLE.get((symbol, position_id))
    if row is None or row.get("status") != "active":
        return
    row["status"] = reason
    row["updated_at"] = datetime.now(UTC).isoformat()
    if durable is not None:
        durable["status"] = reason
    if not _testing() and _use_postgres():
        try:
            from app.infrastructure.persistence.direct_postgres import execute

            execute(_RELEASE, symbol, position_id, reason)
        except Exception as exc:
            _TRUSTED = False
            logger.warning(
                "sell_cascade_release_failed",
                error_type=type(exc).__name__,
                symbol=symbol,
                position_id=position_id,
            )


def _release_symbol(symbol: str, reason: str) -> int:
    key = _key(symbol)
    with _LOCK:
        if not _LOADED:
            load_active_anchors()
        ids = [
            pid
            for (sym, pid), row in list(_CACHE.items())
            if sym == key and row.get("status") == "active"
        ]
    count = 0
    for pid in ids:
        _mark_released(key, pid, reason)
        count += 1
    if count:
        logger.warning(
            "sell_cascade_anchors_released",
            symbol=key,
            count=count,
            reason=reason,
        )
    return count


def release_reclaimed(symbol: str, entry_price: Decimal) -> int:
    """Release only anchors strictly above the reclaim (lower) SELL entry."""
    key = _key(symbol)
    with _LOCK:
        ids = [
            pid
            for (sym, pid), row in list(_CACHE.items())
            if sym == key
            and row.get("status") == "active"
            and Decimal(str(row["entry_price"])) > entry_price
        ]
    count = 0
    for pid in ids:
        _mark_released(key, pid, "released_reclaim")
        count += 1
    return count


def release_reversal(symbol: str) -> int:
    return _release_symbol(_key(symbol), "released_reversal")


def reconcile_anchors(
    *,
    symbol: str,
    open_position_ids: set[int],
    broker_nets: dict[int, Decimal] | None,
    covered_position_ids: set[int] | None = None,
    coverage_from: datetime | None = None,
    broker_login: int | None = None,
) -> dict[str, int]:
    """Drop anchors that are still open, profitable, or absent from this account."""
    key = _key(symbol)
    stats = {"still_open": 0, "broker_win": 0, "not_on_account": 0, "kept": 0}
    anchors, trusted = _symbol_active(key)
    if not trusted:
        logger.warning("sell_cascade_reconcile_untrusted", symbol=key)
        return stats
    for anchor in anchors:
        if broker_login and anchor.broker_login and anchor.broker_login != broker_login:
            _mark_released(key, anchor.position_id, "released_account_mismatch")
            stats["not_on_account"] += 1
            continue
        if anchor.position_id in open_position_ids:
            _mark_released(key, anchor.position_id, "released_reconcile_open")
            stats["still_open"] += 1
            continue
        if (
            broker_nets is not None
            and anchor.position_id in broker_nets
            and broker_nets[anchor.position_id] >= 0
        ):
            _mark_released(key, anchor.position_id, "released_reconcile_win")
            stats["broker_win"] += 1
            continue
        if (
            covered_position_ids is not None
            and coverage_from is not None
            and anchor.closed_at >= coverage_from
            and anchor.position_id not in covered_position_ids
        ):
            _mark_released(key, anchor.position_id, "released_not_on_account")
            stats["not_on_account"] += 1
            continue
        stats["kept"] += 1
    logger.warning("sell_cascade_reconciled", symbol=key, **stats)
    return stats


def evaluate_durable_sell_cascade(
    *,
    symbol: str,
    direction: str,
    entry_price: Decimal | float | str | None,
    reversal_confirmed: bool,
) -> tuple[bool, str]:
    """SELL gate. Untrusted persistence blocks SELL. BUY is never blocked."""
    from app.domain.institutional_trading.ai_scalping.sell_cascade_guard import (
        sell_cascade_blocked,
    )

    side = str(direction or "").strip().upper()
    if side != "SELL":
        return False, "not_sell"
    anchors, trusted = active_anchors(symbol)
    if not trusted:
        return True, PROTECTION_UNAVAILABLE
    if not anchors:
        return False, "no_losing_sell_anchor"
    binding = min(anchors, key=lambda row: row.entry_price)
    parsed_entry: Decimal | None
    if entry_price is None:
        parsed_entry = None
    else:
        try:
            parsed_entry = Decimal(str(entry_price))
        except Exception:
            parsed_entry = None
    if reversal_confirmed:
        release_reversal(symbol)
        return False, "bearish_reversal_confirmed"
    if parsed_entry is not None:
        release_reclaimed(symbol, parsed_entry)
        anchors, trusted = active_anchors(symbol)
        if not trusted:
            return True, PROTECTION_UNAVAILABLE
        if not anchors:
            return False, "reclaimed_failed_sell_entry"
        binding = min(anchors, key=lambda row: row.entry_price)
    blocked, why = sell_cascade_blocked(
        direction="SELL",
        entry_price=parsed_entry,
        anchor=binding.entry_price,
        reversal_confirmed=False,
    )
    return blocked, why


def _mark_untrusted(reason: str) -> None:
    """Block new SELL entries until protection state is trustworthy again."""
    global _TRUSTED
    with _LOCK:
        _TRUSTED = False
    logger.warning("sell_cascade_store_untrusted", reason=reason)


def recover_sell_cascade_on_startup(adapter: Any | None = None) -> dict[str, Any]:
    """Restore active SELL anchors, then correct them from the broker book.

    Missing broker history with a live adapter is uncertain protection state:
    new SELL entries fail closed until history can be reconciled. BUY is
    unaffected.
    """
    anchors, trusted = restore_sell_cascade_anchors()
    summary: dict[str, Any] = {
        "trusted": trusted,
        "restored": len(anchors),
        "reconciled": {},
        "history_ok": None,
    }
    if not trusted or adapter is None:
        logger.warning("sell_cascade_startup_recover", **summary)
        return summary
    try:
        positions = list(adapter.list_positions() or [])
    except Exception as exc:
        _mark_untrusted("positions_unavailable")
        summary["trusted"] = False
        logger.warning(
            "sell_cascade_startup_positions_unavailable",
            error_type=type(exc).__name__,
        )
        logger.warning("sell_cascade_startup_recover", **summary)
        return summary
    open_ids: set[int] = set()
    for row in positions:
        try:
            ticket = int(
                getattr(row, "ticket", 0) or getattr(row, "position_id", 0) or 0
            )
        except (TypeError, ValueError):
            ticket = 0
        if ticket > 0:
            open_ids.add(ticket)
    broker_nets: dict[int, Decimal] | None = None
    hist_ok = False
    deals: list[Any] = []
    try:
        from app.application.services.close_attribution import (
            find_broker_exit_for_position,
            load_history_deals_safe,
        )

        hist_ok, deals = load_history_deals_safe(adapter)
        if hist_ok:
            broker_nets = {}
            for anchor in anchors:
                evidence = find_broker_exit_for_position(
                    deals, position_id=anchor.position_id
                )
                if evidence is not None:
                    broker_nets[anchor.position_id] = Decimal(str(evidence.net_pnl))
    except Exception as exc:
        logger.warning(
            "sell_cascade_startup_deals_unavailable",
            error_type=type(exc).__name__,
        )
        broker_nets = None
        hist_ok = False
    summary["history_ok"] = hist_ok
    if not hist_ok:
        # Keep restored anchors, but do not allow a new SELL while attribution
        # cannot be verified against the broker book.
        _mark_untrusted("broker_history_unavailable")
        summary["trusted"] = False
        logger.warning("sell_cascade_startup_recover", **summary)
        return summary
    login = _adapter_login(adapter)
    global _LIVE_LOGIN
    if login is not None:
        _LIVE_LOGIN = login
    covered_ids, coverage_from = _deal_coverage(deals)
    for symbol in sorted({anchor.symbol for anchor in anchors}):
        summary["reconciled"][symbol] = reconcile_anchors(
            symbol=symbol,
            open_position_ids=open_ids,
            broker_nets=broker_nets,
            covered_position_ids=covered_ids,
            coverage_from=coverage_from,
            broker_login=login,
        )
    summary["backfilled"] = 0
    try:
        summary["backfilled"] = _backfill_unresolved_losses(deals, open_ids)
    except Exception as exc:
        logger.warning(
            "sell_cascade_backfill_failed",
            error_type=type(exc).__name__,
        )
    logger.warning("sell_cascade_startup_recover", **summary)
    return summary


def _adapter_login(adapter: Any) -> int | None:
    try:
        snap = adapter.account_snapshot()
        login = int(getattr(snap, "login", 0) or 0)
    except Exception as exc:
        logger.warning(
            "sell_cascade_login_unavailable",
            error_type=type(exc).__name__,
        )
        return None
    return login or None


def _parse_deal_time(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _deal_coverage(deals: list[Any]) -> tuple[set[int] | None, datetime | None]:
    from app.application.services.close_attribution import deals_as_dicts

    rows = deals_as_dicts(deals)
    if not rows:
        return None, None
    ids: set[int] = set()
    oldest: datetime | None = None
    for row in rows:
        try:
            position_id = int(row.get("position_id") or 0)
        except (TypeError, ValueError):
            position_id = 0
        if position_id > 0:
            ids.add(position_id)
        when = _parse_deal_time(row.get("time") or row.get("time_msc"))
        if when is not None and (oldest is None or when < oldest):
            oldest = when
    return ids, oldest


def _decimal_or_none(value: object) -> Decimal | None:
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _known_anchor(symbol: str, position_id: int) -> bool:
    key = _key(symbol)
    return (key, position_id) in _DURABLE or (key, position_id) in _KNOWN


def _refresh_known_ids() -> bool:
    if _testing():
        return True
    try:
        _ensure_schema()
        from app.infrastructure.persistence.direct_postgres import fetch

        rows = fetch(
            "SELECT symbol, position_id FROM public.sell_cascade_anchor",
        )
    except Exception as exc:
        logger.warning("sell_cascade_known_ids_failed", error_type=type(exc).__name__)
        return False
    for row in rows:
        try:
            _KNOWN.add((_key(str(row["symbol"])), int(row["position_id"])))
        except (KeyError, TypeError, ValueError):
            continue
    return True


def _backfill_unresolved_losses(
    deals: list[Any],
    open_position_ids: set[int],
) -> int:
    """Arm anchors for broker SELL losses newer than the last winning SELL."""
    if not _refresh_known_ids():
        return 0
    from app.application.services.close_attribution import (
        deals_as_dicts,
        find_broker_exit_for_position,
    )
    from app.application.services.signal_intelligence_service import (
        pair_all_symbol_closed_trades,
    )

    raw_deals = deals_as_dicts(deals)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for trade in pair_all_symbol_closed_trades(raw_deals):
        symbol = _key(str(trade.get("symbol") or ""))
        if symbol:
            grouped.setdefault(symbol, []).append(trade)
    created = 0
    for symbol, trades in grouped.items():
        ordered = sorted(trades, key=lambda row: str(row.get("exit_time") or ""))
        last_win = -1
        for index, trade in enumerate(ordered):
            if str(trade.get("side") or "").strip().upper() != "SELL":
                continue
            pnl = _decimal_or_none(trade.get("profit_loss"))
            if pnl is None:
                continue
            if pnl >= 0:
                last_win = index
        for trade in ordered[last_win + 1 :]:
            if str(trade.get("side") or "").strip().upper() != "SELL":
                continue
            try:
                position_id = int(trade.get("position_id") or 0)
            except (TypeError, ValueError):
                continue
            pnl = _decimal_or_none(trade.get("profit_loss"))
            if (
                position_id <= 0
                or pnl is None
                or pnl >= 0
                or position_id in open_position_ids
            ):
                continue
            if _known_anchor(symbol, position_id):
                continue
            evidence = find_broker_exit_for_position(raw_deals, position_id=position_id)
            if evidence is None or evidence.entry_price is None:
                continue
            if Decimal(str(evidence.net_pnl)) >= 0:
                continue
            closed_at: datetime | None = None
            raw_time = str(evidence.exit_time or "").strip()
            if raw_time:
                try:
                    closed_at = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
                except ValueError:
                    closed_at = None
            result = record_losing_sell_close(
                symbol=symbol,
                position_id=position_id,
                entry_price=evidence.entry_price,
                net_pnl=evidence.net_pnl,
                closed_at=closed_at,
                close_outcome=evidence.close_reason or "broker_backfill",
                direction="SELL",
                fully_closed=True,
                broker_login=_LIVE_LOGIN,
            )
            if result == "created":
                created += 1
    if created:
        logger.warning("sell_cascade_backfilled", count=created)
    return created


def restore_sell_cascade_anchors() -> tuple[list[SellCascadeAnchor], bool]:
    """Load active anchors before the worker evaluates new SELL entries."""
    global _LOADED
    with _LOCK:
        _LOADED = False
    anchors, trusted = load_active_anchors()
    logger.warning(
        "sell_cascade_startup_restore",
        trusted=trusted,
        count=len(anchors),
    )
    return anchors, trusted
