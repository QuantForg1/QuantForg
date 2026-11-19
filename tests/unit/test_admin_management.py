"""Admin portal: safety rules, audit on every write, enforcement hooks."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.services import admin_management as am, entitlements

ADMIN = uuid4()
CUSTOMER = uuid4()
OWNER = uuid4()
BROKER = uuid4()


class FakeDb:
    def __init__(self, users=None, brokers=None, overrides=None):
        self.users = users or {}
        self.brokers = brokers or {}
        self.overrides = overrides or set()
        self.tx_calls: list[list[tuple[str, tuple]]] = []

    def fetch(self, sql, *args):
        if "FROM public.users WHERE id" in sql:
            u = self.users.get(args[0])
            return [u] if u else []
        if "FROM public.broker_accounts a" in sql and "WHERE a.id" in sql:
            b = self.brokers.get(args[0])
            return [b] if b else []
        if "FROM public.broker_accounts WHERE user_id" in sql:
            return (
                [1]
                if any(b["user_id"] == args[0] for b in self.brokers.values())
                else []
            )
        if "FROM public.user_access_overrides" in sql:
            return [1] if (args[0], args[1]) in self.overrides else []
        return []

    def execute(self, *a):
        return "UPDATE 1"

    def tx(self, stmts):
        self.tx_calls.append(stmts)
        return ["OK"] * len(stmts)

    @property
    def db(self):
        return self.fetch, self.execute, self.tx


def _actor():
    return am.Actor(user_id=ADMIN, email="admin@x.com", ip="1.2.3.4")


def _db():
    return FakeDb(
        users={
            str(CUSTOMER): {
                "id": CUSTOMER,
                "email": "c@x.com",
                "display_name": "C",
                "role": "trader",
                "status": "active",
            },
            str(OWNER): {
                "id": OWNER,
                "email": "o@x.com",
                "display_name": "O",
                "role": "owner",
                "status": "active",
            },
            str(ADMIN): {
                "id": ADMIN,
                "email": "admin@x.com",
                "display_name": "A",
                "role": "trader",
                "status": "active",
            },
        },
        brokers={
            str(BROKER): {
                "id": BROKER,
                "user_id": str(CUSTOMER),
                "status": "active",
                "label": "HFM",
                "external_account_id": "1234567",
                "role": "trader",
                "email": "c@x.com",
            },
        },
    )


def _sqls(db):
    return [s for call in db.tx_calls for s, _ in call]


def test_suspend_updates_status_stops_robots_and_audits():
    db = _db()
    out = am.set_user_status(
        CUSTOMER, "suspend", reason="fraud check", actor=_actor(), db=db.db
    )
    assert out == {"user_id": str(CUSTOMER), "status": "suspended", "changed": True}
    sqls = _sqls(db)
    assert any("UPDATE public.users" in s for s in sqls)
    assert any("robot_account_controls" in s and "'STOPPED'" in s for s in sqls)
    audit = [p for call in db.tx_calls for s, p in call if "audit_logs" in s]
    assert audit and audit[0][0] == "suspend" and audit[0][3] == str(ADMIN)


@pytest.mark.parametrize("target", [OWNER, ADMIN])
def test_owner_and_self_cannot_be_changed(target):
    db = _db()
    with pytest.raises(am.AdminActionError) as exc:
        am.set_user_status(
            target, "suspend", reason="nope nope", actor=_actor(), db=db.db
        )
    assert exc.value.status == 403
    assert db.tx_calls == []


def test_reason_is_required():
    with pytest.raises(am.AdminActionError) as exc:
        am.set_user_status(CUSTOMER, "suspend", reason=" ", actor=_actor(), db=_db().db)
    assert exc.value.code == "reason_required"


def test_role_can_only_become_trader_or_viewer():
    db = _db()
    with pytest.raises(am.AdminActionError) as exc:
        am.update_user(
            CUSTOMER,
            display_name=None,
            role="admin",
            reason="promote",
            actor=_actor(),
            db=db.db,
        )
    assert exc.value.status == 403
    out = am.update_user(
        CUSTOMER,
        display_name=None,
        role="viewer",
        reason="read only",
        actor=_actor(),
        db=db.db,
    )
    assert out["changes"] == {"role": "viewer"}


def test_remove_robot_access_writes_override_and_stops_robot():
    db = _db()
    am.set_access(
        CUSTOMER,
        "robot_trading",
        allowed=False,
        reason="risk review",
        actor=_actor(),
        db=db.db,
    )
    sqls = _sqls(db)
    assert any("INSERT INTO public.user_access_overrides" in s for s in sqls)
    assert any("robot_account_controls" in s for s in sqls)
    assert any("audit_logs" in s for s in sqls)


def test_restore_access_deletes_override_and_is_noop_without_one():
    db = _db()
    out = am.set_access(
        CUSTOMER, "signals", allowed=True, reason="restore", actor=_actor(), db=db.db
    )
    assert out["changed"] is False and db.tx_calls == []
    db.overrides.add((str(CUSTOMER), "signals"))
    am.set_access(
        CUSTOMER, "signals", allowed=True, reason="restore", actor=_actor(), db=db.db
    )
    assert any("DELETE FROM public.user_access_overrides" in s for s in _sqls(db))


def test_unknown_feature_rejected():
    with pytest.raises(am.AdminActionError):
        am.set_access(
            CUSTOMER,
            "everything",
            allowed=False,
            reason="x y z",
            actor=_actor(),
            db=_db().db,
        )


def test_broker_remove_revokes_credentials_and_stops_robot():
    db = _db()
    out = am.broker_action(
        BROKER, "remove", reason="customer request", actor=_actor(), db=db.db
    )
    assert out["status"] == "revoked"
    sqls = _sqls(db)
    assert any("broker_credentials" in s for s in sqls)
    assert any("robot_account_controls" in s for s in sqls)


def test_broker_disable_then_enable():
    db = _db()
    assert (
        am.broker_action(
            BROKER, "disable", reason="paused by admin", actor=_actor(), db=db.db
        )["status"]
        == "disabled"
    )
    db.brokers[str(BROKER)]["status"] = "disabled"
    assert (
        am.broker_action(BROKER, "enable", reason="ok again", actor=_actor(), db=db.db)[
            "status"
        ]
        == "active"
    )


def test_enable_requires_disabled_and_owner_broker_protected():
    db = _db()
    out = am.broker_action(BROKER, "enable", reason="x y z", actor=_actor(), db=db.db)
    assert out["changed"] is False and db.tx_calls == []
    db.brokers[str(BROKER)]["role"] = "owner"
    with pytest.raises(am.AdminActionError) as exc:
        am.broker_action(BROKER, "remove", reason="x y z", actor=_actor(), db=db.db)
    assert exc.value.status == 403


def test_feature_allowed_reads_override_and_fails_open():
    am.clear_access_cache()
    assert (
        am.feature_allowed(CUSTOMER, "signals", fetch=lambda *_a: [{"allowed": False}])
        is False
    )
    am.clear_access_cache()
    assert am.feature_allowed(CUSTOMER, "signals", fetch=lambda *_a: []) is True

    def boom(*a):
        raise RuntimeError("db down")

    am.clear_access_cache()
    assert am.feature_allowed(CUSTOMER, "signals", fetch=boom) is True
    am.clear_access_cache()


@pytest.mark.parametrize(
    ("row", "allowed", "reason"),
    [
        (
            {
                "role": "trader",
                "licensed": True,
                "user_status": "suspended",
                "trading_removed": False,
            },
            False,
            "ACCOUNT_SUSPENDED",
        ),
        (
            {
                "role": "trader",
                "licensed": True,
                "user_status": "active",
                "trading_removed": True,
            },
            False,
            "ACCESS_REMOVED_BY_ADMIN",
        ),
        (
            {
                "role": "trader",
                "licensed": True,
                "user_status": "active",
                "trading_removed": False,
            },
            True,
            "license_active",
        ),
        (
            {
                "role": "owner",
                "licensed": False,
                "user_status": "active",
                "trading_removed": True,
            },
            True,
            "platform_operator",
        ),
    ],
)
def test_entitlement_honours_suspension_and_admin_removal(row, allowed, reason):
    ent = entitlements.check_trading_entitlement(
        user_id=CUSTOMER, fetch=lambda *_a: [row]
    )
    assert ent.allowed is allowed
    assert ent.reason == reason


def test_disabled_broker_frees_worker_slot():
    from app.application.services.customer_account_assignment import (
        account_still_active,
    )

    assert (
        account_still_active(BROKER, fetch=lambda *_a: [{"status": "disabled"}])
        is False
    )
    assert (
        account_still_active(BROKER, fetch=lambda *_a: [{"status": "active"}]) is True
    )
