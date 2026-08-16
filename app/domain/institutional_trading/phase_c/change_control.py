"""Model / strategy change control — auditable governance records."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from typing import Any
from uuid import uuid4


@dataclass
class ModelChangeRecord:
    change_id: str
    old_commit: str
    new_commit: str
    old_model: str
    new_model: str
    reason: str
    research_run_id: str
    validation_results: dict[str, Any]
    PBO: dict[str, Any] | None
    DSR: dict[str, Any] | None
    monte_carlo: dict[str, Any] | None
    parameter_sensitivity: dict[str, Any] | None
    shadow_performance: dict[str, Any] | None
    risk_impact: str
    execution_impact: str
    approval_status: str
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "change_id": self.change_id,
            "old_commit": self.old_commit,
            "new_commit": self.new_commit,
            "old_model": self.old_model,
            "new_model": self.new_model,
            "reason": self.reason,
            "research_run_id": self.research_run_id,
            "validation_results": dict(self.validation_results),
            "PBO": self.PBO,
            "DSR": self.DSR,
            "Monte Carlo": self.monte_carlo,
            "parameter_sensitivity": self.parameter_sensitivity,
            "shadow_performance": self.shadow_performance,
            "risk_impact": self.risk_impact,
            "execution_impact": self.execution_impact,
            "approval_status": self.approval_status,
            "timestamp": self.timestamp,
        }


@dataclass
class ModelChangeControlStore:
    records: list[ModelChangeRecord] = field(default_factory=list)
    _lock: RLock = field(default_factory=RLock, repr=False)

    def propose(self, **kwargs: Any) -> ModelChangeRecord:
        status = str(kwargs.get("approval_status") or "PROPOSED")
        # Never silently mark approved without actor evidence
        if status in {"APPROVED", "APPROVED_FOR_LIVE", "DEPLOYED"}:
            if not kwargs.get("approval_actor"):
                status = "PROPOSED"
        rec = ModelChangeRecord(
            change_id=str(kwargs.get("change_id") or uuid4()),
            old_commit=str(kwargs.get("old_commit") or ""),
            new_commit=str(kwargs.get("new_commit") or ""),
            old_model=str(kwargs.get("old_model") or ""),
            new_model=str(kwargs.get("new_model") or ""),
            reason=str(kwargs.get("reason") or "UNKNOWN_REASON"),
            research_run_id=str(kwargs.get("research_run_id") or ""),
            validation_results=dict(kwargs.get("validation_results") or {}),
            PBO=kwargs.get("PBO"),
            DSR=kwargs.get("DSR"),
            monte_carlo=kwargs.get("monte_carlo"),
            parameter_sensitivity=kwargs.get("parameter_sensitivity"),
            shadow_performance=kwargs.get("shadow_performance"),
            risk_impact=str(kwargs.get("risk_impact") or "UNKNOWN"),
            execution_impact=str(kwargs.get("execution_impact") or "NONE_SHADOW_ONLY"),
            approval_status=status,
            timestamp=str(kwargs.get("timestamp") or datetime.now(UTC).isoformat()),
        )
        with self._lock:
            self.records.append(rec)
            if len(self.records) > 200:
                self.records = self.records[-200:]
        return rec

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            rows = [r.to_dict() for r in self.records]
        return {"changes": rows[-20:], "count": len(rows)}
