"""Owner live limits (2026-10-23): 9% planned risk, 25% daily stop, entry guard."""

from __future__ import annotations

from decimal import Decimal

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
    OWNER_MAX_LOT,
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
    }
    args.update(overrides)
    return evaluate_owner_entry(**args)  # type: ignore[arg-type]


# --- Ceilings: no 80% values anywhere, configs can be stricter, never looser ---


def test_owner_constants_replace_80_percent_caps() -> None:
    assert MAX_DAILY_LOSS_PCT == D("19.0")
    assert MAX_DAILY_LOSS_CEILING_PCT == D("19.0")
    # Static values are at the $50 reference capital; live checks use equity.
    assert MAX_PLANNED_SL_RISK_USD == D("4.50")
    assert TARGET_PLANNED_RISK_USD == D("4.50")
    assert MIN_PLANNED_RISK_USD == D("0") < TARGET_PLANNED_RISK_USD
    assert MIN_REWARD_RISK == D("1.50")
    assert MicroAccountProfile().hard_max_risk_pct == D("9.0")


def test_default_configs_respect_owner_limits() -> None:
    assert DEFAULT_ITE_CONFIG.max_daily_loss_pct <= MAX_DAILY_LOSS_CEILING_PCT
    assert DEFAULT_ITE_CONFIG.risk_per_trade_pct <= D("2.0")
    assert DEFAULT_ITE_CONFIG.max_open_trades == 1
    assert SCALPING_V1.max_open_trades == 1
    assert SCALPING_V1.max_entries_per_cycle == 1
    assert DEFAULT_AI_SCALPING_CONFIG.max_open_trades == 1
    assert DEFAULT_AI_SCALPING_CONFIG.max_entries_per_cycle == 1
    assert AiScalpingConfig().max_open_trades == 1
    assert scalping_ite_config().max_open_trades == 1
    cfg = RiskEngineConfig()
    assert cfg.max_lot == OWNER_MAX_LOT
    assert cfg.max_open_positions == 1
    assert cfg.max_consecutive_losses == 0  # no loss-streak pause (2026-10-23)
    assert cfg.cooldown_minutes_after_loss_streak == 24 * 60


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_daily_loss_pct", D("19.01")),
        ("max_daily_loss_pct", D("80.0")),
        ("risk_per_trade_pct", D("9.01")),
        ("max_planned_sl_risk_usd", D("4.51")),
        ("max_open_trades", 2),
    ],
)
def test_ite_config_rejects_values_above_owner_ceilings(
    field: str, value: object
) -> None:
    with pytest.raises(ValueError):
        ITEConfig(**{field: value})  # type: ignore[arg-type]


def test_live_scalp_cap_never_exceeds_one() -> None:
    for current in (1, 3, 5, 10, 50):
        assert align_live_scalp_cap(current, trading_mode="scalping") == 1
        assert align_live_scalp_cap(current, trading_mode="alpha") == 1


# --- Daily stop: 19% of the UTC day's starting equity ---


@pytest.mark.parametrize(
    "sod,expected",
    [
        ("50.84", "9.65"),
        ("20.00", "3.80"),
        ("1000", "190.00"),
    ],
)
def test_daily_loss_cap_usd(sod: str, expected: str) -> None:
    assert daily_loss_cap_usd(D(sod)) == D(expected)


def test_daily_loss_at_cap_does_not_block_and_one_cent_over_does() -> None:
    # Start of day 50.84 -> cap $9.65. Equal to the cap does not halt.
    assert daily_loss_exceeded(daily_pnl=D("-9.65"), base_now=D("41.19")) is False
    assert daily_loss_exceeded(daily_pnl=D("-9.66"), base_now=D("41.18")) is True


def test_nineteen_percent_boundary_on_larger_account() -> None:
    # SOD 1000 -> cap $190. One cent over blocks; the exact cap does not.
    assert daily_loss_exceeded(daily_pnl=D("-190.01"), base_now=D("809.99")) is True
    assert daily_loss_exceeded(daily_pnl=D("-190.00"), base_now=D("810.00")) is False


def test_utc_lock_uses_owner_daily_stop() -> None:
    kw = {"equity": D("38.12"), "max_daily_loss_pct": MAX_DAILY_LOSS_PCT}
    assert utc_daily_loss_exceeded(daily_pnl=D("-12.72"), balance=D("38.12"), **kw)
    assert not utc_daily_loss_exceeded(
        daily_pnl=D("-1.60"),
        balance=D("49.24"),
        equity=D("49.24"),
        max_daily_loss_pct=MAX_DAILY_LOSS_PCT,
    )


def test_risk_engine_drawdown_blocks_above_owner_daily_stop() -> None:
    engine = RiskEngine()
    _s, reasons, _w = engine.evaluate_drawdown(
        _account("38.12"), daily_pnl=D("-12.72")
    )
    assert any("owner daily stop" in r for r in reasons)
    _s, reasons_ok, _w = engine.evaluate_drawdown(
        _account("49.24"), daily_pnl=D("-1.60")
    )
    assert not any("daily loss" in r for r in reasons_ok)


def test_daily_loss_cap_pct_matches_usd_stop() -> None:
    pct = daily_loss_cap_pct(daily_pnl=D("0"), base_now=D("50.84"))
    assert (D("50.84") * pct / 100).quantize(D("0.01")) == D("9.65")


# --- Per-trade planned-risk cap: 9% of equity ---


def test_max_sl_risk_usd() -> None:
    assert max_sl_risk_usd(D("50.84")) == D("4.57")
    assert max_sl_risk_usd(D("150")) == D("13.50")


# --- Final owner entry guard ---


def test_valid_gold_entry_passes() -> None:
    assert _entry() == []


def test_production_order_of_2026_10_20_is_rejected() -> None:
    # SELL XAUUSD 0.02 sent at 23:37:07Z: 0.02 lot, $8.46 SL risk, RR 1.0.
    reasons = _entry(
        symbol="XAUUSD",
        volume=D("0.02"),
        stop_loss=D("4120.66"),
        take_profit=D("4111.45"),
    )
    codes = {r.split(":")[0] for r in reasons}
    assert {"OWNER_MAX_LOT", "OWNER_SL_RISK", "OWNER_MIN_RR"} <= codes


def test_volume_002_is_rejected() -> None:
    assert any(r.startswith("OWNER_MAX_LOT") for r in _entry(volume=D("0.02")))


def test_planned_risk_458_rejected_457_allowed() -> None:
    # Equity 50.84 -> cap $4.57. SL 4.19 + spread 0.38 = $4.57 allowed;
    # SL 4.20 + 0.38 = $4.58 rejected. TP far enough for RR.
    assert any(
        r.startswith("OWNER_SL_RISK")
        for r in _entry(stop_loss=D("4120.63"), take_profit=D("4108.00"))
    )
    assert _entry(stop_loss=D("4120.62"), take_profit=D("4108.00")) == []


def test_reward_risk_below_1_5_after_spread_rejected() -> None:
    # SL 1.60, TP 2.90: 2.90 / (1.60 + 0.38) = 1.46
    assert any(r.startswith("OWNER_MIN_RR") for r in _entry(take_profit=D("4113.53")))


def test_reward_risk_counts_spread_once_boundary() -> None:
    # SL $2.00 + spread 0.44 -> minimum TP distance 3.66 (3.66 / 2.44 = 1.50).
    kw = {"stop_loss": D("4118.43"), "spread": D("0.44")}
    assert _entry(take_profit=D("4112.77"), **kw) == []
    assert any(
        r.startswith("OWNER_MIN_RR") for r in _entry(take_profit=D("4112.78"), **kw)
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
    assert MIN_PLANNED_RISK_USD == D("0")


def test_stops_level_distance_enforced() -> None:
    # Broker stops_level 200 points at point 0.01 -> 2.00 minimum distance.
    reasons = _entry(min_stop_distance=D("2.00"))
    assert any(r.startswith("OWNER_STOPS_LEVEL") for r in reasons)
    assert _entry(min_stop_distance=D("1.00")) == []
