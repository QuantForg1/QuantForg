"""Owner baseline 2026-11-16: pre-trade daily budget and strictest-wins caps.

Regression for the 2 November 2026 incident: on a day with no deposits the
robot kept opening entries after the realised loss was already above the
daily stop (15 entries after 48%, 29 after 25%). The final owner guard now
checks ``loss so far + floating loss + planned risk <= daily stop`` before
every new entry, blocks when today's P/L cannot be verified, and never lets
a deposit forgive a loss already taken. The account owner's own saved risk
settings can only tighten the caps.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal as D

import pytest

from app.application.services.live_account_risk_tracker import LiveAccountRiskTracker
from app.domain.institutional_trading import owner_live_limits as ol
from app.domain.institutional_trading.operations.live_prefs_tighten import (
    load_user_live_caps,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

THURSDAY = datetime(2026, 10, 22, 10, 0, tzinfo=UTC)


def _ctx(*, realized: str = "0", deposits: str = "0", balance: str, equity=None):
    bal = D(balance)
    return ol.DailyLossContext(
        trusted=True,
        realized_pnl=D(realized),
        deposits=D(deposits),
        balance=bal,
        equity=D(equity) if equity is not None else bal,
    )


def _entry(equity: str, daily, **kw: object) -> list[str]:
    # BUY 0.01: stop 1.70 + spread 0.30 = $2.00 planned; TP 3.00 -> net RR 1.50.
    base: dict[str, object] = {
        "symbol": "XAUUSD",
        "side": "BUY",
        "volume": D("0.01"),
        "entry": D("4000.00"),
        "stop_loss": D("3998.30"),
        "take_profit": D("4003.00"),
        "spread": D("0.30"),
        "contract_size": D("100"),
        "equity": D(equity),
        "commission": D("0"),
        "now": THURSDAY,
        "daily": daily,
    }
    base.update(kw)
    return ol.evaluate_owner_entry(**base)  # type: ignore[arg-type]


def _codes(reasons: list[str]) -> set[str]:
    return {r.split(":", 1)[0] for r in reasons}


# --- unknown daily P/L fails closed ------------------------------------------


def test_missing_daily_context_blocks_new_entries() -> None:
    assert "OWNER_DAILY_PNL_UNAVAILABLE" in _codes(_entry("50", None))


def test_untrusted_daily_context_blocks_new_entries() -> None:
    untrusted = ol.DailyLossContext(trusted=False, source="history_failed")
    assert "OWNER_DAILY_PNL_UNAVAILABLE" in _codes(_entry("50", untrusted))


def test_flat_trusted_day_allows_a_compliant_entry() -> None:
    assert _entry("50", _ctx(balance="50")) == []


# --- pre-trade budget --------------------------------------------------------


def test_budget_counts_the_new_entry_planned_risk() -> None:
    # Day start $50 -> stop $12.50. Lost $10.50 so far; $2.00 more fits ($12.50).
    assert _entry("39.50", _ctx(realized="-10.50", balance="39.50")) == []
    # Lost $10.51: $10.51 + $2.00 = $12.51 > $12.50 -> rejected before sending.
    reasons = _entry("39.49", _ctx(realized="-10.51", balance="39.49"))
    assert "OWNER_DAILY_BUDGET" in _codes(reasons)


def test_loss_already_above_the_stop_is_a_daily_stop() -> None:
    reasons = _entry("37.49", _ctx(realized="-12.51", balance="37.49"))
    assert "OWNER_DAILY_STOP" in _codes(reasons)


def test_floating_loss_counts_toward_the_budget() -> None:
    # Realised -$9.00 plus floating -$2.00 = $11.00; +$2.00 new = $13.00 > $12.50.
    reasons = _entry(
        "39.00",
        _ctx(realized="-9.00", balance="41.00", equity="39.00"),
    )
    assert "OWNER_DAILY_BUDGET" in _codes(reasons)


def test_deposit_raises_the_base_but_never_forgives_the_loss() -> None:
    # Start $20, lost $5.00, then deposited $20. Balance $35.
    ctx = _ctx(realized="-5.00", deposits="20.00", balance="35.00")
    assert ctx.day_start_equity == D("20.00")
    assert ctx.budget_base == D("40.00")
    assert ctx.committed_loss == D("5.00")
    # Stop is 25% of $40 = $10.00. $5.00 + $2.00 fits.
    assert _entry("35.00", ctx) == []
    # A later -$3.50: $8.50 + $2.00 = $10.50 > $10.00 -> rejected.
    later = _ctx(realized="-8.50", deposits="20.00", balance="31.50")
    assert "OWNER_DAILY_BUDGET" in _codes(_entry("31.50", later))


def test_november_2_replay_blocks_entries_after_the_daily_stop() -> None:
    """Replay of the 2 November 2026 Production journal (day start $36.85).

    Realised P/L before each of the last entries of the day, as recorded. The
    25% stop is $9.21. Every one of these entries must be refused.
    """
    start = D("36.85")
    realised_before = ["-15.71", "-18.02", "-19.39", "-21.82", "-22.83", "-25.15"]
    for realised in realised_before:
        balance = start + D(realised)
        reasons = _entry(str(balance), _ctx(realized=realised, balance=str(balance)))
        assert {"OWNER_DAILY_STOP", "OWNER_DAILY_BUDGET"} & _codes(reasons), realised


# --- strictest wins -----------------------------------------------------------


def test_user_planned_risk_tightens_the_owner_cap() -> None:
    # Equity $50: owner 9% = $4.50, user 3% = $1.50 < $2.00 planned -> rejected.
    reasons = _entry("50", _ctx(balance="50"), user_planned_risk_pct=D("3"))
    assert "OWNER_SL_RISK" in _codes(reasons)
    assert "$2.00 > $1.50" in " ".join(reasons)
    # User 5% = $2.50 >= $2.00 -> allowed.
    assert _entry("50", _ctx(balance="50"), user_planned_risk_pct=D("5")) == []


def test_user_value_above_the_owner_cap_cannot_loosen_it() -> None:
    # Planned $5.00 at $50: owner cap $4.50. A user 20% must not allow it.
    reasons = _entry(
        "50",
        _ctx(balance="50"),
        stop_loss=D("3995.30"),
        take_profit=D("4008.00"),
        user_planned_risk_pct=D("20"),
    )
    assert "OWNER_SL_RISK" in _codes(reasons)


def test_user_daily_loss_tightens_the_owner_stop() -> None:
    # User 10% of $50 = $5.00. Lost $3.50 + $2.00 = $5.50 > $5.00.
    ctx = _ctx(realized="-3.50", balance="46.50")
    assert _entry("46.50", ctx) == []
    reasons = _entry("46.50", ctx, user_daily_loss_pct=D("10"))
    assert "OWNER_DAILY_BUDGET" in _codes(reasons)
    # A user 48% cannot loosen the owner 25% stop.
    heavy = _ctx(realized="-12.51", balance="37.49")
    reasons = _entry("37.49", heavy, user_daily_loss_pct=D("48"))
    assert "OWNER_DAILY_STOP" in _codes(reasons)


def test_presend_applies_the_same_daily_budget_and_user_cap() -> None:
    kwargs = {
        "symbol": "XAUUSD",
        "side": "BUY",
        "volume": D("0.01"),
        "request_price": D("4000.00"),
        "bid": D("3999.70"),
        "ask": D("4000.00"),
        "stop_loss": D("3998.30"),
        "take_profit": D("4003.00"),
        "plan_price": D("4000.00"),
        "contract_size": D("100"),
        "equity": D("50"),
        "commission": D("0"),
        "now": THURSDAY,
    }
    assert ol.presend_owner_violations(**kwargs, daily=_ctx(balance="50")) == []
    blocked = ol.presend_owner_violations(**kwargs, daily=None)
    assert any("OWNER_DAILY_PNL_UNAVAILABLE" in r for r in blocked)
    capped = ol.presend_owner_violations(
        **kwargs, daily=_ctx(balance="50"), user_planned_risk_pct=D("3")
    )
    assert any("OWNER_SL_RISK" in r for r in capped)


# --- broker deals -> daily context ---------------------------------------------


def _deal(ticket: int, hour: int, profit: str, *, kind: int = 1, volume="0.01"):
    moment = datetime(2026, 11, 2, hour, 0, tzinfo=UTC)
    return {
        "ticket": ticket,
        "time": int(moment.timestamp()),
        "type": kind,
        "volume": volume,
        "profit": profit,
        "commission": "0",
        "swap": "0",
    }


def test_daily_context_from_deals_keeps_pre_deposit_losses() -> None:
    deals = [
        _deal(1, 2, "-4.00"),
        _deal(2, 3, "20.00", kind=2, volume="0"),  # balance deposit
        _deal(3, 4, "-1.00"),
    ]
    ctx = LiveAccountRiskTracker.daily_loss_context(
        deals,
        balance=D("45.00"),
        equity=D("45.00"),
        now=datetime(2026, 11, 2, 12, 0, tzinfo=UTC),
    )
    assert ctx.trusted is True
    assert ctx.realized_pnl == D("-5.00")
    assert ctx.deposits == D("20.00")
    assert ctx.day_start_equity == D("30.00")
    assert ctx.committed_loss == D("5.00")
    # The legacy risk P/L would forget the pre-deposit -4.00.
    legacy = LiveAccountRiskTracker.daily_pnl_from_deals(
        deals,
        now=datetime(2026, 11, 2, 12, 0, tzinfo=UTC),
        ending_balance=D("45.00"),
    )
    assert legacy == D("-1.00")


def test_daily_context_ignores_other_days() -> None:
    old = _deal(9, 2, "-30.00")
    old["time"] = int(datetime(2026, 11, 1, 22, 0, tzinfo=UTC).timestamp())
    ctx = LiveAccountRiskTracker.daily_loss_context(
        [old, _deal(10, 8, "-1.00")],
        balance=D("49.00"),
        equity=D("49.00"),
        now=datetime(2026, 11, 2, 12, 0, tzinfo=UTC),
    )
    assert ctx.realized_pnl == D("-1.00")


# --- user caps loader ---------------------------------------------------------


def test_user_caps_loader_without_durable_storage_uses_owner_caps() -> None:
    from uuid import uuid4

    caps = load_user_live_caps(uuid4())
    assert caps.available is True
    assert caps.planned_risk_pct is None
    assert caps.daily_loss_pct is None


def test_user_caps_loader_fails_closed_on_read_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uuid import uuid4

    import app.application.services.user_risk_preferences_service as prefs
    import app.infrastructure.persistence.direct_postgres as dp

    monkeypatch.setattr(dp, "direct_postgres_available", lambda: True)

    def boom(_uid):
        raise RuntimeError("db down")

    monkeypatch.setattr(prefs, "_load_active_row", boom)
    caps = load_user_live_caps(uuid4())
    assert caps.available is False
    assert "db down" in caps.reason


def test_user_caps_loader_reads_the_saved_row(monkeypatch: pytest.MonkeyPatch) -> None:
    from uuid import uuid4

    import app.application.services.user_risk_preferences_service as prefs
    import app.infrastructure.persistence.direct_postgres as dp

    monkeypatch.setattr(dp, "direct_postgres_available", lambda: True)
    monkeypatch.setattr(
        prefs,
        "_load_active_row",
        lambda _uid: {"planned_risk_pct": "5.0000", "daily_loss_pct": "20.0000"},
    )
    caps = load_user_live_caps(uuid4())
    assert caps.available is True
    assert caps.planned_risk_pct == D("5.0000")
    assert caps.daily_loss_pct == D("20.0000")


# --- execution engine wiring --------------------------------------------------


def _engine_submit(monkeypatch: pytest.MonkeyPatch, caps):
    from uuid import uuid4

    from app.application.services import institutional_execution_engine as iee
    from app.domain.institutional_trading.operations import live_prefs_tighten
    from tests.unit.test_manual_ticket_owner_limits import _engine

    monkeypatch.setattr(live_prefs_tighten, "load_user_live_caps", lambda _uid: caps)
    engine, client = _engine()
    sent: list = []
    original_send = client.order_send

    def order_send(request):
        sent.append(request)
        return original_send(request)

    monkeypatch.setattr(client, "order_send", order_send)
    intent = iee.parse_order_intent(
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        volume="0.01",
        stop_loss="2319.00",
        take_profit="2324.30",
    )
    pipeline, _decision = engine.run_submit(
        user_id=uuid4(),
        request_id=f"caps-{caps.reason}",
        intent=intent,
        connected=True,
        login=1,
        recent_decisions=[],
    )
    return pipeline, sent


def test_engine_blocks_when_the_owner_settings_cannot_be_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.domain.institutional_trading.live_trading_control import (
        reset_live_trading_controller_for_tests,
    )
    from app.domain.institutional_trading.operations.live_prefs_tighten import (
        UserLiveCaps,
    )
    from tests.unit.test_institutional_execution_engine import _allow_broker_submit

    _allow_broker_submit()
    try:
        pipeline, sent = _engine_submit(
            monkeypatch, UserLiveCaps(available=False, reason="read_failed: down")
        )
    finally:
        reset_live_trading_controller_for_tests()
    assert pipeline.outcome == "rejected"
    assert "USER_RISK_UNAVAILABLE" in pipeline.message
    assert sent == []


def test_engine_applies_the_owner_saved_planned_risk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.domain.institutional_trading.live_trading_control import (
        reset_live_trading_controller_for_tests,
    )
    from app.domain.institutional_trading.operations.live_prefs_tighten import (
        UserLiveCaps,
    )
    from tests.unit.test_institutional_execution_engine import _allow_broker_submit

    _allow_broker_submit()
    try:
        # Mock equity $10,000: 0.001% = $0.10, below the ~$2.20 planned risk.
        pipeline, sent = _engine_submit(
            monkeypatch,
            UserLiveCaps(
                available=True, planned_risk_pct=D("0.001"), reason="saved_row"
            ),
        )
    finally:
        reset_live_trading_controller_for_tests()
    assert pipeline.outcome == "rejected"
    assert "OWNER_SL_RISK" in pipeline.message
    assert sent == []
