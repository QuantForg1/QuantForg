"""Strategy Registry — catalog of research strategies (XAUUSD only)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import uuid4

from app.domain.trading.gold_only import GOLD_SYMBOL


@dataclass
class StrategyRegistry:
    """In-memory registry — never touches live execution."""

    _items: dict[str, dict[str, Any]] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def __post_init__(self) -> None:
        if not self._items:
            for key, name in (
                ("trend_following", "Trend Following"),
                ("mean_reversion", "Mean Reversion"),
                ("breakout", "Breakout"),
                ("liquidity_sweep", "Liquidity Sweep"),
            ):
                self.register(
                    {
                        "strategy_key": key,
                        "name": name,
                        "status": "research",
                        "notes": "Seed registry entry — not production-certified",
                    }
                )

    def register(self, payload: dict[str, Any]) -> dict[str, Any]:
        key = str(payload.get("strategy_key") or f"strat_{uuid4().hex[:8]}")
        row = {
            "strategy_key": key,
            "name": str(payload.get("name") or key),
            "symbol": GOLD_SYMBOL,
            "status": str(payload.get("status") or "research"),
            "notes": str(payload.get("notes") or ""),
            "registered_at": datetime.now(UTC).isoformat(),
            "production_eligible": False,
            "live_execution": False,
        }
        with self._lock:
            self._items[key] = row
        return dict(row)

    def get(self, strategy_key: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._items.get(strategy_key)
            return dict(row) if row else None

    def set_status(self, strategy_key: str, status: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._items.get(strategy_key)
            if row is None:
                return None
            row = dict(row)
            row["status"] = status
            row["production_eligible"] = status == "certified"
            row["live_execution"] = False
            self._items[strategy_key] = row
            return dict(row)

    def list(self) -> dict[str, Any]:
        with self._lock:
            strategies = sorted(self._items.values(), key=lambda r: r["strategy_key"])
        return {
            "status": "available" if strategies else "empty",
            "count": len(strategies),
            "strategies": strategies,
            "symbol": GOLD_SYMBOL,
            "affects_live_execution": False,
        }
