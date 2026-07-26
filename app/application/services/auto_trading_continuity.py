"""Keep Auto Trading continuously RUNNING when launch locks pass.

Never leave the desk in PAUSED after Railway restart or a false frontend pause.
Real kill-switch / daily-loss locks still block NEW trades via the safety gate
without requiring a manual Resume click.
"""

from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

# States that must auto-promote to running when locks pass.
_RESUMABLE = frozenset({"paused", "stopped", "off"})


def launch_locks_pass(plane: Any, *, settings: Any | None = None) -> tuple[bool, str]:
    """Return (ok, reason) for continuous auto-trading resume."""
    mode = str(getattr(getattr(plane, "mode", None), "value", "") or "")
    if mode not in {"LIVE", "CANARY"}:
        return False, f"ops_mode={mode or 'unknown'} required=LIVE|CANARY"
    if bool(getattr(plane, "kill_switch_armed", False)):
        return False, "kill_switch_armed=true required=false"
    if bool(getattr(plane, "daily_loss_exceeded", False)):
        try:
            from app.domain.institutional_trading.risk_lock_override import (
                risk_lock_override_enabled,
            )

            if not risk_lock_override_enabled(settings):
                return False, "daily_loss_exceeded=true required=false"
        except Exception:
            return False, "daily_loss_exceeded=true required=false"
    exec_on = True
    if settings is not None:
        exec_on = bool(getattr(settings, "execution_enabled", False))
    else:
        try:
            from core.config.settings import get_settings

            exec_on = bool(getattr(get_settings(), "execution_enabled", False))
        except Exception:
            exec_on = False
    if not exec_on:
        return False, "EXECUTION_ENABLED=false required=true"
    return True, "launch_locks_pass"


def ensure_auto_trading_running(
    plane: Any,
    *,
    settings: Any | None = None,
    reason: str = "auto_resume_continuous",
) -> dict[str, Any]:
    """If locks pass and run_state is paused/stopped/off → RUNNING + persist.

    Returns a small diagnostic dict for logs / API.
    """
    before = str(getattr(plane, "auto_trading_run_state", "off") or "off")
    ok, lock_reason = launch_locks_pass(plane, settings=settings)
    if not ok:
        logger.warning(
            "auto_trading_resume_blocked",
            current_run_state=before,
            reason=lock_reason,
        )
        return {
            "changed": False,
            "run_state": before,
            "resumed": False,
            "reason": lock_reason,
        }
    if before == "running" and bool(getattr(plane, "auto_trading_enabled", False)):
        return {
            "changed": False,
            "run_state": "running",
            "resumed": False,
            "reason": "already_running",
        }

    with plane._lock:
        plane.auto_trading_run_state = "running"
        plane.auto_trading_enabled = True
    after = "running"
    logger.warning(
        "auto_trading_auto_resumed",
        previous=before,
        run_state=after,
        reason=reason,
        lock_detail=lock_reason,
    )
    try:
        from app.application.services.ops_state_persistence import save_ops_state

        save_ops_state(
            {
                "auto_trading_enabled": True,
                "auto_trading_run_state": "running",
            }
        )
    except Exception as exc:
        logger.warning("auto_trading_resume_persist_failed", error=str(exc))
    try:
        from uuid import uuid4

        from app.domain.institutional_trading.operations.models import OperatorIdentity

        plane.audit.record(
            operator=OperatorIdentity(
                user_id=uuid4(),
                role="owner",
                display_name="system:auto_resume",
            ),
            action="auto_trading_auto_resume",
            old_value=before,
            new_value=after,
            reason=reason,
        )
    except Exception:
        logger.exception("auto_trading_resume_audit_failed")
    return {
        "changed": before != after,
        "run_state": after,
        "previous": before,
        "resumed": True,
        "reason": reason,
    }
