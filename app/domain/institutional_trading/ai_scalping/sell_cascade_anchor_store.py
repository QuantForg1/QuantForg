"""File-backed losing-SELL anchors for cascade protection.

Separate from the BUY durable Postgres store so BUY semantics stay untouched.
Persists under QUANTFORG data_dir so Railway restarts keep the protection.
Untrusted / unreadable state fails open (does not invent a SELL block).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from threading import Lock
from typing import Any

from app.domain.institutional_trading.ai_scalping.sell_cascade_guard import (
    sell_cascade_blocked,
)
from core.logging import get_logger

logger = get_logger(__name__)

_LOCK = Lock()
_ANCHORS: dict[str, dict[str, Any]] = {}
_LOADED = False
_TRUSTED = True
_FILENAME = "sell_cascade_anchors.json"
PROTECTION_UNAVAILABLE = "SELL_CASCADE_PROTECTION_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class SellCascadeAnchor:
    symbol: str
    position_id: int
    entry_price: Decimal
    closed_at: datetime
    net_pnl: Decimal


def _path() -> Path:
    env_dir = (os.environ.get("QUANTFORG_DATA_DIR") or "").strip()
    if env_dir:
        return Path(env_dir) / _FILENAME
    try:
        from core.config.settings import get_settings

        base = Path(getattr(get_settings(), "data_dir", None) or "data")
    except Exception:
        base = Path("data")
    return base / _FILENAME


def _key(symbol: str) -> str:
    return str(symbol or "").strip().upper()


def reset_sell_cascade_store_for_tests() -> None:
    global _LOADED, _TRUSTED
    with _LOCK:
        _ANCHORS.clear()
        _LOADED = True
        _TRUSTED = True


def force_sell_cascade_store_untrusted_for_tests(down: bool) -> None:
    global _TRUSTED
    with _LOCK:
        _TRUSTED = not bool(down)


def _ensure_loaded() -> None:
    global _LOADED, _TRUSTED
    if _LOADED:
        return
    path = _path()
    try:
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            rows = raw.get("anchors") if isinstance(raw, dict) else None
            if isinstance(rows, list):
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    sym = _key(str(row.get("symbol") or ""))
                    if not sym:
                        continue
                    _ANCHORS[sym] = row
        _TRUSTED = True
    except Exception:
        logger.exception("sell_cascade_store_load_failed")
        _TRUSTED = False
    _LOADED = True


def _persist_unlocked() -> None:
    path = _path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "anchors": list(_ANCHORS.values()),
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        logger.exception("sell_cascade_store_persist_failed")


def record_losing_sell_close(
    *,
    symbol: str,
    position_id: int,
    entry_price: Decimal | float | str | None,
    net_pnl: Decimal | float | str | None,
    closed_at: datetime | None = None,
    direction: str = "SELL",
    fully_closed: bool = False,
) -> str:
    side = str(direction or "").strip().upper()
    if side != "SELL":
        return "ignored_not_sell"
    if not fully_closed:
        return "ignored_partial"
    try:
        pnl = Decimal(str(net_pnl))
        entry = Decimal(str(entry_price))
        pid = int(position_id)
    except Exception:
        return "ignored_unconfirmed"
    if pnl >= 0 or pid <= 0 or entry <= 0:
        if pnl >= 0:
            release_symbol(_key(symbol), "released_win")
            return "ignored_win"
        return "ignored_unconfirmed"
    key = _key(symbol)
    if not key:
        return "ignored_unconfirmed"
    moment = closed_at or datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    with _LOCK:
        _ensure_loaded()
        if not _TRUSTED:
            return "untrusted"
        _ANCHORS[key] = {
            "symbol": key,
            "position_id": pid,
            "entry_price": str(entry),
            "closed_at": moment.isoformat(),
            "net_pnl": str(pnl),
            "status": "active",
        }
        _persist_unlocked()
    logger.warning(
        "sell_cascade_anchor_created",
        symbol=key,
        position_id=pid,
        entry_price=str(entry),
        net_pnl=str(pnl),
    )
    return "created"


def release_symbol(symbol: str, reason: str = "released") -> int:
    key = _key(symbol)
    with _LOCK:
        _ensure_loaded()
        row = _ANCHORS.get(key)
        if row is None or row.get("status") != "active":
            return 0
        row["status"] = reason
        _persist_unlocked()
        return 1


def active_sell_anchor(symbol: str) -> tuple[SellCascadeAnchor | None, bool]:
    with _LOCK:
        _ensure_loaded()
        if not _TRUSTED:
            return None, False
        row = _ANCHORS.get(_key(symbol))
        if row is None or row.get("status") != "active":
            return None, True
        try:
            closed_raw = str(row.get("closed_at") or "")
            closed_at = datetime.fromisoformat(closed_raw.replace("Z", "+00:00"))
            return (
                SellCascadeAnchor(
                    symbol=str(row["symbol"]),
                    position_id=int(row["position_id"]),
                    entry_price=Decimal(str(row["entry_price"])),
                    closed_at=closed_at,
                    net_pnl=Decimal(str(row["net_pnl"])),
                ),
                True,
            )
        except Exception:
            return None, False


def evaluate_durable_sell_cascade(
    *,
    symbol: str,
    direction: str,
    entry_price: Decimal | float | str | None,
    reversal_confirmed: bool,
) -> tuple[bool, str]:
    """SELL gate. Untrusted persistence fails open for SELL (unlike BUY).

    BUY cascade fails closed when Postgres is untrusted because repeated BUY
    losses were the observed production hazard. SELL cascade fails open when
    the file store is unreadable so valid independent SELLs are not silenced.
    """
    side = str(direction or "").strip().upper()
    if side != "SELL":
        return False, "not_sell"
    anchor, trusted = active_sell_anchor(symbol)
    if not trusted:
        logger.warning("sell_cascade_untrusted_fail_open", symbol=_key(symbol))
        return False, PROTECTION_UNAVAILABLE
    if anchor is None:
        return False, "no_losing_sell_anchor"
    parsed: Decimal | None
    try:
        parsed = Decimal(str(entry_price)) if entry_price is not None else None
    except Exception:
        parsed = None
    return sell_cascade_blocked(
        direction=side,
        entry_price=parsed,
        anchor=anchor.entry_price,
        reversal_confirmed=reversal_confirmed,
    )
