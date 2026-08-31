"""Read-only VPS / execution-chain continuity classifier.

Never reboots Windows, MT5, Gateway, Cloudflared, or Railway.
MT5 session recovery after reboot stays UNPROVEN until separately verified.
"""

from __future__ import annotations

from typing import Any

from app.infrastructure.brokers.mt5.deployment_topology import (
    MT5_SESSION_RECOVERY_UNPROVEN,
    topology_snapshot,
)

PROCESS_RUNNING = "PROCESS_RUNNING"
TERMINAL_CONNECTED = "TERMINAL_CONNECTED"
BROKER_CONNECTED = "BROKER_CONNECTED"
AUTOTRADING_ENABLED = "AUTOTRADING_ENABLED"
EXECUTION_PATH_READY = "EXECUTION_PATH_READY"
SESSION_VERIFIED = "SESSION_VERIFIED"
MT5_RECOVERY = "MT5_SESSION_RECOVERY_UNPROVEN"


def classify_gateway_listeners(listener_count: int) -> str:
    if listener_count <= 0:
        return "NO_LISTENER"
    if listener_count == 1:
        return "SINGLE_LISTENER"
    return "DUPLICATE_LISTENERS"


def classify_vps_continuity(facts: dict[str, Any] | None = None) -> dict[str, Any]:
    """Map observed process/session facts. Missing live facts stay unproven."""
    row = dict(facts or {})
    topo = topology_snapshot()
    listeners = int(row.get("gateway_listeners") or 0)
    listener_class = classify_gateway_listeners(listeners)
    process_running = bool(row.get("gateway_process_running") or listeners == 1)
    terminal = bool(row.get("terminal_connected"))
    broker = bool(row.get("broker_connected"))
    autotrading = bool(row.get("autotrading_enabled"))
    data_fresh = bool(row.get("market_data_fresh"))
    session_verified = bool(row.get("session_verified")) and broker and terminal
    ready = bool(
        process_running
        and terminal
        and broker
        and autotrading
        and data_fresh
        and listener_class == "SINGLE_LISTENER"
        and session_verified
    )
    recovery = MT5_RECOVERY if MT5_SESSION_RECOVERY_UNPROVEN else "PROVEN"
    autonomy = "NOT_FULLY_AUTONOMOUS"
    if ready and recovery != MT5_RECOVERY:
        autonomy = "AUTONOMOUS_IF_SESSION_RECOVERY_PROVEN"
    elif process_running and listener_class == "SINGLE_LISTENER":
        autonomy = "HOST_ALIVE_SESSION_RECOVERY_UNPROVEN"
    return {
        "advisory_only": True,
        "never_reboots": True,
        "PROCESS_RUNNING": PROCESS_RUNNING if process_running else "NOT_RUNNING",
        "TERMINAL_CONNECTED": TERMINAL_CONNECTED if terminal else "NOT_CONNECTED",
        "BROKER_CONNECTED": BROKER_CONNECTED if broker else "NOT_CONNECTED",
        "AUTOTRADING_ENABLED": AUTOTRADING_ENABLED if autotrading else "NOT_ENABLED",
        "EXECUTION_PATH_READY": EXECUTION_PATH_READY if ready else "NOT_READY",
        "SESSION_VERIFIED": SESSION_VERIFIED if session_verified else "SESSION_UNVERIFIED",
        "gateway_listeners": listeners,
        "gateway_listener_class": listener_class,
        "orphan_gateway_processes": int(row.get("orphan_gateway_processes") or 0),
        "watchdog": row.get("watchdog") or "UNKNOWN",
        "cloudflared": row.get("cloudflared") or "UNKNOWN",
        "decision_hash_persistence": row.get("decision_hash_persistence") or "UNKNOWN",
        "duplicate_order_prevention": row.get("duplicate_order_prevention") or "ENABLED_CONTRACT",
        "blind_retry": "DISABLED",
        "mt5_reboot_recovery": recovery,
        "vps_autonomy_status": autonomy,
        "owner_pc_required": False,
        "owner_wifi_required": False,
        "browser_required": False,
        "windows_vps_required": True,
        "topology": {
            "mt5_session_recovery": topo.get("mt5_session_recovery"),
            "execution_path_ready_requires": topo.get("execution_path_ready_requires"),
            "running_terminal_is_not_execution_ready": topo.get(
                "running_terminal_is_not_execution_ready"
            ),
        },
        "live_probe_performed": bool(row.get("live_probe_performed")),
        "note": (
            "A running terminal64.exe is not EXECUTION_PATH_READY. "
            "Reboot survival is MT5_SESSION_RECOVERY_UNPROVEN until proven."
        ),
    }
