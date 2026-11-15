"""In-process registries for Phase 7 decisions, modes, approvals, audit.

Governance-only. Never LIVE. Never order_send.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any
from uuid import uuid4

from app.domain.autonomous_trading_control import (
    APPROVAL_ACTIONS,
    AUTONOMY_MODES,
    DEFAULT_MODE,
    MODEL_VERSION,
)

_ALLOWED_MODES = set(AUTONOMY_MODES)
_ALLOWED_ACTIONS = set(APPROVAL_ACTIONS)


def _now() -> str:
    return datetime.now(UTC).isoformat()


class AutonomyStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._mode: str = DEFAULT_MODE
        self._mode_history: list[dict[str, Any]] = [
            {
                "at": _now(),
                "mode": DEFAULT_MODE,
                "actor": "system",
                "note": "default_boot",
            }
        ]
        self._decisions: dict[str, dict[str, Any]] = {}
        self._approvals: dict[str, dict[str, Any]] = {}
        self._audit: list[dict[str, Any]] = []
        self._seen_signal_keys: set[str] = set()

    # --- mode ------------------------------------------------------------------

    def get_mode(self) -> dict[str, Any]:
        with self._lock:
            return {
                "mode": self._mode,
                "default_mode": DEFAULT_MODE,
                "allowed": list(AUTONOMY_MODES),
                "history": list(self._mode_history[-20:]),
                "phase7_live_dispatch": False,
                "never_order_send": True,
                "model_version": MODEL_VERSION,
            }

    def set_mode(
        self,
        mode: str,
        *,
        actor: str,
        note: str = "",
    ) -> dict[str, Any]:
        if mode not in _ALLOWED_MODES:
            return {
                "ok": False,
                "error": "invalid_mode",
                "allowed": list(AUTONOMY_MODES),
            }
        with self._lock:
            prev = self._mode
            self._mode = mode
            row = {
                "at": _now(),
                "from": prev,
                "mode": mode,
                "actor": (actor or "unknown")[:120],
                "note": (note or "")[:500],
            }
            self._mode_history.append(row)
            self._audit.append(
                {
                    "at": row["at"],
                    "action": "mode_change",
                    "actor": row["actor"],
                    "detail": {"from": prev, "to": mode},
                }
            )
            return {
                "ok": True,
                "mode": mode,
                "previous": prev,
                "phase7_live_dispatch": False,
                "never_order_send": True,
                "authorized_is_not_live_submit": True,
            }

    # --- decisions -------------------------------------------------------------

    def list_decisions(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = sorted(
                self._decisions.values(),
                key=lambda r: str(r.get("updated_at") or r.get("created_at") or ""),
                reverse=True,
            )
            return [dict(r) for r in rows[:limit]]

    def get_decision(self, decision_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._decisions.get(decision_id)
            return dict(row) if row else None

    def put_decision(self, decision: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            did = str(decision.get("decision_id") or "")
            if not did:
                did = f"dec-{uuid4().hex[:12]}"
                decision["decision_id"] = did
            now = _now()
            decision.setdefault("created_at", now)
            decision["updated_at"] = now
            decision["model_version"] = MODEL_VERSION
            decision["never_order_send"] = True
            self._decisions[did] = dict(decision)
            sig = decision.get("signal_key")
            if isinstance(sig, str) and sig:
                self._seen_signal_keys.add(sig)
            self._audit.append(
                {
                    "at": now,
                    "action": "decision_recorded",
                    "decision_id": did,
                    "outcome": decision.get("outcome"),
                }
            )
            return dict(self._decisions[did])

    def has_signal_key(self, key: str) -> bool:
        with self._lock:
            return key in self._seen_signal_keys

    # --- approvals -------------------------------------------------------------

    def list_approvals(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = sorted(
                self._approvals.values(),
                key=lambda r: str(r.get("updated_at") or ""),
                reverse=True,
            )
            return [dict(r) for r in rows[:limit]]

    def create_approval(
        self,
        *,
        decision_id: str,
        bound_params: dict[str, Any],
        actor: str,
        expires_in_minutes: int = 30,
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        aid = f"appr-{uuid4().hex[:12]}"
        row = {
            "id": aid,
            "decision_id": decision_id,
            "status": "Pending",
            "bound_params": dict(bound_params),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "expires_at": (
                now + timedelta(minutes=max(1, expires_in_minutes))
            ).isoformat(),
            "actor": (actor or "unknown")[:120],
            "history": [{"at": now.isoformat(), "action": "Created", "actor": actor}],
            "approved_is_not_live": True,
            "never_order_send": True,
        }
        with self._lock:
            self._approvals[aid] = row
            self._audit.append(
                {
                    "at": now.isoformat(),
                    "action": "approval_created",
                    "approval_id": aid,
                    "decision_id": decision_id,
                }
            )
            return dict(row)

    def act_on_approval(
        self,
        approval_id: str,
        *,
        action: str,
        actor: str,
        note: str = "",
        current_params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if action not in _ALLOWED_ACTIONS:
            return {
                "ok": False,
                "error": "invalid_action",
                "allowed": list(APPROVAL_ACTIONS),
            }
        with self._lock:
            row = self._approvals.get(approval_id)
            if row is None:
                return None
            now = _now()
            # Expiry check
            exp = str(row.get("expires_at") or "")
            if exp and exp < now and action == "Approve":
                row["status"] = "Expired"
                row["updated_at"] = now
                row["history"].append(
                    {"at": now, "action": "Expire", "actor": "system", "note": "auto"}
                )
                return {
                    "ok": False,
                    "error": "expired",
                    "approval": dict(row),
                    "approved_is_not_live": True,
                }
            # Material change invalidates prior approval for Approve
            if action == "Approve" and current_params is not None:
                bound = row.get("bound_params") or {}
                for k in (
                    "symbol",
                    "direction",
                    "volume",
                    "stop_loss",
                    "take_profit",
                    "account_id",
                ):
                    if str(bound.get(k, "")) != str(current_params.get(k, "")):
                        row["status"] = "Invalidated"
                        row["updated_at"] = now
                        row["history"].append(
                            {
                                "at": now,
                                "action": "Invalidated",
                                "actor": actor,
                                "note": f"param_mismatch:{k}",
                            }
                        )
                        return {
                            "ok": False,
                            "error": "material_change",
                            "field": k,
                            "approval": dict(row),
                            "approved_is_not_live": True,
                        }
            status_map = {
                "Approve": "Approved",
                "Reject": "Rejected",
                "Request Review": "Under Review",
                "Expire": "Expired",
                "Cancel": "Cancelled",
            }
            row["status"] = status_map[action]
            row["updated_at"] = now
            row["history"].append(
                {
                    "at": now,
                    "action": action,
                    "actor": (actor or "unknown")[:120],
                    "note": (note or "")[:500],
                }
            )
            self._audit.append(
                {
                    "at": now,
                    "action": f"approval_{action.lower().replace(' ', '_')}",
                    "approval_id": approval_id,
                    "actor": actor,
                }
            )
            out = dict(row)
            out["ok"] = True
            out["approved_is_not_live"] = True
            out["never_authorizes_live_execution"] = True
            return out

    def pending_approval_count(self) -> int:
        with self._lock:
            return sum(
                1
                for r in self._approvals.values()
                if r.get("status") in {"Pending", "Under Review"}
            )

    def list_audit(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            return list(reversed(self._audit[-limit:]))


_STORE: AutonomyStore | None = None
_STORE_LOCK = Lock()


def get_autonomy_store() -> AutonomyStore:
    global _STORE
    with _STORE_LOCK:
        if _STORE is None:
            _STORE = AutonomyStore()
        return _STORE


def reset_autonomy_store_for_tests() -> AutonomyStore:
    """Test helper — fresh store."""
    global _STORE
    with _STORE_LOCK:
        _STORE = AutonomyStore()
        return _STORE
