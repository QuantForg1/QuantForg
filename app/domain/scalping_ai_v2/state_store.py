"""Operational state persistence — survive unexpected restarts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any


@dataclass
class OperationalStateStore:
    """Persist Auto Trading operational state (advisory — never order_send).

    Default path is process-local JSON. Tests may inject an in-memory-only
    store by setting ``path=None``.
    """

    path: Path | None = None
    _state: dict[str, Any] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)
    _dirty: bool = False

    def __post_init__(self) -> None:
        if self.path is not None:
            self.path = Path(self.path)
            self.load()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._state)

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._state.get(key, default)

    def update(self, patch: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._state.update(patch)
            self._state["updated_at"] = datetime.now(UTC).isoformat()
            self._dirty = True
            out = dict(self._state)
        self.persist()
        return out

    def restore_bundle(
        self,
        *,
        auto_trading_state: str | None = None,
        pending_supervision: list[dict[str, Any]] | None = None,
        open_positions: list[dict[str, Any]] | None = None,
        execution_identities: list[str] | None = None,
        active_incidents: list[dict[str, Any]] | None = None,
        recovery_state: dict[str, Any] | None = None,
        safe_mode: bool | None = None,
        emergency_stop: bool | None = None,
    ) -> dict[str, Any]:
        patch: dict[str, Any] = {}
        if auto_trading_state is not None:
            patch["auto_trading_state"] = auto_trading_state
        if pending_supervision is not None:
            patch["pending_supervision"] = list(pending_supervision)
        if open_positions is not None:
            patch["open_positions"] = list(open_positions)
        if execution_identities is not None:
            patch["execution_identities"] = list(execution_identities)
        if active_incidents is not None:
            patch["active_incidents"] = list(active_incidents)
        if recovery_state is not None:
            patch["recovery_state"] = dict(recovery_state)
        if safe_mode is not None:
            patch["safe_mode"] = bool(safe_mode)
        if emergency_stop is not None:
            patch["emergency_stop"] = bool(emergency_stop)
        return self.update(patch)

    def load(self) -> dict[str, Any]:
        if self.path is None or not self.path.exists():
            return self.snapshot()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self.snapshot()
        if not isinstance(raw, dict):
            return self.snapshot()
        with self._lock:
            self._state = dict(raw)
            self._dirty = False
            return dict(self._state)

    def persist(self) -> bool:
        if self.path is None:
            return False
        with self._lock:
            if not self._dirty and self.path.exists():
                return True
            payload = dict(self._state)
            self._dirty = False
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(
                json.dumps(payload, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            tmp.replace(self.path)
            return True
        except OSError:
            return False

    def export_for_restart(self) -> dict[str, Any]:
        snap = self.snapshot()
        return {
            "status": "available",
            "restores": [
                "auto_trading_state",
                "pending_supervision",
                "open_positions",
                "execution_identities",
                "active_incidents",
                "recovery_state",
                "safe_mode",
                "emergency_stop",
            ],
            "never_duplicate_on_restart": True,
            "state": snap,
        }
