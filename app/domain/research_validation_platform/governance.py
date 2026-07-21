"""Strategy Version Governance + Rollback Engine — audit-preserving."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import uuid4

from app.domain.research_validation_platform.util import reproducible_hash
from app.domain.trading.gold_only import GOLD_SYMBOL


@dataclass
class VersionGovernance:
    """Traceable strategy versions — every change recorded."""

    max_versions: int = 200
    _versions: list[dict[str, Any]] = field(default_factory=list)
    _active: dict[str, str] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def record(self, payload: dict[str, Any]) -> dict[str, Any]:
        strategy_key = str(payload.get("strategy_key") or "unknown")
        version = str(payload.get("version") or f"v_{uuid4().hex[:8]}")
        params = (
            payload.get("parameters")
            if isinstance(payload.get("parameters"), dict)
            else {}
        )
        row = {
            "version_id": f"ver_{uuid4().hex[:12]}",
            "strategy_key": strategy_key,
            "version": version,
            "symbol": GOLD_SYMBOL,
            "parameters": params,
            "notes": str(payload.get("notes") or ""),
            "parent_version": payload.get("parent_version"),
            "created_at": datetime.now(UTC).isoformat(),
            "content_hash": reproducible_hash(
                {
                    "strategy_key": strategy_key,
                    "version": version,
                    "parameters": params,
                }
            ),
            "traceable": True,
            "affects_live_execution": False,
        }
        with self._lock:
            self._versions.insert(0, row)
            if len(self._versions) > self.max_versions:
                self._versions = self._versions[: self.max_versions]
            if strategy_key not in self._active:
                self._active[strategy_key] = version
        return dict(row)

    def list(
        self, *, strategy_key: str | None = None, limit: int = 50
    ) -> dict[str, Any]:
        with self._lock:
            rows = list(self._versions)
            active = dict(self._active)
        if strategy_key:
            rows = [r for r in rows if r["strategy_key"] == strategy_key]
        return {
            "status": "available" if rows else "empty",
            "versions": rows[: max(1, min(limit, self.max_versions))],
            "active": active,
            "traceable": True,
        }

    def active_version(self, strategy_key: str) -> str | None:
        with self._lock:
            return self._active.get(strategy_key)

    def set_active(self, strategy_key: str, version: str) -> None:
        with self._lock:
            self._active[strategy_key] = version


@dataclass
class RollbackEngine:
    """Rollback to prior version — preserves full audit history."""

    versions: VersionGovernance
    max_audit: int = 1000
    _audit: list[dict[str, Any]] = field(default_factory=list)
    _lock: Lock = field(default_factory=Lock)

    def rollback(self, payload: dict[str, Any]) -> dict[str, Any]:
        strategy_key = str(payload.get("strategy_key") or "unknown")
        target_version = str(payload.get("target_version") or "")
        reason = str(payload.get("reason") or "operator_rollback")

        listed = self.versions.list(strategy_key=strategy_key, limit=200)
        match = next(
            (
                v
                for v in listed["versions"]
                if v.get("version") == target_version
            ),
            None,
        )
        previous = self.versions.active_version(strategy_key)
        if match is None:
            return {
                "status": "unavailable",
                "strategy_key": strategy_key,
                "target_version": target_version,
                "rolled_back": False,
                "reasons": [
                    "Target version not found — never invents version history",
                ],
                "audit_preserved": True,
                "affects_live_execution": False,
            }

        self.versions.set_active(strategy_key, target_version)
        audit = {
            "audit_id": f"rb_{uuid4().hex[:12]}",
            "strategy_key": strategy_key,
            "from_version": previous,
            "to_version": target_version,
            "reason": reason,
            "created_at": datetime.now(UTC).isoformat(),
            "version_snapshot": match,
            "audit_preserved": True,
            "affects_live_execution": False,
            "never_order_send": True,
        }
        with self._lock:
            self._audit.insert(0, audit)
            if len(self._audit) > self.max_audit:
                self._audit = self._audit[: self.max_audit]
        return {
            "status": "available",
            "rolled_back": True,
            "strategy_key": strategy_key,
            "from_version": previous,
            "to_version": target_version,
            "audit_id": audit["audit_id"],
            "audit_preserved": True,
            "reasons": [
                f"Active version set to {target_version}",
                "Prior versions and audit trail retained",
                "Live execution pipeline unchanged",
            ],
            "affects_live_execution": False,
            "never_order_send": True,
        }

    def audit(self, *, limit: int = 50) -> dict[str, Any]:
        with self._lock:
            rows = list(self._audit)[: max(1, min(limit, self.max_audit))]
        return {
            "status": "available" if rows else "empty",
            "items": rows,
            "audit_preserved": True,
        }
