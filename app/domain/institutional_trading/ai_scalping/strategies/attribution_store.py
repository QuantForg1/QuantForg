"""Ticket-keyed strategy attribution — Signal → OMS → Fill → Close.

MT5 exit comments are overwritten with ``[sl]`` / ``[tp]`` and cannot be the
source of truth. Bind ``strategy_id`` (and engine tag) to the broker ticket /
position id at fill time, then resolve on close — including partial closes.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AttributionRecord:
    strategy_id: str
    engine: str  # soe | ite | m1 | unknown
    strategy_name: str | None = None
    symbol: str | None = None
    ticket: str | None = None
    position_id: str | None = None
    opened_at: str = ""
    remaining_volume: float | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class StrategyAttributionStore:
    def __init__(self, path: Path | None = None) -> None:
        self._lock = threading.Lock()
        self._by_key: dict[str, AttributionRecord] = {}
        if path is None:
            try:
                from core.config.settings import get_settings

                settings = get_settings()
                base = Path(
                    getattr(settings, "data_dir", None)
                    or getattr(settings, "ops_state_dir", None)
                    or "data"
                )
            except Exception:
                base = Path("data")
            path = base / "strategy_attribution_bindings.json"
        self._path = path
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            rows = raw.get("bindings", {}) if isinstance(raw, dict) else {}
            loaded: dict[str, AttributionRecord] = {}
            for key, row in rows.items():
                if not isinstance(row, dict):
                    continue
                sid = str(row.get("strategy_id") or "").strip()
                if not sid:
                    continue
                loaded[str(key)] = AttributionRecord(
                    strategy_id=sid,
                    engine=str(row.get("engine") or "unknown"),
                    strategy_name=row.get("strategy_name"),
                    symbol=row.get("symbol"),
                    ticket=row.get("ticket"),
                    position_id=row.get("position_id"),
                    opened_at=str(row.get("opened_at") or ""),
                    remaining_volume=(
                        float(row["remaining_volume"])
                        if row.get("remaining_volume") is not None
                        else None
                    ),
                    meta=(
                        dict(row.get("meta") or {})
                        if isinstance(row.get("meta"), dict)
                        else {}
                    ),
                )
            with self._lock:
                self._by_key = loaded
        except Exception:
            logger.exception("strategy_attribution_load_failed")

    def _persist(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                payload = {
                    "updated_at": datetime.now(UTC).isoformat(),
                    "bindings": {k: v.to_dict() for k, v in self._by_key.items()},
                }
            self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            logger.exception("strategy_attribution_persist_failed")

    @staticmethod
    def _keys(ticket: Any = None, position_id: Any = None) -> list[str]:
        keys: list[str] = []
        for label, value in (("ticket", ticket), ("position", position_id)):
            text = str(value or "").strip()
            if text and text not in {"0", "None"}:
                keys.append(f"{label}:{text}")
        return keys

    def bind_fill(
        self,
        *,
        strategy_id: str,
        engine: str = "soe",
        strategy_name: str | None = None,
        symbol: str | None = None,
        ticket: Any = None,
        position_id: Any = None,
        volume: float | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        sid = str(strategy_id or "").strip()
        if not sid:
            return
        keys = self._keys(ticket=ticket, position_id=position_id)
        if not keys:
            return
        record = AttributionRecord(
            strategy_id=sid,
            engine=str(engine or "unknown"),
            strategy_name=strategy_name,
            symbol=symbol,
            ticket=str(ticket) if ticket not in {None, ""} else None,
            position_id=str(position_id) if position_id not in {None, ""} else None,
            opened_at=datetime.now(UTC).isoformat(),
            remaining_volume=float(volume) if volume is not None else None,
            meta=dict(meta or {}),
        )
        with self._lock:
            for key in keys:
                self._by_key[key] = record
        self._persist()

    def resolve(
        self, *, ticket: Any = None, position_id: Any = None
    ) -> AttributionRecord | None:
        with self._lock:
            for key in self._keys(ticket=ticket, position_id=position_id):
                hit = self._by_key.get(key)
                if hit is not None:
                    return hit
        return None

    def note_partial_close(
        self,
        *,
        ticket: Any = None,
        position_id: Any = None,
        closed_volume: float | None = None,
        fully_closed: bool = False,
    ) -> AttributionRecord | None:
        """Keep binding across partial closes; drop only when fully flat."""
        record = self.resolve(ticket=ticket, position_id=position_id)
        if record is None:
            return None
        if fully_closed:
            self.clear(ticket=ticket, position_id=position_id)
            return record
        if closed_volume is not None and record.remaining_volume is not None:
            remaining = max(0.0, float(record.remaining_volume) - float(closed_volume))
            record.remaining_volume = remaining
            with self._lock:
                for key in self._keys(ticket=ticket, position_id=position_id):
                    if key in self._by_key:
                        self._by_key[key] = record
            self._persist()
            if remaining <= 0:
                self.clear(ticket=ticket, position_id=position_id)
        return record

    def clear(self, *, ticket: Any = None, position_id: Any = None) -> None:
        keys = self._keys(ticket=ticket, position_id=position_id)
        if not keys:
            return
        with self._lock:
            for key in keys:
                self._by_key.pop(key, None)
        self._persist()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "count": len(self._by_key),
                "bindings": {k: v.to_dict() for k, v in self._by_key.items()},
            }


_STORE: StrategyAttributionStore | None = None
_STORE_LOCK = threading.Lock()


def get_strategy_attribution_store() -> StrategyAttributionStore:
    global _STORE
    with _STORE_LOCK:
        if _STORE is None:
            _STORE = StrategyAttributionStore()
        return _STORE


def reset_strategy_attribution_store_for_tests(path: Path | None = None) -> None:
    global _STORE
    with _STORE_LOCK:
        target = path or Path("data") / "strategy_attribution_bindings.test.json"
        if target.exists():
            import contextlib

            with contextlib.suppress(OSError):
                target.unlink()
        _STORE = StrategyAttributionStore(path=target)
