"""Release confidence — deployments, rollbacks, incidents, recovery, health trends."""

from __future__ import annotations

from typing import Any

from app.domain.continuous_improvement.persistence import (
    JsonDocumentStore,
    new_id,
    utc_iso,
)

_deploys = JsonDocumentStore("deployment_history.json", "deployments")
_rollbacks = JsonDocumentStore("rollback_history.json", "rollbacks")


def record_deployment(
    *,
    platform: str,
    deployment_id: str,
    commit_sha: str,
    status: str = "SUCCESS",
    note: str = "",
) -> dict[str, Any]:
    doc = {
        "id": new_id("dep"),
        "platform": platform[:64],
        "deployment_id": deployment_id[:128],
        "commit_sha": commit_sha[:64],
        "status": status[:32],
        "note": note[:500],
        "at": utc_iso(),
        "fabricated": False,
    }
    return _deploys.append(doc)


def record_rollback(
    *,
    platform: str,
    from_deployment: str,
    to_deployment: str,
    reason: str = "",
) -> dict[str, Any]:
    doc = {
        "id": new_id("rb"),
        "platform": platform[:64],
        "from_deployment": from_deployment[:128],
        "to_deployment": to_deployment[:128],
        "reason": reason[:500],
        "at": utc_iso(),
        "fabricated": False,
    }
    return _rollbacks.append(doc)


def build_release_confidence(
    *,
    validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validation = validation or {}
    history = list(validation.get("history") or [])

    # Health trend from validation history (ok_count ratio)
    trend_points: list[dict[str, Any]] = []
    for snap in history[:48]:
        if not isinstance(snap, dict):
            continue
        tc = snap.get("target_count") or 1
        ok = snap.get("ok_count") or 0
        try:
            ratio = round(100.0 * float(ok) / float(tc), 2)
        except (TypeError, ValueError):
            ratio = None
        trend_points.append(
            {
                "as_of": snap.get("as_of"),
                "overall": snap.get("overall"),
                "ok_ratio_percent": ratio,
            }
        )

    incidents: dict[str, Any] = {}
    try:
        from app.domain.production_reliability.incidents import build_incident_center

        incidents = build_incident_center()
    except Exception:
        incidents = {}

    recovery_avg = None
    try:
        from app.domain.production_reliability.reliability_dashboard import (
            build_reliability_dashboard,
        )

        dash = build_reliability_dashboard(
            health={"components": validation.get("components") or {}},
            observability={},
        )
        recovery_avg = dash.get("recovery_time_seconds_avg")
    except Exception:  # noqa: S110
        pass

    deploys = list(reversed(_deploys.list(limit=50)))
    rollbacks = list(reversed(_rollbacks.list(limit=50)))

    confidence = "unknown"
    overall = str(validation.get("overall") or "")
    if overall == "healthy" and (incidents.get("by_status") or {}).get("open", 0) == 0:
        confidence = "high"
    elif overall == "degraded":
        confidence = "medium"
    elif overall:
        confidence = "low"

    return {
        "as_of": utc_iso(),
        "confidence": confidence,
        "deployment_history": deploys,
        "deployment_count": len(deploys),
        "rollback_history": rollbacks,
        "rollback_count": len(rollbacks),
        "production_incidents": {
            "count": incidents.get("count"),
            "by_status": incidents.get("by_status") or {},
            "open": (incidents.get("by_status") or {}).get("open"),
        },
        "recovery_time_seconds_avg": recovery_avg,
        "health_trends": trend_points,
        "fabricated": False,
        "observe_only": True,
    }
