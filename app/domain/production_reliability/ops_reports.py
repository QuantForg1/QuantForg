"""Operational reports — daily / weekly / monthly / quarterly (observe-only)."""

from __future__ import annotations

import contextlib
from typing import Any

from app.domain.production_reliability.persistence import (
    JsonDocumentStore,
    new_id,
    utc_iso,
)

_store = JsonDocumentStore("ops_reports.json", "reports")


def _period_pack(
    period: str,
    *,
    health: dict[str, Any],
    reliability: dict[str, Any],
    observability: dict[str, Any],
    incidents: dict[str, Any],
    security: dict[str, Any],
    performance: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": f"rpt_{period}",
        "period": period,
        "as_of": utc_iso(),
        "health_overall": health.get("overall"),
        "availability_percent": reliability.get("availability_percent"),
        "sla_met": reliability.get("sla_met"),
        "slo_met": reliability.get("slo_met"),
        "error_budget_remaining_percent": reliability.get(
            "error_budget_remaining_percent"
        ),
        "incident_count": incidents.get("count"),
        "open_incidents": reliability.get("open_incidents"),
        "error_rate": observability.get("error_rate"),
        "success_rate": observability.get("success_rate"),
        "high_latency": observability.get("high_latency") or {},
        "security_alert_count": security.get("alert_count"),
        "slow_endpoints": (performance.get("slow_endpoints") or [])[:10],
        "fabricated": False,
        "observe_only": True,
    }


def _upsert_report(pack: dict[str, Any]) -> None:
    doc_id = str(pack.get("id") or new_id("rpt"))

    def mutator(_row: dict[str, Any]) -> dict[str, Any]:
        updated = dict(pack)
        updated["id"] = doc_id
        return updated

    existing = _store.get(doc_id)
    if existing is None:
        _store.append({**pack, "id": doc_id})
    else:
        _store.upsert(doc_id, mutator)


def build_ops_reports(
    *,
    health: dict[str, Any],
    reliability: dict[str, Any],
    observability: dict[str, Any],
    incidents: dict[str, Any],
    security: dict[str, Any],
    performance: dict[str, Any],
) -> dict[str, Any]:
    daily = _period_pack(
        "daily",
        health=health,
        reliability=reliability,
        observability=observability,
        incidents=incidents,
        security=security,
        performance=performance,
    )
    weekly = _period_pack(
        "weekly",
        health=health,
        reliability=reliability,
        observability=observability,
        incidents=incidents,
        security=security,
        performance=performance,
    )
    monthly = _period_pack(
        "monthly",
        health=health,
        reliability=reliability,
        observability=observability,
        incidents=incidents,
        security=security,
        performance=performance,
    )
    quarterly = {
        **_period_pack(
            "quarterly_infrastructure",
            health=health,
            reliability=reliability,
            observability=observability,
            incidents=incidents,
            security=security,
            performance=performance,
        ),
        "infrastructure": {
            "components_ok": health.get("ok_count"),
            "components_total": health.get("target_count"),
            "resources": observability.get("resources") or {},
            "note": "Quarterly infrastructure snapshot from live probes",
        },
    }

    for pack in (daily, weekly, monthly, quarterly):
        with contextlib.suppress(Exception):
            _upsert_report(pack)

    history = list(reversed(_store.list(limit=40)))
    return {
        "as_of": utc_iso(),
        "daily_health_report": daily,
        "weekly_reliability_report": weekly,
        "monthly_operations_report": monthly,
        "quarterly_infrastructure_report": quarterly,
        "history": history,
        "fabricated": False,
    }
