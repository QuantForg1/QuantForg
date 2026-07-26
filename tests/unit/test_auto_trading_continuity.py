"""Auto Trading continuity — never strand PAUSED when locks pass."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.application.services.auto_trading_continuity import (
    ensure_auto_trading_running,
    launch_locks_pass,
)
from app.domain.institutional_trading.operations.control_plane import (
    OperationsControlPlane,
)
from app.domain.institutional_trading.operations.models import OpsExecutionMode


@pytest.mark.unit
def test_launch_locks_require_live_and_execution() -> None:
    plane = OperationsControlPlane()
    plane.mode = OpsExecutionMode.SHADOW
    ok, reason = launch_locks_pass(
        plane, settings=SimpleNamespace(execution_enabled=True)
    )
    assert ok is False
    assert "ops_mode" in reason

    plane.mode = OpsExecutionMode.LIVE
    ok, reason = launch_locks_pass(
        plane, settings=SimpleNamespace(execution_enabled=False)
    )
    assert ok is False
    assert "EXECUTION_ENABLED" in reason


@pytest.mark.unit
def test_ensure_auto_trading_running_promotes_paused() -> None:
    plane = OperationsControlPlane()
    plane.mode = OpsExecutionMode.LIVE
    plane.auto_trading_run_state = "paused"
    plane.auto_trading_enabled = True
    plane.kill_switch_armed = False
    plane.daily_loss_exceeded = False
    plane.audit.record = lambda **_: None  # type: ignore[method-assign]

    result = ensure_auto_trading_running(
        plane,
        settings=SimpleNamespace(execution_enabled=True),
        reason="unit_test",
    )
    assert result["resumed"] is True
    assert plane.auto_trading_run_state == "running"
    assert plane.auto_trading_enabled is True


@pytest.mark.unit
def test_ensure_does_not_resume_when_kill_armed() -> None:
    plane = OperationsControlPlane()
    plane.mode = OpsExecutionMode.LIVE
    plane.auto_trading_run_state = "paused"
    plane.kill_switch_armed = True
    result = ensure_auto_trading_running(
        plane,
        settings=SimpleNamespace(execution_enabled=True),
    )
    assert result["resumed"] is False
    assert plane.auto_trading_run_state == "paused"
