"""Phase 5 — Institutional Ops Control Center unit coverage."""

from __future__ import annotations

from app.application.services import institutional_ops_control as ioc
from app.domain.institutional_ops_control import (
    MODEL_VERSION,
    PHASE5_LIFECYCLE_STAGES,
    isolation_payload,
    live_deploy_allowed,
    map_islm_stage,
)
from app.domain.institutional_ops_control.overview import (
    build_accounts_overview,
    build_execution_overview,
    build_governance_summary,
    build_hub_summary,
    build_incidents_overview,
    build_risk_overview,
    build_strategy_lifecycle_overview,
)


def test_isolation_flags_block_live_and_order_send() -> None:
    flags = isolation_payload()
    assert flags["never_order_send"] is True
    assert flags["never_auto_deploy_live"] is True
    assert flags["never_bypasses_kill_switch"] is True
    assert flags["never_increases_risk_limits"] is True
    assert flags["model_version"] == MODEL_VERSION


def test_health_service() -> None:
    h = ioc.health()
    assert h["ok"] is True
    assert h["order_send"] is False
    assert h["auto_live_deploy"] is False


def test_hub_summary_lists_seven_modules() -> None:
    hub = build_hub_summary()
    assert len(hub["modules"]) == 7
    paths = {m["path"] for m in hub["modules"]}
    assert "/operations" in paths
    assert "/governance" in paths
    assert "start" in hub["robot_controls"]["resume"].lower()
    assert "pause" in hub["robot_controls"]["resume"].lower()


def test_lifecycle_stages_are_ten() -> None:
    assert len(PHASE5_LIFECYCLE_STAGES) == 10
    assert PHASE5_LIFECYCLE_STAGES[0] == "Draft"
    assert PHASE5_LIFECYCLE_STAGES[-1] == "Archived"


def test_map_islm_and_live_gate() -> None:
    assert map_islm_stage("Draft") == "Draft"
    assert map_islm_stage("Research") == "Backtesting"
    assert map_islm_stage("Suspended") == "Paused"
    assert map_islm_stage("Retired") == "Archived"

    assert (
        live_deploy_allowed(
            stage="Deployment",
            human_approved=True,
            risk_cleared=True,
            owner_authorized=True,
        )
        is True
    )
    assert (
        live_deploy_allowed(
            stage="Deployment",
            human_approved=False,
            risk_cleared=True,
            owner_authorized=True,
        )
        is False
    )
    assert (
        live_deploy_allowed(
            stage="Validation",
            human_approved=True,
            risk_cleared=True,
            owner_authorized=True,
        )
        is False
    )


def test_backtest_pass_not_implied_live_in_lifecycle_overview() -> None:
    # May be empty registry in CI — still must carry honest rules.
    out = build_strategy_lifecycle_overview()
    assert out["rules"]["backtest_pass_not_live"] is True
    assert out["rules"]["explicit_authorization_required_for_live"] is True
    assert out["never_auto_deploy_live"] is True
    for row in out.get("strategies") or []:
        if row.get("phase5_stage") == "Validation":
            assert row.get("live_deploy_allowed") is False


def test_execution_overview_does_not_fabricate() -> None:
    empty = build_execution_overview(attempts=[], decisions=[])
    assert empty["empty"] is True
    assert empty["metrics"]["success_rate"] is None
    assert empty["metrics"]["fabricated"] is False

    filled = build_execution_overview(
        attempts=[
            {"outcome": "accepted", "latency_ms": 40, "slippage": 0.2},
            {"outcome": "rejected", "latency_ms": 80},
        ],
        decisions=[{"id": 1}],
    )
    assert filled["metrics"]["attempt_count"] == 2
    assert filled["metrics"]["accepted_count"] == 1
    assert filled["metrics"]["rejected_count"] == 1
    assert filled["metrics"]["success_rate"] == 0.5
    assert filled["metrics"]["avg_latency_ms"] == 60.0


def test_accounts_observe_only_and_no_ready_banner() -> None:
    out = build_accounts_overview(
        ops_summary={"workers": [{"status": "stale", "stale": True}]},
        dispatch_status={"live_submit_allowed": False},
    )
    assert out["one_primary_account_per_user"] is True
    assert out["mt5_authoritative_for_trade_allowed"] is True
    assert out["live_submit_allowed"] is False
    assert out["workers"]["ready_count"] == 0
    assert out["banner"]


def test_risk_overview_cannot_raise_limits() -> None:
    out = build_risk_overview(ati_alerts=[{"code": "x", "advisory_only": True}])
    assert out["enforcement"]["ui_cannot_raise_limits"] is True
    assert out["enforcement"]["ai_cannot_override_hard_constraints"] is True
    assert out["ati_advisory_only"] is True


def test_incidents_normalize_and_safe_recovery() -> None:
    out = build_incidents_overview(
        prp_incidents=[
            {
                "id": "inc-1",
                "severity": "high",
                "status": "open",
                "created_at": "2026-01-01T00:00:00Z",
            }
        ],
        worker_signals=[
            {
                "incident_id": "hb-1",
                "severity": "medium",
                "status": "open",
                "detail": "stale heartbeat",
            }
        ],
    )
    assert out["count"] == 2
    assert out["recovery_rules"]["never_auto_resend_uncertain_orders"] is True
    assert out["recovery_rules"]["reconcile_with_mt5_first"] is True


def test_governance_redacts_secrets() -> None:
    out = build_governance_summary(
        audit_events=[
            {
                "action": "approve",
                "password": "secret",
                "api_key": "k",
                "token": "t",
                "actor": "owner",
            }
        ],
        islm_approvals=[{"id": "a1", "status": "pending"}],
        irdp_approvals=[],
        qsf_approvals=[],
    )
    assert out["pending_count"] == 1
    assert out["secrets_redacted"] is True
    ev = out["audit_events"][0]
    assert "password" not in ev
    assert "api_key" not in ev
    assert "token" not in ev
    assert ev["action"] == "approve"


def test_operations_overview_flags() -> None:
    out = ioc.operations_overview()
    assert out["ok"] is True
    assert out["controls"]["resume_equals_start"] is True
    assert out["controls"]["aoc_mutations"] is False
    assert out["never_order_send"] is True
