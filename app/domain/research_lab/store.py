"""Research Lab — in-memory runs, promotion eligibility (no DB schema)."""

from __future__ import annotations

import threading
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

DEFAULT_PROMOTION_CRITERIA: dict[str, Any] = {
    "min_profit_factor": 1.2,
    "min_sharpe": 0.5,
    "max_drawdown_pct": 20.0,
    "min_trades": 20,
    "min_stability": 0.5,
    "require_walkforward": False,
}


class ResearchLabStore:
    """Process-memory research artifacts + DE eligibility flags."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runs: dict[str, list[dict[str, Any]]] = {}
        self._eligibility: dict[str, dict[str, Any]] = {}
        self._criteria: dict[str, Any] = dict(DEFAULT_PROMOTION_CRITERIA)
        self._param_sandboxes: dict[str, dict[str, Any]] = {}

    def save_run(self, *, user_id: UUID, run: dict[str, Any]) -> dict[str, Any]:
        row = {
            **deepcopy(run),
            "run_id": run.get("run_id") or str(uuid4()),
            "saved_at": datetime.now(UTC).isoformat(),
        }
        with self._lock:
            bucket = self._runs.setdefault(str(user_id), [])
            bucket.append(row)
            if len(bucket) > 500:
                del bucket[:-400]
        return row

    def list_runs(self, user_id: UUID, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = list(self._runs.get(str(user_id), []))
        return list(reversed(rows[-limit:]))

    def get_criteria(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._criteria)

    def set_criteria(self, updates: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            for k, v in updates.items():
                if k in self._criteria:
                    self._criteria[k] = v
            return dict(self._criteria)

    def evaluate_promotion(self, run: dict[str, Any]) -> dict[str, Any]:
        criteria = self.get_criteria()
        metrics = dict(run.get("metrics") or {})
        stability = (run.get("stability") or {}).get("stability_score")
        fails: list[str] = []

        def _f(key: str) -> float | None:
            try:
                return float(metrics[key]) if metrics.get(key) is not None else None
            except (TypeError, ValueError):
                return None

        pf = _f("profit_factor")
        sharpe = _f("sharpe_ratio")
        dd = _f("max_drawdown_pct")
        trades = _f("trade_count")

        if pf is None or pf < float(criteria["min_profit_factor"]):
            fails.append("profit_factor below minimum")
        if sharpe is None or sharpe < float(criteria["min_sharpe"]):
            fails.append("sharpe below minimum")
        if dd is not None and dd > float(criteria["max_drawdown_pct"]):
            fails.append("drawdown exceeds maximum")
        if trades is None or trades < float(criteria["min_trades"]):
            fails.append("insufficient trades")
        if criteria.get("require_walkforward"):
            min_stab = float(criteria["min_stability"])
            if stability is None or float(stability) < min_stab:
                fails.append("walk-forward stability insufficient")
        elif stability is not None:
            if float(stability) < float(criteria["min_stability"]):
                fails.append("stability below preferred threshold")

        eligible = len(fails) == 0
        return {
            "eligible_for_decision_engine": eligible,
            "fails": fails,
            "criteria": criteria,
            "note": (
                "Decision Engine remains the gatekeeper — "
                "eligibility is advisory only"
            ),
            "never_auto_forwards": True,
        }

    def set_eligibility(
        self,
        *,
        user_id: UUID,
        strategy_key: str,
        eligible: bool,
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        key = f"{user_id}:{strategy_key}"
        row = {
            "strategy_key": strategy_key,
            "user_id": str(user_id),
            "eligible_for_decision_engine": eligible,
            "evidence": deepcopy(evidence or {}),
            "updated_at": datetime.now(UTC).isoformat(),
            "decision_engine_untouched": True,
        }
        with self._lock:
            self._eligibility[key] = row
        return row

    def list_eligibility(self, user_id: UUID) -> list[dict[str, Any]]:
        with self._lock:
            return [
                deepcopy(v)
                for k, v in self._eligibility.items()
                if k.startswith(f"{user_id}:")
            ]

    def save_sandbox(self, user_id: UUID, sandbox: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._param_sandboxes[str(user_id)] = deepcopy(sandbox)
        return sandbox

    def get_sandbox(self, user_id: UUID) -> dict[str, Any] | None:
        with self._lock:
            s = self._param_sandboxes.get(str(user_id))
            return deepcopy(s) if s else None


_STORE = ResearchLabStore()


def get_research_store() -> ResearchLabStore:
    return _STORE
