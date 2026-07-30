"""Application facade — Production Validation Mode dashboard (read-only)."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_trading.production_validation_mode.recorder import (
    get_production_validation_recorder,
)


def build_production_validation_dashboard() -> dict[str, Any]:
    recorder = get_production_validation_recorder()
    payload = recorder.dashboard()
    payload.update(
        {
            "mode": "production_validation",
            "purpose": "Capture complete execution evidence for natural eligible trades",
            "observe_only": True,
            "never_modifies_strategy": True,
            "never_bypasses_safety": True,
            "never_lowers_quality_gates": True,
            "never_fabricates_trades": True,
            "export_dir": "docs/production/validation/",
        }
    )
    return payload


def list_production_validation_attempts(*, limit: int = 20) -> dict[str, Any]:
    rows = get_production_validation_recorder().recent(limit=limit)
    return {
        "attempts": rows,
        "count": len(rows),
        "observe_only": True,
    }


def get_production_validation_attempt(validation_id: str) -> dict[str, Any] | None:
    attempt = get_production_validation_recorder().get(validation_id)
    if attempt is None:
        return None
    return attempt.to_dict()
