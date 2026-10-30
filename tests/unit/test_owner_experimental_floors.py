"""Owner experiment 2026-10-30: 14% risk, ATR 1.00, quality 70, net RR.

The active reward:risk default stays 1.50. A saved policy may select net RR
0.10, 0.15, or 0.20, quality 70-100, and an ATR multiplier of 1.00, 1.25, or
1.50. Stops inside one ATR are rejected. Unknown commission is not zero.
The planned-risk ceiling is 14%. Daily loss stays 19%. Lot stays 0.01.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.institutional_trading import owner_live_limits as ol
from app.domain.institutional_trading.ai_scalping.config import AiScalpingConfig
from app.domain.institutional_trading.ai_scalping.structure_targets import (
    compute_structure_targets,
)
from app.domain.institutional_trading.decision_models import TradeDirection
from app.domain.institutional_trading.runtime_policy import (
    active_min_reward_risk,
    active_min_trade_quality,
    active_stop_atr_multiplier,
    approved_baseline,
    reset_runtime_policy,
    use_runtime_policy,
    validate_policy_changes,
)
from tests.unit.test_owner_min_trade_quality import _gates
from tests.unit.test_owner_sl15_tp2 import ATR, ENTRY, _snapshot

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _policy(**changes: object):
    return use_runtime_policy({**approved_baseline(), **changes})


def test_experimental_defaults_are_14_percent_atr_1_and_quality_70() -> None:
    assert Decimal("1.50") == ol.OWNER_MIN_REWARD_RISK
    assert ol.OWNER_MIN_TRADE_QUALITY == 70
    assert Decimal("1.00") == ol.OWNER_SL_ATR_MULTIPLIER
    assert Decimal("0.01") == ol.OWNER_MAX_LOT
    assert Decimal("14.0") == ol.OWNER_MAX_PLANNED_RISK_PCT
    assert Decimal("19.0") == ol.OWNER_DAILY_LOSS_PCT
    assert approved_baseline()["min_reward_risk"] == "1.50"
    assert approved_baseline()["min_trade_quality"] == 70
    assert approved_baseline()["stop_atr_multiplier"] == "1.00"
    assert approved_baseline()["max_planned_risk_pct"] == "14.0"
    assert approved_baseline()["max_aggregate_open_risk_pct"] == "14.0"
    assert active_min_reward_risk() == Decimal("1.50")
    assert active_min_trade_quality() == 70
    assert active_stop_atr_multiplier() == Decimal("1.00")


def test_admin_accepts_only_the_authorized_experiment() -> None:
    base = approved_baseline()
    for raw in ("0.10", "0.15", "0.20", "1.50", "2.00"):
        saved = validate_policy_changes(base, {"min_reward_risk": raw})
        assert saved.ok, (raw, saved.errors)
    for raw in ("0.09", "0.11", "0.50", "1.20", "1.49"):
        saved = validate_policy_changes(base, {"min_reward_risk": raw})
        assert saved.ok is False
        assert any("min_reward_risk" in err for err in saved.errors)
    assert validate_policy_changes(base, {"min_trade_quality": 70}).ok
    assert validate_policy_changes(base, {"min_trade_quality": 100}).ok
    assert validate_policy_changes(base, {"min_trade_quality": 69}).ok is False
    for raw in ("1.00", "1.25", "1.50"):
        assert validate_policy_changes(base, {"stop_atr_multiplier": raw}).ok
    for raw in ("0.75", "0.90"):
        saved = validate_policy_changes(base, {"stop_atr_multiplier": raw})
        assert saved.ok is False
        assert any("noise" in err for err in saved.errors)
    other = validate_policy_changes(base, {"stop_atr_multiplier": "1.10"})
    assert other.ok is False
    assert validate_policy_changes(base, {"kill_switch_bypass": True}).ok is False
    assert validate_policy_changes(base, {"max_lot": "0.02"}).ok is False
    assert validate_policy_changes(base, {"max_planned_risk_pct": "14"}).ok
    assert validate_policy_changes(base, {"max_planned_risk_pct": "14.01"}).ok is False
    assert validate_policy_changes(base, {"daily_loss_pct": "19"}).ok
    assert validate_policy_changes(base, {"daily_loss_pct": "20"}).ok is False


def test_illegal_saved_values_fail_closed_to_the_published_default() -> None:
    token = _policy(
        min_reward_risk="0.50",
        min_trade_quality=10,
        stop_atr_multiplier="0.75",
    )
    try:
        assert active_min_reward_risk() == Decimal("1.50")
        assert active_min_trade_quality() == 70
        assert active_stop_atr_multiplier() == Decimal("1.00")
    finally:
        reset_runtime_policy(token)


def test_saved_experiment_is_what_the_gates_enforce() -> None:
    token = _policy(
        min_reward_risk="0.15",
        min_trade_quality=70,
        stop_atr_multiplier="1.25",
    )
    try:
        assert active_min_reward_risk() == Decimal("0.15")
        assert active_min_trade_quality() == 70
        assert active_stop_atr_multiplier() == Decimal("1.25")
        passed = _gates(70)
        assert not any(
            r.startswith("OWNER_MIN_TRADE_QUALITY") for r in passed.hard_rejects
        )
        low = _gates(69)
        assert any("trade quality 69 < 70" in r for r in low.hard_rejects)
    finally:
        reset_runtime_policy(token)


def test_unset_quality_70_passes_and_69_is_rejected() -> None:
    assert not any("OWNER_MIN_TRADE_QUALITY" in r for r in _gates(70).hard_rejects)
    low = _gates(69)
    assert any("trade quality 69 < 70" in r for r in low.hard_rejects)


def test_net_rr_includes_spread_slippage_and_known_commission_only() -> None:
    spread_only = ol.net_reward_risk(
        tp_distance=Decimal("0.30"),
        stop_distance=Decimal("2"),
        spread=Decimal("0.20"),
    )
    # 0.30 / 2.20. Gross is 0.30 / 2 = 0.15 and must not be used as net.
    assert spread_only.gross_ratio == Decimal("0.15")
    assert spread_only.ratio == Decimal("0.30") / Decimal("2.20")
    assert spread_only.commission_included is False
    with_slip = ol.net_reward_risk(
        tp_distance=Decimal("0.30"),
        stop_distance=Decimal("2"),
        spread=Decimal("0.20"),
        slippage=Decimal("0.10"),
    )
    assert with_slip.ratio == Decimal("0.30") / Decimal("2.30")
    assert with_slip.ratio < spread_only.ratio
    unknown = ol.net_reward_risk(
        tp_distance=Decimal("0.30"),
        stop_distance=Decimal("2"),
        spread=Decimal("0.20"),
        commission=None,
        contract_size=Decimal("100"),
        volume=Decimal("0.01"),
    )
    assert unknown.commission_included is False
    assert unknown.ratio == spread_only.ratio
    known = ol.net_reward_risk(
        tp_distance=Decimal("0.30"),
        stop_distance=Decimal("2"),
        spread=Decimal("0.20"),
        commission=Decimal("0.05"),
        contract_size=Decimal("100"),
        volume=Decimal("0.01"),
    )
    # One price unit at 0.01 lot and contract 100 is $1, so $0.05 is 0.05 price.
    assert known.commission_included is True
    assert known.ratio == Decimal("0.25") / Decimal("2.25")
    assert known.ratio < unknown.ratio


def test_owner_entry_uses_the_saved_net_floor_and_slippage() -> None:
    common = {
        "symbol": "XAUUSD",
        "side": "BUY",
        "volume": Decimal("0.01"),
        "entry": Decimal("100"),
        "stop_loss": Decimal("98"),
        "take_profit": Decimal("100.30"),
        "spread": Decimal("0.20"),
        "contract_size": Decimal("100"),
        "equity": Decimal("50"),
        "commission": Decimal("0"),
    }
    token = _policy(min_reward_risk="0.10")
    try:
        assert ol.evaluate_owner_entry(**common) == []
        slipped = ol.evaluate_owner_entry(**common, slippage=Decimal("1"))
        assert any(r.startswith("OWNER_MIN_RR") for r in slipped)
        priced = ol.evaluate_owner_entry(**{**common, "commission": Decimal("0.50")})
        assert any(r.startswith("OWNER_MIN_RR") for r in priced)
    finally:
        reset_runtime_policy(token)
    # The same geometry is below the published 1.50 default.
    default = ol.evaluate_owner_entry(**common)
    assert any(r.startswith("OWNER_MIN_RR") for r in default)


def test_experimental_floor_can_select_a_structure_target_gross_rr_does_not() -> None:
    snapshot = _snapshot(highs=("4134.50", "4135.20", "4140.00"))
    blocked = compute_structure_targets(
        snapshot,  # type: ignore[arg-type]
        direction=TradeDirection.BUY,
        entry=ENTRY,
        atr=ATR,
        config=AiScalpingConfig(),
    )
    assert blocked.take_profit is None
    token = _policy(min_reward_risk="0.10")
    try:
        chosen = compute_structure_targets(
            snapshot,  # type: ignore[arg-type]
            direction=TradeDirection.BUY,
            entry=ENTRY,
            atr=ATR,
            config=AiScalpingConfig(),
        )
    finally:
        reset_runtime_policy(token)
    assert chosen.take_profit == Decimal("4134.50")
    assert chosen.expected_rr is not None and chosen.expected_rr <= Decimal("1")
    assert chosen.expected_net_rr is not None
    assert chosen.expected_net_rr >= Decimal("0.10")
    assert chosen.expected_net_rr < chosen.expected_rr


def test_tighter_atr_multiplier_never_shrinks_a_wider_structure_stop() -> None:
    token = _policy(stop_atr_multiplier="1.25")
    try:
        tight_structure = compute_structure_targets(
            _snapshot(highs=("4138.00",)),  # type: ignore[arg-type]
            direction=TradeDirection.BUY,
            entry=ENTRY,
            atr=ATR,
            config=AiScalpingConfig(),
        )
        wide_structure = compute_structure_targets(
            _snapshot(swing_low="4129.00", highs=("4141.00",)),  # type: ignore[arg-type]
            direction=TradeDirection.BUY,
            entry=ENTRY,
            atr=ATR,
            config=AiScalpingConfig(),
        )
    finally:
        reset_runtime_policy(token)
    assert tight_structure.stop_distance == ATR * Decimal("1.25")
    assert wide_structure.stop_distance == Decimal("4.30")
    assert wide_structure.stop_source == "owner_structure"


@pytest.mark.parametrize(
    ("multiplier", "verdict"),
    [
        ("0.75", "inside_noise"),
        ("0.90", "inside_noise"),
        ("1.00", "accepted"),
        ("1.25", "accepted"),
        ("1.50", "accepted"),
        ("1.10", "rejected"),
    ],
)
def test_atr_multiplier_structural_verdict(multiplier: str, verdict: str) -> None:
    assert ol.atr_multiplier_verdict(Decimal(multiplier)) == verdict


def test_break_even_win_rate_rises_when_costs_lower_net_rr() -> None:
    """A 0.10-0.20 net target needs a high win rate before extra costs."""

    def breakeven(rr: Decimal) -> Decimal:
        return Decimal("1") / (Decimal("1") + rr)

    assert breakeven(Decimal("0.10")) > Decimal("0.90")
    assert breakeven(Decimal("0.15")) > Decimal("0.86")
    assert breakeven(Decimal("0.20")) > Decimal("0.83")
    gross = ol.net_reward_risk(
        tp_distance=Decimal("0.20"),
        stop_distance=Decimal("1"),
        spread=Decimal("0"),
    )
    net = ol.net_reward_risk(
        tp_distance=Decimal("0.20"),
        stop_distance=Decimal("1"),
        spread=Decimal("0.05"),
        slippage=Decimal("0.01"),
    )
    assert gross.ratio is not None and net.ratio is not None
    assert breakeven(net.ratio) > breakeven(gross.ratio)


def test_gross_precheck_follows_the_saved_floor() -> None:
    assert ol.gross_distance_rr_block(
        tp_distance=Decimal("1"), stop_distance=Decimal("1")
    )
    assert ol.estimated_rr_block(Decimal("1"))
    token = _policy(min_reward_risk="0.10")
    try:
        assert (
            ol.gross_distance_rr_block(
                tp_distance=Decimal("0.15"), stop_distance=Decimal("1")
            )
            is None
        )
        assert ol.gross_distance_rr_block(
            tp_distance=Decimal("0.05"), stop_distance=Decimal("1")
        )
        assert ol.estimated_rr_block(Decimal("0.15")) is None
        assert ol.estimated_rr_block(Decimal("0.05"))
    finally:
        reset_runtime_policy(token)


def test_presend_slippage_buffer_uses_the_active_floor() -> None:
    token = _policy(min_reward_risk="0.10")
    try:
        reasons = ol.presend_owner_violations(
            symbol="XAUUSD",
            side="BUY",
            volume=Decimal("0.01"),
            request_price=Decimal("100"),
            bid=Decimal("99.80"),
            ask=Decimal("100"),
            stop_loss=Decimal("98"),
            take_profit=Decimal("100.30"),
            plan_price=Decimal("100"),
            contract_size=Decimal("100"),
            equity=Decimal("50"),
            rr_buffer=Decimal("0.05"),
            commission=Decimal("0"),
        )
    finally:
        reset_runtime_policy(token)
    assert not any("OWNER_MIN_RR" in r for r in reasons)
    # Same prices at the published floor are refused.
    refused = ol.presend_owner_violations(
        symbol="XAUUSD",
        side="BUY",
        volume=Decimal("0.01"),
        request_price=Decimal("100"),
        bid=Decimal("99.80"),
        ask=Decimal("100"),
        stop_loss=Decimal("98"),
        take_profit=Decimal("100.30"),
        plan_price=Decimal("100"),
        contract_size=Decimal("100"),
        equity=Decimal("50"),
        commission=Decimal("0"),
    )
    assert any("OWNER_MIN_RR" in r for r in refused)
