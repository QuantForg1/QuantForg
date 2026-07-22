"""Configuration change history — never overwrite prior versions."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import uuid4


def _iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class ConfigurationChangeHistory:
    """Append-only history of production configuration changes."""

    def __init__(self) -> None:
        self._rows: list[dict[str, Any]] = []
        self._lock = Lock()

    def record(self, raw: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise TypeError("Configuration change must be a dict")
        entry = {
            "change_id": str(raw.get("change_id") or uuid4()),
            "timestamp": str(raw.get("timestamp") or _iso()),
            "scope": str(
                raw.get("scope") or raw.get("component") or "configuration"
            )
            .strip()
            .lower(),
            "key": str(raw.get("key") or raw.get("name") or ""),
            "previous_value": raw.get("previous_value")
            if raw.get("previous_value") is not None
            else raw.get("old_value"),
            "new_value": raw.get("new_value")
            if raw.get("new_value") is not None
            else raw.get("value"),
            "environment": str(raw.get("environment") or "unknown"),
            "version": str(raw.get("version") or ""),
            "actor": str(raw.get("actor") or raw.get("operator") or "system"),
            "approval": raw.get("approval"),
            "reason": str(raw.get("reason") or ""),
            "immutable": True,
            "never_overwrite_history": True,
        }
        with self._lock:
            # Never overwrite by change_id — append only
            self._rows.append(entry)
            return deepcopy(entry)

    def list(
        self, *, limit: int = 200, scope: str | None = None
    ) -> list[dict[str, Any]]:
        with self._lock:
            rows = list(self._rows)
        if scope:
            rows = [r for r in rows if r.get("scope") == scope]
        rows.sort(key=lambda r: str(r.get("timestamp") or ""))
        return deepcopy(rows[-limit:] if limit else rows)

    def count(self) -> int:
        with self._lock:
            return len(self._rows)

    def clear_for_tests_only(self) -> None:
        with self._lock:
            self._rows.clear()


_CFG_HISTORY = ConfigurationChangeHistory()


def get_config_change_history() -> ConfigurationChangeHistory:
    return _CFG_HISTORY
