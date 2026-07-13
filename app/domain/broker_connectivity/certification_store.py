"""In-process certification history — no DB schema change."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import uuid4

from app.domain.broker_connectivity.certification_states import CertificationState


@dataclass
class CertificationHistoryRecord:
    record_id: str
    at: str
    broker_slug: str
    broker_name: str
    result: str
    state: str
    failure_reason: str
    tester: str
    diagnostics: list[dict[str, str]] = field(default_factory=list)
    report: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "date": self.at,
            "broker": self.broker_slug,
            "broker_name": self.broker_name,
            "result": self.result,
            "state": self.state,
            "failure_reason": self.failure_reason,
            "tester": self.tester,
            "diagnostics": list(self.diagnostics),
            "report": dict(self.report),
        }


class CertificationStore:
    """Process-scoped certification status + history."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._status: dict[str, dict[str, Any]] = {}
        self._history: list[CertificationHistoryRecord] = []

    def get_status(self, slug: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._status.get(slug.strip().lower())
            return dict(row) if row else None

    def all_status(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(v) for v in self._status.values()]

    def set_status(self, slug: str, payload: dict[str, Any]) -> None:
        with self._lock:
            self._status[slug.strip().lower()] = dict(payload)

    def append_history(
        self,
        *,
        broker_slug: str,
        broker_name: str,
        result: str,
        state: CertificationState,
        failure_reason: str,
        tester: str,
        diagnostics: list[dict[str, str]] | None = None,
        report: dict[str, Any] | None = None,
    ) -> CertificationHistoryRecord:
        rec = CertificationHistoryRecord(
            record_id=str(uuid4()),
            at=datetime.now(UTC).isoformat(),
            broker_slug=broker_slug.strip().lower(),
            broker_name=broker_name,
            result=result,
            state=state.value,
            failure_reason=failure_reason,
            tester=tester.strip() or "operator",
            diagnostics=list(diagnostics or []),
            report=dict(report or {}),
        )
        with self._lock:
            self._history.append(rec)
            self._history = self._history[-500:]
        return rec

    def history(
        self, *, broker_slug: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        with self._lock:
            rows = list(self._history)
        if broker_slug:
            code = broker_slug.strip().lower()
            rows = [r for r in rows if r.broker_slug == code]
        rows = rows[-max(1, limit) :]
        return [r.to_dict() for r in reversed(rows)]
