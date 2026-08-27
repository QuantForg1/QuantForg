"""Production reliability hardening — infrastructure only.

Does not change Opportunity 70, sniper, Risk 40%, Safety, OMS, or MT5
order_send semantics. Fail-closed on unverified duplicate-protection state.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.application.services.institutional_oms_adapter import RecordingOmsPort
from app.domain.institutional_trading.config import MAX_DAILY_LOSS_PCT
from app.domain.institutional_trading.execution.decision_hash_store import (
    DecisionHashLoad,
    HASH_PAYLOAD_KEY,
    load_decision_hash_report,
    load_executed_hashes,
    persist_executed_hashes,
)
from app.domain.institutional_trading.execution.models import BridgeAbortReason
from app.domain.institutional_trading.operations.communication_fault import (
    should_blind_retry_order_submit,
)
from app.domain.institutional_trading.operations.execution_chain_log import (
    bridge_abort_stage,
    build_execution_handoff,
)
from app.domain.institutional_trading.operations.infrastructure_heartbeats import (
    CLOUDFLARED_HEARTBEAT,
    GATEWAY_HEARTBEAT,
    MT5_HEARTBEAT,
    RAILWAY_ITE_HEARTBEAT,
    heartbeat_snapshot,
    note_heartbeat,
)
from app.domain.institutional_trading.operations.probability_selector import (
    OPPORTUNITY_SCORE_THRESHOLD,
)
from app.domain.institutional_trading.operations.resource_snapshot import (
    collect_resource_snapshot,
)
from app.infrastructure.brokers.mt5.deployment_topology import topology_snapshot
from tests.unit.test_institutional_trading_phase_c import (
    _bridge,
    _buy_decision,
    _ctx,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

REPO = Path(__file__).resolve().parents[2]


def test_owner_surfaces_not_required() -> None:
    snap = topology_snapshot()
    assert snap["owner_home_pc_required"] is False
    assert snap["owner_wifi_required"] is False
    assert snap["browser_required"] is False
    assert snap["works_without_user_pc"] is True
    assert snap["works_without_user_browser"] is True
    assert snap["windows_vps_required"] is True
    assert snap["mt5_session_recovery_unproven"] is True
    assert snap["running_terminal_is_not_execution_ready"] is True


def test_opportunity_70_and_daily_loss_40_unchanged() -> None:
    assert OPPORTUNITY_SCORE_THRESHOLD == 70
    assert MAX_DAILY_LOSS_PCT == pytest.approx(40.0)


def test_take_is_not_executed_without_ticket() -> None:
    handoff = build_execution_handoff(
        take=True,
        abort_reason="RISK_REJECTED",
        blocking_stage="RISK",
        forwarded_to_oms=False,
        mt5_ticket=None,
    )
    assert handoff["execution_confirmed"] is False
    assert handoff["mt5_ticket"] is None
    executed = build_execution_handoff(
        take=True,
        forwarded_to_oms=True,
        mt5_ticket=123456,
    )
    assert executed["execution_confirmed"] is True
    assert executed["mt5_ticket"] == 123456


def test_no_fabricated_ticket_and_no_blind_order_retry() -> None:
    assert should_blind_retry_order_submit() is False
    handoff = build_execution_handoff(take=True, forwarded_to_oms=True, mt5_ticket=0)
    assert handoff["mt5_ticket"] is None
    assert handoff["execution_confirmed"] is False


def test_decision_hash_unverified_is_execution_health_not_oms() -> None:
    assert (
        bridge_abort_stage(BridgeAbortReason.DECISION_HASH_UNVERIFIED.value)
        == "EXECUTION_HEALTH"
    )
    from app.application.services.signal_center_service import _overlay_last_ite_cycle

    row = {
        "direction": "BUY",
        "pipeline": {
            "final_decision": "BUY",
            "oms": "READY",
            "execution_lifecycle": "EXECUTING",
        },
    }
    last = {
        "abort_reason": "DECISION_HASH_UNVERIFIED",
        "forwarded_to_oms": False,
        "mt5_ticket": None,
        "execution_blocked": {
            "stage": "EXECUTION_HEALTH",
            "reason_code": "DECISION_HASH_UNVERIFIED",
            "human_reason": "hash store unverified",
        },
    }
    out = _overlay_last_ite_cycle(row, last)
    assert out["pipeline"]["oms"] == "NOT_REACHED"
    assert out["pipeline"].get("oms") != "BLOCK"
    assert out["first_blocker"] == "DECISION_HASH_UNVERIFIED"


def test_risk_rejected_overlay_keeps_human_reason() -> None:
    from app.application.services.signal_center_service import _overlay_last_ite_cycle

    row = {
        "direction": "BUY",
        "pipeline": {"final_decision": "BUY"},
    }
    last = {
        "abort_reason": "RISK_REJECTED",
        "forwarded_to_oms": False,
        "decision_reasons": ["generic eligibility: spread too wide"],
        "execution_blocked": {
            "stage": "RISK",
            "reason_code": "RISK_REJECTED",
            "human_reason": "generic eligibility: spread too wide",
        },
    }
    out = _overlay_last_ite_cycle(row, last)
    assert out["first_blocker"] == "RISK_REJECTED"
    assert out["pipeline"]["oms"] == "NOT_REACHED"
    assert "spread too wide" in str(out.get("reasoning") or "")


def test_atomic_hash_persist_and_reload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.domain.institutional_trading.execution.decision_hash_store as store

    monkeypatch.setattr(store, "_path", lambda: tmp_path / "execution_decision_hashes.json")
    persist_executed_hashes(["aaa", "bbb"])
    loaded, order = load_executed_hashes()
    assert loaded == {"aaa", "bbb"}
    assert order == ["aaa", "bbb"]
    report = load_decision_hash_report()
    assert report.verified is True
    path = tmp_path / "execution_decision_hashes.json"
    assert path.is_file()
    assert not path.with_suffix(path.suffix + ".tmp").exists()


def test_unverified_postgres_is_not_empty_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.application.services.ops_state_persistence.load_postgres_state_strict",
        lambda: (True, False, {}, "ConnectError"),
    )
    report = load_decision_hash_report()
    assert report.verified is False
    assert report.hashes == set()
    assert report.source == "postgres_unverified"


def test_postgres_hashes_merge_without_clobber(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.application.services.ops_state_persistence.load_postgres_state_strict",
        lambda: (
            True,
            True,
            {HASH_PAYLOAD_KEY: {"hashes": ["pg-only"]}},
            None,
        ),
    )
    monkeypatch.setattr(
        "app.domain.institutional_trading.execution.decision_hash_store._load_file_hashes",
        lambda **_k: (["file-only"], True, None),
    )
    report = load_decision_hash_report()
    assert report.verified is True
    assert "pg-only" in report.hashes
    assert "file-only" in report.hashes


def test_unverified_hash_hydrate_blocks_oms(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.domain.institutional_trading.execution.decision_hash_store.load_decision_hash_report",
        lambda **_k: DecisionHashLoad(
            hashes=set(),
            order=[],
            verified=False,
            source="postgres_unverified",
            durable=False,
            error="ConnectError",
        ),
    )
    oms = RecordingOmsPort()
    integ = _bridge(oms)
    integ.bridge._hashes_hydrated = True
    integ.bridge._hashes_unverified = True
    decision, snap, acct = _buy_decision()
    result = integ.bridge.handle(decision, _ctx(decision, snap, acct))
    assert result.forwarded_to_oms is False
    assert result.abort_reason is BridgeAbortReason.DECISION_HASH_UNVERIFIED
    assert oms.calls == []


def test_scanner_heartbeat_fields_and_dead_scanner_fail_closed() -> None:
    from app.domain.institutional_trading.operations.worker_runtime_state import (
        healthy_cycle_window_seconds,
        scheduler_is_stalled,
    )

    assert healthy_cycle_window_seconds(5.0) >= 90.0
    stalled = scheduler_is_stalled(
        last_cycle_finished_mono=1.0,
        now_mono=1.0 + 10_000.0,
        interval_seconds=5.0,
        started_mono=0.0,
        running=True,
    )
    assert stalled is True
    note_heartbeat(RAILWAY_ITE_HEARTBEAT, ok=False, state="UNHEALTHY", reason="stalled")
    snap = heartbeat_snapshot()
    beat = snap["heartbeats"][RAILWAY_ITE_HEARTBEAT]
    assert beat["state"] == "UNHEALTHY"
    assert beat["failure_count"] >= 1
    assert "timestamp" in beat
    assert "uptime_seconds" in beat


def test_component_heartbeats_named() -> None:
    note_heartbeat(GATEWAY_HEARTBEAT, ok=True, state="HEALTHY")
    note_heartbeat(MT5_HEARTBEAT, ok=False, state="DISCONNECTED", reason="broker")
    note_heartbeat(CLOUDFLARED_HEARTBEAT, ok=True, state="UP")
    snap = heartbeat_snapshot()
    assert GATEWAY_HEARTBEAT in snap["heartbeats"]
    assert MT5_HEARTBEAT in snap["heartbeats"]
    assert CLOUDFLARED_HEARTBEAT in snap["heartbeats"]
    assert snap["heartbeats"][MT5_HEARTBEAT]["last_failure_reason"] == "broker"


def test_resource_snapshot_does_not_change_thresholds() -> None:
    snap = collect_resource_snapshot()
    assert snap["modifies_trading_thresholds"] is False
    assert snap["kills_processes"] is False
    assert "ram_band" in snap
    assert "disk_band" in snap
    assert OPPORTUNITY_SCORE_THRESHOLD == 70
    assert MAX_DAILY_LOSS_PCT == pytest.approx(40.0)


def test_railway_restart_policy_always() -> None:
    text = (REPO / "railway.toml").read_text(encoding="utf-8")
    assert 'restartPolicyType = "ALWAYS"' in text
    assert "restartPolicyMaxRetries" not in text


def test_watchdog_session_states_and_no_duplicate_spawn() -> None:
    wd = (REPO / "deploy" / "mt5_gateway" / "watchdog_vps.ps1").read_text(
        encoding="utf-8"
    )
    host = (REPO / "deploy" / "mt5_gateway" / "_host_recovery.ps1").read_text(
        encoding="utf-8"
    )
    assert "PROCESS_RUNNING" in wd
    assert "PROCESS_MISSING" in wd
    assert "PROCESS_UNHEALTHY" in wd
    assert "not_spawning_duplicate" in wd
    assert "MT5_SESSION_RECOVERY_UNPROVEN" in host
    assert "EXECUTION_PATH_READY" in host
    assert "BROKER_CONNECTED" in host
    assert "AUTOTRADING_ENABLED" in host
    assert "Get-Mt5SessionClassification" in host
    assert "Get-LocalGatewayHealth" in host
    assert "live_ok_one_listener" in wd
    assert "Task Scheduler Ready is NOT health" in wd
    assert "order_send" not in wd.lower()


def test_book_facts_incomplete_still_fail_closed() -> None:
    src = (
        REPO / "app" / "application" / "services" / "ite_cycle_market_context.py"
    ).read_text(encoding="utf-8")
    assert "book_facts_incomplete" in src
    assert "blocking add-on" in (
        REPO / "app" / "application" / "services" / "institutional_decision_pipeline.py"
    ).read_text(encoding="utf-8")


def test_hash_payload_key_does_not_replace_ops_mode() -> None:
    assert HASH_PAYLOAD_KEY == "execution_decision_hashes"
    assert HASH_PAYLOAD_KEY != "ops_mode"
    assert HASH_PAYLOAD_KEY != "trading_mode"
