"""Owner live limits: 9% planned risk, 25% daily stop, entry guard."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import ROUND_DOWN, Decimal

import pytest

from app.application.services.risk_engine import RiskEngine
from app.domain.entities.mt5_portfolio import AccountSnapshot
from app.domain.entities.risk_engine import RiskEngineConfig
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    AiScalpingConfig,
    scalping_ite_config,
)
from app.domain.institutional_trading.ai_scalping.profiles.scalping_v1 import (
    SCALPING_V1,
    align_live_scalp_cap,
)
from app.domain.institutional_trading.config import (
    DEFAULT_ITE_CONFIG,
    MAX_DAILY_LOSS_CEILING_PCT,
    MAX_DAILY_LOSS_PCT,
    MAX_PLANNED_SL_RISK_USD,
    MIN_PLANNED_RISK_USD,
    MIN_REWARD_RISK,
    TARGET_PLANNED_RISK_USD,
    ITEConfig,
)
from app.domain.institutional_trading.micro_account_mode import MicroAccountProfile
from app.domain.institutional_trading.operations.daily_loss_lock import (
    utc_daily_loss_exceeded,
)
from app.domain.institutional_trading.owner_live_limits import (
    OWNER_MAX_OPEN_POSITIONS,
    OWNER_MAX_SL_RISK_USD,
    OWNER_RISK_REFERENCE_USD,
    DailyLossContext,
    daily_loss_cap_pct,
    daily_loss_cap_usd,
    daily_loss_exceeded,
    evaluate_owner_entry,
    max_sl_risk_usd,
)

pytestmark = pytest.mark.unit

D = Decimal


def _account(balance: str) -> AccountSnapshot:
    bal = D(balance)
    return AccountSnapshot(
        login=1,
        balance=bal,
        equity=bal,
        margin=D("0"),
        free_margin=bal,
        margin_level=D("0"),
        profit=D("0"),
        leverage=1000,
    )


def _entry(**overrides: object) -> list[str]:
    # SELL 0.01 at 4116.43, SL 1.60 away (planned $1.98 incl. spread), TP 3.50
    # away -> RR 3.50/1.98 = 1.77. Equity $50.84 -> 9% cap $4.57.
    args: dict[str, object] = {
        "symbol": "XAUUSD_i",
        "side": "sell",
        "volume": D("0.01"),
        "entry": D("4116.43"),
        "stop_loss": D("4118.03"),
        "take_profit": D("4112.93"),
        "spread": D("0.38"),
        "contract_size": D("100"),
        "equity": D("50.84"),
        # Fixture declares a known zero. Unknown commission is rejected.
        "commission": D("0"),
        # Thursday 10:00 UTC, inside the owner Mon-Fri 07:00-17:00 window.
        "now": datetime(2026, 10, 22, 10, 0, tzinfo=UTC),
        "daily": DailyLossContext(trusted=True, balance=D("50.84"), equity=D("50.84")),
    }
    args.update(overrides)
    return evaluate_owner_entry(**args)  # type: ignore[arg-type]


# --- Ceilings: no 80% values anywhere, configs can be stricter, never looser ---


def test_owner_constants_replace_80_percent_caps() -> None:
    assert D("30.0") == MAX_DAILY_LOSS_PCT
    assert D("50.0") == MAX_DAILY_LOSS_CEILING_PCT
    # Static values follow the reference capital; live checks use equity.
    reference_trade = (OWNER_RISK_REFERENCE_USD * D("15") / D("100")).quantize(
        D("0.01"), rounding=ROUND_DOWN
    )
    assert reference_trade == MAX_PLANNED_SL_RISK_USD
    assert reference_trade == TARGET_PLANNED_RISK_USD
    assert MIN_PLANNED_RISK_USD == D("0") < TARGET_PLANNED_RISK_USD
    assert D("1.50") == MIN_REWARD_RISK
    assert MicroAccountProfile().hard_max_risk_pct == D("9.0")


def test_default_configs_respect_owner_limits() -> None:
    assert DEFAULT_ITE_CONFIG.max_daily_loss_pct <= MAX_DAILY_LOSS_CEILING_PCT
    assert DEFAULT_ITE_CONFIG.risk_per_trade_pct <= D("9.0")
    assert DEFAULT_ITE_CONFIG.max_open_trades == OWNER_MAX_OPEN_POSITIONS
    assert SCALPING_V1.max_open_trades == 10  # static ceiling
    assert SCALPING_V1.max_entries_per_cycle == 1
    assert DEFAULT_AI_SCALPING_CONFIG.max_open_trades == 10
    assert DEFAULT_AI_SCALPING_CONFIG.max_entries_per_cycle == 1
    assert AiScalpingConfig().max_open_trades == 10
    assert scalping_ite_config().max_open_trades == 10
    cfg = RiskEngineConfig()
    # Built under the installed (former-baseline) profile.
    assert cfg.max_lot == D("0.01")
    assert cfg.max_open_positions == 1
    assert cfg.max_consecutive_losses == 0  # no loss-streak pause (2026-10-23)
    assert cfg.cooldown_minutes_after_loss_streak == 24 * 60


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_daily_loss_pct", D("50.01")),
        ("max_daily_loss_pct", D("80.0")),
        ("risk_per_trade_pct", D("25.01")),
        ("max_open_trades", 11),
    ],
)
def test_ite_config_rejects_values_above_owner_ceilings(
    field: str, value: object
) -> None:
    with pytest.raises(ValueError):
        ITEConfig(**{field: value})  # type: ignore[arg-type]


def test_ite_config_accepts_the_owner_ceilings() -> None:
    cfg = ITEConfig(
        max_daily_loss_pct=D("25"),
        risk_per_trade_pct=D("9"),
        max_planned_sl_risk_usd=OWNER_MAX_SL_RISK_USD,
        max_open_trades=OWNER_MAX_OPEN_POSITIONS,
    )
    assert cfg.max_open_trades == OWNER_MAX_OPEN_POSITIONS


def test_ite_config_rejects_planned_risk_above_the_reference_cap() -> None:
    with pytest.raises(ValueError):
        ITEConfig(max_planned_sl_risk_usd=OWNER_MAX_SL_RISK_USD + D("0.01"))


def test_live_scalp_cap_never_exceeds_owner_maximum() -> None:
    for current in (1, 3, 5, 10, 50):
        assert align_live_scalp_cap(current, trading_mode="scalping") == (
            1  # the installed profile's cap
        )
    assert align_live_scalp_cap(1, trading_mode="alpha") == 1
    assert align_live_scalp_cap(3, trading_mode="alpha") == 1
    assert align_live_scalp_cap(10, trading_mode="alpha") == 1
    assert align_live_scalp_cap(50, trading_mode="alpha") == 1


# --- Daily stop: 25% of the UTC day's starting equity ---


@pytest.mark.parametrize(
    "sod,expected",
    [
        ("50.84", "12.71"),
        ("20.00", "5.00"),
        ("1000", "250.00"),
    ],
)
def test_daily_loss_cap_usd(sod: str, expected: str) -> None:
    assert daily_loss_cap_usd(D(sod)) == D(expected)


def test_daily_loss_at_cap_does_not_block_and_one_cent_over_does() -> None:
    # Start of day 50.84 -> cap $12.71. Equal to the cap does not halt.
    assert daily_loss_exceeded(daily_pnl=D("-12.71"), base_now=D("38.13")) is False
    assert daily_loss_exceeded(daily_pnl=D("-12.72"), base_now=D("38.12")) is True


def test_twenty_five_percent_boundary_on_larger_account() -> None:
    # SOD 1000 -> cap $250. One cent over blocks; the exact cap does not.
    assert daily_loss_exceeded(daily_pnl=D("-250.01"), base_now=D("749.99")) is True
    assert daily_loss_exceeded(daily_pnl=D("-250.00"), base_now=D("750.00")) is False


def test_utc_lock_uses_owner_daily_stop() -> None:
    assert utc_daily_loss_exceeded(
        daily_pnl=D("-15.26"),
        balance=D("35.58"),
        equity=D("35.58"),
        max_daily_loss_pct=MAX_DAILY_LOSS_PCT,
    )
    assert not utc_daily_loss_exceeded(
        daily_pnl=D("-1.60"),
        balance=D("49.24"),
        equity=D("49.24"),
        max_daily_loss_pct=MAX_DAILY_LOSS_PCT,
    )


def test_risk_engine_drawdown_blocks_above_owner_daily_stop() -> None:
    engine = RiskEngine()
    _s, reasons, _w = engine.evaluate_drawdown(_account("35.58"), daily_pnl=D("-15.26"))
    assert any("owner daily stop" in r for r in reasons)
    _s, reasons_ok, _w = engine.evaluate_drawdown(
        _account("49.24"), daily_pnl=D("-1.60")
    )
    assert not any("daily loss" in r for r in reasons_ok)


def test_daily_loss_cap_pct_matches_usd_stop() -> None:
    pct = daily_loss_cap_pct(daily_pnl=D("0"), base_now=D("50.84"))
    assert (D("50.84") * pct / 100).quantize(D("0.01")) == D("12.71")


# --- Per-trade planned-risk cap: 9% of equity ---


def test_max_sl_risk_usd() -> None:
    assert max_sl_risk_usd(D("50.84")) == D("4.57")
    assert max_sl_risk_usd(D("150")) == D("13.50")


# --- Final owner entry guard ---


def test_valid_gold_entry_passes() -> None:
    assert _entry() == []


def test_production_order_of_2026_10_20_is_rejected() -> None:
    # SELL XAUUSD 0.02 sent at 23:37:07Z: 0.02 lot, $9.22 SL risk, RR ~1.08.
    # Under the owner baseline the lot, the 9% cap and the 1.50 RR floor
    # each reject it on their own.
    reasons = _entry(
        symbol="XAUUSD",
        volume=D("0.02"),
        stop_loss=D("4120.66"),
        take_profit=D("4111.45"),
    )
    codes = {r.split(":")[0] for r in reasons}
    assert "OWNER_MAX_LOT" in codes
    assert "OWNER_SL_RISK" in codes
    assert "OWNER_MIN_RR" in codes


def test_volume_002_is_rejected() -> None:
    assert any(r.startswith("OWNER_MAX_LOT") for r in _entry(volume=D("0.02")))


def test_planned_risk_one_cent_over_9_percent_is_rejected() -> None:
    # Equity 50.84 -> cap $4.57. SL 4.19 + spread 0.38 = $4.57 allowed;
    # SL 4.20 + 0.38 = $4.58 rejected. TP far enough for owner RR 1.50.
    assert any(
        r.startswith("OWNER_SL_RISK")
        for r in _entry(stop_loss=D("4120.63"), take_profit=D("4101.00"))
    )
    assert _entry(stop_loss=D("4120.62"), take_profit=D("4101.00")) == []


def test_reward_risk_below_1_50_after_spread_rejected() -> None:
    # SL 1.60, TP 2.96: 2.96 / (1.60 + 0.38) = 1.4949 < 1.50
    assert any(r.startswith("OWNER_MIN_RR") for r in _entry(take_profit=D("4113.47")))


def test_reward_risk_counts_spread_once_boundary() -> None:
    # SL $2.00 + spread 0.44 -> net loss 2.44; min TP distance 3.66 (RR 1.50).
    kw = {"stop_loss": D("4118.43"), "spread": D("0.44")}
    assert _entry(take_profit=D("4112.77"), **kw) == []
    assert any(
        r.startswith("OWNER_MIN_RR") for r in _entry(take_profit=D("4112.771"), **kw)
    )


@pytest.mark.parametrize("field", ["stop_loss", "take_profit"])
def test_missing_sl_or_tp_rejected(field: str) -> None:
    assert _entry(**{field: None})


def test_stops_on_wrong_side_rejected() -> None:
    assert any(
        r.startswith("OWNER_STOPS_WRONG_SIDE")
        for r in _entry(stop_loss=D("4114.00"), take_profit=D("4120.00"))
    )


def test_unknown_spread_fails_closed() -> None:
    assert any(r.startswith("OWNER_SPREAD_UNKNOWN") for r in _entry(spread=None))


def test_non_gold_symbol_rejected() -> None:
    assert any(r.startswith("OWNER_GOLD_ONLY") for r in _entry(symbol="EURUSD"))


def test_no_minimum_planned_risk_floor() -> None:
    # The old $1.50 floor is gone: SL 0.50 away ($0.88 incl. spread) is valid.
    assert _entry(stop_loss=D("4116.93"), take_profit=D("4108.00")) == []
    assert D("0") == MIN_PLANNED_RISK_USD


def test_stops_level_distance_enforced() -> None:
    # Broker stops_level 200 points at point 0.01 -> 2.00 minimum distance.
    reasons = _entry(min_stop_distance=D("2.00"))
    assert any(r.startswith("OWNER_STOPS_LEVEL") for r in reasons)
    assert _entry(min_stop_distance=D("1.00")) == []
