"""In-process registries for Phase 8 research projects, experiments, artifacts.

Governance-only. Never LIVE. Never order_send.
"""

from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import uuid4

from app.domain.quantitative_research_control import MODEL_VERSION


def _now() -> str:
    return datetime.now(UTC).isoformat()


class ResearchStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._projects: dict[str, dict[str, Any]] = {}
        self._experiments: dict[str, dict[str, Any]] = {}
        self._hypotheses: dict[str, dict[str, Any]] = {}
        self._approvals: dict[str, dict[str, Any]] = {}
        self._audit: list[dict[str, Any]] = []

    def list_projects(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = sorted(
                self._projects.values(),
                key=lambda r: str(r.get("updated_at") or ""),
                reverse=True,
            )
            return [dict(r) for r in rows[:limit]]

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._projects.get(project_id)
            return dict(row) if row else None

    def create_project(
        self,
        *,
        name: str,
        hypothesis: str = "",
        instruments: list[str] | None = None,
        timeframe: str | None = None,
        actor: str = "user",
    ) -> dict[str, Any]:
        now = _now()
        pid = f"proj-{uuid4().hex[:12]}"
        row = {
            "id": pid,
            "name": (name or "")[:200],
            "hypothesis": (hypothesis or "")[:4000],
            "instruments": [str(x)[:32] for x in (instruments or [])][:20],
            "timeframe": (timeframe or "")[:32] or None,
            "status": "Research Draft",
            "created_at": now,
            "updated_at": now,
            "actor": (actor or "user")[:120],
            "model_version": MODEL_VERSION,
            "research_only": True,
            "never_order_send": True,
        }
        with self._lock:
            self._projects[pid] = row
            self._audit.append(
                {"at": now, "action": "project_created", "project_id": pid}
            )
            return dict(row)

    def list_experiments(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = sorted(
                self._experiments.values(),
                key=lambda r: str(r.get("created_at") or ""),
                reverse=True,
            )
            return [dict(r) for r in rows[:limit]]

    def create_experiment(
        self,
        *,
        project_id: str | None,
        strategy_id: str | None,
        strategy_version: str | None,
        config: dict[str, Any],
        actor: str = "user",
    ) -> dict[str, Any]:
        now = _now()
        eid = f"exp-{uuid4().hex[:12]}"
        snap = {
            "data_window": config.get("data_window"),
            "parameters": config.get("parameters") or {},
            "costs": config.get("costs") or {},
            "engine_version": config.get("engine_version") or MODEL_VERSION,
            "assumptions": config.get("assumptions") or [],
            "symbol": config.get("symbol"),
            "timeframe": config.get("timeframe"),
        }
        row = {
            "id": eid,
            "project_id": project_id,
            "strategy_id": strategy_id,
            "strategy_version": strategy_version,
            "config_snapshot": snap,
            "status": "configured",
            "result_class": "research",
            "created_at": now,
            "updated_at": now,
            "actor": (actor or "user")[:120],
            "reproducible": True,
            "model_version": MODEL_VERSION,
            "backtest_is_not_live": True,
            "never_order_send": True,
            "fabricated": False,
        }
        with self._lock:
            self._experiments[eid] = row
            self._audit.append(
                {"at": now, "action": "experiment_created", "experiment_id": eid}
            )
            return dict(row)

    def put_hypothesis(self, hyp: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            hid = str(hyp.get("id") or f"hyp-{uuid4().hex[:12]}")
            hyp["id"] = hid
            hyp.setdefault("created_at", _now())
            hyp["updated_at"] = _now()
            hyp["research_artifact"] = True
            hyp["never_auto_live"] = True
            hyp["profitability_claimed"] = False
            hyp["never_order_send"] = True
            hyp["order_send"] = False
            hyp["model_version"] = MODEL_VERSION
            self._hypotheses[hid] = dict(hyp)
            self._audit.append(
                {"at": hyp["updated_at"], "action": "hypothesis_recorded", "id": hid}
            )
            return dict(self._hypotheses[hid])

    def list_hypotheses(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = sorted(
                self._hypotheses.values(),
                key=lambda r: str(r.get("updated_at") or ""),
                reverse=True,
            )
            return [dict(r) for r in rows[:limit]]

    def create_approval(
        self,
        *,
        strategy_id: str,
        strategy_version: str,
        bound_params: dict[str, Any],
        stage: str,
        actor: str,
    ) -> dict[str, Any]:
        now = _now()
        aid = f"rappr-{uuid4().hex[:12]}"
        row = {
            "id": aid,
            "strategy_id": strategy_id,
            "strategy_version": strategy_version,
            "stage": stage,
            "status": "Pending",
            "bound_params": dict(bound_params),
            "created_at": now,
            "updated_at": now,
            "actor": (actor or "user")[:120],
            "history": [{"at": now, "action": "Created", "actor": actor}],
            "approved_is_not_live": True,
            "backtest_is_not_live": True,
            "never_order_send": True,
        }
        with self._lock:
            self._approvals[aid] = row
            self._audit.append(
                {"at": now, "action": "approval_created", "approval_id": aid}
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
        with self._lock:
            row = self._approvals.get(approval_id)
            if row is None:
                return None
            now = _now()
            if action == "Approve" and current_params is not None:
                bound = row.get("bound_params") or {}
                for k in (
                    "strategy_id",
                    "strategy_version",
                    "parameters_hash",
                    "symbol",
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
            if action not in status_map:
                return {
                    "ok": False,
                    "error": "invalid_action",
                    "allowed": list(status_map),
                }
            row["status"] = status_map[action]
            row["updated_at"] = now
            row["history"].append(
                {
                    "at": now,
                    "action": action,
                    "actor": (actor or "user")[:120],
                    "note": (note or "")[:500],
                }
            )
            out = dict(row)
            out["ok"] = True
            out["approved_is_not_live"] = True
            out["never_auto_live_deploy"] = True
            return out

    def list_approvals(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = sorted(
                self._approvals.values(),
                key=lambda r: str(r.get("updated_at") or ""),
                reverse=True,
            )
            return [dict(r) for r in rows[:limit]]

    def pending_review_count(self) -> int:
        with self._lock:
            return sum(
                1
                for r in self._approvals.values()
                if r.get("status") in {"Pending", "Under Review"}
            )

    def list_audit(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            return list(reversed(self._audit[-limit:]))


_STORE: ResearchStore | None = None
_STORE_LOCK = Lock()


def get_research_store() -> ResearchStore:
    global _STORE
    with _STORE_LOCK:
        if _STORE is None:
            _STORE = ResearchStore()
        return _STORE


def reset_research_store_for_tests() -> ResearchStore:
    global _STORE
    with _STORE_LOCK:
        _STORE = ResearchStore()
        return _STORE
