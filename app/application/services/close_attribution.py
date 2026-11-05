"""Broker-confirmed close attribution — analytics only.

When MT5 removes a ticket from the open book (broker SL/TP), PME truth repair
historically dropped the managed row without calling SOE ``record_closed`` /
telemetry ``observe_close``. This module propagates **confirmed** exits into
analytics exactly once.

Hard rules
----------
* Never invent exit prices, PnL, or strategy IDs.
* Never treat an empty/failed positions snapshot as proof of close for analytics.
* Require a broker ``entry_out`` (or paired exit deal) before recording.
* Idempotent by ``position_id`` (full close) — duplicate delivery is a no-op.
* Does not submit orders, modify SL/TP, or change Risk / OMS / strategy logic.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


def _f(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _settings_data_dir() -> Path:
    try:
        from core.config.settings import get_settings

        settings = get_settings()
        return Path(
            getattr(settings, "data_dir", None)
            or getattr(settings, "ops_state_dir", None)
            or "data"
        )
    except Exception:
        return Path("data")


def classify_exit_comment(comment: str | None) -> str:
    text = str(comment or "").strip().lower()
    if text.startswith("[sl") or " sl " in f" {text} " or text.startswith("sl "):
        return "sl"
    if text.startswith("[tp") or " tp " in f" {text} " or text.startswith("tp "):
        return "tp"
    if "stop" in text and "loss" in text:
        return "sl"
    if "take" in text and "profit" in text:
        return "tp"
    return "closed"


def strategy_id_from_entry_comment(comment: str | None) -> str | None:
    """Map broker *entry* comment engine tags only — never invent five-pack IDs."""
    text = str(comment or "").strip()
    if not text:
        return None
    lower = text.lower()
    if lower.startswith("m1:") or lower.startswith("m1 "):
        return "m1_micro"
    if lower.startswith("ite:") or lower.startswith("ite "):
        return "ite_primary"
    return None


def deals_as_dicts(deals: list[Any] | tuple[Any, ...] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in deals or []:
        if hasattr(raw, "to_dict"):
            row = raw.to_dict()
            if isinstance(row, dict):
                out.append(row)
        elif isinstance(raw, dict):
            out.append(raw)
    return out


@dataclass(frozen=True, slots=True)
class BrokerExitEvidence:
    """Authoritative exit facts from paired MT5 history deals — never fabricated."""

    position_id: int
    symbol: str
    exit_deal_id: int
    entry_deal_id: int | None
    exit_price: float
    entry_price: float | None
    exit_time: str
    entry_time: str | None
    volume: float
    profit: float
    commission: float
    swap: float
    net_pnl: float
    close_reason: str
    side: str
    hold_seconds: float | None
    exit_comment: str = ""
    entry_comment: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def find_broker_exit_for_position(
    deals: list[Any] | tuple[Any, ...] | None,
    *,
    position_id: int,
) -> BrokerExitEvidence | None:
    """Return paired close evidence for ``position_id`` or None if unconfirmed.

    Requires an exit deal (``entry_out`` / deal_type containing ``out``). Does not
    invent a close from a lone entry deal.
    """
    pid = int(position_id or 0)
    if pid <= 0:
        return None
    from app.application.services.signal_intelligence_service import (
        pair_all_symbol_closed_trades,
    )

    rows = deals_as_dicts(deals)
    if not rows:
        return None
    # Prefer rows that mention this position; pairing is symbol-scoped.
    matched = [
        t
        for t in pair_all_symbol_closed_trades(rows)
        if int(t.get("position_id") or 0) == pid
    ]
    if not matched:
        return None
    trade = matched[0]
    exit_deal = int(trade.get("exit_ticket") or 0)
    if exit_deal <= 0:
        return None
    # Re-sum commission/swap/profit from raw deals for this position (authoritative).
    group = [
        d
        for d in rows
        if int(d.get("position_id") or 0) == pid
        or int(d.get("order_ticket") or 0) == pid
    ]
    profit = 0.0
    commission = 0.0
    swap = 0.0
    exit_comment = str(trade.get("comment") or "")
    entry_comment = ""
    for d in group:
        profit += _f(d.get("profit"))
        commission += _f(d.get("commission"))
        swap += _f(d.get("swap"))
        dt = str(d.get("deal_type") or "").lower()
        entry_flag = str(d.get("entry") if d.get("entry") is not None else "").lower()
        raw_c = str(d.get("comment") or "").strip()
        is_out = "out" in dt or entry_flag in {"1", "out", "deal_entry_out"}
        is_in = ("in" in dt and "out" not in dt) or entry_flag in {
            "0",
            "in",
            "deal_entry_in",
        }
        if is_out and raw_c:
            exit_comment = raw_c
        if is_in and raw_c and not raw_c.lower().startswith(("[sl", "[tp")):
            entry_comment = raw_c
    if not entry_comment:
        entry_comment = str(
            trade.get("entry_comment") or trade.get("open_comment") or ""
        )
    net = profit + commission + swap
    hold = trade.get("holding_time_sec")
    try:
        hold_f = float(hold) if hold is not None else None
    except (TypeError, ValueError):
        hold_f = None
    try:
        entry_px = float(trade["entry"]) if trade.get("entry") is not None else None
    except (TypeError, ValueError):
        entry_px = None
    try:
        exit_px = float(trade["exit"]) if trade.get("exit") is not None else None
    except (TypeError, ValueError):
        exit_px = None
    if exit_px is None:
        return None
    return BrokerExitEvidence(
        position_id=pid,
        symbol=str(trade.get("symbol") or "").upper(),
        exit_deal_id=exit_deal,
        entry_deal_id=(
            int(trade["entry_ticket"]) if trade.get("entry_ticket") else None
        ),
        exit_price=exit_px,
        entry_price=entry_px,
        exit_time=str(trade.get("exit_time") or ""),
        entry_time=(str(trade.get("entry_time")) if trade.get("entry_time") else None),
        volume=float(trade.get("volume") or 0.0),
        profit=round(profit, 6),
        commission=round(commission, 6),
        swap=round(swap, 6),
        net_pnl=round(net, 6),
        close_reason=classify_exit_comment(exit_comment),
        side=str(trade.get("side") or "").lower(),
        hold_seconds=hold_f,
        exit_comment=exit_comment,
        entry_comment=entry_comment,
    )


@dataclass
class CloseAttributionLedger:
    """Persist recorded full-close keys so analytics stay idempotent."""

    _path: Path | None = None
    _recorded: set[str] = field(default_factory=set)
    _pending: dict[str, dict[str, Any]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self) -> None:
        if self._path is None:
            self._path = _settings_data_dir() / "close_attribution_ledger.json"
        self._load()

    @staticmethod
    def full_close_key(position_id: int, *, exit_deal_id: int | None = None) -> str:
        pid = int(position_id)
        if exit_deal_id:
            return f"full:{pid}:exit:{int(exit_deal_id)}"
        return f"full:{pid}"

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            recorded = raw.get("recorded") if isinstance(raw, dict) else None
            pending = raw.get("pending") if isinstance(raw, dict) else None
            with self._lock:
                if isinstance(recorded, list):
                    self._recorded = {str(x) for x in recorded if str(x).strip()}
                if isinstance(pending, dict):
                    self._pending = {
                        str(k): dict(v)
                        for k, v in pending.items()
                        if isinstance(v, dict)
                    }
        except Exception:
            logger.exception("close_attribution_ledger_load_failed")

    def _persist(self) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                payload = {
                    "updated_at": datetime.now(UTC).isoformat(),
                    "recorded": sorted(self._recorded),
                    "pending": dict(self._pending),
                }
            self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            logger.exception("close_attribution_ledger_persist_failed")

    def already_recorded(
        self, position_id: int, *, exit_deal_id: int | None = None
    ) -> bool:
        keys = {
            self.full_close_key(position_id),
            (
                self.full_close_key(position_id, exit_deal_id=exit_deal_id)
                if exit_deal_id
                else ""
            ),
        }
        keys.discard("")
        with self._lock:
            return bool(keys & self._recorded)

    def mark_recorded(
        self, position_id: int, *, exit_deal_id: int | None = None
    ) -> None:
        keys = [self.full_close_key(position_id)]
        if exit_deal_id:
            keys.append(self.full_close_key(position_id, exit_deal_id=exit_deal_id))
        with self._lock:
            self._recorded.update(keys)
            self._pending.pop(str(int(position_id)), None)
        self._persist()

    def note_pending(
        self,
        position_id: int,
        *,
        reason: str,
        symbol: str | None = None,
        strategy_id: str | None = None,
    ) -> None:
        pid = str(int(position_id))
        with self._lock:
            self._pending[pid] = {
                "position_id": int(position_id),
                "reason": str(reason or "awaiting_broker_exit_deal"),
                "symbol": symbol,
                "strategy_id": strategy_id,
                "noted_at": datetime.now(UTC).isoformat(),
            }
        self._persist()

    def pending_ids(self) -> list[int]:
        with self._lock:
            return [int(k) for k in self._pending]

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "recorded_count": len(self._recorded),
                "pending_count": len(self._pending),
                "pending": dict(self._pending),
            }


_LEDGER: CloseAttributionLedger | None = None
_LEDGER_LOCK = threading.Lock()


def get_close_attribution_ledger() -> CloseAttributionLedger:
    global _LEDGER
    with _LEDGER_LOCK:
        if _LEDGER is None:
            _LEDGER = CloseAttributionLedger()
        return _LEDGER


def reset_close_attribution_ledger_for_tests(
    path: Path | None = None,
) -> CloseAttributionLedger:
    """Test helper — replace process singleton."""
    global _LEDGER
    with _LEDGER_LOCK:
        _LEDGER = CloseAttributionLedger(_path=path)
        return _LEDGER


def resolve_strategy_id_for_ticket(
    *,
    ticket: int,
    position_id: int | None = None,
    strategy_hint: str | None = None,
    entry_comment: str | None = None,
) -> str | None:
    """Prefer attribution store / fill meta; optional hint or entry-comment tag."""
    hint = str(strategy_hint or "").strip()
    try:
        from app.domain.institutional_trading.ai_scalping.strategies import (
            attribution_store as _attr_mod,
        )
        from app.domain.institutional_trading.management.class_policy import (
            last_fill_metadata,
            merge_position_metadata,
        )

        meta = merge_position_metadata(
            snapshot={"ticket": ticket, "position_id": position_id or ticket},
            comment=str(entry_comment or ""),
            live_meta=last_fill_metadata(),
            ticket=ticket,
            position_id=position_id or ticket,
        )
        sid = str(meta.get("strategy_id") or "").strip()
        if sid:
            return sid
        bound = _attr_mod.get_strategy_attribution_store().resolve(
            ticket=ticket, position_id=position_id or ticket
        )
        if bound is not None and str(bound.strategy_id or "").strip():
            return str(bound.strategy_id).strip()
    except Exception:
        logger.exception("close_attribution_strategy_resolve_failed", ticket=ticket)
    tagged = strategy_id_from_entry_comment(entry_comment)
    if tagged:
        return tagged
    return hint or None


def record_broker_confirmed_close(
    *,
    evidence: BrokerExitEvidence,
    strategy_id: str | None = None,
    strategy_hint: str | None = None,
    source: str = "broker_history",
    ledger: CloseAttributionLedger | None = None,
) -> dict[str, Any]:
    """Record SOE + telemetry close analytics once for a confirmed broker exit."""
    book = ledger or get_close_attribution_ledger()
    pid = int(evidence.position_id)
    if book.already_recorded(pid, exit_deal_id=evidence.exit_deal_id):
        return {
            "status": "duplicate",
            "position_id": pid,
            "exit_deal_id": evidence.exit_deal_id,
            "source": source,
        }

    sid = str(strategy_id or "").strip() or resolve_strategy_id_for_ticket(
        ticket=pid,
        position_id=pid,
        strategy_hint=strategy_hint,
        entry_comment=evidence.entry_comment,
    )

    # Mark ledger first so concurrent duplicate deliveries cannot double-count
    # even if a downstream hook raises mid-flight.
    book.mark_recorded(pid, exit_deal_id=evidence.exit_deal_id)

    soe_recorded = False
    if sid:
        try:
            from app.domain.institutional_trading.ai_scalping.strategies.stats import (
                get_strategy_stats_book,
            )

            hold_m = (
                float(evidence.hold_seconds) / 60.0
                if evidence.hold_seconds is not None
                else None
            )
            get_strategy_stats_book().record_closed(
                sid,
                win=bool(evidence.net_pnl > 0),
                pnl=float(evidence.net_pnl),
                hold_minutes=hold_m,
            )
            soe_recorded = True
        except Exception:
            logger.exception(
                "close_attribution_soe_record_failed",
                position_id=pid,
                strategy_id=sid,
            )
    else:
        logger.warning(
            "close_attribution_missing_strategy_id",
            position_id=pid,
            exit_deal_id=evidence.exit_deal_id,
            entry_comment=(evidence.entry_comment or "")[:80] or None,
            source=source,
        )

    telemetry_recorded = False
    try:
        from app.application.services.strategy_performance_telemetry import (
            get_strategy_performance_telemetry,
        )

        get_strategy_performance_telemetry().observe_close(
            ticket=pid,
            exit_price=evidence.exit_price,
            realized_pnl=evidence.net_pnl,
            exit_reason=evidence.close_reason or evidence.exit_comment or "closed",
            hold_seconds=evidence.hold_seconds,
        )
        telemetry_recorded = True
    except Exception:
        logger.exception("close_attribution_telemetry_observe_failed", position_id=pid)

    # Clear fill binding only after strategy attribution succeeds. Premature
    # clear caused LIVE soe_recorded=False / strategy_id=None races.
    if sid:
        try:
            from app.domain.institutional_trading.ai_scalping.strategies import (
                attribution_store as _attr_close,
            )

            _attr_close.get_strategy_attribution_store().note_partial_close(
                ticket=pid,
                position_id=pid,
                closed_volume=float(evidence.volume or 0) or None,
                fully_closed=True,
            )
        except Exception:
            logger.exception("close_attribution_binding_clear_failed", position_id=pid)

    logger.warning(
        "broker_confirmed_close_attributed",
        position_id=pid,
        exit_deal_id=evidence.exit_deal_id,
        strategy_id=sid or None,
        net_pnl=evidence.net_pnl,
        close_reason=evidence.close_reason,
        source=source,
        soe_recorded=soe_recorded,
        telemetry_recorded=telemetry_recorded,
    )
    return {
        "status": "recorded" if (soe_recorded or telemetry_recorded) else "ledger_only",
        "position_id": pid,
        "exit_deal_id": evidence.exit_deal_id,
        "strategy_id": sid or None,
        "net_pnl": evidence.net_pnl,
        "close_reason": evidence.close_reason,
        "exit_price": evidence.exit_price,
        "exit_time": evidence.exit_time,
        "commission": evidence.commission,
        "swap": evidence.swap,
        "volume": evidence.volume,
        "soe_recorded": soe_recorded,
        "telemetry_recorded": telemetry_recorded,
        "source": source,
        "fabricated": False,
    }


def attribute_missing_tickets(
    *,
    tickets: list[int] | tuple[int, ...],
    deals: list[Any] | tuple[Any, ...] | None,
    strategy_hints: dict[int, str] | None = None,
    source: str = "missing_from_mt5_book",
    ledger: CloseAttributionLedger | None = None,
) -> list[dict[str, Any]]:
    """Attribute analytics for tickets absent from a **reliable** open book.

    If broker history has no exit deal yet, queue as pending — do not invent.
    """
    book = ledger or get_close_attribution_ledger()
    hints = dict(strategy_hints or {})
    results: list[dict[str, Any]] = []
    deal_rows = deals_as_dicts(deals)
    for raw_ticket in tickets:
        ticket = int(raw_ticket or 0)
        if ticket <= 0:
            continue
        if book.already_recorded(ticket):
            results.append(
                {"status": "duplicate", "position_id": ticket, "source": source}
            )
            continue
        evidence = find_broker_exit_for_position(deal_rows, position_id=ticket)
        if evidence is None:
            book.note_pending(
                ticket,
                reason="awaiting_broker_exit_deal",
                strategy_id=hints.get(ticket),
            )
            results.append(
                {
                    "status": "pending_history",
                    "position_id": ticket,
                    "source": source,
                    "fabricated": False,
                }
            )
            continue
        results.append(
            record_broker_confirmed_close(
                evidence=evidence,
                strategy_hint=hints.get(ticket),
                source=source,
                ledger=book,
            )
        )
    return results


def reconcile_pending_closes(
    *,
    deals: list[Any] | tuple[Any, ...] | None,
    strategy_hints: dict[int, str] | None = None,
    ledger: CloseAttributionLedger | None = None,
) -> list[dict[str, Any]]:
    """Retry pending tickets once broker history catches up."""
    book = ledger or get_close_attribution_ledger()
    return attribute_missing_tickets(
        tickets=book.pending_ids(),
        deals=deals,
        strategy_hints=strategy_hints,
        source="pending_reconcile",
        ledger=book,
    )


def reconcile_historical_closes(
    *,
    position_ids: list[int] | tuple[int, ...],
    deals: list[Any] | tuple[Any, ...] | None,
    strategy_bindings: dict[int, str] | None = None,
    ledger: CloseAttributionLedger | None = None,
) -> list[dict[str, Any]]:
    """Backfill analytics for known position IDs using broker history only.

    ``strategy_bindings`` must come from fill-time evidence (lifecycle / store),
    never invented exit facts.
    """
    hints = dict(strategy_bindings or {})
    # Restore attribution bindings before record so SOE books get the strategy.
    try:
        from app.domain.institutional_trading.ai_scalping.strategies import (
            attribution_store as _attr_hist,
        )

        store = _attr_hist.get_strategy_attribution_store()
        for pid, sid in hints.items():
            if not sid:
                continue
            if store.resolve(ticket=int(pid), position_id=int(pid)) is None:
                store.bind_fill(
                    strategy_id=str(sid),
                    engine="soe",
                    ticket=int(pid),
                    position_id=int(pid),
                    meta={"reconcile": "historical_fill_evidence"},
                )
    except Exception:
        logger.exception("close_attribution_historical_bind_failed")

    return attribute_missing_tickets(
        tickets=list(position_ids),
        deals=deals,
        strategy_hints=hints,
        source="historical_reconcile",
        ledger=ledger,
    )


def load_history_deals_safe(mt5_adapter: Any) -> tuple[bool, list[Any]]:
    """Fetch history deals without raising into the sync path.

    Returns ``(ok, deals)``. ``ok=False`` means history was unavailable — caller
    must not invent closes (may still queue pending).
    """
    if mt5_adapter is None:
        return False, []
    hist = getattr(mt5_adapter, "history_deals", None)
    if not callable(hist):
        client = getattr(mt5_adapter, "client", None) or getattr(
            mt5_adapter, "_client", None
        )
        hist = getattr(client, "history_deals", None) if client is not None else None
    if not callable(hist):
        return False, []
    try:
        return True, list(hist() or [])
    except Exception:
        logger.exception("close_attribution_history_deals_failed")
        return False, []
