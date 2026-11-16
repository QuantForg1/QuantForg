"""Multi-account worker path applies the same final owner guard.

Before this change ``authorize_worker_execution`` skipped the owner entry
guard (RR, spread, session, daily budget, quality floor on risk, user caps)
and took the account environment from the job payload, defaulting to demo.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.services.multi_account_oms_execution import (
    authorize_worker_execution,
)
from app.application.services.multi_account_owner_guard import (
    environment_from_snapshot,
    evaluate_worker_entry,
)
from app.domain.multi_account.worker_runtime import (
    WorkerLifecycleState,
    WorkerRuntime,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

NOW = datetime(2026, 10, 22, 10, 0, tzinfo=UTC)  # Thursday
CAPS = SimpleNamespace(available=True, planned_risk_pct=None, daily_loss_pct=None)
SETTINGS = SimpleNamespace(
    multi_account_dispatch_enabled=True,
    multi_account_live_submit_enabled=True,
    multi_account_oms_live_order_send_enabled=False,
)
BUY = {
    "symbol": "XAUUSD",
    "side": "BUY",
    "volume": "0.01",
    "stop_loss": "3995.00",
    "take_profit": "4010.00",
}


def _snap(**over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "captured_at": NOW.isoformat(),
        "trade_mode": "demo",
        "balance": "1000",
        "equity": "1000",
        "bid": "4000.00",
        "ask": "4000.20",
        "contract_size": "100",
        "open_positions": 0,
        "commission_source": "verified_account_tariff",
        "commission_usd": "0",
        "deals_today": [],
    }
    base.update(over)
    return base


def _guard(snapshot: dict[str, object] | None, **order: object) -> tuple[str, ...]:
    o = {**BUY, **order}
    return evaluate_worker_entry(
        snapshot=snapshot,
        claimed_environment=None,
        user_id=uuid4(),
        symbol=str(o["symbol"]),
        side=str(o["side"]),
        volume=o["volume"],
        entry=None,
        stop_loss=o["stop_loss"],
        take_profit=o["take_profit"],
        now=NOW,
        user_caps=CAPS,
    ).reasons


def _codes(reasons: tuple[str, ...]) -> set[str]:
    return {r.split(":")[0] for r in reasons}


def test_compliant_entry_passes() -> None:
    assert _guard(_snap()) == ()


def test_missing_snapshot_rejects() -> None:
    assert "account_snapshot_unavailable" in _guard(None)


def test_stale_snapshot_rejects() -> None:
    old = (NOW - timedelta(seconds=120)).isoformat()
    assert "account_snapshot_stale" in _guard(_snap(captured_at=old))


@pytest.mark.parametrize(
    ("mode", "env"), [("demo", "demo"), ("contest", "demo"), ("real", "live")]
)
def test_environment_comes_from_mt5_trade_mode(mode: str, env: str) -> None:
    assert environment_from_snapshot(_snap(trade_mode=mode)) == env


def test_unknown_trade_mode_is_never_demo() -> None:
    assert environment_from_snapshot(_snap(trade_mode="")) is None
    assert "account_environment_unverified" in _guard(_snap(trade_mode=""))


def test_claimed_demo_on_a_real_account_rejects() -> None:
    result = evaluate_worker_entry(
        snapshot=_snap(trade_mode="real"),
        claimed_environment="demo",
        user_id=uuid4(),
        symbol="XAUUSD",
        side="BUY",
        volume="0.01",
        entry=None,
        stop_loss="3995",
        take_profit="4010",
        now=NOW,
        user_caps=CAPS,
    )
    assert result.environment == "live"
    assert "account_environment_mismatch" in result.reasons


def test_spread_above_045_rejects() -> None:
    assert "OWNER_MAX_SPREAD" in _codes(_guard(_snap(ask="4000.60")))


def test_rr_below_15_rejects() -> None:
    assert "OWNER_MIN_RR" in _codes(_guard(_snap(), take_profit="4005.00"))


def test_risk_above_9_percent_rejects() -> None:
    assert "OWNER_SL_RISK" in _codes(
        _guard(_snap(equity="50", balance="50"), stop_loss="3990", take_profit="4030")
    )


def test_outside_session_rejects() -> None:
    late = datetime(2026, 10, 22, 18, 0, tzinfo=UTC)
    reasons = evaluate_worker_entry(
        snapshot=_snap(captured_at=late.isoformat()),
        claimed_environment=None,
        user_id=uuid4(),
        **BUY,
        entry=None,
        now=late,
        user_caps=CAPS,
    ).reasons
    assert "OWNER_SESSION" in _codes(reasons)


def test_open_position_rejects() -> None:
    assert "OWNER_MAX_POSITIONS" in _codes(_guard(_snap(open_positions=1)))


def test_unverified_commission_rejects() -> None:
    reasons = _guard(_snap(commission_source="guess"))
    assert reasons  # unknown commission is never zero


def test_deals_unavailable_rejects() -> None:
    assert _guard(_snap(deals_today=None))


def test_daily_stop_with_loss_today_rejects() -> None:
    loss = {
        "ticket": 1,
        "time": int((NOW - timedelta(hours=1)).timestamp()),
        "type": 0,
        "entry": 1,
        "volume": "0.01",
        "profit": "-260",
        "commission": "0",
        "swap": "0",
    }
    reasons = _guard(_snap(balance="740", equity="740", deals_today=[loss]))
    assert _codes(reasons) & {"OWNER_DAILY_STOP", "OWNER_DAILY_BUDGET"}


def test_user_caps_unreadable_rejects() -> None:
    reasons = evaluate_worker_entry(
        snapshot=_snap(),
        claimed_environment=None,
        user_id=uuid4(),
        **BUY,
        entry=None,
        now=NOW,
        user_caps=SimpleNamespace(available=False),
    ).reasons
    assert "USER_RISK_UNAVAILABLE" in reasons


def _worker() -> WorkerRuntime:
    return WorkerRuntime(
        worker_id=uuid4(),
        worker_code="demo-a",
        user_id=uuid4(),
        broker_account_id=uuid4(),
        host_id=uuid4(),
        lifecycle=WorkerLifecycleState.READY,
        last_heartbeat_at=datetime.now(UTC),
        account_login_verified="123456",
        server_verified="XMGlobal-MT5 2",
        trade_allowed=True,
    )


def test_authorize_without_snapshot_never_allows_order_send() -> None:
    w = _worker()
    auth = authorize_worker_execution(
        worker=w,
        intent_id=uuid4(),
        job_payload={**BUY, "environment": "demo"},
        job_user_id=w.user_id,
        job_broker_account_id=w.broker_account_id,
        job_idempotency_key="k",
        account_environment="demo",
        settings=SETTINGS,
        now=NOW,
        user_caps=CAPS,
    )
    assert auth.order_send_allowed is False
    assert "account_snapshot_unavailable" in auth.reasons
    assert auth.environment == "live"  # unknown is treated as LIVE, never demo


def test_authorize_rejects_a_non_compliant_demo_entry() -> None:
    w = _worker()
    auth = authorize_worker_execution(
        worker=w,
        intent_id=uuid4(),
        job_payload={**BUY, "take_profit": "4001.00"},
        job_user_id=w.user_id,
        job_broker_account_id=w.broker_account_id,
        job_idempotency_key="k",
        account_environment="demo",
        settings=SETTINGS,
        account_snapshot=_snap(),
        now=NOW,
        user_caps=CAPS,
    )
    assert auth.order_send_allowed is False
    assert "OWNER_MIN_RR" in _codes(auth.reasons)


def test_paused_account_never_gets_order_send(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.application.services import robot_control_service as rc

    monkeypatch.setattr(
        rc, "entry_block", lambda **_: "ROBOT_PAUSED: new entries are blocked"
    )
    w = _worker()
    auth = authorize_worker_execution(
        worker=w,
        intent_id=uuid4(),
        job_payload=dict(BUY),
        job_user_id=w.user_id,
        job_broker_account_id=w.broker_account_id,
        job_idempotency_key="k",
        account_environment="demo",
        settings=SETTINGS,
        account_snapshot=_snap(),
        now=NOW,
        user_caps=CAPS,
    )
    assert auth.order_send_allowed is False
    assert "ROBOT_PAUSED" in auth.reasons
