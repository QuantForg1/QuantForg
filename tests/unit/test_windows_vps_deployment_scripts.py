"""Static checks for Windows VPS deployment scripts.

Does not register Scheduled Tasks, does not start MT5, does not call order_send.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.infrastructure.brokers.mt5.deployment_topology import topology_snapshot

REPO = Path(__file__).resolve().parents[2]
DEPLOY = REPO / "deploy" / "mt5_gateway"

pytestmark = [pytest.mark.unit]


def _read(name: str) -> str:
    return (DEPLOY / name).read_text(encoding="utf-8")


def test_install_gateway_task_is_unattended_and_idempotent() -> None:
    text = _read("install_gateway_task.ps1")
    assert "AtStartup" in text
    assert "AtLogOn" in text
    assert "IgnoreNew" in text
    assert "ExecutionTimeLimit" in text
    assert "supervise_gateway.ps1" in text
    assert "QuantForgMT5Gateway" in text
    assert "-Force" in text
    assert "order_send" not in text.lower()


def test_install_mt5_terminal_task_prevents_duplicates() -> None:
    text = _read("install_mt5_terminal_task.ps1")
    assert "AtStartup" in text
    assert "IgnoreNew" in text
    assert "start_mt5_terminal.ps1" in text
    assert "QuantForgMT5Terminal" in text
    assert "-Force" in text


def test_start_mt5_terminal_never_logs_in_or_trades() -> None:
    text = _read("start_mt5_terminal.ps1")
    assert "terminal64.exe" in text
    assert "duplicate start prevented" in text
    assert "Start-Process -FilePath $TerminalPath" in text
    assert "order_send" not in text
    assert "MT5_PASSWORD" not in text


def test_supervisor_mutex_backoff_and_mt5_wait() -> None:
    text = _read("supervise_gateway.ps1")
    assert "QuantForgMT5GatewaySupervisor" in text
    assert "duplicate supervisor prevented" in text
    assert "MaxBackoffSec" in text
    assert "health/live" in text
    assert "mt5_unavailable" in text
    assert "stale pid" in text
    assert "not a market/Risk block" in text or "not restarting" in text


def test_verify_script_is_read_only() -> None:
    text = _read("verify_production_vps.ps1")
    assert "PASS" in text
    assert "WARN" in text
    assert "FAIL" in text
    assert "NEVER calls order_send" in text
    assert "Invoke-RestMethod" in text
    assert "order_send" in text  # mentioned only as forbidden


def test_deploy_entrypoint_is_idempotent_and_secret_safe() -> None:
    text = _read("deploy_production_vps.ps1")
    assert "idempotent" in text.lower() or "Idempotent" in text
    assert "verify_production_vps.ps1" in text
    assert "install_gateway_task.ps1" in text
    assert "values not printed" in text
    assert "order_send" not in text


def test_recover_script_forbids_live_orders() -> None:
    text = _read("recover_production_vps.ps1")
    assert "RestartGateway" in text
    assert "RestartSupervisor" in text
    assert "NEVER" in text or "never" in text
    assert "order_send" in text  # mentioned as forbidden
    assert "BUY" in text or "never" in text.lower()


def test_topology_still_requires_human_cutover() -> None:
    snap = topology_snapshot()
    assert snap["migration_executed"] is False
    assert snap["user_windows_pc_may_be_off"] is False
    assert snap["vps_deployment_automation_in_repo"] is True
    assert snap["vps_cutover_requires_human"] is True


def test_vps_doc_exists_without_secrets() -> None:
    doc = (REPO / "docs" / "production" / "VPS_WINDOWS_DEPLOYMENT.md").read_text(
        encoding="utf-8"
    )
    assert "MT5_GATEWAY_BASE_URL" in doc
    assert "MT5_GATEWAY_CALLER_TOKEN" in doc
    assert "127.0.0.1:8765" in doc
    assert "order_send" in doc
    lowered = doc.lower()
    assert "eyj" not in lowered
    assert "-----begin" not in lowered
