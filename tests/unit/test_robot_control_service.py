"""Account-scoped robot controls: ownership, transitions, enforcement."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.application.services import robot_control_service as rc

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


class FakeDB:
    """In-memory stand-in for direct_postgres (fetch / execute_transaction)."""

    def __init__(self) -> None:
        self.accounts: dict[str, dict[str, Any]] = {}
        self.controls: dict[str, dict[str, Any]] = {}
        self.events: list[dict[str, Any]] = []
        self.fail = False

    def add_account(self, user: UUID, login: str) -> UUID:
        aid = uuid4()
        self.accounts[str(aid)] = {
            "id": aid,
            "user_id": user,
            "external_account_id": login,
            "server": "Demo",
            "environment": "demo",
            "status": "active",
            "metadata": {},
            "broker_slug": "xm",
            "broker_name": "XM",
            "created_at": datetime.now(UTC),
        }
        return aid

    def fetch(self, q: str, *args: Any) -> list[dict[str, Any]]:
        if self.fail:
            raise RuntimeError("db down")
        if "FROM public.broker_accounts a" in q and "WHERE a.id" in q:
            a = self.accounts.get(args[0])
            return [a] if a and str(a["user_id"]) == args[1] else []
        if (
            q.strip().startswith("SELECT state FROM public.robot_account_controls")
            and len(args) == 1
        ):
            c = self.controls.get(args[0])
            return [c] if c else []
        if "WHERE broker_account_id = $1::uuid AND user_id = $2::uuid" in q:
            c = self.controls.get(args[0])
            return [c] if c and str(c["user_id"]) == args[1] else []
        if "a.external_account_id = $2" in q:
            return [
                c
                for k, c in self.controls.items()
                if str(c["user_id"]) == args[0]
                and self.accounts[k]["external_account_id"] == args[1]
            ]
        raise AssertionError(q)

    def execute_transaction(
        self, stmts: list[tuple[str, tuple[Any, ...]]]
    ) -> list[str]:
        (_upsert, (aid, uid, state, reason)), (_ev, ev_args) = stmts
        existing = self.controls.get(aid)
        if existing is None or str(existing["user_id"]) == uid:
            self.controls[aid] = {"state": state, "user_id": uid, "reason": reason}
        self.events.append({"args": ev_args})
        return ["OK"]


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> FakeDB:
    fake = FakeDB()
    monkeypatch.setattr(rc, "_db", lambda: fake)
    return fake


READY = lambda _acct: rc.Readiness(ready=True, checks={"ok": True})  # noqa: E731
NOT_READY = lambda _acct: rc.Readiness(  # noqa: E731
    ready=False, reasons=("mt5_trade_allowed_false",)
)


def test_pause_blocks_new_entries_for_that_account_only(db: FakeDB) -> None:
    alice, bob = uuid4(), uuid4()
    a = db.add_account(alice, "1001")
    db.add_account(bob, "2002")
    rc.apply_action(user_id=alice, broker_account_id=a, action="pause")
    assert rc.entry_block(user_id=alice, login=1001).startswith("ROBOT_PAUSED")
    assert rc.entry_block(user_id=alice, broker_account_id=a).startswith("ROBOT_PAUSED")
    assert rc.entry_block(user_id=bob, login=2002) is None  # other user unaffected


def test_user_cannot_control_another_users_account(db: FakeDB) -> None:
    alice, bob = uuid4(), uuid4()
    b = db.add_account(bob, "2002")
    with pytest.raises(rc.RobotControlError) as err:
        rc.apply_action(user_id=alice, broker_account_id=b, action="stop")
    assert err.value.status == 404
    assert rc.entry_block(user_id=bob, broker_account_id=b) is None


def test_resume_requires_readiness(db: FakeDB) -> None:
    u = uuid4()
    a = db.add_account(u, "1001")
    rc.apply_action(user_id=u, broker_account_id=a, action="pause")
    with pytest.raises(rc.RobotControlError) as err:
        rc.apply_action(
            user_id=u, broker_account_id=a, action="resume", readiness_probe=NOT_READY
        )
    assert err.value.code == "not_ready"
    assert rc.entry_block(user_id=u, broker_account_id=a)  # still paused
    out = rc.apply_action(
        user_id=u, broker_account_id=a, action="resume", readiness_probe=READY
    )
    assert out["state"] == "RUNNING"
    assert rc.entry_block(user_id=u, broker_account_id=a) is None


def test_stop_cannot_be_resumed_only_started(db: FakeDB) -> None:
    u = uuid4()
    a = db.add_account(u, "1001")
    out = rc.apply_action(user_id=u, broker_account_id=a, action="stop")
    assert out["positions_closed"] is False  # stop never closes positions
    with pytest.raises(rc.RobotControlError):
        rc.apply_action(
            user_id=u, broker_account_id=a, action="resume", readiness_probe=READY
        )
    assert (
        rc.apply_action(
            user_id=u, broker_account_id=a, action="start", readiness_probe=READY
        )["state"]
        == "RUNNING"
    )


def test_emergency_stop_needs_a_reason_to_restart(db: FakeDB) -> None:
    u = uuid4()
    a = db.add_account(u, "1001")
    rc.apply_action(
        user_id=u, broker_account_id=a, action="emergency_stop", reason="spike"
    )
    assert rc.entry_block(user_id=u, broker_account_id=a).startswith(
        "ROBOT_EMERGENCY_STOPPED"
    )
    with pytest.raises(rc.RobotControlError) as err:
        rc.apply_action(
            user_id=u, broker_account_id=a, action="start", readiness_probe=READY
        )
    assert err.value.code == "reason_required"
    rc.apply_action(
        user_id=u,
        broker_account_id=a,
        action="start",
        reason="checked",
        readiness_probe=READY,
    )
    assert rc.entry_block(user_id=u, broker_account_id=a) is None


def test_every_change_is_audited(db: FakeDB) -> None:
    u = uuid4()
    a = db.add_account(u, "1001")
    rc.apply_action(user_id=u, broker_account_id=a, action="pause", reason="news")
    assert db.events and db.events[0]["args"][2:5] == ("pause", "RUNNING", "PAUSED")


def test_unreadable_state_fails_closed(db: FakeDB) -> None:
    db.fail = True
    assert rc.entry_block(user_id=uuid4(), login=1001).startswith(
        "ROBOT_CONTROL_UNAVAILABLE"
    )


def test_no_durable_store_means_running(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rc, "_db", lambda: None)
    assert rc.entry_block(user_id=uuid4(), login=1001) is None


def test_readiness_uses_real_mt5_trade_allowed() -> None:
    acct = {"id": uuid4(), "external_account_id": "1001"}
    gw = SimpleNamespace(login=1001, trade_allowed=False)
    r = rc.account_readiness(acct, gateway_account=gw)
    assert not r.ready and "mt5_trade_allowed_false" in r.reasons
    gw_ok = SimpleNamespace(login=1001, trade_allowed=True)
    assert rc.account_readiness(acct, gateway_account=gw_ok).ready


def test_readiness_for_worker_accounts_needs_a_ready_worker() -> None:
    acct = {"id": uuid4(), "external_account_id": "5005"}
    assert rc.account_readiness(acct).reasons == ("no_worker_assigned",)
    w = {
        "broker_account_id": str(acct["id"]),
        "dispatch_ready": True,
        "trade_allowed": False,
    }
    assert rc.account_readiness(acct, workers=[w]).reasons == ("worker_not_ready",)
    w["trade_allowed"] = True
    assert rc.account_readiness(acct, workers=[w]).ready


# --- verified connection state ---------------------------------------------


def _acct(login: str = "1001") -> dict[str, Any]:
    return {"id": uuid4(), "external_account_id": login}


def test_gateway_trade_allowed_is_robot_ready() -> None:
    gw = SimpleNamespace(login=1001, trade_allowed=True)
    assert rc.connection_state(_acct(), gateway_account=gw)["state"] == "ROBOT_READY"


def test_authenticated_but_trading_disabled_is_not_ready() -> None:
    # Investor/read-only logins authenticate but MT5 reports trade_allowed=false.
    gw = SimpleNamespace(login=1001, trade_allowed=False)
    out = rc.connection_state(_acct(), gateway_account=gw)
    assert out["state"] == "TRADING_PERMISSION_DISABLED"


def test_unknown_permission_is_only_connected() -> None:
    gw = SimpleNamespace(login=1001, trade_allowed=None)
    assert rc.connection_state(_acct(), gateway_account=gw)["state"] == "CONNECTED"


def test_no_session_is_not_connected() -> None:
    assert rc.connection_state(_acct())["state"] == "NOT_CONNECTED"


def test_worker_states() -> None:
    a = _acct("5005")
    base = {"broker_account_id": str(a["id"])}
    cases = [
        (
            {"last_error": "login_failed:(-6, 'Authorization failed')"},
            "REQUIRES_USER_ACTION",
        ),
        ({"connected": False, "ready": False}, "DEGRADED"),
        (
            {"connected": True, "ready": True, "trade_allowed": False},
            "TRADING_PERMISSION_DISABLED",
        ),
        (
            {
                "connected": True,
                "ready": True,
                "trade_allowed": True,
                "dispatch_ready": False,
            },
            "DEGRADED",
        ),
        (
            {
                "connected": True,
                "ready": True,
                "trade_allowed": True,
                "dispatch_ready": True,
            },
            "ROBOT_READY",
        ),
    ]
    for extra, want in cases:
        assert rc.connection_state(a, workers=[{**base, **extra}])["state"] == want


def test_another_accounts_worker_does_not_count() -> None:
    other = {
        "broker_account_id": str(uuid4()),
        "connected": True,
        "trade_allowed": True,
        "dispatch_ready": True,
    }
    assert rc.connection_state(_acct(), workers=[other])["state"] == "NOT_CONNECTED"
