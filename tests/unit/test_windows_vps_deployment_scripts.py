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
    assert "HOST HEALTHY" in text
    assert "SOFTWARE RECOVERY READY" in text
    assert "PUBLIC TUNNEL HEALTHY" in text
    assert "REBOOT READINESS" in text
    assert "PROCESS UNIQUENESS" in text
    assert "AUTO_LOGON" in text
    assert "watchdog_repetition" in text
    assert "mt5_attached" in text
    assert "VPS remains powered" in text or "VPS/Windows host remains available" in text
    assert "never-stop" in text or "never stops" in text.lower()
    assert "NO ORDER IS SENT" in text
    assert "LIVE ORDER SENT: NO" in text
    assert "PROVIDER POWER RECOVERY" in text


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


def test_topology_vps_cutover_executed_session_unproven() -> None:
    snap = topology_snapshot()
    assert snap["migration_executed"] is True
    assert snap["user_windows_pc_may_be_off"] is True
    assert snap["vps_deployment_automation_in_repo"] is True
    assert snap["vps_cutover_requires_human"] is False
    assert snap["mt5_session_recovery_unproven"] is True
    assert snap["windows_vps_required"] is True


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


def test_supervisor_pid_file_parse_does_not_capture_listener_label() -> None:
    """Regression: filter regex must not leave $Matches[1]='listener' for [int]."""
    text = _read("supervise_gateway.ps1")
    assert "rawPidLines" in text
    assert "foreach ($pidLine in $rawPidLines)" in text
    assert "^(?:listener|tree_root)=(\\d+)" in text
    # Must not use a capturing group on the label token before the PID.
    assert '$_ -match "^(listener|tree_root)="' not in text


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
    assert "Stop-Process -Name python" not in text
    assert "Stop-Process -Name terminal64" not in text
    assert "Stop-Process -Name cloudflared" not in text
    assert "while ($true)" not in text
    assert "while($true)" not in text


def test_watchdog_starts_gateway_process_not_only_task() -> None:
    text = _read("watchdog_vps.ps1")
    assert 'ArgumentList @("-m", "services.mt5_gateway.main")' in text
    assert "Start-WatchdogGateway" in text
    assert "Task Scheduler Ready is NOT health" in text
    assert "Start-ScheduledTask" in text
    assert "not_restarting_gateway" in text
    assert "local_ok_public_fail" in text
    assert "exit 0" in text
    assert "exitCode = 1" in text or "$exitCode = 1" in text
    assert "exitCode = 2" in text or "$exitCode = 2" in text
    assert "Global\\QuantForgVpsWatchdog" in text
    assert "order_send" not in text.lower()
    assert "FORCE_FIRST_TRADE" not in text
    assert "ALLOW_RISK_LOCK_OVERRIDE" not in text
    assert "MT5_GATEWAY_TOKEN" not in text
    assert "Authorization" not in text


def test_watchdog_duplicate_and_unhealthy_listener_reclaim() -> None:
    text = _read("watchdog_vps.ps1")
    helpers = _read("_gateway_process.ps1")
    assert "Stop-GatewayProcessTree" in text
    assert "duplicate_listeners" in text
    assert "listener_unhealthy" in text
    assert "Get-IndependentGatewayTreeRoots" in helpers
    assert "taskkill.exe /F /T" in helpers
    assert "Stop-Process -Name python" not in helpers


def test_watchdog_task_scheduler_config() -> None:
    text = _read("install_watchdog_task.ps1")
    assert "AtStartup" in text
    assert "AtLogOn" in text
    assert "IgnoreNew" in text
    assert "-RunLevel Highest" in text
    assert "watchdog_vps.ps1" in text
    assert "supervise_gateway.ps1 -Once" not in text
    assert r"System32\WindowsPowerShell\v1.0\powershell.exe" in text
    assert "-RepetitionInterval" in text
    assert "New-TimeSpan -Minutes 2" in text
    assert "New-TimeSpan -Days 9999" in text
    assert ".Repetition.Interval =" not in text
    assert 'Interval = "PT2M"' not in text
    assert "Verified watchdog repetition" in text
    assert "Ready is not treated as health" in text


def test_no_secret_leakage_in_vps_scripts() -> None:
    for name in (
        "watchdog_vps.ps1",
        "_host_recovery.ps1",
        "supervise_gateway.ps1",
        "install_watchdog_task.ps1",
        "verify_production_vps.ps1",
        "inspect_autologon.ps1",
        "open_autologon_ui.ps1",
        "confirm_provider_power_recovery.ps1",
        "finalize_unattended_reboot.ps1",
        "verify_reboot_readiness.ps1",
        "harden_cloudflared_service.ps1",
    ):
        body = _read(name).lower()
        assert "eyj" not in body
        assert "bearer " not in body or "authorization" not in body
        assert "c:\\programdata\\cloudflared\\token" not in body or "not logged" in body or "never" in body
        assert "getvalue(\"defaultpassword\")" not in body
        assert "getvalue('defaultpassword')" not in body


def test_interactive_rdp_and_reboot_documented() -> None:
    doc = (REPO / "docs" / "production" / "VPS_WINDOWS_DEPLOYMENT.md").read_text(
        encoding="utf-8"
    )
    assert "0xC000013A" in doc
    assert "auto-logon" in doc.lower()
    assert "Restart-Computer" in doc
    assert "BIOS" in doc or "BIOS" in doc
    assert "cannot enable Windows Auto-Logon" in doc
    assert "PROVIDER POWER RECOVERY" in doc
    assert "authoritative" in doc.lower()
    assert "Ready is NOT health" in doc or "Ready is not health" in doc
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
    assert "watchdog_vps.ps1" in rec
    wd = _read("watchdog_vps.ps1")
    assert "never sends broker orders" in wd.lower()


def test_watchdog_ps1_files_parse() -> None:
    import subprocess
    import sys

    if sys.platform != "win32":
        pytest.skip("PowerShell parse is Windows-only")
    names = (
        "watchdog_vps.ps1",
        "install_watchdog_task.ps1",
        "verify_production_vps.ps1",
        "recover_production_vps.ps1",
        "supervise_gateway.ps1",
        "install_gateway_task.ps1",
        "_gateway_process.ps1",
        "_host_recovery.ps1",
        "start_gateway.ps1",
        "start_mt5_terminal.ps1",
        "inspect_autologon.ps1",
        "open_autologon_ui.ps1",
        "confirm_provider_power_recovery.ps1",
        "finalize_unattended_reboot.ps1",
        "verify_reboot_readiness.ps1",
        "harden_cloudflared_service.ps1",
        "install_mt5_terminal_task.ps1",
    )
    for name in names:
        path = DEPLOY / name
        cmd = (
            "$errs = $null; "
            "$null = [System.Management.Automation.Language.Parser]::ParseFile("
            f"'{path}', [ref]$null, [ref]$errs); "
            "if ($errs) { $errs | ForEach-Object { $_.ToString() }; exit 1 }; "
            "exit 0"
        )
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, f"{name}: {completed.stdout}\n{completed.stderr}"


def test_autologon_detection_does_not_expose_password() -> None:
    host = _read("_host_recovery.ps1")
    inspect = _read("inspect_autologon.ps1")
    verify = _read("verify_production_vps.ps1")
    reboot = _read("verify_reboot_readiness.ps1")
    text = host + inspect + verify + reboot
    assert "Get-AutoLogonReadiness" in host
    assert "AUTO_LOGON" in inspect
    assert "ACTION_REQUIRED" in inspect
    assert "NOT_SUPPORTED" in inspect
    assert "ERROR" in inspect
    assert "READY" in inspect
    assert "cannot enable Auto-Logon" in inspect
    assert "GetValue(\"DefaultPassword\")" not in text
    assert "GetValue('DefaultPassword')" not in text
    assert "Restart-Computer" not in inspect
    assert "order_send" not in inspect.lower()


def test_watchdog_does_not_trust_task_state_as_health() -> None:
    text = _read("watchdog_vps.ps1")
    assert "Task Scheduler Ready is NOT health" in text
    assert "Start-WatchdogGateway" in text
    assert "health is live" in text.lower() or "health_is_live" in text or "ignored_health_is_live" in text
    assert "restart_storm_prevented" in text
    assert "Test-WatchdogGatewayStartAllowed" in text
    assert "duplicate_terminal" in text
    assert "not_restarting_gateway" in text
    assert "PROCESS_RUNNING" in text
    assert "PROCESS_UNHEALTHY" in text
    assert "not_spawning_duplicate" in text
    assert "do_not_fake_readiness" in text
    assert "MT5_SESSION_RECOVERY_UNPROVEN" in _read("_host_recovery.ps1")


def test_reboot_readiness_script_never_reboots() -> None:
    text = _read("verify_reboot_readiness.ps1")
    assert "REBOOT READINESS" in text
    assert "Restart-Computer" not in text
    assert "NO ORDER IS SENT" in text
    assert "does not reboot" in text.lower()
    assert "Get-AutoLogonReadiness" in text
    assert "QuantForgVpsWatchdog" in text
    assert "PT2M" in text
    assert "SOFTWARE RECOVERY" in text
    assert "PROVIDER POWER RECOVERY" in text
    assert "LIVE ORDER SENT: NO" in text
    assert "HOST HEALTH" in text
    assert "MT5 SESSION" in text
    assert "PUBLIC TUNNEL" in text
    assert "AUTO_LOGON=READY" in text
    assert "MT5_SESSION_RECOVERY_UNPROVEN" in text
    assert "EXECUTION_PATH" in text
    assert "Get-Mt5SessionClassification" in text


def test_open_autologon_ui_never_takes_password() -> None:
    text = _read("open_autologon_ui.ps1")
    assert "LaunchUi" in text
    assert "netplwiz" in text
    assert "[string]$Password" not in text
    assert "[SecureString]" not in text
    assert "DefaultPassword" not in text
    assert "cannot enable Windows Auto-Logon" in text
    assert "param(" in text
    assert "-Password" not in text
    assert "Write-AutologonOperatorInstructions" in text
    assert "Set-AutologonNonSecretIdentity" in text
    assert 'Domain=. applied' in text or "Domain=." in text


def test_local_autologon_uses_dot_domain_not_dns_hostname() -> None:
    host = _read("_host_recovery.ps1")
    inspect = _read("inspect_autologon.ps1")
    open_ui = _read("open_autologon_ui.ps1")
    finalize = _read("finalize_unattended_reboot.ps1")
    reboot = _read("verify_reboot_readiness.ps1")
    verify = _read("verify_production_vps.ps1")
    doc = (REPO / "docs" / "production" / "VPS_WINDOWS_DEPLOYMENT.md").read_text(
        encoding="utf-8"
    )
    identity = host + inspect + open_ui + finalize
    assert "Get-LocalAutologonIdentity" in host
    assert '$AutoLogonUser = "Administrator"' in host
    assert '$AutoLogonDomain = "."' in host
    assert "Test-IsIncorrectLocalAutologonDomain" in host
    assert "US-HOST-421124" in host
    assert "invalid Autologon domain" in host
    assert "US-HOST-421124" in inspect
    assert "invalid local-account Autologon domain" in inspect
    assert "Password=dialog only" in host
    assert "Password = enter only in that dialog, then Enable." in host
    assert "Write-AutologonOperatorInstructions" in inspect
    assert "Write-AutologonOperatorInstructions" in finalize
    assert "Write-AutologonOperatorInstructions" in open_ui
    assert "Set-AutologonNonSecretIdentity" in host
    assert "Set-AutologonNonSecretIdentity" not in inspect
    assert 'Name "AutoAdminLogon"' not in host
    assert 'Name "DefaultPassword"' not in host
    assert 'GetValue("DefaultPassword")' not in identity
    assert "New-LocalUser" not in identity
    assert "Restart-Computer" not in identity
    assert "order_send" not in identity.lower()
    assert 'Username=Administrator  Domain={0}' not in identity
    assert '-f $computer' not in identity
    assert 'Domain   = {0}' not in open_ui
    assert "the VPS computer name" not in doc
    assert '$result.Enabled -and $result.UserConfigured' in host
    assert '$result.Enabled -and $result.UserConfigured -and $result.DomainConfigured' not in host
    assert "ACTION_REQUIRED" in inspect
    assert "ACTION_REQUIRED" in reboot
    assert "cannot enable Auto-Logon" in inspect
    assert "[string]$Password" not in identity
    assert "-Password" not in identity
    assert "DefaultDomainName={0}" not in inspect
    assert "LIVE ORDER SENT: NO" in finalize
    assert "LIVE ORDER SENT: NO" in reboot
    assert "does not reboot" in reboot.lower()
    assert "Domain=." in verify or "Domain=." in reboot


def test_autologon_identity_never_uses_hostname_as_domain() -> None:
    host = _read("_host_recovery.ps1")
    start = host.index("function Get-LocalAutologonIdentity")
    end = host.index("# True when Winlogon DefaultDomainName")
    body = host[start:end]
    assert "$env:COMPUTERNAME" not in body
    assert "US-HOST-421124" not in body
    assert '$AutoLogonDomain = "."' in body
    assert "$env:USERDOMAIN" not in body
    assert "whoami" not in body
    assert "GetValue" not in body
    checker = host[
        host.index("function Test-IsIncorrectLocalAutologonDomain") : host.index(
            "function Test-AutologonDomainLooksLikeRejectedDnsHostname"
        )
    ]
    assert 'if ($Domain -eq ".") { return $false }' in checker
    assert "return $true" in checker




def test_provider_power_attestation_is_not_bios_detection() -> None:
    host = _read("_host_recovery.ps1")
    conf = _read("confirm_provider_power_recovery.ps1")
    assert "Get-ProviderPowerReadiness" in host
    assert "ProgramData" in host
    assert "IConfirmTheProviderIsConfigured" in conf
    assert "[string]$Password" not in conf
    assert "cannot be verified from inside Windows" in conf
    assert "BIOS" in conf
    assert "DefaultPassword" not in conf


def test_cloudflared_scm_hardener_is_token_safe() -> None:
    text = _read("harden_cloudflared_service.ps1")
    assert "Set-CloudflaredScmRestartOnFailure" in text
    assert "Start-Service" in text
    assert "does not place trades" in text.lower() or "never" in text.lower()
    assert "does not reboot" in text.lower()


def test_mt5_path_candidates_and_duplicate_guard() -> None:
    start = _read("start_mt5_terminal.ps1")
    host = _read("_host_recovery.ps1")
    assert "Meta Trader 5" in start
    assert "duplicate start prevented" in start
    assert "Resolve-Mt5TerminalPath" in host
    assert "Meta Trader 5" in host


def test_autologon_lsa_case_is_ready_without_winlogon_secret_name() -> None:
    host = _read("_host_recovery.ps1")
    assert 'SecretStorage = "lsa_or_external"' in host
    assert "NOT_SUPPORTED" in host
    assert '$result.State = "ERROR"' in host
    assert "GetValue(\"DefaultPassword\")" not in host
    assert "New-LocalUser" not in host
    assert "Get-LocalAdministratorState" in host


def test_finalize_unattended_reboot_never_takes_password_or_creates_users() -> None:
    text = _read("finalize_unattended_reboot.ps1")
    assert "SkipUi" in text
    assert "[string]$Password" not in text
    assert "[SecureString]" not in text
    assert "New-LocalUser" not in text
    assert "Administrator" in text
    assert "S4U" in text
    assert "LIVE ORDER SENT: NO" in text
    assert "open_autologon_ui.ps1" in text
    assert "Restart-Computer" not in text
    assert "-Password" not in text
