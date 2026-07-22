"""Strategy / risk / safety / execution version traceability for trades."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import uuid4


def _iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


DEFAULT_VERSIONS: dict[str, str] = {
    "strategy": "v1.0.1",
    "risk": "v1.0.1",
    "safety": "v1.0.1",
    "execution": "v1.0.1",
    "configuration": "v1.0.1",
}


def normalize_trade_versions(raw: dict[str, Any]) -> dict[str, Any]:
    versions = raw.get("versions") if isinstance(raw.get("versions"), dict) else {}
    merged = {**DEFAULT_VERSIONS, **{k: str(v) for k, v in versions.items()}}
    # Also accept flat keys
    for key in DEFAULT_VERSIONS:
        flat = raw.get(f"{key}_version")
        if flat is not None:
            merged[key] = str(flat)
    return {
        "record_id": str(raw.get("record_id") or uuid4()),
        "trade_id": str(raw.get("trade_id") or raw.get("id") or ""),
        "timestamp": str(raw.get("timestamp") or _iso()),
        "strategy_version": merged["strategy"],
        "risk_version": merged["risk"],
        "safety_version": merged["safety"],
        "execution_version": merged["execution"],
        "configuration_version": merged["configuration"],
        "versions": merged,
        "immutable": True,
        "note": "Version tags are permanent forensic metadata — never rewrite",
    }


class TradeVersionRegistry:
    """Permanent version tags per trade — append-only."""

    def __init__(self) -> None:
        self._rows: list[dict[str, Any]] = []
        self._lock = Lock()

    def record(self, raw: dict[str, Any]) -> dict[str, Any]:
        entry = normalize_trade_versions(raw)
        with self._lock:
            self._rows.append(entry)
            return deepcopy(entry)

    def list(
        self, *, limit: int = 200, trade_id: str | None = None
    ) -> list[dict[str, Any]]:
        with self._lock:
            rows = list(self._rows)
        if trade_id:
            rows = [r for r in rows if str(r.get("trade_id")) == str(trade_id)]
        rows.sort(key=lambda r: str(r.get("timestamp") or ""))
        return deepcopy(rows[-limit:] if limit else rows)

    def get(self, trade_id: str) -> dict[str, Any] | None:
        matches = self.list(limit=10_000, trade_id=trade_id)
        return matches[-1] if matches else None

    def clear_for_tests_only(self) -> None:
        with self._lock:
            self._rows.clear()


_VERSIONS = TradeVersionRegistry()


def get_trade_version_registry() -> TradeVersionRegistry:
    return _VERSIONS
