"""Application facade — Production Execution Evidence (read-only)."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_trading.execution_evidence.collector import (
    build_evidence_from_attempt,
)
from app.domain.institutional_trading.execution_evidence.export import (
    WAITING_MESSAGE,
    build_acceptance_status,
    export_waiting_state,
    load_latest_evidence,
)
from app.domain.institutional_trading.production_validation_mode.recorder import (
    get_production_validation_recorder,
)


def build_execution_evidence_status() -> dict[str, Any]:
    """NOC / ops status for Production Acceptance."""
    status = build_acceptance_status()
    # Ensure waiting artifacts exist when nothing captured yet
    if status.get("latest_execution") is None:
        export_waiting_state()
        status = build_acceptance_status()
        if status.get("latest_execution") is None:
            status["message"] = WAITING_MESSAGE
    return status


def get_latest_execution_evidence() -> dict[str, Any]:
    latest = load_latest_evidence()
    if latest.get("latest") is None:
        # Attempt materialize from in-memory eligible PVM attempts
        recorder = get_production_validation_recorder()
        for row in recorder.recent(limit=50):
            attempt = recorder.get(str(row.get("validation_id") or ""))
            if attempt is None:
                continue
            package = build_evidence_from_attempt(attempt)
            if package is None:
                continue
            from app.domain.institutional_trading.execution_evidence.export import (
                export_evidence_package,
            )

            export_evidence_package(package)
            return load_latest_evidence()
        export_waiting_state()
        return load_latest_evidence()
    return latest
