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
    assert "-RunLevel Highest" in text
    assert "order_send" not in text.lower()


def test_install_mt5_terminal_task_prevents_duplicates() -> None:
    text = _read("install_mt5_terminal_task.ps1")
    assert "AtStartup" in text
    assert "IgnoreNew" in text
    assert "start_mt5_terminal.ps1" in text
    assert "QuantForgMT5Terminal" in text
    assert "-Force" in text
    assert "-RunLevel Highest" in text


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


def _tree_root(processes: list[dict], pid: int) -> int:
    by_id = {int(p["pid"]): p for p in processes}

    def is_gw(proc: dict | None) -> bool:
        if not proc:
            return False
        return "services.mt5_gateway.main" in str(proc.get("cmd") or "")

    current = int(pid)
    for _ in range(8):
        proc = by_id.get(current)
        if proc is None:
            break
        parent = by_id.get(int(proc["ppid"]))
        if not is_gw(parent):
            break
        current = int(parent["pid"])
    return current


def test_parent_child_gateway_is_one_tree_not_duplicate() -> None:
    processes = [
        {"pid": 3168, "ppid": 1, "cmd": "powershell.exe -File supervise_gateway.ps1"},
        {"pid": 7728, "ppid": 3168, "cmd": r"C:\QuantForg\.venv\Scripts\python.exe -m services.mt5_gateway.main"},
        {"pid": 7848, "ppid": 7728, "cmd": r"C:\QuantForg\.venv\Scripts\python.exe -m services.mt5_gateway.main"},
    ]
    listen = [7848]
    roots = {_tree_root(processes, pid) for pid in listen}
    assert roots == {7728}
    assert len(roots) == 1


def test_one_listener_is_pass_invariant() -> None:
    text = _read("verify_production_vps.ps1")
    helpers = _read("_gateway_process.ps1")
    assert "Get-GatewayListenPids" in text
    assert "127.0.0.1" in text
    assert "listener_count=1" in text
    assert "duplicate gateway processes count" not in text
    assert "/health/live" in text
    assert "Get-IndependentGatewayTreeRoots" in helpers
    assert r"127\.0\.0\.1:$($script:GatewayPort)" in helpers


def test_two_independent_listeners_are_fail() -> None:
    processes = [
        {"pid": 100, "ppid": 1, "cmd": "python.exe -m services.mt5_gateway.main"},
        {"pid": 200, "ppid": 1, "cmd": "python.exe -m services.mt5_gateway.main"},
    ]
    roots = {_tree_root(processes, pid) for pid in (100, 200)}
    assert roots == {100, 200}
    text = _read("verify_production_vps.ps1")
    assert "independent Gateway trees" in text


def test_supervisor_adopts_healthy_listener() -> None:
    text = _read("supervise_gateway.ps1")
    assert "Ensure-SingleHealthyInstance" in text
    assert "Test-LiveOk" in text
    assert "Start-GatewayProcess" in text
    assert "gateway already live" in text
    # Start only when not healthy
    assert "if (-not $healthy)" in text


def test_process_tree_reclaim_handles_parent_and_child() -> None:
    supervise = _read("supervise_gateway.ps1")
    helpers = _read("_gateway_process.ps1")
    text = supervise + helpers
    assert "Stop-GatewayProcessTree" in text
    assert "Get-GatewayTreeRoot" in text
    assert "taskkill.exe /F /T" in text
    assert "tree_root" in text
    assert supervise.count("function Stop-GatewayPids") == 1
    assert "Stop-Process -Id" not in supervise


def test_production_task_not_once_and_startup_ignore_new() -> None:
    text = _read("install_gateway_task.ps1")
    assert "AtStartup" in text
    assert "IgnoreNew" in text
    assert "Do NOT append -Once" in text
    assert (
        '$arg = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Supervise`""'
        in text
    )
    assert "-Once" not in text.split("Do NOT append -Once")[1].split("$arg =")[1].split("\n")[0]


def test_trading_logic_untouched_by_vps_process_fix() -> None:
    from app.domain.institutional_trading.compounding.models import LIVE_ACTIVATION

    assert LIVE_ACTIVATION == "SHADOW_ONLY"
    for name in (
        "verify_production_vps.ps1",
        "supervise_gateway.ps1",
        "_gateway_process.ps1",
        "install_gateway_task.ps1",
    ):
        body = _read(name).lower()
        assert "order_send" not in body or "never" in body


def test_pid_file_includes_timestamp_and_health() -> None:
    helpers = _read("_gateway_process.ps1")
    assert "updated_utc=" in helpers
    assert "health=$Health" in helpers


def test_gateway_unhealthy_recovery_and_storm_cap() -> None:
    text = _read("supervise_gateway.ps1")
    assert "MaxGatewayStartsPerHour" in text
    assert "restart storm prevented" in text
    assert "Start-Mt5IfMissing" in text
    assert "Repair-CloudflaredIfStopped" in text
    assert "recovery_attempt" in text


def test_duplicate_supervisor_prevention() -> None:
    text = _read("supervise_gateway.ps1")
    assert "Global\\QuantForgMT5GatewaySupervisor" in text
    assert "duplicate supervisor prevented" in text
    assert text.count("WaitOne(0)") >= 1


def test_mt5_missing_recovery_uses_starter_not_order() -> None:
    text = _read("supervise_gateway.ps1") + _read("watchdog_vps.ps1")
    assert "start_mt5_terminal.ps1" in text
    assert "no broker login" in text or "no broker login" in text.lower()
    assert "order_send" not in text.lower() or "never" in text.lower()


def test_cloudflared_missing_and_duplicate_detection() -> None:
    host = _read("_host_recovery.ps1")
    wd = _read("watchdog_vps.ps1")
    verify = _read("verify_production_vps.ps1")
    assert "Cloudflared" in host
    assert "Get-CloudflaredPids" in host
    assert "cloudflared_duplicate" in wd
    assert "Start-Service" in wd
    assert "duplicate cloudflared" in verify
    assert "gateway.quantforg.com/health/live" in host
    assert "tunnel_public_live" in verify


def test_watchdog_does_not_kill_healthy_gateway() -> None:
    text = _read("watchdog_vps.ps1")
    assert "adopted not restarted" in text
    assert "QuantForgVpsWatchdog" in text
    assert "taskkill" not in text.lower()
    assert "never sends broker orders" in text.lower()


def test_watchdog_task_scheduler_config() -> None:
    text = _read("install_watchdog_task.ps1")
    assert "AtStartup" in text
    assert "AtLogOn" in text
    assert "IgnoreNew" in text
    assert "-RunLevel Highest" in text
    assert "PT2M" in text
    assert "watchdog_vps.ps1" in text
    assert "supervise_gateway.ps1 -Once" not in text


def test_no_secret_leakage_in_vps_scripts() -> None:
    for name in (
        "watchdog_vps.ps1",
        "_host_recovery.ps1",
        "supervise_gateway.ps1",
        "install_watchdog_task.ps1",
        "verify_production_vps.ps1",
    ):
        body = _read(name).lower()
        assert "eyj" not in body
        assert "bearer " not in body or "authorization" not in body
        assert "c:\\programdata\\cloudflared\\token" not in body or "not logged" in body or "never" in body


def test_interactive_rdp_and_reboot_documented() -> None:
    doc = (REPO / "docs" / "production" / "VPS_WINDOWS_DEPLOYMENT.md").read_text(
        encoding="utf-8"
    )
    assert "0xC000013A" in doc
    assert "auto-logon" in doc.lower()
    assert "Restart-Computer" in doc
    assert "BIOS" in doc or "BIOS" in doc
    assert "S4U" in doc
    text = _read("install_gateway_task.ps1")
    assert "Interactive is NOT sufficient" in text


def test_host_health_model_states() -> None:
    host = _read("_host_recovery.ps1")
    verify = _read("verify_production_vps.ps1")
    assert 'return "CRITICAL"' in host
    assert 'return "HEALTHY"' in host
    assert 'return "DEGRADED"' in host
    assert "host_state" in verify


def test_recovery_forbids_trading() -> None:
    rec = _read("recover_production_vps.ps1")
    assert "RestartCloudflared" in rec
    assert "order_send" in rec.lower()
    wd = _read("watchdog_vps.ps1")
    assert "never sends broker orders" in wd.lower()
