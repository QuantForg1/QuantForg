"""Owner risk settings (2026-10-22 final): 9% planned risk, 19% daily, no DD.

Planned risk = (|entry - SL| + spread) x contract x volume <= 9% of equity.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.domain.institutional_trading import owner_live_limits as ol

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

LONDON = datetime(2026, 10, 22, 10, 0, tzinfo=UTC)
NIGHT = datetime(2026, 10, 22, 22, 0, tzinfo=UTC)


def _entry(**kw: object) -> list[str]:
    base: dict[str, object] = {
        "symbol": "XAUUSD",
        "side": "BUY",
        "volume": Decimal("0.01"),
        "entry": Decimal("4133.00"),
        "stop_loss": Decimal("4128.80"),
        "take_profit": Decimal("4140.00"),
        "spread": Decimal("0.30"),
        "contract_size": Decimal("100"),
        "equity": Decimal("50"),
        "now": LONDON,
    }
    base.update(kw)
    return ol.evaluate_owner_entry(**base)  # type: ignore[arg-type]


def _codes(reasons: list[str]) -> set[str]:
    return {r.split(":", 1)[0] for r in reasons}


# --- 9% planned-risk boundary ----------------------------------------------


def test_450_accepted_at_50_equity() -> None:
    # SL 4.20 + spread 0.30 = 4.50 x 100 x 0.01 = $4.50 = 9% of $50.
    assert _entry() == []


def test_451_rejected_at_50_equity() -> None:
    reasons = _entry(stop_loss=Decimal("4128.79"))
    assert "OWNER_SL_RISK" in _codes(reasons)
    assert "$4.51 > $4.50" in " ".join(reasons)


@pytest.mark.parametrize(
    ("equity", "cap"),
    [("50", "4.50"), ("80", "7.20"), ("33.33", "2.99"), ("120", "10.80")],
)
def test_cap_recomputes_from_equity(equity: str, cap: str) -> None:
    assert ol.max_planned_risk_usd(Decimal(equity)) == Decimal(cap)


def test_cap_dynamic_at_80_equity() -> None:
    # $6.00 planned risk: rejected at $50 equity, accepted at $80 equity.
    wide = {"stop_loss": Decimal("4127.30"), "take_profit": Decimal("4142.00")}
    assert "OWNER_SL_RISK" in _codes(_entry(**wide))
    assert _entry(**wide, equity=Decimal("80")) == []


def test_missing_equity_fails_closed() -> None:
    assert "OWNER_EQUITY_UNKNOWN" in _codes(_entry(equity=Decimal("0")))


def test_spread_counts_in_planned_risk() -> None:
    assert ol.planned_risk_usd(
        stop_distance=Decimal("4.20"),
        spread=Decimal("0.30"),
        contract_size=Decimal("100"),
        volume=Decimal("0.01"),
    ) == Decimal("4.50")


def test_no_minimum_risk_floor() -> None:
    # $1.30 planned risk (old $1.50 floor would reject) is allowed now.
    assert _entry(stop_loss=Decimal("4132.00"), take_profit=Decimal("4135.00")) == []


# --- 19% daily loss, no overall drawdown ------------------------------------


def test_daily_cap_is_19_pct_of_day_start() -> None:
    assert ol.daily_loss_cap_usd(Decimal("50")) == Decimal("9.50")
    assert ol.daily_loss_cap_usd(Decimal("80")) == Decimal("15.20")


def test_daily_boundary() -> None:
    # Day started at $50: a $9.50 loss is at the cap (allowed), $9.51 blocks.
    assert not ol.daily_loss_exceeded(
        daily_pnl=Decimal("-9.50"), base_now=Decimal("40.50")
    )
    assert ol.daily_loss_exceeded(daily_pnl=Decimal("-9.51"), base_now=Decimal("40.49"))


def test_no_independent_overall_drawdown_limit() -> None:
    from app.application.services.risk_engine import RiskEngine
    from app.domain.entities.risk_engine import RiskEngineConfig

    cfg = RiskEngineConfig()
    assert cfg.max_drawdown_pct == Decimal("0")
    # Disabled limit -> "n/a", never "fail", even at an 80% drawdown.
    assert RiskEngine._limit_status(Decimal("80"), cfg.max_drawdown_pct) == "n/a"


def test_weekly_and_monthly_sit_above_one_daily_stop() -> None:
    from app.domain.entities.risk_engine import RiskEngineConfig

    cfg = RiskEngineConfig()
    assert cfg.max_weekly_loss_pct == ol.OWNER_WEEKLY_LOSS_PCT == Decimal("38.0")
    assert cfg.max_monthly_loss_pct == ol.OWNER_MONTHLY_LOSS_PCT == Decimal("57.0")
    # One maximum loss (9%) or one full daily stop (19%) never blocks the week.
    assert (
        ol.OWNER_WEEKLY_LOSS_PCT
        > ol.OWNER_DAILY_LOSS_PCT
        > ol.OWNER_MAX_PLANNED_RISK_PCT
    )


# --- Stop loss policy --------------------------------------------------------


def test_stop_is_max_of_atr_and_structure() -> None:
    assert ol.owner_stop_distance(
        atr=Decimal("1.2"), structure_distance=None
    ) == Decimal("1.80")
    assert ol.owner_stop_distance(
        atr=Decimal("1.2"), structure_distance=Decimal("1.5")
    ) == Decimal("1.80")  # never narrower than 1.5 x ATR
    assert ol.owner_stop_distance(
        atr=Decimal("1.2"), structure_distance=Decimal("3.6")
    ) == Decimal("3.6")  # beyond structure when it is further away
    assert ol.owner_stop_distance(atr=None, structure_distance=Decimal("3.0")) is None


def test_structure_targets_place_stop_beyond_m1_structure_plus_spread() -> None:
    from app.domain.institutional_trading.ai_scalping.structure_targets import (
        compute_structure_targets,
    )
    from app.domain.institutional_trading.decision_models import TradeDirection

    m1 = SimpleNamespace(last_swing_low=Decimal("4129.00"), swings=[])
    snapshot = SimpleNamespace(
        structure_by_tf={"M1": m1},
        spread=Decimal("0.30"),
        order_blocks=None,
        fair_value_gaps=None,
        primary_structure=None,
        liquidity=None,
    )
    targets = compute_structure_targets(
        snapshot,  # type: ignore[arg-type]
        direction=TradeDirection.BUY,
        entry=Decimal("4133.00"),
        atr=Decimal("1.2"),
    )
    # Structure 4.00 below entry + 0.30 spread = 4.30 > 1.5 x 1.2 = 1.80.
    assert targets.stop_distance == Decimal("4.30")
    assert targets.stop_loss == Decimal("4128.70")


def test_wide_structure_stop_means_no_trade_not_a_smaller_stop() -> None:
    # The strategy stop that blocked production on 2026-10-22 (7.78) is never
    # shrunk: at $50 equity it is simply rejected.
    reasons = _entry(stop_loss=Decimal("4125.22"), take_profit=Decimal("4150.00"))
    assert "OWNER_SL_RISK" in _codes(reasons)


# --- Symbol, volume, session, spread, RR ------------------------------------


@pytest.mark.parametrize("symbol", ["EURUSD", "XAGUSD", "BTCUSD"])
def test_non_gold_rejected(symbol: str) -> None:
    assert "OWNER_GOLD_ONLY" in _codes(_entry(symbol=symbol))


@pytest.mark.parametrize("symbol", ["XAUUSD", "XAUUSD_i", "XAUUSD_I"])
def test_gold_variants_accepted(symbol: str) -> None:
    assert _entry(symbol=symbol) == []


def test_volume_above_owner_max_rejected() -> None:
    assert "OWNER_MAX_LOT" in _codes(_entry(volume=Decimal("0.02")))


def test_outside_session_rejected() -> None:
    assert "OWNER_SESSION" in _codes(_entry(now=NIGHT))
    assert ol.in_owner_session(datetime(2026, 10, 22, 7, 0, tzinfo=UTC))
    assert not ol.in_owner_session(datetime(2026, 10, 22, 17, 0, tzinfo=UTC))


def test_spread_above_045_rejected() -> None:
    assert "OWNER_MAX_SPREAD" in _codes(
        _entry(spread=Decimal("0.46"), stop_loss=Decimal("4130.00"))
    )


def test_missing_stop_loss_or_spread_rejected() -> None:
    assert "OWNER_SL_REQUIRED" in _codes(_entry(stop_loss=None))
    assert "OWNER_SPREAD_UNKNOWN" in _codes(_entry(spread=None))


def test_rr_after_spread() -> None:
    assert "OWNER_MIN_RR" in _codes(_entry(take_profit=Decimal("4139.00")))


# --- Loss streak pause until the next UTC day --------------------------------


def test_three_losses_pause_until_next_utc_day_then_reset() -> None:
    from app.domain.institutional_trading.live_trading_control import (
        reset_live_trading_controller_for_tests,
    )

    ctrl = reset_live_trading_controller_for_tests()
    for _ in range(3):
        ctrl.note_closed_trade(loss=True, volume=Decimal("0.01"))
    until = ctrl.loss_streak_cooldown_until
    assert until is not None
    assert until == ol.next_utc_day_start()
    assert ctrl.loss_streak_cooldown_active() is True
    # Next UTC day: the pause ends and the streak resets (no permanent block).
    assert ctrl.loss_streak_cooldown_active(now=until + timedelta(seconds=1)) is False
    assert ctrl.consecutive_losses == 0
    reset_live_trading_controller_for_tests()


def test_no_martingale_volume_after_losses() -> None:
    # Volume never rises after a loss: the owner guard caps every entry at 0.01.
    assert "OWNER_MAX_LOT" in _codes(_entry(volume=Decimal("0.02")))
    assert Decimal("0.01") == ol.OWNER_MAX_LOT
