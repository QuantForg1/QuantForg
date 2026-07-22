"""Unit tests — Institutional Audit Trail & Governance (governance only)."""

from __future__ import annotations

import pytest

from app.domain.audit_governance.change_history import ConfigurationChangeHistory
from app.domain.audit_governance.reports import (
    build_audit_governance_pack,
    build_forensic_timeline,
)
from app.domain.audit_governance.store import ImmutableAuditStore
from app.domain.audit_governance.versions import TradeVersionRegistry


@pytest.mark.unit
class TestAuditGovernance:
    def test_append_only_and_immutable(self) -> None:
        store = ImmutableAuditStore()
        e1 = store.append(
            {
                "category": "operations",
                "action": "ops_promotion",
                "previous_state": "SHADOW",
                "new_state": "CANARY",
                "actor": "owner",
                "timestamp": "2026-07-22T09:05:00Z",
                "reason": "approved",
            }
        )
        assert e1["timestamp"]
        assert e1["immutable"] is True
        assert e1["integrity_hash"]
        with pytest.raises(RuntimeError, match="immutable"):
            store.update_forbidden(e1["event_id"], {"new_state": "LIVE"})
        with pytest.raises(RuntimeError, match="deleted"):
            store.delete_forbidden(e1["event_id"])
        with pytest.raises(ValueError, match="already exists"):
            store.append({**e1, "new_state": "LIVE"})

    def test_never_omits_timestamp(self) -> None:
        store = ImmutableAuditStore()
        e = store.append({"category": "system", "action": "daily_report_generated"})
        assert e["timestamp"]
        assert "T" in e["timestamp"]

    def test_forensic_timeline_order(self) -> None:
        store = ImmutableAuditStore()
        store.append(
            {
                "timestamp": "2026-07-22T09:02:00Z",
                "category": "broker",
                "action": "broker_login",
            }
        )
        store.append(
            {
                "timestamp": "2026-07-22T09:00:00Z",
                "category": "gateway",
                "action": "gateway_connected",
            }
        )
        timeline = build_forensic_timeline(store.list(limit=50))
        assert timeline["steps"][0]["action"] == "gateway_connected"
        assert timeline["steps"][1]["action"] == "broker_login"

    def test_config_history_never_overwrites(self) -> None:
        hist = ConfigurationChangeHistory()
        a = hist.record(
            {
                "key": "EXECUTION_ENABLED",
                "previous_value": "false",
                "new_value": "true",
                "actor": "owner",
                "reason": "arm",
            }
        )
        b = hist.record(
            {
                "key": "EXECUTION_ENABLED",
                "previous_value": "true",
                "new_value": "false",
                "actor": "owner",
                "reason": "disarm",
            }
        )
        rows = hist.list()
        assert len(rows) == 2
        assert a["change_id"] != b["change_id"]
        assert rows[0]["new_value"] == "true"
        assert rows[1]["new_value"] == "false"

    def test_trade_version_traceability(self) -> None:
        reg = TradeVersionRegistry()
        tag = reg.record({"trade_id": "515822"})
        assert tag["strategy_version"] == "v1.0.1"
        assert tag["risk_version"] == "v1.0.1"
        assert tag["safety_version"] == "v1.0.1"
        assert tag["execution_version"] == "v1.0.1"
        assert tag["configuration_version"] == "v1.0.1"
        got = reg.get("515822")
        assert got is not None
        assert got["trade_id"] == "515822"

    def test_governance_pack_recommendations_only(self) -> None:
        store = ImmutableAuditStore()
        hist = ConfigurationChangeHistory()
        vers = TradeVersionRegistry()
        store.append(
            {
                "timestamp": "2026-07-22T09:06:00Z",
                "category": "execution",
                "severity": "critical",
                "action": "execution_enabled",
                "actor": "owner",
                "reason": "canary",
                "approval": {"required": True},
            }
        )
        pack = build_audit_governance_pack(
            store=store, config_history=hist, versions=vers
        )
        assert pack["governance_only"] is True
        assert pack["never_modifies_trading_behaviour"] is True
        assert pack["security"]["append_only"] is True
        assert pack["dashboard"]["accountability"]["sensitive_actions"] >= 1
        assert isinstance(pack["recommendations"], list)
        assert "daily_audit_report" in pack["reports"]
        assert "monthly_compliance_report" in pack["reports"]

    def test_filters_and_search(self) -> None:
        store = ImmutableAuditStore()
        store.append(
            {
                "category": "safety",
                "severity": "critical",
                "action": "kill_switch_armed",
                "actor": "owner.bob",
                "reason": "drill",
                "timestamp": "2026-07-22T09:12:00Z",
            }
        )
        store.append(
            {
                "category": "gateway",
                "severity": "info",
                "action": "gateway_connected",
                "actor": "system",
                "timestamp": "2026-07-22T09:00:00Z",
            }
        )
        crit = store.list(severity="critical")
        assert len(crit) == 1
        found = store.list(q="kill_switch")
        assert len(found) == 1
        ranged = store.list(since="2026-07-22T09:10:00Z")
        assert len(ranged) == 1
