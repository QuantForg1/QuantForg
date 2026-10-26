"""Owner identity, runtime policy, and broker-claim restore."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.services.account_execution_gate import (
    bind_execution_account,
    bound_execution_account,
    reset_execution_binding_for_tests,
)
from app.application.services.broker_ownership_restore import (
    rehydrate_designated_owner_binding,
)
from app.application.services.owner_identity_policy import (
    reconcile_privileged_roles,
)
from app.application.services.runtime_policy_store import (
    install_cycle_policy,
    last_applied_version,
    load_runtime_policy,
    reset_runtime_policy_store_for_tests,
    save_runtime_policy,
)
from app.domain.entities.user import User
from app.domain.enums.user import UserRole
from app.domain.identity.designated_owner import DESIGNATED_OWNER_EMAIL
from app.domain.institutional_trading.m1_micro.config import (
    m1_live_submit_enabled,
    m1_micro_enabled,
)
from app.domain.institutional_trading.owner_live_limits import (
    evaluate_owner_entry,
)
from app.domain.institutional_trading.runtime_policy import (
    approved_baseline,
    reset_runtime_policy,
    use_runtime_policy,
    validate_policy_changes,
)
from app.domain.interfaces.auth import AuthUserIdentity


class _Users:
    def __init__(self) -> None:
        self.items: dict = {}

    async def get_by_auth_user_id(self, auth_user_id):
        for user in self.items.values():
            if user.auth_user_id == auth_user_id:
                return user
        return None

    async def get_by_email(self, email):
        for user in self.items.values():
            if str(user.email) == str(email):
                return user
        return None

    async def update(self, user):
        self.items[user.id] = user
        return user


class _Audits:
    def __init__(self) -> None:
        self.rows: list = []

    async def add(self, entry):
        self.rows.append(entry)
        return entry


class _Uow:
    def __init__(self) -> None:
        self.users = _Users()
        self.audit_logs = _Audits()


def _user(email: str, role: UserRole) -> User:
    user = User.create(email=email, display_name="Trader", role=role)
    user.activate()
    user.link_auth_identity(uuid4())
    return user


def _identity(user: User, *, confirmed: bool) -> AuthUserIdentity:
    return AuthUserIdentity(
        id=user.auth_user_id,
        email=str(user.email),
        email_confirmed=confirmed,
        display_name=str(user.display_name),
    )


@pytest.fixture(autouse=True)
def _clean():
    reset_execution_binding_for_tests()
    reset_runtime_policy_store_for_tests()
    yield
    reset_execution_binding_for_tests()
    reset_runtime_policy_store_for_tests()


@pytest.mark.unit
async def test_verified_designated_owner_is_sole_privileged_role():
    owner = _user(DESIGNATED_OWNER_EMAIL, UserRole.TRADER)
    other = _user("other@example.com", UserRole.ADMIN)
    uow = _Uow()
    uow.users.items[owner.id] = owner
    uow.users.items[other.id] = other

    changes = await reconcile_privileged_roles(uow, _identity(owner, confirmed=True))

    assert owner.role == UserRole.OWNER
    assert other.role == UserRole.TRADER
    assert {row["action"] for row in changes} == {
        "promoted_owner",
        "demoted_not_designated",
    }
    assert uow.audit_logs.rows


@pytest.mark.unit
async def test_unconfirmed_designated_email_is_not_promoted():
    owner = _user(DESIGNATED_OWNER_EMAIL, UserRole.TRADER)
    uow = _Uow()
    uow.users.items[owner.id] = owner
    claimed = AuthUserIdentity(
        id=owner.auth_user_id,
        email=DESIGNATED_OWNER_EMAIL,
        email_confirmed=False,
        display_name="Owner",
    )
    await reconcile_privileged_roles(uow, claimed)
    assert owner.role == UserRole.TRADER


@pytest.mark.unit
async def test_request_email_alone_does_not_promote_a_different_identity():
    attacker = _user("attacker@example.com", UserRole.TRADER)
    uow = _Uow()
    uow.users.items[attacker.id] = attacker
    forged = AuthUserIdentity(
        id=attacker.auth_user_id,
        email="attacker@example.com",
        email_confirmed=True,
        display_name="Owner",
        metadata={"requested_email": DESIGNATED_OWNER_EMAIL},
    )
    await reconcile_privileged_roles(uow, forged)
    assert attacker.role == UserRole.TRADER


@pytest.mark.unit
def test_policy_rejects_looser_risk_and_disabled_safeguards():
    base = approved_baseline()
    loose = validate_policy_changes(base, {"max_planned_risk_pct": "20"})
    assert loose.ok is False
    unlocked = validate_policy_changes(base, {"gold_only": False})
    assert unlocked.ok is False
    killed = validate_policy_changes(base, {"kill_switch_bypass": True})
    assert killed.ok is False
    tighter = validate_policy_changes(
        base, {"max_planned_risk_pct": "5", "daily_loss_pct": "10"}
    )
    assert tighter.ok is True
    assert tighter.document is not None
    assert tighter.document["max_planned_risk_pct"] == "5"
    weekly = validate_policy_changes(
        base, {"weekly_loss_pct": "0", "daily_loss_pct": "19"}
    )
    assert weekly.ok is True
    too_wide = validate_policy_changes(
        {**base, "daily_loss_pct": "10"}, {"weekly_loss_pct": "12"}
    )
    assert too_wide.ok is False


@pytest.mark.unit
def test_saved_policy_is_stricter_and_a_stale_version_conflicts():
    actor = uuid4()
    first = save_runtime_policy(
        actor_id=actor,
        expected_version=0,
        changes={"max_planned_risk_pct": "5"},
    )
    assert first.ok is True
    assert first.version == 1
    stale = save_runtime_policy(
        actor_id=actor,
        expected_version=0,
        changes={"max_planned_risk_pct": "4"},
    )
    assert stale.ok is False
    assert stale.error == "stale_version"
    loaded = load_runtime_policy()
    assert loaded.version == 1
    token = use_runtime_policy(loaded.document)
    try:
        blocked = evaluate_owner_entry(
            symbol="XAUUSD",
            side="BUY",
            volume=Decimal("0.01"),
            entry=Decimal("2400"),
            stop_loss=Decimal("2300"),
            take_profit=Decimal("2600"),
            spread=Decimal("0.20"),
            contract_size=Decimal("100"),
            equity=Decimal("100"),
            weekly_pnl=Decimal("0"),
        )
    finally:
        reset_runtime_policy(token)
    assert any(item.startswith("OWNER_SL_RISK") for item in blocked)


@pytest.mark.unit
def test_missing_policy_read_blocks_entries():
    token = use_runtime_policy({"unavailable": True})
    try:
        reasons = evaluate_owner_entry(
            symbol="XAUUSD",
            side="BUY",
            volume=Decimal("0.01"),
            entry=Decimal("2400"),
            stop_loss=Decimal("2390"),
            take_profit=Decimal("2420"),
            spread=Decimal("0.20"),
            contract_size=Decimal("100"),
            equity=Decimal("100"),
        )
    finally:
        reset_runtime_policy(token)
    assert reasons == ["CONFIG_UNAVAILABLE: runtime trading policy could not be read"]


@pytest.mark.unit
def test_non_gold_and_missing_stop_still_block():
    reasons = evaluate_owner_entry(
        symbol="EURUSD",
        side="BUY",
        volume=Decimal("0.01"),
        entry=Decimal("1.1"),
        stop_loss=None,
        take_profit=Decimal("1.2"),
        spread=Decimal("0.0001"),
        contract_size=Decimal("100000"),
        equity=Decimal("100"),
    )
    assert any("OWNER_GOLD_ONLY" in item for item in reasons)
    assert any("OWNER_SL_REQUIRED" in item for item in reasons)


@pytest.mark.unit
def test_rehydrate_binds_only_the_designated_owner_claim(monkeypatch):
    owner_id = uuid4()

    def _fetch(query, login, email):
        assert login == 4242
        assert email == DESIGNATED_OWNER_EMAIL
        if "other" in query:
            return []
        return [{"user_id": str(owner_id), "email": email}]

    monkeypatch.setattr(
        "app.infrastructure.persistence.direct_postgres.direct_postgres_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.infrastructure.persistence.direct_postgres.fetch",
        _fetch,
    )
    result = rehydrate_designated_owner_binding(4242)
    assert result["reason"] == "restored"
    bound_user, bound_login = bound_execution_account()
    assert bound_user == owner_id
    assert bound_login == 4242

    def _other(query, login, email):
        return [{"user_id": str(uuid4()), "email": "other@example.com"}]

    monkeypatch.setattr(
        "app.infrastructure.persistence.direct_postgres.fetch",
        _other,
    )
    reset_execution_binding_for_tests()
    refused = rehydrate_designated_owner_binding(4242)
    assert refused["reason"] == "claim_not_designated_owner"
    assert bound_execution_account() == (None, 0)


@pytest.mark.unit
def test_unbound_gateway_is_not_treated_as_owned(monkeypatch):
    monkeypatch.setattr(
        "app.infrastructure.persistence.direct_postgres.direct_postgres_available",
        lambda: False,
    )
    result = rehydrate_designated_owner_binding(4242)
    assert result["bound"] is False
    assert bound_execution_account()[1] == 0
    bind_execution_account(user_id=uuid4(), login=100)
    _user_id, login = bound_execution_account()
    assert login == 100
    installed = install_cycle_policy()
    assert installed.ok is True
    assert installed.source == "approved_baseline"
    assert SimpleNamespace(**(installed.document or {})).weekly_loss_pct == "0"


def _quiet_entry(**overrides: object) -> list[str]:
    payload = {
        "symbol": "XAUUSD",
        "side": "BUY",
        "volume": Decimal("0.01"),
        "entry": Decimal("2400"),
        "stop_loss": Decimal("2399"),
        "take_profit": Decimal("2402"),
        "spread": Decimal("0.20"),
        "contract_size": Decimal("100"),
        "equity": Decimal("10000"),
        "weekly_pnl": Decimal("0"),
    }
    payload.update(overrides)
    return evaluate_owner_entry(**payload)  # type: ignore[arg-type]


@pytest.mark.unit
def test_worker_applies_saved_policy_version():
    actor = uuid4()
    saved = save_runtime_policy(
        actor_id=actor,
        expected_version=0,
        changes={"max_planned_risk_pct": "5"},
    )
    installed = install_cycle_policy()
    assert saved.ok is True
    assert installed.version == saved.version == 1
    assert installed.status == "applied"
    assert last_applied_version() == 1


@pytest.mark.unit
def test_configured_weekly_limit_fails_closed_without_pnl():
    token = use_runtime_policy(
        {**approved_baseline(), "weekly_loss_pct": "5", "daily_loss_pct": "19"}
    )
    try:
        blocked = _quiet_entry(weekly_pnl=None)
    finally:
        reset_runtime_policy(token)
    assert any(item.startswith("WEEKLY_PNL_UNAVAILABLE") for item in blocked)


@pytest.mark.unit
def test_m1_policy_cannot_bypass_a_disabled_deployment_flag(monkeypatch):
    monkeypatch.delenv("QUANTFORG_M1_MICRO_SCALPING", raising=False)
    monkeypatch.delenv("QUANTFORG_M1_MICRO_LIVE_SUBMIT", raising=False)
    token = use_runtime_policy(
        {
            **approved_baseline(),
            "m1_micro_enabled": True,
            "m1_live_submit": True,
        }
    )
    try:
        assert m1_micro_enabled() is False
        assert m1_live_submit_enabled() is False
    finally:
        reset_runtime_policy(token)


@pytest.mark.unit
def test_unavailable_policy_turns_m1_off(monkeypatch):
    monkeypatch.setenv("QUANTFORG_M1_MICRO_SCALPING", "true")
    monkeypatch.setenv("QUANTFORG_M1_MICRO_LIVE_SUBMIT", "true")
    token = use_runtime_policy({"unavailable": True})
    try:
        assert m1_micro_enabled() is False
        assert m1_live_submit_enabled() is False
    finally:
        reset_runtime_policy(token)
