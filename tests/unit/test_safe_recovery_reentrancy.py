"""Restart-PAUSED safe recovery must not recurse.

Production 2026-10-22 17:08Z (a0a68230 boot): ``live_trading_probe_failed
maximum recursion depth exceeded``. evaluate_auto_trading -> safe recovery ->
_live_probe_facts -> build_auto_trading_status -> evaluate_auto_trading -> ...
"""

from __future__ import annotations

from typing import Any

import pytest

import app.application.services.live_trading_control_service as svc
from app.domain.institutional_trading.live_trading_control import (
    reset_live_trading_controller_for_tests,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def test_reentrant_recovery_probes_once(monkeypatch: pytest.MonkeyPatch) -> None:
    ctrl = reset_live_trading_controller_for_tests()
    assert ctrl.hydrate({"live_trading_state": "ENABLED"}, persist_recovery=False) == (
        "PAUSED"
    )
    calls: list[int] = []

    def probe(*, enrich_account: bool = False) -> dict[str, Any]:
        calls.append(1)
        # The real probe re-enters via build_auto_trading_status.
        svc.resume_live_trading_after_safe_recovery()
        return {}

    monkeypatch.setattr(svc, "_live_probe_facts", probe)
    state = svc.resume_live_trading_after_safe_recovery()
    assert calls == [1]
    # Empty facts fail the activation probes: stays PAUSED, never auto-enables.
    assert state == "PAUSED"
    reset_live_trading_controller_for_tests()


def test_guard_is_released_after_each_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    ctrl = reset_live_trading_controller_for_tests()
    ctrl.hydrate({"live_trading_state": "ENABLED"}, persist_recovery=False)
    calls: list[int] = []

    def probe(*, enrich_account: bool = False) -> dict[str, Any]:
        calls.append(1)
        return {}

    monkeypatch.setattr(svc, "_live_probe_facts", probe)
    svc.resume_live_trading_after_safe_recovery()
    svc.resume_live_trading_after_safe_recovery()
    assert calls == [1, 1]
    reset_live_trading_controller_for_tests()
