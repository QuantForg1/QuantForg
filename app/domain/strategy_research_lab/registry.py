"""Strategy Registry — lab catalog metadata (no fabricated performance)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.domain.research_lab.library import STRATEGY_LIBRARY, get_strategy


@dataclass(frozen=True, slots=True)
class RegistryEntry:
    key: str
    name: str
    family: str
    status: str  # registered | validating | approved | promoted | rejected
    engine_plugin: bool
    best_regimes: tuple[str, ...]
    description: str
    version: str = "0.0.0"
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "name": self.name,
            "family": self.family,
            "status": self.status,
            "engine_plugin": self.engine_plugin,
            "best_regimes": list(self.best_regimes),
            "description": self.description,
            "version": self.version,
            "tags": list(self.tags),
            "lab_only": True,
        }


@dataclass
class StrategyRegistry:
    """Mutable lab registry — starts from research library, no live wiring."""

    _entries: dict[str, RegistryEntry] = field(default_factory=dict)
    _updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self._entries:
            for row in STRATEGY_LIBRARY:
                key = str(row["key"])
                self._entries[key] = RegistryEntry(
                    key=key,
                    name=str(row.get("name") or key),
                    family=str(row.get("family") or "unknown"),
                    status="registered",
                    engine_plugin=bool(row.get("engine_plugin")),
                    best_regimes=tuple(str(x) for x in (row.get("best_regimes") or [])),
                    description=str(row.get("description") or ""),
                    version="1.0.0-lab",
                    tags=("research_lab",),
                )
            self._updated_at = datetime.now(UTC)

    def list_entries(self) -> list[dict[str, object]]:
        ordered = sorted(self._entries.values(), key=lambda x: x.key)
        return [e.to_dict() for e in ordered]

    def get(self, key: str) -> dict[str, object] | None:
        entry = self._entries.get(key)
        if entry:
            return entry.to_dict()
        # Fall back to static library metadata without inventing metrics
        lib = get_strategy(key)
        return dict(lib) if lib else None

    def set_status(self, key: str, status: str) -> dict[str, object] | None:
        entry = self._entries.get(key)
        if not entry:
            return None
        allowed = {
            "registered",
            "validating",
            "approved",
            "promoted",
            "rejected",
        }
        if status not in allowed:
            return entry.to_dict()
        updated = RegistryEntry(
            key=entry.key,
            name=entry.name,
            family=entry.family,
            status=status,
            engine_plugin=entry.engine_plugin,
            best_regimes=entry.best_regimes,
            description=entry.description,
            version=entry.version,
            tags=entry.tags,
        )
        self._entries[key] = updated
        self._updated_at = datetime.now(UTC)
        return updated.to_dict()

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": len(self._entries),
            "updated_at": self._updated_at.isoformat(),
            "strategies": self.list_entries(),
            "note": (
                "Registry metadata only — no fabricated performance. "
                "Lab isolated from live execution."
            ),
        }
