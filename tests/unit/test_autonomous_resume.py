"""Autonomous pause / resume (owner decision 2026-10-23).

The robot resumes by itself after a restart, a PC reboot, a safety pause or
a daily stop (next UTC day) only when every owner condition holds; an owner
Pause survives every restart until the owner presses Enable. Every auto-pause
and auto-resume sends an operator alert with the reason.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.services import live_trading_control_service as svc
from app.domain.institutional_trading import owner_live_limits as ol
from app.domain.institutional_trading.live_trading_control import (
    reset_live_trading_controller_for_tests,
)
from app.domain.institutional_trading.operations.models import OperatorIdentity

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

PRO_LOGIN = 50001234

OK_FACTS = {
    "gateway_online": True,
    "mt5_connected": True,
    "mt5_attached": True,
    "ownership": "OWNED",
    "account_available": True,
    "account_login": PRO_LOGIN,
    "equity": Decimal("32.88"),
    "balance": Decimal("32.88"),
}
DOWN_FACTS = {
    "gateway_online": False,
    "mt5_connected": False,
    "mt5_attached": False,
    "ownership": "NOT_OWNED",
}


class World:
    """Patchable live facts: probes, daily stop, positions, clock, alerts."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.facts = dict(OK_FACTS)
        self.plane = SimpleNamespace(
            daily_loss_exceeded=False,
            auto_trading_run_state="running",
            auto_trading_enabled=True,
        )
        self.unknown: list[str] | None = []
        self.now = datetime(2026, 10, 26, 10, 0, tzinfo=UTC)  # Monday, in session
        self.alerts: list[tuple[str, str]] = []
        self.persisted: list[dict] = []
        monkeypatch.setattr(svc, "_live_probe_facts", lambda **_k: dict(self.facts))
        monkeypatch.setattr(svc, "_unknown_positions", lambda: self.unknown)
        monkeypatch.setattr(
            "app.domain.institutional_trading.operations.control_plane"
            ".get_control_plane",
            lambda: self.plane,
        )
        monkeypatch.setattr(ol, "_now", lambda: self.now)
        monkeypatch.setattr(
            svc,
            "_notify_operator",
            lambda kind, text, *, key: self.alerts.append((kind, text)),  # noqa: ARG005
        )
        monkeypatch.setattr(
            svc,
            "persist_live_trading",
            lambda ctrl: self.persisted.append(ctrl.persist_payload()) or True,
        )
        monkeypatch.setenv("OWNER_APPROVED_MT5_LOGINS", str(PRO_LOGIN))
        svc._LAST_RESUME_BLOCKERS.clear()

    def kinds(self) -> list[str]:
        return [k for k, _t in self.alerts]


def _owner() -> OperatorIdentity:
    return OperatorIdentity(user_id=uuid4(), role="owner", display_name="Owner")


def _enabled():
    ctrl = reset_live_trading_controller_for_tests()
    ctrl.transition(_owner(), "ARMED", confirmed=True, reason="arm")
    ctrl.transition(_owner(), "ENABLED", confirmed=True, reason="enable")
    return ctrl


def _restart(payload: dict):
    ctrl = reset_live_trading_controller_for_tests()
    ctrl.hydrate(payload)
    return ctrl


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> World:
    return World(monkeypatch)


# (d) safety pause: gateway lost -> auto-pause, alert; back -> auto-resume, alert
def test_safety_pause_and_auto_resume_with_alerts(world: World) -> None:
    ctrl = _enabled()
    world.facts = dict(DOWN_FACTS)
    assert svc.apply_fail_closed_from_probes() == "PAUSED"
    assert ctrl.paused_for_safety and not ctrl.owner_paused
    assert world.kinds() == ["ROBOT AUTO-PAUSED"]
    assert "gateway_offline" in world.alerts[0][1]
    # Persisted while paused: durable authorization stays ENABLED.
    assert world.persisted[-1]["live_trading_state"] == "ENABLED"
    assert world.persisted[-1]["live_trading_runtime_state"] == "PAUSED"
    assert svc.resume_live_trading_after_safe_recovery() == "PAUSED"  # still down
    world.facts = dict(OK_FACTS)
    assert svc.resume_live_trading_after_safe_recovery() == "ENABLED"
    assert world.kinds()[-1] == "ROBOT AUTO-RESUMED"
    assert "gateway_offline" in world.alerts[-1][1]


# (b) Railway restart while ENABLED, and (c) PC reboot: restart while a safety
# pause was persisted -> both auto-resume once every check passes.
@pytest.mark.parametrize("paused_before_restart", [False, True])
def test_restart_auto_resumes(world: World, paused_before_restart: bool) -> None:
    ctrl = _enabled()
    if paused_before_restart:
        ctrl.safety_pause(reason="gateway_offline")
    payload = ctrl.persist_payload()
    assert payload["live_trading_state"] == "ENABLED"
    ctrl2 = _restart(payload)
    assert ctrl2.snapshot_state() == "PAUSED" and not ctrl2.owner_paused
    world.facts = dict(DOWN_FACTS)  # gateway / MT5 still starting
    assert svc.resume_live_trading_after_safe_recovery() == "PAUSED"
    world.facts = dict(OK_FACTS)
    assert svc.resume_live_trading_after_safe_recovery() == "ENABLED"
    assert ctrl2.research_can_execute() is True
    assert world.kinds()[-1] == "ROBOT AUTO-RESUMED"


# Owner Pause survives every restart until the owner presses Enable.
def test_owner_pause_survives_restarts_until_enable(world: World) -> None:
    ctrl = _enabled()
    ctrl.transition(_owner(), "PAUSED", confirmed=True, reason="owner pause")
    assert ctrl.owner_paused is True
    payload = ctrl.persist_payload()
    assert payload["live_trading_state"] == "PAUSED"
    assert payload["live_trading_owner_paused"] is True
    for _ in range(3):  # three restarts, all checks passing
        ctrl = _restart(payload)
        assert ctrl.owner_paused is True
        assert svc.resume_live_trading_after_safe_recovery() == "PAUSED"
        payload = ctrl.persist_payload()
    assert "ROBOT AUTO-RESUMED" not in world.kinds()
    assert ctrl.transition(_owner(), "ENABLED", confirmed=True, reason="enable")
    assert ctrl.owner_paused is False and ctrl.research_can_execute() is True


def test_owner_pause_wins_over_a_later_safety_pause(world: World) -> None:
    ctrl = _enabled()
    ctrl.transition(_owner(), "PAUSED", confirmed=True, reason="owner pause")
    ctrl.safety_pause(reason="gateway_offline")  # no-op: not ENABLED
    assert ctrl.owner_paused is True
    assert ctrl.persist_payload()["live_trading_state"] == "PAUSED"
    assert svc.resume_live_trading_after_safe_recovery() == "PAUSED"


def test_legacy_persisted_paused_is_treated_as_owner_pause(world: World) -> None:
    ctrl = _restart({"live_trading_state": "PAUSED"})
    assert ctrl.owner_paused is True
    assert svc.resume_live_trading_after_safe_recovery() == "PAUSED"


# Any other login: stay paused + alert; ENABLED on another login -> auto-pause.
def test_unapproved_login_stays_paused_and_alerts(world: World) -> None:
    ctrl = _restart(_enabled().persist_payload())
    world.facts = {**OK_FACTS, "account_login": 50009999}
    assert svc.resume_live_trading_after_safe_recovery() == "PAUSED"
    assert svc.resume_live_trading_after_safe_recovery() == "PAUSED"
    assert world.kinds() == ["ROBOT STAYS PAUSED"]  # alerted once, not every cycle
    assert "unapproved_login" in world.alerts[0][1]
    assert ctrl.research_can_execute() is False


def test_enabled_on_unapproved_login_auto_pauses(world: World) -> None:
    ctrl = _enabled()
    world.facts = {**OK_FACTS, "account_login": 50009999}
    assert svc.apply_fail_closed_from_probes() == "PAUSED"
    assert ctrl.safety_pause_reason == "unapproved_login"
    assert world.kinds() == ["ROBOT AUTO-PAUSED"]


# (a) 25% daily stop: no resume today; next UTC day the latch clears -> resume.
def test_daily_stop_blocks_resume_until_next_utc_day(world: World) -> None:
    ctrl = _restart(_enabled().persist_payload())
    world.plane.daily_loss_exceeded = True
    assert svc.resume_live_trading_after_safe_recovery() == "PAUSED"
    assert "daily_stop_hit" in svc.autonomous_resume_blockers(dict(OK_FACTS))
    world.plane.daily_loss_exceeded = False  # latch cleared on the new UTC day
    world.now = datetime(2026, 10, 27, 7, 0, tzinfo=UTC)
    assert svc.resume_live_trading_after_safe_recovery() == "ENABLED"
    assert ctrl.research_can_execute() is True


@pytest.mark.parametrize(
    ("unknown", "blocker"),
    [(["999"], "unknown_position"), (None, "positions_unverified")],
)
def test_positions_must_be_reconciled(world: World, unknown, blocker) -> None:
    _restart(_enabled().persist_payload())
    world.unknown = unknown
    assert svc.resume_live_trading_after_safe_recovery() == "PAUSED"
    assert blocker in svc.autonomous_resume_blockers(dict(OK_FACTS))
    world.unknown = []
    assert svc.resume_live_trading_after_safe_recovery() == "ENABLED"


def test_resume_waits_for_the_session(world: World) -> None:
    _restart(_enabled().persist_payload())
    world.now = datetime(2026, 10, 26, 18, 30, tzinfo=UTC)
    assert svc.resume_live_trading_after_safe_recovery() == "PAUSED"
    assert "outside_session" in svc.autonomous_resume_blockers(dict(OK_FACTS))
    world.now = datetime(2026, 10, 27, 7, 0, tzinfo=UTC)
    assert svc.resume_live_trading_after_safe_recovery() == "ENABLED"


@pytest.mark.parametrize(
    ("override", "blocker"),
    [
        ({"equity": None}, "equity_unavailable"),
        ({"gateway_online": False}, "gateway_offline"),
        ({"mt5_connected": False}, "mt5_disconnected"),
        ({"ownership": "NOT_OWNED"}, "broker_ownership_failure"),
    ],
)
def test_each_health_condition_blocks_resume(world: World, override, blocker) -> None:
    _restart(_enabled().persist_payload())
    world.facts = {**OK_FACTS, **override}
    assert svc.resume_live_trading_after_safe_recovery() == "PAUSED"
    assert blocker in svc.autonomous_resume_blockers(world.facts)


def test_without_an_allowlist_ownership_is_the_approval(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OWNER_APPROVED_MT5_LOGINS", raising=False)
    assert svc.approved_mt5_logins() == frozenset()
    _restart(_enabled().persist_payload())
    world.facts = {**OK_FACTS, "account_login": 555}
    assert svc.resume_live_trading_after_safe_recovery() == "ENABLED"
