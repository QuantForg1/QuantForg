"""Per-user risk profiles: defaults, validation, isolation, engine enforcement."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.services import (
    runtime_policy_store as rps,
    user_risk_profile_store as store,
)
from app.domain.institutional_trading import (
    owner_live_limits as ol,
    runtime_policy as rp,
)
from app.domain.institutional_trading.live_trading_control import (
    LiveTradingRiskConfig,
)
from app.domain.institutional_trading.risk_profile import (
    SOURCE_CUSTOM,
    SOURCE_DEFAULT,
    resolve_profile,
    validate_profile_changes,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


@pytest.fixture(autouse=True)
def _clean() -> object:
    store.reset_for_tests()
    token = rp.use_runtime_policy(None)
    yield
    rp.reset_runtime_policy(token)
    store.reset_for_tests()


def test_defaults_are_the_owner_approved_values() -> None:
    eff = resolve_profile({})
    v = eff.values
    assert v["planned_risk_pct"] == Decimal("15.0")
    assert v["aggregate_open_risk_pct"] == Decimal("20.0")
    assert v["daily_loss_pct"] == Decimal("30.0")
    assert v["weekly_loss_pct"] == v["monthly_loss_pct"] == v["max_drawdown_pct"] == 0
    assert v["min_reward_risk"] == Decimal("1.50")
    assert v["max_spread"] == Decimal("1.00")
    assert v["max_lot"] == Decimal("0.50")
    assert v["max_open_positions"] == 5
    assert v["min_trade_quality"] == 75
    assert v["trading_days"] == (0, 1, 2, 3, 4)
    assert v["trading_hours_utc"] == "00:00-24:00"
    assert set(eff.sources.values()) == {SOURCE_DEFAULT}


def test_no_profile_installed_uses_defaults() -> None:
    assert rp.active_max_planned_risk_pct() == Decimal("15.0")
    assert rp.active_max_aggregate_open_risk_pct() == Decimal("20.0")
    assert rp.active_daily_loss_pct() == Decimal("30.0")
    assert rp.active_max_lot() == Decimal("0.50")
    assert rp.active_max_open_positions() == 5
    assert rp.active_max_spread() == Decimal("1.00")
    assert rp.active_min_reward_risk() == Decimal("1.50")
    assert rp.active_min_trade_quality() == 75
    assert rp.weekly_loss_limit_pct() == 0
    assert rp.monthly_loss_limit_pct() == 0
    assert rp.drawdown_limit_pct() == 0


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"planned_risk_pct": "-1"}, "planned_risk_pct"),
        ({"planned_risk_pct": "26"}, "planned_risk_pct"),
        ({"planned_risk_pct": "abc"}, "planned_risk_pct"),
        ({"daily_loss_pct": "51"}, "daily_loss_pct"),
        ({"weekly_loss_pct": "0.05"}, "weekly_loss_pct"),
        ({"min_reward_risk": "0.5"}, "min_reward_risk"),
        ({"max_spread": "2.5"}, "max_spread"),
        ({"max_lot": "0.015"}, "max_lot"),
        ({"max_lot": "6"}, "max_lot"),
        ({"max_open_positions": "1.5"}, "max_open_positions"),
        ({"max_open_positions": 11}, "max_open_positions"),
        ({"min_trade_quality": 60}, "min_trade_quality"),
        ({"trading_days": []}, "trading_days"),
        ({"trading_days": [7]}, "trading_days"),
        ({"trading_hours_utc": "25:00-26:00"}, "trading_hours_utc"),
        ({"martingale": True}, "martingale"),
        (
            {"planned_risk_pct": "15", "aggregate_open_risk_pct": "10"},
            "aggregate_open_risk_pct",
        ),
    ],
)
def test_invalid_settings_are_rejected(changes: dict, field: str) -> None:
    checked = validate_profile_changes({}, changes)
    assert not checked.ok
    assert field in checked.errors


def test_custom_values_persist_and_mark_custom() -> None:
    user = uuid4()
    store.save_profile(
        user, {"planned_risk_pct": "5", "weekly_loss_pct": "10"}, actor_id=user
    )
    eff = store.effective_profile(user, use_cache=False)
    assert eff.values["planned_risk_pct"] == Decimal("5")
    assert eff.values["weekly_loss_pct"] == Decimal("10")
    assert eff.sources["planned_risk_pct"] == SOURCE_CUSTOM
    assert eff.sources["daily_loss_pct"] == SOURCE_DEFAULT
    assert eff.version == 1
    events = store.list_events(user)
    assert events[0]["action"] == "update"


def test_reset_restores_defaults_and_null_resets_one_field() -> None:
    user = uuid4()
    store.save_profile(
        user, {"planned_risk_pct": "5", "max_lot": "0.10"}, actor_id=user
    )
    store.save_profile(user, {"max_lot": None}, actor_id=user)
    eff = store.effective_profile(user, use_cache=False)
    assert eff.sources["max_lot"] == SOURCE_DEFAULT
    assert eff.values["planned_risk_pct"] == Decimal("5")
    reset = store.reset_profile(user, actor_id=user)
    assert set(reset.sources.values()) == {SOURCE_DEFAULT}
    assert reset.version == 3


def test_user_a_settings_never_reach_user_b() -> None:
    a, b = uuid4(), uuid4()
    store.save_profile(
        a, {"planned_risk_pct": "2", "max_open_positions": 1}, actor_id=a
    )
    doc_a = rps.effective_user_document({"gold_only": True}, a)
    doc_b = rps.effective_user_document({"gold_only": True}, b)
    assert doc_a["max_planned_risk_pct"] == "2"
    assert doc_a["max_concurrent_positions"] == 1
    assert doc_b["max_planned_risk_pct"] == "15.0"
    assert doc_b["max_concurrent_positions"] == 5
    assert doc_a["risk_profile_user"] != doc_b["risk_profile_user"]


def test_concurrent_update_with_stale_version_is_refused() -> None:
    user = uuid4()
    store.save_profile(user, {"planned_risk_pct": "5"}, actor_id=user)
    with pytest.raises(store.ProfileConflictError):
        store.save_profile(
            user, {"planned_risk_pct": "6"}, actor_id=user, expected_version=0
        )
    assert store.effective_profile(user, use_cache=False).values[
        "planned_risk_pct"
    ] == Decimal("5")


def test_shared_owner_document_no_longer_controls_the_profile() -> None:
    user = uuid4()
    legacy_shared = {
        "max_planned_risk_pct": "9",
        "daily_loss_pct": "25",
        "max_concurrent_positions": 1,
        "max_spread": "0.45",
        "max_lot": "0.01",
        "session_utc": "07:00-17:00 Mon-Fri",
        "gold_only": True,
        "protective_stop_required": True,
    }
    doc = rps.effective_user_document(legacy_shared, user)
    token = rp.use_runtime_policy(doc)
    try:
        assert rp.active_max_planned_risk_pct() == Decimal("15.0")
        assert rp.active_daily_loss_pct() == Decimal("30.0")
        assert rp.active_max_open_positions() == 5
        assert rp.active_max_spread() == Decimal("1.00")
        assert rp.active_max_lot() == Decimal("0.50")
        assert doc["gold_only"] is True
        assert doc["protective_stop_required"] is True
    finally:
        rp.reset_runtime_policy(token)


def test_install_cycle_policy_is_per_user_and_fails_closed(monkeypatch) -> None:
    user = uuid4()
    store.save_profile(user, {"max_spread": "0.30"}, actor_id=user)
    installed = rps.install_cycle_policy(user)
    assert installed.ok
    assert rp.active_max_spread() == Decimal("0.30")
    assert installed.document["risk_profile_version"] == 1

    def boom(*_a, **_k):
        raise store.ProfileStoreError("down")

    monkeypatch.setattr(store, "effective_profile", boom)
    failed = rps.install_cycle_policy(user)
    assert not failed.ok
    assert rp.policy_unavailable()


def test_system_bounds_clamp_a_tampered_document() -> None:
    token = rp.use_runtime_policy(
        {
            "max_planned_risk_pct": "90",
            "max_lot": "50",
            "max_concurrent_positions": 99,
            "max_spread": "9",
            "daily_loss_pct": "95",
        }
    )
    try:
        assert rp.active_max_planned_risk_pct() == Decimal("15.0")
        assert rp.active_max_lot() == Decimal("0.50")
        assert rp.active_max_open_positions() == 5
        assert rp.active_max_spread() == Decimal("1.00")
        assert rp.active_daily_loss_pct() == Decimal("30.0")
    finally:
        rp.reset_runtime_policy(token)


def test_default_schedule_is_24_5_and_custom_window_applies() -> None:
    monday_03 = datetime(2026, 11, 16, 3, 0, tzinfo=UTC)
    friday_2359 = datetime(2026, 11, 20, 23, 59, tzinfo=UTC)
    saturday = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)
    assert ol.in_owner_session(monday_03)
    assert ol.in_owner_session(friday_2359)
    assert not ol.in_owner_session(saturday)
    token = rp.use_runtime_policy(
        {"trading_days": [0, 1, 2, 3, 4], "trading_hours_utc": "07:00-17:00"}
    )
    try:
        assert not ol.in_owner_session(monday_03)
        assert ol.in_owner_session(datetime(2026, 11, 16, 7, 0, tzinfo=UTC))
    finally:
        rp.reset_runtime_policy(token)


def _entry(**overrides) -> list[str]:
    params = {
        "symbol": "XAUUSD",
        "side": "BUY",
        "volume": Decimal("0.01"),
        "entry": Decimal("3750.00"),
        "stop_loss": Decimal("3747.00"),
        "take_profit": Decimal("3756.00"),
        "spread": Decimal("0.40"),
        "contract_size": Decimal("100"),
        "equity": Decimal("100"),
        "now": datetime(2026, 11, 18, 12, 0, tzinfo=UTC),
        "commission": Decimal("0"),
        "daily": ol.DailyLossContext(
            trusted=True, balance=Decimal("100"), equity=Decimal("100")
        ),
    }
    params.update(overrides)
    return ol.evaluate_owner_entry(**params)


def test_engine_enforces_each_users_risk_per_trade() -> None:
    # (3.00 + 0.40 spread) x 100 x 0.01 = $3.40 planned risk on $100 equity.
    user_default, user_tight = uuid4(), uuid4()
    store.save_profile(user_tight, {"planned_risk_pct": "3"}, actor_id=user_tight)
    rps.install_cycle_policy(user_default)
    assert _entry() == []
    rps.install_cycle_policy(user_tight)
    reasons = _entry()
    assert any(r.startswith("OWNER_SL_RISK") for r in reasons)


def test_engine_enforces_monthly_and_weekly_limits_only_when_on() -> None:
    user = uuid4()
    rps.install_cycle_policy(user)
    assert _entry(monthly_pnl=Decimal("-50"), weekly_pnl=Decimal("-50")) == []
    store.save_profile(
        user, {"monthly_loss_pct": "20", "weekly_loss_pct": "20"}, actor_id=user
    )
    rps.install_cycle_policy(user)
    reasons = _entry(monthly_pnl=Decimal("-50"), weekly_pnl=Decimal("-50"))
    assert any(r.startswith("OWNER_MONTHLY_LOSS") for r in reasons)
    assert any(r.startswith("OWNER_WEEKLY_LOSS") for r in reasons)
    assert any(r.startswith("MONTHLY_PNL_UNAVAILABLE") for r in _entry())


def test_engine_enforces_user_spread_and_rr() -> None:
    user = uuid4()
    store.save_profile(
        user, {"max_spread": "0.30", "min_reward_risk": "2.0"}, actor_id=user
    )
    rps.install_cycle_policy(user)
    reasons = _entry()
    assert any(r.startswith("OWNER_MAX_SPREAD") for r in reasons)
    assert any(r.startswith("OWNER_MIN_RR") for r in reasons)


def test_live_control_gate_uses_the_installed_profile() -> None:
    stored = LiveTradingRiskConfig(max_open_positions=1, max_spread=Decimal("0.45"))
    assert stored.with_active_profile() is stored
    user = uuid4()
    store.save_profile(user, {"max_open_positions": 3}, actor_id=user)
    rps.install_cycle_policy(user)
    cfg = stored.with_active_profile()
    assert cfg.max_open_positions == 3
    assert cfg.max_spread == Decimal("1.00")
    assert cfg.risk_per_trade_pct == Decimal("15.0")
    assert cfg.max_slippage == stored.max_slippage


def test_sizing_budget_follows_the_profile_percent() -> None:
    from app.domain.institutional_trading.config import TARGET_PLANNED_RISK_USD
    from app.domain.institutional_trading.operations.min_lot_feasibility import (
        resolve_target_risk_budget_usd,
    )

    user = uuid4()
    store.save_profile(user, {"planned_risk_pct": "4"}, actor_id=user)
    rps.install_cycle_policy(user)
    budget = resolve_target_risk_budget_usd(
        equity=Decimal("1000"), target_usd=TARGET_PLANNED_RISK_USD
    )
    assert budget == Decimal("40.00")
    explicit = resolve_target_risk_budget_usd(
        equity=Decimal("1000"), target_usd=Decimal("5")
    )
    assert explicit == Decimal("5.00")
