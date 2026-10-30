"""Owner stop: 1.00 x ATR by default, second-level structure TP.

Stop = max(1.00 x ATR, beyond nearest M1/M5 structure + spread), never shrunk.
A saved 1.50 multiplier is still honoured. TP = the nearest real structure
level with RR after spread >= 1.50, looking at most two levels out.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.domain.institutional_trading import owner_live_limits as ol
from app.domain.institutional_trading.ai_scalping.config import AiScalpingConfig
from app.domain.institutional_trading.ai_scalping.structure_targets import (
    compute_structure_targets,
    owner_tp_levels,
    select_owner_structure_tp,
)
from app.domain.institutional_trading.decision_models import TradeDirection

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

ENTRY = Decimal("4133.00")
ATR = Decimal("2.00")  # 1.00 x ATR = 2.00
SPREAD = Decimal("0.30")  # risk after spread = 2.00 + 0.30 = 2.30


def _swing(price: str, kind: str) -> SimpleNamespace:
    return SimpleNamespace(price=Decimal(price), kind=kind)


def _snapshot(
    *,
    swing_low: str | None = "4131.50",
    swing_high: str | None = None,
    highs: tuple[str, ...] = (),
    lows: tuple[str, ...] = (),
    pools: tuple[tuple[str, str], ...] = (),
) -> SimpleNamespace:
    swings = [_swing(p, "SWING_HIGH") for p in highs]
    swings += [_swing(p, "SWING_LOW") for p in lows]
    m1 = SimpleNamespace(
        last_swing_low=Decimal(swing_low) if swing_low else None,
        last_swing_high=Decimal(swing_high) if swing_high else None,
        swings=swings,
    )
    liquidity = (
        SimpleNamespace(
            pools=[SimpleNamespace(price=Decimal(p), side=s) for p, s in pools]
        )
        if pools
        else None
    )
    return SimpleNamespace(
        structure_by_tf={"M1": m1},
        spread=SPREAD,
        order_blocks=None,
        fair_value_gaps=None,
        primary_structure=None,
        liquidity=liquidity,
    )


def _targets(snapshot: SimpleNamespace, direction: TradeDirection = TradeDirection.BUY):
    return compute_structure_targets(
        snapshot,  # type: ignore[arg-type]
        direction=direction,
        entry=ENTRY,
        atr=ATR,
        config=AiScalpingConfig(),
    )


# --- 1.00 x ATR stop ----------------------------------------------------------


def test_default_multiplier_is_1_00() -> None:
    assert Decimal("1.00") == ol.OWNER_SL_ATR_MULTIPLIER
    assert AiScalpingConfig().owner_stop_atr_mult == Decimal("1.00")
    assert ol.OWNER_SL_ATR_TIMEFRAME == "M1"


def test_stop_is_1_00_atr_when_structure_is_closer() -> None:
    # Swing low 1.50 below entry + 0.30 spread = 1.80 < 1.00 x 2.00 = 2.00.
    t = _targets(_snapshot(highs=("4138.00",)))
    assert t.stop_distance == Decimal("2.000")
    assert t.stop_loss == ENTRY - Decimal("2.00")
    assert t.stop_source == "owner_atr"


def test_saved_1_50_multiplier_still_uses_the_wider_floor() -> None:
    from app.domain.institutional_trading.runtime_policy import (
        approved_baseline,
        reset_runtime_policy,
        use_runtime_policy,
    )

    token = use_runtime_policy({**approved_baseline(), "stop_atr_multiplier": "1.50"})
    try:
        t = _targets(_snapshot(highs=("4138.00",)))
    finally:
        reset_runtime_policy(token)
    assert t.stop_distance == Decimal("3.000")
    assert t.stop_source == "owner_atr"


def test_stop_beyond_structure_plus_spread_when_wider_never_shrunk() -> None:
    # Swing low 4.00 below + 0.30 spread = 4.30 > 3.00: stop sits beyond it.
    t = _targets(_snapshot(swing_low="4129.00", highs=("4141.00",)))
    assert t.stop_distance == Decimal("4.30")
    assert t.stop_loss == Decimal("4128.70")
    assert t.stop_source == "owner_structure"


def test_sell_stop_mirrors_buy() -> None:
    snap = _snapshot(swing_low=None, swing_high="4134.00", lows=("4127.00",))
    t = _targets(snap, TradeDirection.SELL)
    # Swing high 1.00 above + 0.30 = 1.30 < 2.00 -> 1.00 x ATR.
    assert t.stop_loss == ENTRY + Decimal("2.00")
    assert t.take_profit == Decimal("4127.00")  # 6.00 / 3.30 = 1.82


# --- Second-level TP ----------------------------------------------------------


def test_first_level_used_when_it_clears_1_5() -> None:
    # L1 4138.00: 5.00 / 2.30 = 2.17 -> L1 even though L2 is further.
    t = _targets(_snapshot(highs=("4138.00", "4142.00")))
    assert t.take_profit == Decimal("4138.00")
    assert t.tp_level == 1
    assert t.tp_source == "swing_M1"


def test_second_level_chosen_only_when_first_fails() -> None:
    # L1 4136.00: 3.00 / 2.30 = 1.30 fails; L2 4138.50: 5.50 / 2.30 = 2.39.
    t = _targets(_snapshot(highs=("4136.00", "4138.50")))
    assert t.take_profit == Decimal("4138.50")
    assert t.tp_level == 2
    assert "TP structure level 2" in t.reason
    assert t.to_dict()["tp_level"] == 2


def test_no_tp_beyond_the_second_level() -> None:
    # L1 3.00/2.30 = 1.30, L2 3.40/2.30 = 1.48; L3 4140.00 is never used.
    t = _targets(_snapshot(highs=("4136.00", "4136.40", "4140.00")))
    assert t.take_profit is None
    assert t.tp_level is None
    assert t.reason.startswith("OWNER_TP_NO_STRUCTURE_RR")
    assert "4140.00" not in t.reason


def test_no_level_beyond_entry_means_no_tp_not_atr_stretch() -> None:
    t = _targets(_snapshot(highs=()))
    assert t.take_profit is None
    assert "no level beyond entry" in t.reason


def test_liquidity_pool_counts_as_a_level() -> None:
    snap = _snapshot(highs=("4136.00",), pools=(("4139.00", "BUY_SIDE_HIGH"),))
    t = _targets(snap)
    assert t.take_profit == Decimal("4139.00")
    assert t.tp_level == 2
    assert t.tp_source == "liquidity"


def test_levels_within_the_spread_are_one_level() -> None:
    levels = owner_tp_levels(
        [
            (Decimal("4136.00"), "swing_M1"),
            (Decimal("4136.20"), "liquidity"),
            (Decimal("4138.50"), "swing_M5"),
        ],
        direction=TradeDirection.BUY,
        entry=ENTRY,
        merge_tolerance=SPREAD,
    )
    assert levels == [
        (Decimal("4136.00"), "swing_M1+liquidity"),
        (Decimal("4138.50"), "swing_M5"),
    ]


def test_sell_levels_sorted_nearest_first() -> None:
    levels = owner_tp_levels(
        [(Decimal("4120.00"), "zone"), (Decimal("4130.00"), "swing_M1")],
        direction=TradeDirection.SELL,
        entry=ENTRY,
        merge_tolerance=SPREAD,
    )
    assert [p for p, _ in levels] == [Decimal("4130.00"), Decimal("4120.00")]


# --- RR boundary 1.49 vs 1.50 (after spread) ----------------------------------


@pytest.mark.parametrize(
    ("tp_distance", "accepted"),
    [("3.00", True), ("2.98", False)],  # /(1.70 + 0.30): 1.50 vs 1.49
)
def test_rr_boundary(tp_distance: str, accepted: bool) -> None:
    entry = Decimal("100")
    choice = select_owner_structure_tp(
        [(entry + Decimal(tp_distance), "swing_M1")],
        entry=entry,
        stop_distance=Decimal("1.70"),
        spread=Decimal("0.30"),
    )
    assert (choice.level == 1) is accepted


@pytest.mark.parametrize(("tp", "ok"), [("4136.00", True), ("4135.98", False)])
def test_final_owner_guard_uses_same_boundary(tp: str, ok: bool) -> None:
    reasons = ol.evaluate_owner_entry(
        symbol="XAUUSD",
        side="BUY",
        volume=Decimal("0.01"),
        entry=Decimal("4133.00"),
        stop_loss=Decimal("4131.30"),  # 1.70 + 0.30 spread = 2.00 risk
        take_profit=Decimal(tp),  # 3.00 -> 1.50 ; 2.98 -> 1.49
        spread=Decimal("0.30"),
        contract_size=Decimal("100"),
        equity=Decimal("50"),
        commission=Decimal("0"),
    )
    assert (not any(r.startswith("OWNER_MIN_RR") for r in reasons)) is ok


# --- Stop ATR is M1 on the live (swing-config) scan snapshot ------------------


def test_scan_snapshot_stop_atr_is_m1_not_m15() -> None:
    """Production scans with the default (swing) analysis config, whose entry
    ATR is M15. The owner stop must still use ATR(M1)."""
    import asyncio
    from datetime import UTC, datetime, timedelta

    from app.application.services.institutional_trading_analysis import (
        InstitutionalTradingAnalysisService,
    )
    from app.application.services.production_replay_validation import (
        build_synthetic_bars,
    )
    from app.domain.institutional_trading.atr import compute_atr
    from app.domain.market_data.candle import Candle
    from app.domain.market_data.timeframe import Timeframe

    end = datetime(2026, 10, 22, 10, 0, tzinfo=UTC)
    bars = build_synthetic_bars(days=10, end=end)
    m1 = []
    for i in range(120, 0, -1):
        ot = end - timedelta(minutes=i)
        m1.append(
            Candle.create(
                symbol_code="XAUUSD",
                timeframe=Timeframe.M1,
                open_time=ot,
                close_time=ot + timedelta(minutes=1),
                open="4000.00",
                high="4000.50",
                low="3999.50",
                close="4000.00",
            )
        )
    bars[Timeframe.M1] = m1
    snap = asyncio.run(
        InstitutionalTradingAnalysisService().analyze_bars(
            bars, as_of=end, symbol="XAUUSD"
        )
    )
    assert snap.stop_atr == compute_atr(m1) == Decimal("1.00")
    assert snap.entry_atr == snap.atr  # swing config: analysis ATR untouched
    assert snap.atr != snap.stop_atr
