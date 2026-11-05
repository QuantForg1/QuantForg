"""Shadow reversal exit book — observe only, never submits orders.

In-memory ring buffer plus optional durable JSON under QUANTFORG data_dir so
Railway restarts do not wipe evidence needed for LIVE-activation gates.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any

from app.domain.institutional_trading.management.exit_context import (
    ReversalExitProposal,
    shadow_log_fields,
)
from core.logging import get_logger

logger = get_logger(__name__)

_LOCK = Lock()
_ENTRIES: list[dict[str, Any]] = []
_MAX = 500
_LOADED = False
_BOOK_FILENAME = "pme_shadow_exits.json"


def _book_path() -> Path:
    env_dir = (os.environ.get("QUANTFORG_DATA_DIR") or "").strip()
    if env_dir:
        return Path(env_dir) / _BOOK_FILENAME
    try:
        from core.config.settings import get_settings

        base = Path(getattr(get_settings(), "data_dir", None) or "data")
    except Exception:
        base = Path("data")
    return base / _BOOK_FILENAME


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _ensure_loaded() -> None:
    global _LOADED
    if _LOADED:
        return
    path = _book_path()
    try:
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            rows = raw.get("entries") if isinstance(raw, dict) else None
            if isinstance(rows, list):
                cleaned = [r for r in rows if isinstance(r, dict)]
                _ENTRIES.clear()
                _ENTRIES.extend(cleaned[-_MAX:])
    except Exception:
        # Fail-open: memory book still works if disk is unreadable.
        logger.exception("pme_shadow_book_load_failed")
    _LOADED = True


def _persist_unlocked() -> None:
    path = _book_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": _utc_now(),
            "count": len(_ENTRIES),
            "entries": list(_ENTRIES[-_MAX:]),
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        # Never break LIVE manage cycles on shadow persistence failure.
        logger.exception("pme_shadow_book_persist_failed")


@dataclass
class ShadowExitRecord:
    ticket: int
    symbol: str
    side: str
    proposal: ReversalExitProposal
    recorded_at: str = field(default_factory=_utc_now)
    live_fed: bool = False
    note: str = ""


def record_shadow_exit(
    *,
    ticket: int,
    symbol: str,
    side: str,
    proposal: ReversalExitProposal,
    live_fed: bool = False,
    note: str = "",
) -> dict[str, Any]:
    row = ShadowExitRecord(
        ticket=int(ticket),
        symbol=str(symbol or ""),
        side=str(side or ""),
        proposal=proposal,
        live_fed=bool(live_fed),
        note=str(note or ""),
    )
    payload = {
        "ticket": row.ticket,
        "symbol": row.symbol,
        "side": row.side,
        "recorded_at": row.recorded_at,
        "live_fed": row.live_fed,
        "note": row.note,
        "outcome": None,
        "outcome_at": None,
        "outcome_net_pnl": None,
        "outcome_note": "",
        **shadow_log_fields(proposal),
        "proposal": asdict(proposal),
    }
    with _LOCK:
        _ensure_loaded()
        _ENTRIES.append(payload)
        if len(_ENTRIES) > _MAX:
            del _ENTRIES[: len(_ENTRIES) - _MAX]
        _persist_unlocked()
    return payload


def mark_shadow_outcome(
    *,
    ticket: int,
    outcome: str,
    net_pnl: float | None = None,
    note: str = "",
) -> int:
    """Attach broker/close outcome to open shadow rows for ``ticket`` (idempotent).

    Returns the number of rows updated. Does not invent P&L — pass only
    broker-confirmed values when available.
    """
    ticket_i = int(ticket)
    outcome_s = str(outcome or "").strip() or "unknown"
    note_s = str(note or "")
    updated = 0
    with _LOCK:
        _ensure_loaded()
        now = _utc_now()
        for row in _ENTRIES:
            if int(row.get("ticket") or 0) != ticket_i:
                continue
            if row.get("outcome"):
                continue
            row["outcome"] = outcome_s
            row["outcome_at"] = now
            if net_pnl is not None:
                try:
                    row["outcome_net_pnl"] = float(net_pnl)
                except (TypeError, ValueError):
                    row["outcome_net_pnl"] = None
            if note_s:
                row["outcome_note"] = note_s
            updated += 1
        if updated:
            _persist_unlocked()
    return updated


def list_shadow_exits(*, limit: int = 100) -> list[dict[str, Any]]:
    with _LOCK:
        _ensure_loaded()
        return list(_ENTRIES[-max(1, int(limit)) :])


def shadow_exit_summary() -> dict[str, Any]:
    """Aggregate counts for activation-gate reporting (no fabricated significance)."""
    with _LOCK:
        _ensure_loaded()
        rows = list(_ENTRIES)
    total = len(rows)
    with_signal = sum(
        1
        for r in rows
        if r.get("shadow_structure_broken") or r.get("shadow_trend_reversed")
    )
    with_outcome = sum(1 for r in rows if r.get("outcome"))
    buy_n = sum(1 for r in rows if str(r.get("side") or "").lower() == "buy")
    sell_n = sum(1 for r in rows if str(r.get("side") or "").lower() == "sell")
    return {
        "total": total,
        "with_reversal_signal": with_signal,
        "with_outcome": with_outcome,
        "buy": buy_n,
        "sell": sell_n,
        "live_fed": sum(1 for r in rows if r.get("live_fed")),
    }


def clear_shadow_exits() -> None:
    global _LOADED
    with _LOCK:
        _ENTRIES.clear()
        _LOADED = True
        _persist_unlocked()
