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
    bootstrap_owner_control_plane,
    enforce_designated_owner_rows,
    install_cycle_policy,
    last_applied_version,
    load_runtime_policy,
    memory_audit_events,
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
            commission=Decimal("0"),
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
@pytest.mark.unit
def test_enforce_demotes_non_designated_privileged_rows(monkeypatch):
    target = uuid4()
    actor = uuid4()
    executed: list[tuple] = []

    def _fetch(query, *args):
        compact = " ".join(query.split())
        assert args == (DESIGNATED_OWNER_EMAIL,)
        if compact.startswith("UPDATE"):
            assert "deactivated" in compact
            assert "owner" in compact and "admin" in compact
            return [{"id": str(target)}]
        return [{"id": str(actor)}]

    def _execute(_query, *args):
        executed.append(args)
        return "INSERT 0 1"

    monkeypatch.setattr(
        "app.infrastructure.persistence.direct_postgres.direct_postgres_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.infrastructure.persistence.direct_postgres.fetch",
        _fetch,
    )
    monkeypatch.setattr(
        "app.infrastructure.persistence.direct_postgres.execute",
        _execute,
    )
    assert enforce_designated_owner_rows() == 1
    assert executed
    message = str(executed[0][3])
    assert message == "privileged role demoted_not_designated"
    assert "@" not in message


@pytest.mark.unit
def test_bootstrap_reports_schema_failure_without_enabling_trade(monkeypatch):
    def _boom() -> None:
        raise RuntimeError("schema")

    monkeypatch.setattr(
        "app.application.services.runtime_policy_store.ensure_owner_schema",
        _boom,
    )
    monkeypatch.setattr(
        "app.application.services.runtime_policy_store.enforce_designated_owner_rows",
        lambda: 0,
    )
    result = bootstrap_owner_control_plane()
    assert result == {"schema_ok": False, "demoted": 0}


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
        "commission": Decimal("0"),
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
    from app.presentation.routers.admin_control import _policy_view

    confirmed = load_runtime_policy()
    assert confirmed.applied_version == 1
    assert _policy_view(confirmed)["worker_confirmed"] is True
    second = save_runtime_policy(
        actor_id=actor,
        expected_version=1,
        changes={"max_planned_risk_pct": "4"},
    )
    assert second.ok is True
    assert second.version == 2
    assert second.applied_version == 1
    pending = load_runtime_policy()
    view = _policy_view(pending)
    assert pending.version == 2
    assert pending.applied_version == 1
    assert view["worker_confirmed"] is False
    unacked = _policy_view(
        type(confirmed)(
            True,
            2,
            confirmed.document,
            "persisted",
            applied_version=None,
        )
    )
    assert unacked["worker_confirmed"] is False
    assert unacked["applied_version"] is None


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
def test_saved_min_lot_blocks_a_smaller_volume():
    token = use_runtime_policy({**approved_baseline(), "min_lot": "0.01"})
    try:
        blocked = _quiet_entry(volume=Decimal("0.001"))
    finally:
        reset_runtime_policy(token)
    assert any(item.startswith("OWNER_MIN_LOT") for item in blocked)


@pytest.mark.unit
def test_aggregate_cap_stays_inside_the_per_trade_cap():
    from app.domain.institutional_trading.owner_live_limits import (
        max_aggregate_risk_usd,
        max_planned_risk_usd,
    )

    token = use_runtime_policy(
        {**approved_baseline(), "max_aggregate_open_risk_pct": "4"}
    )
    try:
        equity = Decimal("100")
        assert max_aggregate_risk_usd(equity) == Decimal("4.00")
        assert max_aggregate_risk_usd(equity) <= max_planned_risk_usd(equity)
    finally:
        reset_runtime_policy(token)


@pytest.mark.unit
def test_disabling_the_full_utc_day_blocks_entry():
    token = use_runtime_policy({**approved_baseline(), "evaluate_full_utc_day": False})
    try:
        blocked = _quiet_entry()
    finally:
        reset_runtime_policy(token)
    assert any(item.startswith("OWNER_SESSION_POLICY") for item in blocked)


@pytest.mark.unit
def test_saved_position_cap_cannot_rise_above_one():
    from app.domain.institutional_trading.runtime_policy import (
        active_max_open_positions,
    )

    token = use_runtime_policy({**approved_baseline(), "max_concurrent_positions": 5})
    try:
        assert active_max_open_positions() == 1
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


@pytest.mark.unit
def test_weekly_halt_stays_off_until_the_owner_sets_it():
    token = use_runtime_policy(approved_baseline())
    try:
        clear = _quiet_entry(weekly_pnl=None)
    finally:
        reset_runtime_policy(token)
    assert not any(item.startswith("WEEKLY_PNL_UNAVAILABLE") for item in clear)
    assert not any(item.startswith("OWNER_WEEKLY_LOSS") for item in clear)


@pytest.mark.unit
@pytest.mark.trading_core
def test_drawdown_halt_stays_off_until_the_owner_sets_it():
    token = use_runtime_policy(approved_baseline())
    try:
        clear = _quiet_entry(peak_known=False, peak_equity=None)
    finally:
        reset_runtime_policy(token)
    assert not any(item.startswith("DRAWDOWN_BASE_UNAVAILABLE") for item in clear)
    assert not any(item.startswith("OWNER_DRAWDOWN") for item in clear)


@pytest.mark.unit
@pytest.mark.trading_core
def test_configured_drawdown_fails_closed_without_a_peak():
    token = use_runtime_policy(
        {**approved_baseline(), "max_drawdown_pct": "10", "daily_loss_pct": "19"}
    )
    try:
        blocked = _quiet_entry(peak_known=False, peak_equity=None)
    finally:
        reset_runtime_policy(token)
    assert any(item.startswith("DRAWDOWN_BASE_UNAVAILABLE") for item in blocked)


@pytest.mark.unit
@pytest.mark.trading_core
def test_drawdown_blocks_only_above_the_saved_percent():
    token = use_runtime_policy(
        {**approved_baseline(), "max_drawdown_pct": "10", "daily_loss_pct": "19"}
    )
    try:
        breached = _quiet_entry(
            equity=Decimal("89"),
            peak_equity=Decimal("100"),
            peak_known=True,
            volume=Decimal("0.01"),
            stop_loss=Decimal("2399.95"),
            spread=Decimal("0.01"),
        )
        at_cap = _quiet_entry(
            equity=Decimal("90"),
            peak_equity=Decimal("100"),
            peak_known=True,
            volume=Decimal("0.01"),
            stop_loss=Decimal("2399.95"),
            spread=Decimal("0.01"),
        )
    finally:
        reset_runtime_policy(token)
    assert any(item.startswith("OWNER_DRAWDOWN") for item in breached)
    assert not any(item.startswith("OWNER_DRAWDOWN") for item in at_cap)


@pytest.mark.unit
@pytest.mark.trading_core
def test_drawdown_cannot_exceed_the_daily_halt():
    base = approved_baseline()
    too_wide = validate_policy_changes(
        {**base, "daily_loss_pct": "10"}, {"max_drawdown_pct": "12"}
    )
    assert too_wide.ok is False
    allowed = validate_policy_changes(base, {"max_drawdown_pct": "0"})
    assert allowed.ok is True


@pytest.mark.unit
@pytest.mark.trading_core
def test_presend_forwards_weekly_pnl_and_drawdown_peak():
    from app.domain.institutional_trading.owner_live_limits import (
        presend_owner_violations,
    )

    token = use_runtime_policy(
        {
            **approved_baseline(),
            "weekly_loss_pct": "5",
            "max_drawdown_pct": "10",
            "daily_loss_pct": "19",
        }
    )
    try:
        blocked = presend_owner_violations(
            symbol="XAUUSD",
            side="BUY",
            volume=Decimal("0.01"),
            request_price=Decimal("2400"),
            bid=Decimal("2399.90"),
            ask=Decimal("2400.10"),
            stop_loss=Decimal("2399"),
            take_profit=Decimal("2402"),
            plan_price=Decimal("2400"),
            contract_size=Decimal("100"),
            equity=Decimal("10000"),
            weekly_pnl=None,
            peak_equity=None,
            peak_known=False,
            commission=Decimal("0"),
        )
        clear = presend_owner_violations(
            symbol="XAUUSD",
            side="BUY",
            volume=Decimal("0.01"),
            request_price=Decimal("2400"),
            bid=Decimal("2399.90"),
            ask=Decimal("2400.10"),
            stop_loss=Decimal("2399"),
            take_profit=Decimal("2402"),
            plan_price=Decimal("2400"),
            contract_size=Decimal("100"),
            equity=Decimal("10000"),
            weekly_pnl=Decimal("0"),
            peak_equity=Decimal("10000"),
            peak_known=True,
            commission=Decimal("0"),
        )
    finally:
        reset_runtime_policy(token)
    assert any("WEEKLY_PNL_UNAVAILABLE" in item for item in blocked)
    assert any("DRAWDOWN_BASE_UNAVAILABLE" in item for item in blocked)
    assert not any("WEEKLY_PNL_UNAVAILABLE" in item for item in clear)
    assert not any("DRAWDOWN_BASE_UNAVAILABLE" in item for item in clear)


@pytest.mark.unit
@pytest.mark.trading_core
def test_equity_peak_survives_a_lower_reading_and_fails_closed_when_down():
    from app.application.services.equity_peak_store import (
        force_equity_peak_unavailable_for_tests,
        observe_equity_peak,
        reset_equity_peak_for_tests,
    )

    reset_equity_peak_for_tests()
    try:
        first, trusted = observe_equity_peak(Decimal("50"))
        second, still = observe_equity_peak(Decimal("40"))
        assert trusted is True
        assert still is True
        assert first == Decimal("50")
        assert second == Decimal("50")
        force_equity_peak_unavailable_for_tests(True)
        missing, outage = observe_equity_peak(Decimal("80"))
        assert missing is None
        assert outage is False
    finally:
        reset_equity_peak_for_tests()


def _stub_policy_store(monkeypatch, transaction):
    calls = {"execute": 0, "statements": []}

    def available() -> bool:
        return True

    def execute(*_args, **_kwargs):
        calls["execute"] += 1
        return "OK"

    def fetch(*_args, **_kwargs):
        return []

    def execute_transaction(statements):
        calls["statements"].append(statements)
        return transaction(statements)

    monkeypatch.setattr(
        "app.application.services.runtime_policy_store._postgres",
        lambda: (available, execute, fetch),
    )
    monkeypatch.setattr(
        "app.infrastructure.persistence.direct_postgres.execute_transaction",
        execute_transaction,
    )
    return calls


@pytest.mark.unit
def test_policy_write_and_success_audit_share_one_transaction(monkeypatch):
    def transaction(statements):
        assert len(statements) == 2
        assert "trading_runtime_config" in statements[0][0]
        assert "audit_logs" in statements[1][0]
        return ["INSERT 0 1", "INSERT 0 1"]

    calls = _stub_policy_store(monkeypatch, transaction)
    saved = save_runtime_policy(
        actor_id=uuid4(),
        expected_version=0,
        changes={"max_planned_risk_pct": "5", "weekly_loss_pct": "0"},
    )
    assert saved.ok is True
    assert saved.version == 1
    assert saved.source == "persisted"
    assert saved.status == "saved"
    assert len(calls["statements"]) == 1
    # Five execute() calls are the schema setup, including the worker-ack
    # columns. The success audit is the second statement inside the one
    # transaction.
    assert calls["execute"] == 5
    outcomes = [event["outcome"] for event in memory_audit_events()]
    assert outcomes == ["success"]


@pytest.mark.unit
def test_zero_row_policy_write_rolls_back_as_a_conflict(monkeypatch):
    from app.infrastructure.persistence.direct_postgres import TransactionNoRow

    def transaction(_statements):
        raise TransactionNoRow("INSERT 0 0")

    _stub_policy_store(monkeypatch, transaction)
    saved = save_runtime_policy(
        actor_id=uuid4(),
        expected_version=0,
        changes={"max_planned_risk_pct": "5"},
    )
    assert saved.ok is False
    assert saved.error == "stale_version"
    assert saved.source == "conflict"
    outcomes = [event["outcome"] for event in memory_audit_events()]
    assert outcomes == ["denied"]
    assert "success" not in outcomes


@pytest.mark.unit
def test_policy_transaction_failure_does_not_report_a_save(monkeypatch):
    def transaction(_statements):
        raise RuntimeError("db down")

    _stub_policy_store(monkeypatch, transaction)
    saved = save_runtime_policy(
        actor_id=uuid4(),
        expected_version=0,
        changes={"max_planned_risk_pct": "5"},
    )
    assert saved.ok is False
    assert saved.error == "config_write_failed"
    outcomes = [event["outcome"] for event in memory_audit_events()]
    assert outcomes == ["failure"]


@pytest.mark.unit
def test_postgres_status_rowcount_uses_the_last_token():
    from app.infrastructure.persistence.direct_postgres import _status_rowcount

    assert _status_rowcount("INSERT 0 1") == 1
    assert _status_rowcount("INSERT 0 0") == 0
    assert _status_rowcount("UPDATE 1") == 1
    assert _status_rowcount("UPDATE 0") == 0
    assert _status_rowcount("") == 0
