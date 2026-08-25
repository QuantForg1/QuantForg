"""Honest 24/7 topology facts. Python cannot host MetaTrader on Linux Railway.

Do not claim the user Windows PC may be OFF until MT5 + Gateway run on an
always-on Windows trading host independent of that PC.
"""

from __future__ import annotations

from typing import Any

# Railway (Linux): QuantForg API + ITE worker. Always-on while the service is up.
CLOUD_COMPONENTS = (
    "quantforg_api",
    "ite_worker",
    "scheduler",
)

# Today these MUST run on an always-on Windows trading host (intended: Windows VPS).
# Cutover is operator-executed. This module does not inspect any VPS.
USER_WINDOWS_COMPONENTS = (
    "mt5_terminal",
    "mt5_gateway",
    "broker_login_session",
)

# Broker connectivity is whatever the MT5 terminal has — not the user's browser.
BROKER_PATH_FOLLOWS_MT5_HOST = True

USER_WINDOWS_PC_MAY_BE_OFF = False
MT5_CLOUD_VPS_MIGRATION_REQUIRED = True
VPS_DEPLOYMENT_AUTOMATION_IN_REPO = True

RECOMMENDED_ALWAYS_ON_HOST = (
    "Dedicated Windows Server / Windows VPS (always-on) running "
    "MetaTrader 5 terminal + QuantForg MT5 Gateway, with the existing "
    "Railway worker pointing MT5_GATEWAY_BASE_URL at that host "
    "(direct private URL or dedicated tunnel). Host choice must be "
    "approved before any production migration."
)


def topology_snapshot() -> dict[str, Any]:
    return {
        "user_windows_pc_may_be_off": USER_WINDOWS_PC_MAY_BE_OFF,
        "mt5_cloud_vps_migration_required": MT5_CLOUD_VPS_MIGRATION_REQUIRED,
        "cloud_components": list(CLOUD_COMPONENTS),
        "user_windows_components": list(USER_WINDOWS_COMPONENTS),
        "broker_path_follows_mt5_host": BROKER_PATH_FOLLOWS_MT5_HOST,
        "works_without_user_browser": True,
        "works_without_user_pc": False,
        "works_without_internet_on_mt5_host": False,
        "recommended_always_on_host": RECOMMENDED_ALWAYS_ON_HOST,
        "migration_executed": False,
        "vps_deployment_automation_in_repo": VPS_DEPLOYMENT_AUTOMATION_IN_REPO,
        "vps_cutover_requires_human": True,
    }
