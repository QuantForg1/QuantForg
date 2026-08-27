"""Honest 24/7 topology facts. Python cannot host MetaTrader on Linux Railway.

Owner home PC / home Wi-Fi / browser are not on the execution path.
MT5 + Gateway run on the Windows VPS. Broker session recovery after a
VPS reboot is UNPROVEN — a running terminal64.exe is not EXECUTION_PATH_READY.
"""

from __future__ import annotations

from typing import Any

# Railway (Linux): QuantForg API + ITE worker. Always-on while the service is up.
CLOUD_COMPONENTS = (
    "quantforg_api",
    "ite_worker",
    "scheduler",
)

# These MUST run on the always-on Windows trading host (production VPS).
USER_WINDOWS_COMPONENTS = (
    "mt5_terminal",
    "mt5_gateway",
    "broker_login_session",
)

# Broker connectivity is whatever the MT5 terminal has — not the user's browser.
BROKER_PATH_FOLLOWS_MT5_HOST = True

# Owner's personal PC may be off. The Windows VPS must stay on.
USER_WINDOWS_PC_MAY_BE_OFF = True
OWNER_HOME_PC_REQUIRED = False
OWNER_WIFI_REQUIRED = False
BROWSER_REQUIRED = False
WINDOWS_VPS_REQUIRED = True

# Cutover to us-host-421124 is executed. Reboot→broker-login is not proven.
MT5_CLOUD_VPS_MIGRATION_REQUIRED = False
VPS_DEPLOYMENT_AUTOMATION_IN_REPO = True
MT5_SESSION_RECOVERY_UNPROVEN = True

RECOMMENDED_ALWAYS_ON_HOST = (
    "Dedicated Windows Server / Windows VPS (always-on) running "
    "MetaTrader 5 terminal + QuantForg MT5 Gateway, with the existing "
    "Railway worker pointing MT5_GATEWAY_BASE_URL at that host "
    "(direct private URL or dedicated tunnel)."
)


def topology_snapshot() -> dict[str, Any]:
    return {
        "user_windows_pc_may_be_off": USER_WINDOWS_PC_MAY_BE_OFF,
        "owner_home_pc_required": OWNER_HOME_PC_REQUIRED,
        "owner_wifi_required": OWNER_WIFI_REQUIRED,
        "browser_required": BROWSER_REQUIRED,
        "windows_vps_required": WINDOWS_VPS_REQUIRED,
        "mt5_cloud_vps_migration_required": MT5_CLOUD_VPS_MIGRATION_REQUIRED,
        "cloud_components": list(CLOUD_COMPONENTS),
        "user_windows_components": list(USER_WINDOWS_COMPONENTS),
        "broker_path_follows_mt5_host": BROKER_PATH_FOLLOWS_MT5_HOST,
        "works_without_user_browser": True,
        "works_without_user_pc": True,
        "works_without_owner_wifi": True,
        "works_without_internet_on_mt5_host": False,
        "recommended_always_on_host": RECOMMENDED_ALWAYS_ON_HOST,
        "migration_executed": True,
        "vps_deployment_automation_in_repo": VPS_DEPLOYMENT_AUTOMATION_IN_REPO,
        "vps_cutover_requires_human": False,
        "mt5_session_recovery_unproven": MT5_SESSION_RECOVERY_UNPROVEN,
        "mt5_session_recovery": "MT5_SESSION_RECOVERY_UNPROVEN",
        "execution_path_ready_requires": (
            "PROCESS_RUNNING",
            "TERMINAL_CONNECTED",
            "BROKER_CONNECTED",
            "AUTOTRADING_ENABLED",
            "MARKET_DATA_FRESH",
        ),
        "running_terminal_is_not_execution_ready": True,
    }
