"""Owner risk baseline (2026-11-16): 9% planned risk, 25% daily, no DD.

Planned risk = (|entry - SL| + spread + slippage) x contract x volume
+ known commission <= 9% of equity. Unknown commission is rejected.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.services.risk_engine import RiskCheckInput, RiskEngine
from app.domain.entities.mt5_portfolio import AccountSnapshot
from app.domain.enums.risk import PositionSizingMethod, RiskDecision
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
        # The fixture declares a known zero. Unknown commission is rejected.
        "commission": Decimal("0"),
        # A flat, trusted UTC day. Missing daily P/L is rejected.
        "daily": ol.DailyLossContext(
            trusted=True, balance=Decimal("50"), equity=Decimal("50")
        ),
    }
    base.update(kw)
    return ol.evaluate_owner_entry(**base)  # type: ignore[arg-type]


def _codes(reasons: list[str]) -> set[str]:
    return {r.split(":", 1)[0] for r in reasons}


# --- 9% planned-risk boundary ----------------------------------------------


def test_exact_9_percent_of_50_is_allowed() -> None:
    # SL 4.20 + spread 0.30 = $4.50 = 9% of $50. Net RR 7.00 / 4.50 = 1.56.
    assert _entry(stop_loss=Decimal("4128.80"), take_profit=Decimal("4140.00")) == []


def test_one_cent_over_9_percent_is_rejected() -> None:
    reasons = _entry(stop_loss=Decimal("4128.79"), take_profit=Decimal("4140.00"))
    assert "OWNER_SL_RISK" in _codes(reasons)
    assert "$4.51 > $4.50" in " ".join(reasons)


def test_unknown_commission_rejects_without_a_zero_fee_pass() -> None:
    reasons = _entry(commission=None)
    assert "OWNER_COMMISSION_UNKNOWN" in _codes(reasons)
    assert "OWNER_SL_RISK" not in _codes(reasons)


def test_known_commission_can_push_a_ticket_over_9_percent() -> None:
    # Exact $4.50 geometry plus $0.50 commission ceilings above the cap.
    reasons = _entry(
        stop_loss=Decimal("4128.80"),
        take_profit=Decimal("4141.00"),
        commission=Decimal("0.50"),
    )
    assert "OWNER_SL_RISK" in _codes(reasons)
    assert "$5.00 > $4.50" in " ".join(reasons)


@pytest.mark.parametrize(
    ("equity", "cap"),
    [("50", "4.50"), ("80", "7.20"), ("33.33", "2.99"), ("120", "10.80")],
)
def test_cap_recomputes_from_equity(equity: str, cap: str) -> None:
    assert ol.max_planned_risk_usd(Decimal(equity)) == Decimal(cap)


def test_cap_dynamic_at_80_equity() -> None:
    # $4.51 planned risk: rejected at $50 equity, accepted at $80 equity.
    wide = {"stop_loss": Decimal("4128.79"), "take_profit": Decimal("4140.00")}
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


def test_reported_geometry_above_the_9_percent_cap() -> None:
    """Equity 29.86 at 9% floors to $2.68. The lot is already the minimum.

    The correction is a tighter stop, not a smaller volume and not a higher cap.
    """
    assert ol.max_planned_risk_usd(Decimal("29.86")) == Decimal("2.68")
    assert ol.planned_risk_usd(
        stop_distance=Decimal("2.380"),
        spread=Decimal("0.310"),
        contract_size=Decimal("100"),
        volume=Decimal("0.01"),
    ) == Decimal("2.69")
    reasons = _entry(
        equity=Decimal("29.86"),
        entry=Decimal("4000"),
        stop_loss=Decimal("3997.620"),
        take_profit=Decimal("4010"),
        spread=Decimal("0.310"),
    )
    text = reasons[0]
    assert text.startswith(
        "OWNER_SL_RISK: planned risk $2.69 > $2.68 (9.0% of equity 29.86)"
    )
    assert "stop 2.380 + spread 0.310" in text
    assert "volume 0.01" in text
    assert "contract 100" in text
    assert "Tighten the stop to 2.370" in text
    assert (
        _entry(
            equity=Decimal("29.86"),
            entry=Decimal("4000"),
            stop_loss=Decimal("3997.630"),
            take_profit=Decimal("4010"),
            spread=Decimal("0.310"),
        )
        == []
    )


def test_risk_is_never_rounded_down_to_the_cap() -> None:
    # 2.681 would half-even to 2.68 and pass. Ceiling keeps it at 2.69.
    assert ol.planned_risk_usd(
        stop_distance=Decimal("2.681"),
        spread=Decimal("0"),
        contract_size=Decimal("100"),
        volume=Decimal("0.01"),
    ) == Decimal("2.69")
    assert "OWNER_SL_RISK" in _codes(
        _entry(
            equity=Decimal("29.86"),
            entry=Decimal("4000"),
            stop_loss=Decimal("3997.319"),
            take_profit=Decimal("4010"),
            spread=Decimal("0"),
        )
    )


def test_exact_cap_passes_and_one_cent_over_fails() -> None:
    assert ol.planned_risk_usd(
        stop_distance=Decimal("2.68"),
        spread=Decimal("0"),
        contract_size=Decimal("100"),
        volume=Decimal("0.01"),
    ) == Decimal("2.68")
    assert (
        _entry(
            equity=Decimal("29.86"),
            entry=Decimal("4000"),
            stop_loss=Decimal("3997.32"),
            take_profit=Decimal("4010"),
            spread=Decimal("0"),
        )
        == []
    )
    assert "OWNER_SL_RISK" in _codes(
        _entry(
            equity=Decimal("29.86"),
            entry=Decimal("4000"),
            stop_loss=Decimal("3997.31"),
            take_profit=Decimal("4010"),
            spread=Decimal("0"),
        )
    )


def test_buy_and_sell_use_the_same_monetary_risk() -> None:
    common = {
        "equity": Decimal("29.86"),
        "entry": Decimal("4000"),
        "spread": Decimal("0.310"),
        "contract_size": Decimal("100"),
        "volume": Decimal("0.01"),
    }
    buy = _entry(
        **common,
        side="BUY",
        stop_loss=Decimal("3997.620"),
        take_profit=Decimal("4010"),
    )
    sell = _entry(
        **common,
        side="SELL",
        stop_loss=Decimal("4002.380"),
        take_profit=Decimal("3990"),
    )
    assert buy[0].startswith("OWNER_SL_RISK: planned risk $2.69 > $2.68")
    assert sell[0].startswith("OWNER_SL_RISK: planned risk $2.69 > $2.68")


def test_tick_value_matches_contract_size_100() -> None:
    assert ol.price_unit_value(
        contract_size=Decimal("100"),
        tick_size=Decimal("0.001"),
        tick_value=Decimal("0.1"),
    ) == Decimal("100")
    assert ol.planned_risk_usd(
        stop_distance=Decimal("2.710"),
        spread=Decimal("0"),
        contract_size=ol.price_unit_value(
            contract_size=Decimal("0"),
            tick_size=Decimal("0.001"),
            tick_value=Decimal("0.1"),
        ),
        volume=Decimal("0.01"),
    ) == Decimal("2.71")


def test_slippage_and_commission_count_only_when_supplied() -> None:
    bare = ol.planned_risk_usd(
        stop_distance=Decimal("2.40"),
        spread=Decimal("0.28"),
        contract_size=Decimal("100"),
        volume=Decimal("0.01"),
    )
    assert bare == Decimal("2.68")
    with_slip = ol.planned_risk_usd(
        stop_distance=Decimal("2.40"),
        spread=Decimal("0.28"),
        contract_size=Decimal("100"),
        volume=Decimal("0.01"),
        slippage=Decimal("0.01"),
    )
    assert with_slip == Decimal("2.69")
    with_fee = ol.planned_risk_usd(
        stop_distance=Decimal("2.40"),
        spread=Decimal("0.20"),
        contract_size=Decimal("100"),
        volume=Decimal("0.01"),
        commission=Decimal("0.05"),
    )
    assert with_fee == Decimal("2.65")


def test_minimum_lot_above_the_cap_names_the_constraint() -> None:
    reasons = _entry(
        equity=Decimal("29.86"),
        entry=Decimal("4000"),
        stop_loss=Decimal("3999"),
        take_profit=Decimal("4010"),
        spread=Decimal("0.20"),
        commission=Decimal("6.00"),
    )
    text = " ".join(reasons)
    assert "OWNER_SL_RISK" in text
    assert "No smaller lot is allowed" in text
    assert (
        ol.maximum_affordable_stop_distance(
            cap=Decimal("2.68"),
            spread=Decimal("0.20"),
            contract_size=Decimal("100"),
            volume=Decimal("0.01"),
            commission=Decimal("6.00"),
        )
        is None
    )


def test_risk_engine_uses_the_same_spread_inclusive_cap() -> None:
    engine = RiskEngine()
    result = engine.evaluate(
        RiskCheckInput(
            user_id=uuid4(),
            request_id="owner-sl-271",
            symbol="XAUUSD",
            side="buy",
            requested_lots=Decimal("0.01"),
            stop_loss_distance=Decimal("2.380"),
            sizing_method=PositionSizingMethod.FIXED_LOT,
            entry_price=Decimal("10"),
            spread=Decimal("0.310"),
            contract_size=Decimal("100"),
            tick_size=Decimal("0.001"),
            tick_value=Decimal("0.1"),
            commission=Decimal("0"),
        ),
        account=AccountSnapshot(
            login=1,
            balance=Decimal("29.86"),
            equity=Decimal("29.86"),
            margin=Decimal("0"),
            free_margin=Decimal("29.86"),
            margin_level=Decimal("0"),
            profit=Decimal("0"),
            leverage=1000,
        ),
        positions=[],
    )
    assert result.decision is RiskDecision.REJECT
    assert any(
        r.startswith("OWNER_SL_RISK: planned risk $2.69 > $2.68")
        for r in result.reasons
    )
    assert result.checks.get("owner_planned_risk") is False


def test_risk_engine_rejects_unknown_commission_before_a_dollar_pass() -> None:
    engine = RiskEngine()
    result = engine.evaluate(
        RiskCheckInput(
            user_id=uuid4(),
            request_id="owner-fee-unknown",
            symbol="XAUUSD",
            side="buy",
            requested_lots=Decimal("0.01"),
            stop_loss_distance=Decimal("1.000"),
            sizing_method=PositionSizingMethod.FIXED_LOT,
            entry_price=Decimal("4000"),
            spread=Decimal("0.20"),
            contract_size=Decimal("100"),
            commission=None,
        ),
        account=AccountSnapshot(
            login=1,
            balance=Decimal("50"),
            equity=Decimal("50"),
            margin=Decimal("0"),
            free_margin=Decimal("50"),
            margin_level=Decimal("0"),
            profit=Decimal("0"),
            leverage=1000,
        ),
        positions=[],
    )
    assert result.decision is RiskDecision.REJECT
    assert any("OWNER_COMMISSION_UNKNOWN" in r for r in result.reasons)
    assert not any(r.startswith("OWNER_SL_RISK") for r in result.reasons)


def test_safety_snapshot_distance_rejects_above_the_cap() -> None:
    # Stored safety tick: distance 2.877 + spread 0.444 = 3.321 → ceiling $3.33.
    assert ol.planned_risk_usd(
        stop_distance=Decimal("2.877"),
        spread=Decimal("0.444"),
        contract_size=Decimal("100"),
        volume=Decimal("0.01"),
    ) == Decimal("3.33")
    assert "OWNER_SL_RISK" in _codes(
        _entry(
            equity=Decimal("29.86"),
            entry=Decimal("4000"),
            stop_loss=Decimal("3994.000"),
            take_profit=Decimal("4010"),
            spread=Decimal("0.444"),
        )
    )


def test_no_minimum_risk_floor() -> None:
    # $1.30 planned risk (old $1.50 floor would reject) is allowed now.
    assert _entry(stop_loss=Decimal("4132.00"), take_profit=Decimal("4135.00")) == []


# --- 25% daily loss, no overall drawdown ------------------------------------


def test_daily_cap_is_25_pct_of_day_start() -> None:
    assert ol.daily_loss_cap_usd(Decimal("50")) == Decimal("12.50")
    assert ol.daily_loss_cap_usd(Decimal("80")) == Decimal("20.00")


def test_daily_boundary() -> None:
    # Day started at $50: a $12.50 loss is at the cap (allowed), $12.51 blocks.
    assert not ol.daily_loss_exceeded(
        daily_pnl=Decimal("-12.50"), base_now=Decimal("37.50")
    )
    assert ol.daily_loss_exceeded(
        daily_pnl=Decimal("-12.51"), base_now=Decimal("37.49")
    )


def test_no_independent_overall_drawdown_limit() -> None:
    from app.application.services.risk_engine import RiskEngine
    from app.domain.entities.risk_engine import RiskEngineConfig

    cfg = RiskEngineConfig()
    assert cfg.max_drawdown_pct == Decimal("0")
    # Disabled limit -> "n/a", never "fail", even at an 80% drawdown.
    assert RiskEngine._limit_status(Decimal("80"), cfg.max_drawdown_pct) == "n/a"


def test_weekly_and_monthly_limits_are_disabled() -> None:
    from app.domain.entities.risk_engine import RiskEngineConfig

    cfg = RiskEngineConfig()
    # Owner 2026-10-23: only the daily stop applies (0 = disabled).
    assert cfg.max_weekly_loss_pct == ol.OWNER_WEEKLY_LOSS_PCT == Decimal("0")
    assert cfg.max_monthly_loss_pct == ol.OWNER_MONTHLY_LOSS_PCT == Decimal("0")


# --- Stop loss policy --------------------------------------------------------


def test_stop_is_max_of_atr_and_structure() -> None:
    assert ol.owner_stop_distance(
        atr=Decimal("1.2"), structure_distance=None
    ) == Decimal("1.20")
    assert ol.owner_stop_distance(
        atr=Decimal("1.2"), structure_distance=Decimal("1.0")
    ) == Decimal("1.20")  # never narrower than 1.00 x ATR
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
    # Structure 4.00 below entry + 0.30 spread = 4.30 > 1.00 x 1.2 = 1.20.
    assert targets.stop_distance == Decimal("4.30")
    assert targets.stop_loss == Decimal("4128.70")


def test_wide_structure_stop_is_not_shrunk_to_force_a_fill() -> None:
    # Distance 3.90 + spread 0.30 = $4.20, inside 9% of $50 ($4.50).
    assert _entry(stop_loss=Decimal("4129.10"), take_profit=Decimal("4150.00")) == []
    # Distance 11.00 + spread 0.30 = $11.30 is rejected. The stop stays 11.00.
    reasons = _entry(stop_loss=Decimal("4122.00"), take_profit=Decimal("4150.00"))
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


def test_entries_outside_the_owner_desk_hours_are_rejected() -> None:
    assert "OWNER_SESSION" in _codes(_entry(now=NIGHT))
    assert ol.in_owner_session(datetime(2026, 10, 22, 7, 0, tzinfo=UTC))
    assert ol.in_owner_session(datetime(2026, 10, 22, 16, 59, tzinfo=UTC))
    assert not ol.in_owner_session(datetime(2026, 10, 22, 6, 59, tzinfo=UTC))
    assert not ol.in_owner_session(datetime(2026, 10, 22, 17, 0, tzinfo=UTC))
    assert not ol.in_owner_session(NIGHT)
    # Saturday 2026-10-24 and Sunday 2026-10-25 are closed all day.
    assert not ol.in_owner_session(datetime(2026, 10, 24, 10, 0, tzinfo=UTC))
    assert not ol.in_owner_session(datetime(2026, 10, 25, 10, 0, tzinfo=UTC))


def test_spread_above_0_45_rejected() -> None:
    assert "OWNER_MAX_SPREAD" in _codes(
        _entry(spread=Decimal("0.46"), stop_loss=Decimal("4130.00"))
    )


def test_missing_stop_loss_or_spread_rejected() -> None:
    assert "OWNER_SL_REQUIRED" in _codes(_entry(stop_loss=None))
    assert "OWNER_SPREAD_UNKNOWN" in _codes(_entry(spread=None))


def test_rr_after_spread() -> None:
    assert "OWNER_MIN_RR" in _codes(_entry(take_profit=Decimal("4133.80")))


# --- No loss-streak pause (owner 2026-10-23) ----------------------------------


def test_losing_streak_never_pauses_entries() -> None:
    from app.domain.institutional_trading.live_trading_control import (
        reset_live_trading_controller_for_tests,
    )

    assert ol.OWNER_MAX_CONSECUTIVE_LOSSES == 0
    ctrl = reset_live_trading_controller_for_tests()
    for _ in range(5):
        ctrl.note_closed_trade(loss=True, volume=Decimal("0.01"))
    assert ctrl.consecutive_losses == 5  # still counted for reporting
    assert ctrl.loss_streak_cooldown_until is None
    assert ctrl.loss_streak_cooldown_active() is False
    reset_live_trading_controller_for_tests()


def test_no_martingale_volume_after_losses() -> None:
    # Volume never rises after a loss: the owner guard caps every entry at 0.01.
    assert "OWNER_MAX_LOT" in _codes(_entry(volume=Decimal("0.02")))
    from app.domain.institutional_trading.runtime_policy import active_max_lot

    assert Decimal("0.01") == active_max_lot()  # installed former-baseline profile


# --- Persisted Live Trading Control profile follows the owner limits ----------


def test_stale_persisted_ltc_profile_shows_and_enforces_owner_limits() -> None:
    from app.domain.institutional_trading.live_trading_control import (
        LiveTradingRiskConfig,
    )

    # Exact operator profile still stored in production ops state (2026-10-23).
    stale = {
        "min_score": "70",
        "max_spread": "1.50",
        "max_slippage": "0.50",
        "min_reward_risk": "1.20",
        "max_daily_loss_pct": "3.00",
        "max_open_positions": 1,
        "risk_per_trade_pct": "0.50",
        "max_consecutive_losses": 2,
    }
    # Since 2026-11-18 the per-user values come from the installed profile
    # (here the former baseline), whatever the stale stored values say.
    cfg = LiveTradingRiskConfig.from_dict(stale).with_active_profile()
    assert cfg.risk_per_trade_pct == Decimal("9.0")
    assert cfg.max_daily_loss_pct == Decimal("25.0")
    assert cfg.max_consecutive_losses == 0  # no loss-streak pause
    assert cfg.min_reward_risk == Decimal("1.50")
    assert cfg.max_spread == Decimal("0.45")
    assert cfg.max_open_positions == 1
    # Signal quality is a per-user profile value (75 in this profile); the
    # operator-only slippage setting is kept.
    assert cfg.min_score == Decimal("75")
    assert cfg.max_slippage == Decimal("0.50")
    shown = cfg.to_dict()
    assert shown["max_daily_loss_pct"] == "25.0"
    assert shown["risk_per_trade_pct"] == "9.0"
