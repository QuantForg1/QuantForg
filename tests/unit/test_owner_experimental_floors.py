"""Owner policy: 20% risk, 30% book, ATR 1.00, quality 70, net RR 0.20.

The active reward:risk floor is 0.20. Candidates 0.10 and 0.15 can be
saved under experimental and stay inactive until promoted. Quality 70-100 and
ATR multipliers 1.00, 1.25, and 1.50 remain savable on the active document.
Stops inside one ATR are rejected. Unknown commission is not zero. The
planned-risk ceiling is 20% and the shared book ceiling is 30%. Daily loss
is 48%. Lot stays 0.01. The verified commission is 0.00 USD.
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


def test_owner_defaults_are_20_percent_atr_1_quality_70_and_zero_commission() -> None:
    assert Decimal("0.20") == ol.OWNER_MIN_REWARD_RISK
    assert ol.OWNER_MIN_TRADE_QUALITY == 70
    assert Decimal("1.00") == ol.OWNER_SL_ATR_MULTIPLIER
    assert Decimal("0.01") == ol.OWNER_MAX_LOT
    assert Decimal("20.0") == ol.OWNER_MAX_PLANNED_RISK_PCT
    assert Decimal("30.0") == ol.OWNER_MAX_AGGREGATE_OPEN_RISK_PCT
    assert Decimal("48.0") == ol.OWNER_DAILY_LOSS_PCT
    assert ol.OWNER_MAX_OPEN_POSITIONS == 1
    baseline = approved_baseline()
    assert baseline["min_reward_risk"] == "0.20"
    assert baseline["min_trade_quality"] == 70
    assert baseline["preferred_reward_risk"] == "0.50"
    assert baseline["stop_atr_multiplier"] == "1.00"
    assert baseline["max_planned_risk_pct"] == "20.0"
    assert baseline["max_aggregate_open_risk_pct"] == "30.0"
    assert baseline["daily_loss_pct"] == "48.0"
    assert baseline["max_spread"] == "1.00"
    assert baseline["max_concurrent_positions"] == 1
    commission = baseline["commission"]
    assert commission["amount_usd"] == "0.00"
    assert commission["status"] == "VERIFIED_BY_OWNER_SUPPORT"
    assert commission["source"] == "OWNER_CONFIRMED_WELTRADE_SUPPORT"
    assert commission["symbol"] == "XAUUSD"
    assert active_min_reward_risk() == Decimal("0.20")
    assert active_min_trade_quality() == 70
    assert active_stop_atr_multiplier() == Decimal("1.00")


def _experiment(reward: str = "0.10") -> dict[str, object]:
    return {
        "max_planned_risk_pct": "14",
        "max_aggregate_open_risk_pct": "14",
        "daily_loss_pct": "19",
        "max_lot": "0.01",
        "max_spread": "0.45",
        "min_reward_risk": reward,
        "min_trade_quality": 70,
        "stop_atr_multiplier": "1.00",
        "max_concurrent_positions": 1,
    }


def test_admin_accepts_only_the_authorized_experiment() -> None:
    base = approved_baseline()
    for raw in ("0.20", "0.50", "1.20", "1.49", "1.50", "1.75", "2.00", "3.00"):
        saved = validate_policy_changes(base, {"min_reward_risk": raw})
        assert saved.ok, (raw, saved.errors)
    for raw in ("0.10", "0.15", "0.09", "0.11", "0.19"):
        saved = validate_policy_changes(base, {"min_reward_risk": raw})
        assert saved.ok is False
        assert any("min_reward_risk" in err for err in saved.errors)
    for raw in ("0.10", "0.15"):
        saved = validate_policy_changes(base, {"experimental": _experiment(raw)})
        assert saved.ok, (raw, saved.errors)
        assert saved.document is not None
        assert saved.document["min_reward_risk"] == "0.20"
        assert saved.document["experimental_promoted"] is False
        assert saved.document["experimental"]["min_reward_risk"] == raw
    assert validate_policy_changes(base, {"min_trade_quality": 70}).ok
    assert validate_policy_changes(base, {"min_trade_quality": 75}).ok
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
    assert validate_policy_changes(base, {"max_planned_risk_pct": "20"}).ok
    assert validate_policy_changes(base, {"max_planned_risk_pct": "20.01"}).ok is False
    assert validate_policy_changes(base, {"daily_loss_pct": "19"}).ok
    assert validate_policy_changes(base, {"daily_loss_pct": "48"}).ok
    assert validate_policy_changes(base, {"daily_loss_pct": "48.01"}).ok is False


def test_illegal_saved_values_fail_closed_to_the_published_default() -> None:
    token = _policy(
        min_reward_risk="0.05",
        min_trade_quality=10,
        stop_atr_multiplier="0.75",
    )
    try:
        assert active_min_reward_risk() == Decimal("0.20")
        assert active_min_trade_quality() == 70
        assert active_stop_atr_multiplier() == Decimal("1.00")
    finally:
        reset_runtime_policy(token)


def test_saved_experiment_stays_inactive_and_cannot_undercut_rr_floor() -> None:
    """Experimental RR candidates may be stored but never promoted < 0.20."""
    base = approved_baseline()
    saved = validate_policy_changes(base, {"experimental": _experiment("0.15")})
    assert saved.ok and saved.document is not None
    token = use_runtime_policy(saved.document)
    try:
        assert active_min_reward_risk() == Decimal("0.20")
        assert active_min_trade_quality() == 70
    finally:
        reset_runtime_policy(token)
    promoted = validate_policy_changes(
        base,
        {"experimental": _experiment("0.15"), "promote_experimental": True},
    )
    assert promoted.ok is False
    assert any("promote_experimental cannot lower" in err for err in promoted.errors)
    # Stale promoted documents still fail closed to 0.20 at enforcement time.
    token = _policy(
        min_reward_risk="0.15",
        experimental_promoted=True,
        min_trade_quality=70,
        stop_atr_multiplier="1.25",
    )
    try:
        assert active_min_reward_risk() == Decimal("0.20")
        assert active_min_trade_quality() == 70
        assert active_stop_atr_multiplier() == Decimal("1.25")
    finally:
        reset_runtime_policy(token)
    # Any save of a sub-0.20 active RR is rewritten to the owner floor.
    rewritten = validate_policy_changes(
        {
            **approved_baseline(),
            "min_reward_risk": "0.10",
            "experimental_promoted": True,
        },
        {"reason": "owner_rr_floor_lock"},
    )
    assert rewritten.ok and rewritten.document is not None
    assert rewritten.document["min_reward_risk"] == "0.20"
    assert rewritten.document["experimental_promoted"] is False


def test_promoted_quality_and_atr_still_apply_without_lowering_rr() -> None:
    token = _policy(
        min_reward_risk="0.20",
        experimental_promoted=False,
        min_trade_quality=80,
        stop_atr_multiplier="1.25",
    )
    try:
        assert active_min_reward_risk() == Decimal("0.20")
        assert active_min_trade_quality() == 80
        assert active_stop_atr_multiplier() == Decimal("1.25")
        passed = _gates(80)
        assert not any(
            r.startswith("OWNER_MIN_TRADE_QUALITY") for r in passed.hard_rejects
        )
        low = _gates(79)
        assert any("trade quality 79 < 80" in r for r in low.hard_rejects)
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


def test_owner_entry_uses_the_locked_net_floor_and_slippage() -> None:
    """Even a stale promoted 0.10 document enforces 0.20."""
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
    token = _policy(min_reward_risk="0.10", experimental_promoted=True)
    try:
        # Geometry clears 0.10 but fails the locked 0.20 owner floor.
        blocked = ol.evaluate_owner_entry(**common)
        assert any(r.startswith("OWNER_MIN_RR") for r in blocked)
    finally:
        reset_runtime_policy(token)
    default = ol.evaluate_owner_entry(**common)
    assert any(r.startswith("OWNER_MIN_RR") for r in default)
    # A geometry that clears 0.20 after costs is accepted.
    ok = ol.evaluate_owner_entry(
        **{
            **common,
            "take_profit": Decimal("104"),
            "stop_loss": Decimal("99"),
        }
    )
    assert not any(r.startswith("OWNER_MIN_RR") for r in ok)


def test_structure_targets_respect_locked_rr_floor_not_experimental_candidate() -> None:
    snapshot = _snapshot(highs=("4134.50", "4135.20", "4140.00"))
    # Active floor 0.20 accepts L1 (net ~0.75); experimental 0.10 must not
    # lower the live floor further.
    published = compute_structure_targets(
        snapshot,  # type: ignore[arg-type]
        direction=TradeDirection.BUY,
        entry=ENTRY,
        atr=ATR,
        config=AiScalpingConfig(),
    )
    assert published.take_profit == Decimal("4134.50")
    token = _policy(min_reward_risk="0.10", experimental_promoted=True)
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
    assert chosen.take_profit == published.take_profit
    assert chosen.expected_net_rr == published.expected_net_rr


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


def test_gross_precheck_follows_the_locked_floor() -> None:
    # Active floor 0.20: gross precheck requires tp/stop >= 0.20.
    assert ol.gross_distance_rr_block(
        tp_distance=Decimal("0.19"), stop_distance=Decimal("1")
    )
    assert ol.estimated_rr_block(Decimal("0.19"))
    assert (
        ol.gross_distance_rr_block(
            tp_distance=Decimal("0.20"), stop_distance=Decimal("1")
        )
        is None
    )
    assert ol.estimated_rr_block(Decimal("0.20")) is None
    token = _policy(min_reward_risk="0.10", experimental_promoted=True)
    try:
        # Stale promotion cannot admit 0.15 gross RR under the 0.20 lock.
        assert ol.gross_distance_rr_block(
            tp_distance=Decimal("0.15"), stop_distance=Decimal("1")
        )
        assert ol.estimated_rr_block(Decimal("0.15"))
        assert (
            ol.gross_distance_rr_block(
                tp_distance=Decimal("0.20"), stop_distance=Decimal("1")
            )
            is None
        )
    finally:
        reset_runtime_policy(token)


def test_presend_slippage_buffer_uses_the_locked_floor() -> None:
    token = _policy(min_reward_risk="0.10", experimental_promoted=True)
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
    assert any("OWNER_MIN_RR" in r for r in reasons)
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
