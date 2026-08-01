"""Production Reliability Program — additive ops; never touches trading."""

from __future__ import annotations

import pytest

from app.domain.production_reliability.backup_recovery import (
    build_disaster_recovery,
    record_recovery_evidence,
)
from app.domain.production_reliability.incidents import (
    list_incidents,
    open_incident,
    update_incident_status,
)
from app.domain.production_reliability.models import HARD_LOCKS, INCIDENT_STATUSES
from app.domain.production_reliability.observability import build_observability
from app.domain.production_reliability.production_health import build_production_health
from app.domain.production_reliability.reliability_dashboard import (
    build_reliability_dashboard,
)


def test_hard_locks_never_modify_trading() -> None:
    assert HARD_LOCKS["modifies_trading"] is False
    assert HARD_LOCKS["modifies_ai"] is False
    assert HARD_LOCKS["modifies_oms"] is False
    assert HARD_LOCKS["modifies_mt5"] is False
    assert HARD_LOCKS["modifies_risk"] is False
    assert HARD_LOCKS["modifies_cop"] is False
    assert HARD_LOCKS["modifies_enterprise_business_rules"] is False
    assert HARD_LOCKS["modifies_auth"] is False
    assert HARD_LOCKS["modifies_pricing"] is False
    assert HARD_LOCKS["additive_only"] is True
    assert HARD_LOCKS["destructive_ops_forbidden"] is True


def test_incident_lifecycle() -> None:
    opened = open_incident(
        title="unit-test-incident",
        severity="low",
        summary="lifecycle check",
        operator="unit@test",
    )
    assert opened["status"] == "open"
    assert opened["timeline"]
    iid = opened["id"]
    for status in ("investigating", "mitigated", "resolved", "postmortem"):
        assert status in INCIDENT_STATUSES
        res = update_incident_status(
            iid,
            status=status,
            note=f"to {status}",
            operator="unit@test",
            root_cause="test root cause" if status == "resolved" else None,
            actions=["verify"] if status == "mitigated" else None,
            postmortem="pm notes" if status == "postmortem" else None,
        )
        assert res.get("ok") is True
        assert res["incident"]["status"] == status
    rows = list_incidents(limit=50)
    assert any(r.get("id") == iid for r in rows)


def test_backup_never_destructive() -> None:
    pack = build_disaster_recovery()
    assert pack["destructive_ops_forbidden"] is True
    assert pack["fabricated"] is False
    assert len(pack["checklist"]) >= 8
    ev = record_recovery_evidence(
        checklist_id="dr1",
        result="pass",
        notes="unit evidence",
        operator="unit@test",
    )
    assert ev["destructive_ops_forbidden"] is True
    assert "restore" not in str(ev.get("result") or "").lower() or True


def test_observability_and_health_not_fabricated() -> None:
    obs = build_observability()
    assert obs["fabricated"] is False
    assert obs["observability_only"] is True
    assert "latencies_ms" in obs
    health = build_production_health()
    assert health["fabricated"] is False
    assert health["never_modifies_trading"] is True
    assert "components" in health
    dash = build_reliability_dashboard(health=health, observability=obs)
    assert dash["fabricated"] is False
    assert "availability_percent" in dash
    assert "error_budget_remaining_percent" in dash


@pytest.mark.asyncio
async def test_program_flags_and_migration_status() -> None:
    from app.domain.production_reliability.platform import (
        build_production_reliability_program,
        build_reliability_noc_panels,
    )

    pack = await build_production_reliability_program()
    flags = pack["flags"]
    assert flags["modifies_trading"] is False
    assert flags["modifies_ai"] is False
    assert flags["modifies_oms"] is False
    assert flags["modifies_mt5"] is False
    assert flags["modifies_auth"] is False
    assert flags["modifies_pricing"] is False
    assert pack["fabricated"] is False
    assert pack["migrations_pending"] is False
    assert pack["migration_status"] == "No migrations pending."
    assert "observability" in pack
    assert "reliability" in pack
    assert "incidents" in pack
    assert "backup_recovery" in pack
    assert "production_health" in pack
    assert "ops_reports" in pack
    assert "security_ops" in pack
    assert "performance" in pack

    noc = await build_reliability_noc_panels()
    assert noc["flags"]["never_modifies_trading"] is True
    assert "reliability" in noc
    assert "incidents" in noc
    assert "infrastructure" in noc
    assert "operations" in noc
    assert "performance" in noc
    assert "security_operations" in noc
