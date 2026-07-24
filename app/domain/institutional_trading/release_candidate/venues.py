"""Separate Paper / Demo / Live statistics — never mix."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.domain.institutional_trading.release_candidate.config import (
    DEFAULT_RC1_CONFIG,
    TRADING_VENUES,
)
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class VenueStatsStore:
    _by_venue: dict[str, dict[str, Any]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _path: Path | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._path is None:
            try:
                from core.config.settings import get_settings

                base = Path(getattr(get_settings(), "data_dir", None) or "data")
            except Exception:
                base = Path("data")
            self._path = base / "rc1_venue_stats.json"
        self._load()
        with self._lock:
            for v in TRADING_VENUES:
                self._by_venue.setdefault(
                    v,
                    {
                        "venue": v,
                        "trades": 0,
                        "win_rate": None,
                        "profit_factor": None,
                        "drawdown": None,
                        "pnl": None,
                        "updated_at": None,
                    },
                )

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            rows = raw.get("venues") or {}
            with self._lock:
                if isinstance(rows, dict):
                    for k, v in rows.items():
                        if k in TRADING_VENUES and isinstance(v, dict):
                            self._by_venue[k] = v
        except Exception:
            logger.exception("venue_stats_load_failed")

    def _persist(self) -> None:
        if self._path is None:
            return
        with self._lock:
            payload = {
                "updated_at": datetime.now(UTC).isoformat(),
                "venues": dict(self._by_venue),
                "never_mix": True,
            }
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            logger.exception("venue_stats_persist_failed")

    def record(self, venue: str, metrics: dict[str, Any]) -> dict[str, Any]:
        if venue not in TRADING_VENUES:
            raise ValueError(f"Unknown venue {venue}; allowed={TRADING_VENUES}")
        assert DEFAULT_RC1_CONFIG.never_mix_trading_venues is True
        with self._lock:
            row = dict(self._by_venue.get(venue) or {"venue": venue})
            for k, v in metrics.items():
                if k == "venue":
                    continue
                row[k] = v
            row["venue"] = venue
            row["updated_at"] = datetime.now(UTC).isoformat()
            self._by_venue[venue] = row
            out = dict(row)
        self._persist()
        return out

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            venues = {v: dict(self._by_venue.get(v) or {"venue": v}) for v in TRADING_VENUES}
        return {
            "venues": venues,
            "never_mix": True,
            "note": "Paper, Demo, and Live statistics are stored separately and never mixed.",
        }


_STORE: VenueStatsStore | None = None
_LOCK = threading.Lock()


def get_venue_stats_store() -> VenueStatsStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = VenueStatsStore()
        return _STORE
