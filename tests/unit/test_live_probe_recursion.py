"""Live probe re-entry (production incident 2026-10-26).

While ENABLED with OWNER_APPROVED_MT5_LOGINS set, every cycle ran
apply_fail_closed_from_probes -> _live_probe_facts -> build_auto_trading_status
-> plane.evaluate_auto_trading -> apply_fail_closed_from_probes -> ... until
"maximum recursion depth exceeded". The probe must never re-enter itself, the
approved-login check must still see the real login, and a probe that failed
during a gateway outage must work again on the next call.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.services import (
    auto_trading_status as ats,
    live_trading_control_service as svc,
)
from app.domain.institutional_trading import owner_live_limits as ol
from app.domain.institutional_trading.auto_trading import AutoTradeLiveFacts
from app.domain.institutional_trading.live_trading_control import (
    reset_live_trading_controller_for_tests,
)
from app.domain.institutional_trading.operations.models import OperatorIdentity

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

PRO_LOGIN = 50001234
OTHER_LOGIN = 50009999


def _facts(*, up: bool) -> AutoTradeLiveFacts:
    return AutoTradeLiveFacts(
        gateway_connected=up,
        broker_connected=up,
        market_data_live=up,
        execution_enabled=True,
        ops_mode="LIVE",
        emergency_stop=False,
        session="london",
        session_evaluated=True,
        spread=Decimal("0.20"),
        spread_evaluated=True,
        news_blocked=False,
        account_trading_enabled=True,
        mt5_autotrading_enabled=True,
        account_flags_evaluated=True,
        symbol_tradable=True,
        no_broker_restrictions=True,
        margin_available=True,
        margin_evaluated=True,
        risk_engine_pass=True,
        risk_engine_evaluated=True,
        symbol="XAUUSD",
    )


class Gateway:
    """The real status builder and control plane over a fake gateway."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        monkeypatch.setenv("QUANTFORG_OPS_STATE_PATH", str(tmp_path / "ops.json"))
        # Build the plane first: its first creation hydrates the controller.
        from app.domain.institutional_trading.operations.control_plane import (
            get_control_plane,
        )

        get_control_plane()
        svc._LAST_GOOD_PROBE.clear()
        self.up = True
        self.login = PRO_LOGIN
        self.status_builds = 0
        self.alerts: list[str] = []
        monkeypatch.setenv("OWNER_APPROVED_MT5_LOGINS", str(PRO_LOGIN))
        monkeypatch.setattr(ats, "build_status_facts", self._build_status_facts)
        monkeypatch.setattr(svc, "_unknown_positions", lambda: [])
        monkeypatch.setattr(svc, "persist_live_trading", lambda _ctrl=None: True)
        monkeypatch.setattr(
            svc,
            "_notify_operator",
            lambda kind, text, *, key: self.alerts.append(kind),  # noqa: ARG005
        )
        monkeypatch.setattr(
            ol,
            "_now",
            lambda: datetime(2026, 10, 26, 10, 0, tzinfo=UTC),  # Monday, in session
        )
        ats.reset_auto_trading_status_cache()
        svc._LAST_RESUME_BLOCKERS.clear()

    def _build_status_facts(self, plane, *, settings=None):
        self.status_builds += 1
        live = {
            "health_payload": {
                "mt5": {
                    "session_mode": "attached" if self.up else "",
                    "connected": self.up,
                    "login": self.login if self.up else None,
                    "server": "Weltrade-Real",
                    "account": {
                        "login": self.login if self.up else None,
                        "equity": "27.88" if self.up else None,
                        "balance": "27.88" if self.up else None,
                    },
                }
            }
        }
        return _facts(up=self.up), live


@pytest.fixture
def gw(monkeypatch: pytest.MonkeyPatch, tmp_path) -> Gateway:
    return Gateway(monkeypatch, tmp_path)


def _owner() -> OperatorIdentity:
    return OperatorIdentity(user_id=uuid4(), role="owner", display_name="Owner")


def _enabled():
    ctrl = reset_live_trading_controller_for_tests()
    ctrl.transition(_owner(), "ARMED", confirmed=True, reason="arm")
    ctrl.transition(_owner(), "ENABLED", confirmed=True, reason="enable")
    return ctrl


def test_enabled_cycle_check_does_not_recurse(gw: Gateway, monkeypatch) -> None:
    _enabled()
    warnings: list[str] = []
    monkeypatch.setattr(
        svc.logger, "warning", lambda event, **_kw: warnings.append(event)
    )
    # The ITE cycle passes its own facts; the login check used to re-probe.
    state = svc.apply_fail_closed_from_probes(
        gateway_online=True, mt5_connected=True, mt5_attached=True
    )
    assert state == "ENABLED"
    assert "live_trading_probe_failed" not in warnings
    assert gw.status_builds <= 2


def test_probe_while_enabled_returns_real_login(gw: Gateway) -> None:
    _enabled()
    facts = svc._live_probe_facts(enrich_account=False)
    assert facts.get("probe_error") is None
    assert facts["gateway_online"] is True
    assert facts["account_login"] == PRO_LOGIN


def test_unapproved_login_still_pauses_while_enabled(gw: Gateway) -> None:
    ctrl = _enabled()
    gw.login = OTHER_LOGIN
    state = svc.apply_fail_closed_from_probes(
        gateway_online=True, mt5_connected=True, mt5_attached=True
    )
    assert state == "PAUSED"
    assert ctrl.paused_for_safety and ctrl.safety_pause_reason == "unapproved_login"


def test_start_inside_session_after_restart(gw: Gateway) -> None:
    ctrl = _enabled()
    payload = ctrl.persist_payload()
    ctrl2 = reset_live_trading_controller_for_tests()
    ctrl2.hydrate(payload)
    assert ctrl2.snapshot_state() == "PAUSED" and not ctrl2.owner_paused
    assert svc.resume_live_trading_after_safe_recovery() == "ENABLED"
    assert gw.alerts == ["ROBOT AUTO-RESUMED"]
    # Next cycles while ENABLED: no recursion, stays ENABLED.
    for _ in range(3):
        ats.reset_auto_trading_status_cache()
        assert (
            svc.apply_fail_closed_from_probes(
                gateway_online=True, mt5_connected=True, mt5_attached=True
            )
            == "ENABLED"
        )


def test_resume_by_itself_after_gateway_outage(gw: Gateway) -> None:
    ctrl = _enabled()
    gw.up = False
    ats.reset_auto_trading_status_cache()
    assert svc.apply_fail_closed_from_probes() == "PAUSED"
    assert ctrl.safety_pause_reason == "gateway_offline"
    ats.reset_auto_trading_status_cache()
    assert svc.resume_live_trading_after_safe_recovery() == "PAUSED"  # still down
    gw.up = True
    ats.reset_auto_trading_status_cache()
    assert svc.resume_live_trading_after_safe_recovery() == "ENABLED"
    assert gw.alerts == ["ROBOT AUTO-PAUSED", "ROBOT AUTO-RESUMED"]
    ats.reset_auto_trading_status_cache()
    assert svc._live_probe_facts().get("probe_error") is None


def test_probe_reentry_on_same_thread_is_short_circuited(gw: Gateway) -> None:
    _enabled()
    seen: list[dict] = []
    real_build = gw._build_status_facts

    def nested_build(plane, *, settings=None):
        # A status build that probes again (any re-entrant caller).
        seen.append(svc._live_probe_facts(enrich_account=False))
        return real_build(plane, settings=settings)

    ats.build_status_facts = nested_build
    try:
        facts = svc._live_probe_facts(enrich_account=False)
    finally:
        ats.build_status_facts = gw._build_status_facts
    assert facts.get("probe_error") is None
    assert len(seen) == 1 and seen[0].get("probe_reentrant") is True
