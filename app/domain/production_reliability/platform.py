"""Assemble Production Reliability & Operational Excellence Program."""

from __future__ import annotations

from typing import Any

from app.domain.production_reliability import PROGRAM_VERSION
from app.domain.production_reliability.backup_recovery import build_disaster_recovery
from app.domain.production_reliability.incidents import build_incident_center
from app.domain.production_reliability.models import HARD_LOCKS
from app.domain.production_reliability.observability import build_observability
from app.domain.production_reliability.ops_reports import build_ops_reports
from app.domain.production_reliability.performance import build_performance_monitoring
from app.domain.production_reliability.persistence import utc_iso
from app.domain.production_reliability.production_health import build_production_health
from app.domain.production_reliability.reliability_dashboard import (
    build_reliability_dashboard,
)
from app.domain.production_reliability.security_ops import build_security_ops_async


async def build_production_reliability_program() -> dict[str, Any]:
    observability = build_observability()
    health = build_production_health()
    reliability = build_reliability_dashboard(
        health=health, observability=observability
    )
    incidents = build_incident_center()
    backup = build_disaster_recovery()
    security = await build_security_ops_async()
    performance = build_performance_monitoring(observability=observability)
    reports = build_ops_reports(
        health=health,
        reliability=reliability,
        observability=observability,
        incidents=incidents,
        security=security,
        performance=performance,
    )
    return {
        "as_of": utc_iso(),
        "program_version": PROGRAM_VERSION,
        "observability": observability,
        "reliability": reliability,
        "incidents": incidents,
        "backup_recovery": backup,
        "production_health": health,
        "ops_reports": reports,
        "security_ops": security,
        "performance": performance,
        "flags": {
            **HARD_LOCKS,
            "program_version": PROGRAM_VERSION,
        },
        "fabricated": False,
        "migrations_pending": False,
        "migration_status": "No migrations pending.",
    }


async def build_reliability_noc_panels() -> dict[str, Any]:
    pack = await build_production_reliability_program()
    rel = pack.get("reliability") or {}
    health = pack.get("production_health") or {}
    obs = pack.get("observability") or {}
    incidents = pack.get("incidents") or {}
    security = pack.get("security_ops") or {}
    perf = pack.get("performance") or {}
    backup = pack.get("backup_recovery") or {}
    return {
        "reliability": {
            "availability_percent": rel.get("availability_percent"),
            "sla_met": rel.get("sla_met"),
            "slo_met": rel.get("slo_met"),
            "error_budget_remaining_percent": rel.get("error_budget_remaining_percent"),
            "open_incidents": rel.get("open_incidents"),
            "observe_only": True,
        },
        "incidents": {
            "count": incidents.get("count"),
            "by_status": incidents.get("by_status") or {},
            "observe_only": True,
        },
        "infrastructure": {
            "overall": health.get("overall"),
            "ok_count": health.get("ok_count"),
            "target_count": health.get("target_count"),
            "observe_only": True,
        },
        "operations": {
            "success_rate": obs.get("success_rate"),
            "error_rate": obs.get("error_rate"),
            "backup_artifacts": (backup.get("backup_status") or {}).get(
                "artifact_count"
            ),
            "dr_passed": backup.get("passed_count"),
            "observe_only": True,
        },
        "performance": {
            "cpu_percent": (perf.get("cpu") or {}).get("percent"),
            "memory_percent": (perf.get("memory") or {}).get("percent"),
            "slow_endpoints": len(perf.get("slow_endpoints") or []),
            "observe_only": True,
        },
        "security_operations": {
            "alert_count": security.get("alert_count"),
            "failed_auth_count": security.get("failed_auth_count"),
            "expired_api_key_count": security.get("expired_api_key_count"),
            "observe_only": True,
        },
        "latencies_ms": obs.get("latencies_ms") or {},
        "flags": {
            "observe_only": True,
            "never_modifies_trading": True,
            "destructive_ops_forbidden": True,
            "program_version": PROGRAM_VERSION,
        },
        "fabricated": False,
    }
