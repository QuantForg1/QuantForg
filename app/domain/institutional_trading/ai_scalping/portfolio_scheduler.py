"""Multi-asset scan scheduler — simultaneous institutional universe cycles (v7).

Schedules full-universe scans each cycle. Does not change quality or risk.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    DEFAULT_SCALPING_UNIVERSE,
    AiScalpingConfig,
)


@dataclass
class MultiAssetScanScheduler:
    """Simultaneous scan of the full multi-asset universe each cycle."""

    config: AiScalpingConfig = field(default_factory=lambda: DEFAULT_AI_SCALPING_CONFIG)
    cycle_index: int = 0
    last_cycle_at: str | None = None
    last_best_symbol: str | None = None
    last_eligible_count: int = 0
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    @property
    def universe(self) -> tuple[str, ...]:
        return tuple(self.config.universe or DEFAULT_SCALPING_UNIVERSE)

    def symbols_for_cycle(self) -> tuple[str, ...]:
        """Return every symbol for simultaneous institutional scanning."""
        return self.universe

    def next_focus_symbol(self) -> str | None:
        """Optional round-robin focus for data-fetch prioritization."""
        uni = self.universe
        if not uni:
            return None
        with self._lock:
            idx = self.cycle_index % len(uni)
            return uni[idx]

    def begin_cycle(self) -> dict[str, Any]:
        with self._lock:
            self.cycle_index += 1
            self.last_cycle_at = datetime.now(UTC).isoformat()
            uni = self.universe
            focus = uni[(self.cycle_index - 1) % len(uni)] if uni else None
            return {
                "cycle_index": self.cycle_index,
                "as_of": self.last_cycle_at,
                "symbols": list(uni),
                "mode": "simultaneous",
                "focus_symbol": focus,
                "version": getattr(self.config, "portfolio_version", None)
                or self.config.version,
            }

    def complete_cycle(
        self,
        *,
        best_symbol: str | None,
        eligible_count: int,
    ) -> dict[str, Any]:
        with self._lock:
            self.last_best_symbol = (
                str(best_symbol).upper() if best_symbol else None
            )
            self.last_eligible_count = int(eligible_count)
            return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "cycle_index": self.cycle_index,
                "last_cycle_at": self.last_cycle_at,
                "universe": list(self.universe),
                "last_best_symbol": self.last_best_symbol,
                "last_eligible_count": self.last_eligible_count,
                "mode": "simultaneous",
                "version": getattr(self.config, "portfolio_version", None)
                or self.config.version,
                "note": (
                    "Scan all symbols each cycle; execute only the best opportunity."
                ),
            }

    def reset(self) -> None:
        with self._lock:
            self.cycle_index = 0
            self.last_cycle_at = None
            self.last_best_symbol = None
            self.last_eligible_count = 0


_SCHED: MultiAssetScanScheduler | None = None
_SCHED_LOCK = threading.Lock()


def get_multi_asset_scheduler(
    config: AiScalpingConfig | None = None,
) -> MultiAssetScanScheduler:
    global _SCHED
    with _SCHED_LOCK:
        if _SCHED is None:
            _SCHED = MultiAssetScanScheduler(
                config=config or DEFAULT_AI_SCALPING_CONFIG
            )
        elif config is not None:
            _SCHED.config = config
        return _SCHED
