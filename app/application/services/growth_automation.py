"""Owner-invoked growth checks.

These checks are not registered on the trading scheduler. The emergency
stop starts engaged, so a run request does not execute until an owner
releases it. Releasing the stop does not enable ads, billing changes, or
orders. State lives in process memory and returns to stopped on restart.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.application.services.decision_evidence import evidence_contract
from app.domain.billing.plans import plans_public

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_EMERGENCY_STOP = True
_HISTORY: list[dict[str, Any]] = []
_IDEMPOTENCY: dict[str, dict[str, Any]] = {}
_MAX_HISTORY = 20
_TIMEOUT_SECONDS = 2.0

_JOBS: dict[str, dict[str, str]] = {
    "catalog_prices": {
        "title": "Published software prices",
        "source": "app.domain.billing.plans.plans_public",
    },
    "public_route_policy": {
        "title": "Public index policy",
        "source": "declared_public_index_policy",
    },
    "integration_sources": {
        "title": "Integration sources",
        "source": "repository_configuration",
    },
    "decision_evidence_contract": {
        "title": "Decision Evidence contract",
        "source": "app.application.services.decision_evidence.evidence_contract",
    },
}


class UnknownGrowthJob(ValueError):
    """Raised when an owner asks for a job this module does not define."""


def reset_growth_automation_state() -> None:
    """Test helper. Production startup uses the module defaults."""
    global _EMERGENCY_STOP
    with _LOCK:
        _EMERGENCY_STOP = True
        _HISTORY.clear()
        _IDEMPOTENCY.clear()


def _stamp(kind: str, **fields: Any) -> dict[str, Any]:
    entry = {
        "id": str(uuid4()),
        "kind": kind,
        "at": datetime.now(UTC).isoformat(),
        "places_orders": False,
        "changes_billing": False,
        "enables_ads": False,
        **fields,
    }
    _HISTORY.append(entry)
    del _HISTORY[:-_MAX_HISTORY]
    return entry


def growth_automation_status() -> dict[str, Any]:
    with _LOCK:
        return {
            "emergency_stop": _EMERGENCY_STOP,
            "scheduler_attachment": "not_registered",
            "persistence": "process_memory",
            "ads_can_be_enabled": False,
            "places_orders": False,
            "changes_billing": False,
            "retry_limit": 0,
            "timeout_seconds": _TIMEOUT_SECONDS,
            "jobs": [
                {"id": job_id, **meta, "invocation": "owner_request"}
                for job_id, meta in _JOBS.items()
            ],
            "history": list(_HISTORY),
            "note": (
                "Nothing is attached to the trading scheduler. "
                "A restart engages the emergency stop and drops this log. "
                "Search Console and analytics stay not connected."
            ),
        }


def set_growth_emergency_stop(engaged: bool) -> dict[str, Any]:
    global _EMERGENCY_STOP
    with _LOCK:
        _EMERGENCY_STOP = engaged
        _stamp(
            "emergency_stop",
            executed=False,
            status="stopped" if engaged else "released",
            job_id=None,
        )
        return {
            "emergency_stop": _EMERGENCY_STOP,
            "ads_can_be_enabled": False,
            "places_orders": False,
        }


def _catalog_prices() -> dict[str, Any]:
    plans = plans_public()
    return {
        "source": "app.domain.billing.plans.plans_public",
        "plan_count": len(plans),
        "prices_usd": [plan.get("monthly_price_usd") for plan in plans],
        "trial_offered": False,
        "subscriber_count": None,
        "note": "Catalog prices. Not a subscriber count or revenue figure.",
    }


def _public_route_policy() -> dict[str, Any]:
    return {
        "source": "declared_public_index_policy",
        "indexable": ["/", "/pricing", "/learn", "/live", "/contact"],
        "noindex": [
            "/decision-evidence",
            "/signals",
            "/ai-trading-intelligence",
            "/admin",
        ],
        "indexed_page_count": None,
        "note": "Code policy only. Not a Search Console index count.",
    }


def _integration_sources() -> dict[str, Any]:
    return {
        "search_console": "not_connected",
        "analytics": "not_connected",
        "ads": "stopped",
        "impressions": None,
        "clicks": None,
        "sessions": None,
    }


def _decision_contract() -> dict[str, Any]:
    contract = evidence_contract()
    return {
        "source": "app.application.services.decision_evidence.evidence_contract",
        "read_only": contract["read_only"],
        "executes_orders": contract["executes_orders"],
        "invents_reasoning": contract["invents_reasoning"],
        "calculates_risk": contract["calculates_risk"],
        "history_observation": contract["history_observation"],
        "usage_events": None,
    }


_RUNNERS = {
    "catalog_prices": _catalog_prices,
    "public_route_policy": _public_route_policy,
    "integration_sources": _integration_sources,
    "decision_evidence_contract": _decision_contract,
}


def run_growth_job(job_id: str) -> dict[str, Any]:
    if job_id not in _RUNNERS:
        raise UnknownGrowthJob(job_id)
    minute = datetime.now(UTC).strftime("%Y%m%d%H%M")
    key = f"{job_id}:{minute}"
    with _LOCK:
        if _EMERGENCY_STOP:
            return _stamp(
                "job",
                job_id=job_id,
                executed=False,
                status="stopped",
                attempts=0,
                result=None,
                idempotent_replay=False,
            )
        cached = _IDEMPOTENCY.get(key)
        if cached is not None:
            replay = dict(cached)
            replay["idempotent_replay"] = True
            return replay
    started = time.perf_counter()
    try:
        result: dict[str, Any] | None = _RUNNERS[job_id]()
        status = "completed"
        error = None
    except Exception as exc:  # one attempt; no automatic retry
        logger.exception("growth_job_failed", extra={"job_id": job_id})
        result = None
        status = "error"
        error = type(exc).__name__
    elapsed = time.perf_counter() - started
    if status == "completed" and elapsed > _TIMEOUT_SECONDS:
        status = "timeout"
        result = None
    with _LOCK:
        if _EMERGENCY_STOP:
            return _stamp(
                "job",
                job_id=job_id,
                executed=False,
                status="stopped",
                attempts=1,
                result=None,
                idempotent_replay=False,
            )
        entry = _stamp(
            "job",
            job_id=job_id,
            executed=status == "completed",
            status=status,
            attempts=1,
            elapsed_ms=round(elapsed * 1000, 1),
            error=error,
            result=result,
            idempotent_replay=False,
        )
        if status == "completed":
            _IDEMPOTENCY[key] = dict(entry)
        return entry
