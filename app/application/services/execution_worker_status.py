"""Read-only execution-worker / live-trading continuity diagnostics.

Never enables trading. Never calls order_send. Surfaces why continuous
auto-trading may be blocked despite EXECUTION_ENABLED=true.
"""

from __future__ import annotations

from typing import Any

from core.config.settings import Settings, get_settings
from core.logging import get_logger

logger = get_logger(__name__)


def collect_execution_worker_status(
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Snapshot ITE worker, live-trading gate, and dependency blockers."""
    settings = settings or get_settings()
    payload: dict[str, Any] = {
        "status": "ok",
        "execution_enabled": bool(settings.execution_enabled),
        "worker": {
            "present": False,
            "running": False,
            "watchdog_state": "UNKNOWN",
            "watchdog_restarts": 0,
            "auto_trading_run_state": "unknown",
            "ops_mode": "unknown",
            "heartbeat": None,
        },
        "live_trading": {
            "state": "DISABLED",
            "orders_may_submit": False,
            "recovered_from_enabled": False,
            "paused_for_safety": False,
            "blocker": "live_trading_controller_unavailable",
        },
        "openai": {
            "configured": False,
            "enabled": False,
            "status": "unknown",
            "detail": "",
            "degraded": False,
            "authorizes_trade": False,
            "gemini": False,
        },
        "orders_path_healthy": False,
        "continuous_trading_authorized": False,
        "blockers": [],
    }
    blockers: list[str] = []

    if not settings.execution_enabled:
        blockers.append("EXECUTION_ENABLED=false")

    # --- ITE / control plane -------------------------------------------------
    try:
        from app.domain.institutional_trading.operations.control_plane import (
            get_control_plane,
        )
        from core.di.container import get_container

        plane = get_control_plane()
        runtime = None
        try:
            runtime = getattr(get_container(), "ite_runtime", None)
        except Exception:
            runtime = None

        run_state = str(getattr(plane, "auto_trading_run_state", "off") or "off")
        ops_mode = str(getattr(getattr(plane, "mode", None), "value", "") or "")
        watchdog_state = "IDLE"
        restarts = 0
        if runtime is not None:
            watchdog_state = str(
                getattr(runtime, "_watchdog_state", "UNKNOWN") or "UNKNOWN"
            )
            restarts = int(getattr(runtime, "_watchdog_restarts", 0) or 0)
        worker_running = (
            runtime is not None
            and watchdog_state in {"RUNNING", "BACKOFF"}
            and run_state == "running"
        )
        payload["worker"] = {
            "present": runtime is not None,
            "running": worker_running,
            "watchdog_state": watchdog_state,
            "watchdog_restarts": restarts,
            "auto_trading_run_state": run_state,
            "ops_mode": ops_mode or "unknown",
            "auto_trading_enabled": bool(getattr(plane, "auto_trading_enabled", False)),
            "kill_switch_armed": bool(getattr(plane, "kill_switch_armed", False)),
            "daily_loss_exceeded": bool(getattr(plane, "daily_loss_exceeded", False)),
            "heartbeat": None,
        }
        if runtime is None:
            blockers.append("ite_runtime_absent")
        elif not worker_running:
            blockers.append(
                f"ite_worker_not_running watchdog={watchdog_state} "
                f"run_state={run_state}"
            )
        if ops_mode and ops_mode not in {"LIVE", "CANARY"}:
            blockers.append(f"ops_mode={ops_mode} required=LIVE|CANARY")
        if bool(getattr(plane, "kill_switch_armed", False)):
            blockers.append("kill_switch_armed")
        if bool(getattr(plane, "daily_loss_exceeded", False)):
            blockers.append("daily_loss_exceeded")

        try:
            from app.domain.institutional_trading.operations import (
                infrastructure_heartbeats as _qf_infrastructure_heartbeats,
            )

            RAILWAY_ITE_HEARTBEAT = _qf_infrastructure_heartbeats.RAILWAY_ITE_HEARTBEAT
            heartbeat_snapshot = _qf_infrastructure_heartbeats.heartbeat_snapshot

            snap = heartbeat_snapshot()
            beats = snap.get("heartbeats") if isinstance(snap, dict) else None
            hb = beats.get(RAILWAY_ITE_HEARTBEAT) if isinstance(beats, dict) else None
            if hb is not None:
                payload["worker"]["heartbeat"] = hb
        except Exception:
            logger.debug("execution_worker_heartbeat_snapshot_failed", exc_info=True)
    except Exception as exc:
        blockers.append("control_plane_unavailable")
        logger.warning("execution_worker_plane_probe_failed", error=type(exc).__name__)

    # --- Live trading authorization (separate from EXECUTION_ENABLED) --------
    try:
        from app.domain.institutional_trading.live_trading_control import (
            get_live_trading_controller,
            orders_may_submit,
        )

        ctrl = get_live_trading_controller()
        state = ctrl.snapshot_state()
        may_submit = orders_may_submit(state)
        blocker = ""
        if not may_submit:
            if state == "DISABLED":
                blocker = (
                    "live_trading_state=DISABLED — operator must ARM then ENABLE "
                    "(EXECUTION_ENABLED alone does not authorize orders)"
                )
            elif state == "PAUSED":
                if ctrl.recovered_from_enabled or ctrl.paused_for_safety:
                    blocker = (
                        "live_trading_state=PAUSED (safety/restart) — waiting for "
                        "gateway/MT5 ownership probes to auto-resume"
                    )
                else:
                    blocker = (
                        "live_trading_state=PAUSED (operator) — explicit resume "
                        "required"
                    )
            elif state == "ARMED":
                blocker = "live_trading_state=ARMED — ENABLE required before orders"
            elif state == "KILLED":
                blocker = "live_trading_state=KILLED — emergency stop latched"
            else:
                blocker = f"live_trading_state={state} — orders blocked"
            blockers.append(blocker)
        payload["live_trading"] = {
            "state": state,
            "orders_may_submit": may_submit,
            "recovered_from_enabled": bool(ctrl.recovered_from_enabled),
            "paused_for_safety": bool(ctrl.paused_for_safety),
            "emergency_latched": bool(ctrl.emergency_latched),
            "blocker": blocker or None,
        }
    except Exception as exc:
        blockers.append("live_trading_controller_unavailable")
        logger.warning(
            "execution_worker_live_trading_probe_failed",
            error=type(exc).__name__,
        )

    # --- OpenAI advisory (never authorizes) ---------------------------------
    try:
        from app.application.services.openai_advisor_service import (
            build_openai_advisor_from_settings,
            last_openai_provider_error,
        )

        st = build_openai_advisor_from_settings(settings).provider_status().to_dict()
        last_err = last_openai_provider_error()
        err_code = last_err.get("code") if last_err is not None else None
        degraded = err_code in {
            "insufficient_quota",
            "rate_limited",
            "auth_failed",
            "provider_outage",
        }
        if degraded:
            blockers.append(
                f"openai_degraded code={err_code} "
                "(advisory only — does not block OMS)"
            )
        payload["openai"] = {
            **st,
            "degraded": degraded,
            "last_error_code": (last_err or {}).get("code"),
            "last_error_detail": (last_err or {}).get("detail"),
        }
    except Exception:
        payload["openai"]["status"] = "unavailable"

    authorized = bool(payload["live_trading"].get("orders_may_submit"))
    worker_ok = bool(payload["worker"].get("running"))
    exec_on = bool(payload["execution_enabled"])
    payload["continuous_trading_authorized"] = authorized and worker_ok and exec_on
    payload["orders_path_healthy"] = exec_on and worker_ok
    # OpenAI degradation is advisory — strip from hard blockers for path health.
    hard = [b for b in blockers if not str(b).startswith("openai_degraded")]
    payload["blockers"] = hard
    payload["advisory_blockers"] = [b for b in blockers if b not in hard]
    if hard:
        payload["status"] = "blocked"
    elif payload["openai"].get("degraded"):
        payload["status"] = "degraded"
    else:
        payload["status"] = "ok"

    # --- Activation workflow (observe-only; never ARM/ENABLE) ----------------
    payload["activation_workflow"] = {
        "steps": [
            "Verify EXECUTION_ENABLED=true and gateway/MT5 ownership probes",
            "OWNER/ADMIN POST /live-trading/arm with confirmation phrase",
            "OWNER/ADMIN POST /live-trading/enable with confirmation phrase",
            "Confirm live_trading.state=ENABLED and orders_may_submit=true",
        ],
        "confirmation_phrase": "I UNDERSTAND THIS USES REAL MONEY",
        "current_blocker": payload["live_trading"].get("blocker"),
        "auto_enable_on_deploy": False,
        "openai_can_enable": False,
        "unified_brain_can_enable": False,
    }

    if hard and exec_on:
        logger.warning(
            "continuous_trading_blocked",
            blockers=hard[:8],
            live_trading_state=payload["live_trading"].get("state"),
            worker_running=worker_ok,
        )
    return payload
