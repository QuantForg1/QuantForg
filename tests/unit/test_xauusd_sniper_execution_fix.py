"""XAUUSD sniper execution — chase ATR TF, FVG freshness, opportunity mapping.

Does not send orders. Does not lower the 70 opportunity threshold.
Does not remove chase protection, Risk, Safety, or OMS.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
)
from app.domain.institutional_trading.ai_scalping.direction import DirectionDecision
from app.domain.institutional_trading.ai_scalping.duplicate_guard import (
    may_add_scalping_trade,
)
from app.domain.institutional_trading.ai_scalping.sniper_entry import (
    evaluate_sniper_entry,
)
from app.domain.institutional_trading.decision_models import TradeDirection
from app.domain.institutional_trading.operations.communication_fault import (
    should_blind_retry_order_submit,
)
from app.domain.institutional_trading.operations.probability_selector import (
    OPPORTUNITY_SCORE_THRESHOLD,
    evaluate_from_score_dict,
)
from app.domain.institutional_trading.phase_a.market_data_firewall import (
    MarketDataState,
    evaluate_market_data_firewall,
)
from app.domain.market_data.timeframe import Timeframe
from app.domain.market_structure.enums import TrendDirection
from app.domain.scalping_ai_v2.reliability import DuplicateProtection
from app.domain.trading.gold_only import DisabledAutonomousSymbolError, require_xauusd
from app.domain.value_objects.market import Price
from app.domain.multi_agent_ai import CollaborationInput, MultiAgentSystem

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

MIN_RR = Decimal("1.20")


def _snap(
    *,
    fvgs: list[object] | None = None,
    bos: list[object] | None = None,
    choch: list[object] | None = None,
    sweeps: list[object] | None = None,
    order_blocks: list[object] | None = None,
    equal_highs: list[object] | None = None,
    equal_lows: list[object] | None = None,
) -> MagicMock:
    trend = MagicMock()
    trend.macro_bias = TrendDirection.DOWN
    trend.primary = TrendDirection.DOWN
    trend.alignment_score = 70
    structure = MagicMock()
    structure.breaks_of_structure = list(bos or [])
    structure.changes_of_character = list(choch or [])
    liq = MagicMock()
    liq.sweeps = list(sweeps or [])
    liq.equal_highs = list(equal_highs or [])
    liq.equal_lows = list(equal_lows or [])
    snap = MagicMock()
    snap.trend = trend
    snap.primary_structure = structure
    snap.liquidity = liq
    snap.order_blocks = MagicMock(order_blocks=list(order_blocks or []))
    snap.fair_value_gaps = MagicMock(active_gaps=list(fvgs or []))
    snap.trade_quality = MagicMock(total=80, components={"momentum": 70})
    snap.session = MagicMock(session=MagicMock(value="london"), allowed=True)
    snap.spread = Decimal("0.20")
    snap.symbol = "XAUUSD_i"
    return snap


def _dir(side: TradeDirection, *, buy: int = 18, sell: int = 82) -> DirectionDecision:
    return DirectionDecision(
        direction=side,
        buy_score=buy,
        sell_score=sell,
        reasons=("fixture",),
        structure_score=70,
        factors={},
    )


def _fvg(
    *,
    side: str = "BEARISH",
    high: str = "4628.00",
    low: str = "4624.00",
    timeframe: Timeframe = Timeframe.M15,
    freshness_bars: int = 3,
    formed_at: datetime | None = None,
) -> MagicMock:
    zone = MagicMock()
    zone.high_price = Price.of(high)
    zone.low_price = Price.of(low)
    zone.timeframe = timeframe
    zone.formed_at = formed_at or datetime.now(UTC)
    gap = MagicMock()
    gap.side = side
    gap.bias = None
    gap.direction = None
    gap.zone = zone
    gap.timeframe = timeframe
    gap.quality = MagicMock()
    gap.quality.freshness_bars = freshness_bars
    gap.lifecycle = MagicMock(detected_at=zone.formed_at)
    return gap


def _sniper(snap: MagicMock, direction: DirectionDecision, **kwargs: object) -> object:
    defaults: dict[str, object] = {
        "mid": Decimal("4618.00"),
        "bid": Decimal("4617.90"),
        "ask": Decimal("4618.10"),
        "atr": Decimal("5.61"),
        "atr_timeframe": "M5",
        "expected_rr": MIN_RR,
        "min_expected_rr": MIN_RR,
        "stop_loss": Decimal("4628.00"),
        "setup_family_direction": None,
        "spread_reject": False,
        "pa_score": 70,
        "momentum": 70,
        "min_momentum": 55,
        "config": DEFAULT_AI_SCALPING_CONFIG,
    }
    defaults.update(kwargs)
    return evaluate_sniper_entry(snap, direction=direction, **defaults)  # type: ignore[arg-type]


def test_buy_sniper_setup_is_take_candidate() -> None:
    snap = _snap(
        fvgs=[_fvg(side="BULLISH", high="2612", low="2608")],
        bos=[MagicMock(direction="UP", trend_direction="UP")],
        sweeps=[MagicMock(side="LOW")],
    )
    out = _sniper(
        snap,
        _dir(TradeDirection.BUY, buy=82, sell=18),
        mid=Decimal("2610"),
        bid=Decimal("2609.90"),
        ask=Decimal("2610.10"),
        stop_loss=Decimal("2604"),
    )
    assert out.passed is True
    assert out.action == "BUY"


def test_sell_sniper_setup_is_take_candidate() -> None:
    snap = _snap(fvgs=[_fvg(side="BEARISH", high="4628", low="4624")])
    out = _sniper(snap, _dir(TradeDirection.SELL))
    assert out.passed is True
    assert out.action == "SELL"
    assert out.pillars["not_chasing"] is True


def test_conflicting_buy_sell_is_wait() -> None:
    snap = _snap(fvgs=[_fvg(side="BEARISH")])
    out = _sniper(
        snap,
        _dir(TradeDirection.SELL),
        setup_family_direction="BUY",
    )
    assert out.passed is False
    assert out.action == "WAIT"
    assert out.primary_reason == "WAIT_CONFLICTING_BUY_SELL"


def test_weak_setup_is_wait() -> None:
    snap = _snap()
    out = _sniper(snap, _dir(TradeDirection.SELL), pa_score=0, momentum=0)
    assert out.passed is False
    assert out.action == "WAIT"
    assert out.primary_reason in {"WAIT_NO_SNIPER_TRIGGER", "WAIT_SNIPER_INCOMPLETE"}


def test_already_extended_fvg_is_wait_chase() -> None:
    """Price already >1.5 zone-TF ATR beyond the nearest SELL FVG."""
    snap = _snap(fvgs=[_fvg(side="BEARISH", high="4648", low="4644")])
    out = _sniper(snap, _dir(TradeDirection.SELL))
    assert out.passed is False
    assert out.action == "WAIT"
    assert out.primary_reason == "WAIT_CHASE"
    assert out.pillars["not_chasing"] is False
    assert out.diagnostics["chase_distance"] is not None


def test_fresh_m15_fvg_not_rejected_by_m5_atr() -> None:
    """M5 ATR vs M15 FVG must not false-chase a still-nearby gap."""
    snap = _snap(fvgs=[_fvg(side="BEARISH", high="4628.00", low="4624.00")])
    out = _sniper(
        snap,
        _dir(TradeDirection.SELL),
        bid=Decimal("4617.90"),
        ask=Decimal("4618.10"),
        mid=Decimal("4618.00"),
        atr=Decimal("5.61"),
        atr_timeframe="M5",
    )
    assert out.primary_reason != "WAIT_CHASE"
    assert out.passed is True
    assert out.action == "SELL"


def test_stale_fvg_is_wait_chase_or_stale() -> None:
    old = datetime.now(UTC) - timedelta(hours=20)
    snap = _snap(
        fvgs=[
            _fvg(
                side="BEARISH",
                high="4648",
                low="4644",
                freshness_bars=80,
                formed_at=old,
            )
        ]
    )
    out = _sniper(snap, _dir(TradeDirection.SELL))
    assert out.passed is False
    assert out.action == "WAIT"
    assert out.primary_reason in {"WAIT_CHASE", "WAIT_STALE_FVG"}


def test_stale_near_fvg_cannot_take() -> None:
    old = datetime.now(UTC) - timedelta(hours=20)
    snap = _snap(
        fvgs=[
            _fvg(
                side="BEARISH",
                high="4620",
                low="4616",
                freshness_bars=90,
                formed_at=old,
            )
        ]
    )
    out = _sniper(snap, _dir(TradeDirection.SELL))
    assert out.passed is False
    assert out.primary_reason == "WAIT_STALE_FVG"


def test_abnormal_spread_is_wait() -> None:
    snap = _snap(fvgs=[_fvg()])
    out = _sniper(snap, _dir(TradeDirection.SELL), spread_reject=True)
    assert out.passed is False
    assert out.primary_reason == "WAIT_ABNORMAL_SPREAD"


def test_stale_market_data_blocks_execution() -> None:
    stale = evaluate_market_data_firewall(
        symbol="XAUUSD_i",
        bid=4617.90,
        ask=4618.10,
        quote_age_seconds=200.0,
    )
    assert stale.state is MarketDataState.MARKET_DATA_STALE
    assert stale.allow_new_entry is False


def test_opportunity_threshold_remains_70() -> None:
    assert OPPORTUNITY_SCORE_THRESHOLD == 70
    assert DEFAULT_AI_SCALPING_CONFIG.allow_martingale is False


def test_absent_bos_sentinel_does_not_count_as_structure() -> None:
    """factors.bos=20 means no BOS — must not average to structure 20."""
    weak = evaluate_from_score_dict(
        {
            "direction": "SELL",
            "trade_quality": 48,
            "ai_confidence": 38,
            "structure_score": 18,
            "momentum": 0,
            "liquidity": 65,
            "spread_score": 100,
            "expected_rr": Decimal("1.20"),
            "market_regime": "range",
            "mtf_alignment": 0,
            "pa_confluence": 41,
            "factors": {
                "bos": 20,
                "choch": 20,
                "fvg": 25,
                "order_block": 20,
                "liquidity_sweep": 65,
            },
        }
    )
    assert weak.threshold == 70
    assert weak.score_breakdown.get("structure", 0) <= 18
    assert weak.opportunity_score < 70
    assert weak.eligible is False


def test_live_fvg_maps_into_opportunity_structure() -> None:
    mapped = evaluate_from_score_dict(
        {
            "direction": "SELL",
            "trade_quality": 48,
            "ai_confidence": 38,
            "structure_score": 18,
            "momentum": 0,
            "liquidity": 65,
            "spread_score": 100,
            "expected_rr": Decimal("1.20"),
            "market_regime": "range",
            "mtf_alignment": 0,
            "pa_confluence": 41,
            "factors": {
                "bos": 20,
                "choch": 20,
                "fvg": 80,
                "order_block": 20,
                "liquidity_sweep": 65,
            },
        }
    )
    assert mapped.threshold == 70
    assert mapped.score_breakdown["structure"] == 80
    assert mapped.score_breakdown["liquidity"] == 80
    assert mapped.opportunity_score < 70


def test_valid_score_and_sniper_gates_are_take_candidate() -> None:
    snap = _snap(
        fvgs=[_fvg(side="BEARISH", high="4628", low="4624")],
        bos=[MagicMock(trend_direction="DOWN", direction="DOWN")],
    )
    sniper = _sniper(snap, _dir(TradeDirection.SELL))
    assert sniper.passed is True
    verdict = evaluate_from_score_dict(
        {
            "direction": "SELL",
            "trade_quality": 84,
            "ai_confidence": 82,
            "structure_score": 80,
            "momentum": 74,
            "liquidity": 88,
            "spread_score": 90,
            "expected_rr": Decimal("1.40"),
            "market_regime": "trend",
            "mtf_alignment": 80,
            "pa_confluence": 72,
            "factors": {
                "bos": 85,
                "choch": 80,
                "fvg": 80,
                "order_block": 85,
                "momentum": 74,
            },
        }
    )
    assert verdict.opportunity_score >= 70
    assert verdict.eligible is True
    assert verdict.next_action == "RISK_ASSESSMENT"


def test_risk_rejection_does_not_reach_oms() -> None:
    out = MultiAgentSystem().collaborate(
        CollaborationInput(
            side="sell",
            spread=Decimal("0.4"),
            confidence=Decimal("75"),
            regime="trend",
            strategy_id="gold-a",
            strategy_signal="sell",
            portfolio_exposure=Decimal("15"),
            open_positions=1,
            execution_mode="LIVE",
            news_blackout=False,
            kill_switch=False,
            risk_engine_passed=False,
            safety_engine_passed=True,
        )
    )
    assert out["allow_execution_path"] is False


def test_safety_rejection_does_not_reach_oms() -> None:
    out = MultiAgentSystem().collaborate(
        CollaborationInput(
            side="buy",
            spread=Decimal("0.4"),
            confidence=Decimal("75"),
            regime="trend",
            strategy_id="gold-a",
            strategy_signal="buy",
            portfolio_exposure=Decimal("15"),
            open_positions=1,
            execution_mode="LIVE",
            news_blackout=False,
            kill_switch=False,
            risk_engine_passed=True,
            safety_engine_passed=False,
        )
    )
    assert out["allow_execution_path"] is False


def test_duplicate_signal_one_oms_claim() -> None:
    dup = DuplicateProtection()
    first = dup.claim("xauusd-sniper-req-1")
    second = dup.claim("xauusd-sniper-req-1")
    assert first["allowed"] is True
    assert second["allowed"] is False
    assert second["duplicate"] is True
    assert should_blind_retry_order_submit() is False


def test_unavailable_account_facts_fail_closed() -> None:
    blocked = may_add_scalping_trade(
        open_positions=1,
        max_open=3,
        new_confidence=80,
        best_open_confidence=70,
        new_direction="SELL",
        open_directions=("SELL",),
        require_unrealized_profit=True,
        open_profits=(),
    )
    assert blocked.allow is False


def test_losing_position_no_scale_in() -> None:
    blocked = may_add_scalping_trade(
        open_positions=1,
        max_open=3,
        new_confidence=80,
        best_open_confidence=70,
        new_direction="SELL",
        open_directions=("SELL",),
        require_unrealized_profit=True,
        open_profits=(Decimal("-12.50"),),
    )
    assert blocked.allow is False


def test_profitable_position_new_signal_scale_in_candidate() -> None:
    allowed = may_add_scalping_trade(
        open_positions=1,
        max_open=3,
        new_confidence=84,
        best_open_confidence=70,
        new_direction="SELL",
        open_directions=("SELL",),
        require_unrealized_profit=True,
        require_improvement=True,
        min_confidence_delta=3,
        open_profits=(Decimal("18.00"),),
        same_direction_profits=(Decimal("18.00"),),
    )
    assert allowed.allow is True


def test_non_xauusd_hard_reject(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.domain.trading.gold_only.gold_only_enabled",
        lambda: True,
    )
    with pytest.raises(DisabledAutonomousSymbolError):
        require_xauusd("EURUSD")


def test_martingale_and_revenge_impossible() -> None:
    assert DEFAULT_AI_SCALPING_CONFIG.allow_martingale is False
    cfg = DEFAULT_AI_SCALPING_CONFIG
    assert getattr(cfg, "allow_martingale", True) is False
    loser = may_add_scalping_trade(
        open_positions=1,
        max_open=5,
        new_confidence=90,
        best_open_confidence=40,
        new_direction="SELL",
        open_directions=("SELL",),
        require_unrealized_profit=True,
        open_profits=(Decimal("-4.00"),),
    )
    assert loser.allow is False


def test_restart_does_not_blind_resend() -> None:
    assert should_blind_retry_order_submit() is False
    dup = DuplicateProtection()
    dup.claim("restart-req-1")
    again = dup.claim("restart-req-1")
    assert again["duplicate"] is True


def test_buy_sell_field_mapping_from_production_fvg_price() -> None:
    """Production FairValueGapZone uses Price objects + side enum, not .direction."""
    snap = _snap(fvgs=[_fvg(side="BEARISH")])
    out = _sniper(snap, _dir(TradeDirection.SELL))
    assert out.pillars["entry_zone"] is True
    assert out.pillars["liquidity_event"] is False
    assert out.diagnostics["ref_price"] == "4617.90"
    assert out.diagnostics["zone_source"] == "fvg"


def test_missing_zone_timeframe_defaults_to_m15_structure_atr() -> None:
    """If FVG timeframe is blank, still scale M5 ATR to M15 — do not false-chase."""
    gap = _fvg(side="BEARISH", high="4628.00", low="4624.00")
    gap.zone.timeframe = None
    gap.timeframe = None
    snap = _snap(fvgs=[gap])
    out = _sniper(snap, _dir(TradeDirection.SELL), atr_timeframe="M5")
    assert out.primary_reason != "WAIT_CHASE"
    assert out.passed is True
    assert out.diagnostics.get("setup_state") == "TAKE"


def test_chase_uses_bid_for_sell_not_ask() -> None:
    snap = _snap(fvgs=[_fvg(side="BEARISH", high="4628", low="4624")])
    out = _sniper(
        snap,
        _dir(TradeDirection.SELL),
        bid=Decimal("4617.90"),
        ask=Decimal("4700.00"),
        mid=Decimal("4658.95"),
    )
    assert out.diagnostics["ref_price"] == "4617.90"
    assert out.passed is True


def test_fresh_buy_and_sell_are_setup_ready() -> None:
    buy = _sniper(
        _snap(fvgs=[_fvg(side="BULLISH", high="2612", low="2608")]),
        _dir(TradeDirection.BUY, buy=82, sell=18),
        mid=Decimal("2610"),
        bid=Decimal("2609.90"),
        ask=Decimal("2610.10"),
        stop_loss=Decimal("2604"),
    )
    sell = _sniper(
        _snap(fvgs=[_fvg(side="BEARISH")]),
        _dir(TradeDirection.SELL),
    )
    assert buy.diagnostics["setup_state"] == "TAKE"
    assert buy.passed is True
    assert sell.diagnostics["setup_state"] == "TAKE"
    assert sell.passed is True


def test_extended_setup_is_invalidated_wait_chase() -> None:
    out = _sniper(
        _snap(fvgs=[_fvg(side="BEARISH", high="4648", low="4644")]),
        _dir(TradeDirection.SELL),
    )
    assert out.primary_reason == "WAIT_CHASE"
    assert out.diagnostics["setup_state"] == "CHASING"
    assert out.diagnostics["canonical_blocker"] == "WAIT_CHASE"


def test_opportunity_pass_does_not_fake_sniper_or_risk() -> None:
    from app.application.services.signal_center_service import _row_from_score

    row = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "SELL",
            "signal_action": "WAIT",
            "opportunity_score": 73,
            "opportunity_threshold": 70,
            "buy_score": 6,
            "sell_score": 48,
            "reject": True,
            "reject_reason": "WAIT_CHASE",
            "sniper_entry": {
                "passed": False,
                "action": "WAIT",
                "setup_state": "INVALIDATED",
                "primary_reason": "WAIT_CHASE",
            },
            "quote_age_seconds": 0.4,
            "market_data_live": True,
        }
    )
    assert row["pipeline"]["opportunity_gate"] == "PASS"
    assert row["pipeline"]["sniper"] == "WAIT"
    assert row["first_blocker"] == "WAIT_CHASE"
    assert row["pipeline"]["risk"] == "NOT_REACHED"
    assert row["pipeline"]["safety"] == "NOT_REACHED"
    assert row["pipeline"]["oms"] == "NOT_REACHED"


def test_m1_m5_m15_exist_m3_is_not_a_broker_bar() -> None:
    assert Timeframe.M1.value == "M1"
    assert Timeframe.M5.value == "M5"
    assert Timeframe.M15.value == "M15"
    assert not hasattr(Timeframe, "M3")
    assert DEFAULT_AI_SCALPING_CONFIG.execution_tf is Timeframe.M1
    assert DEFAULT_AI_SCALPING_CONFIG.entry_tf is Timeframe.M5
    assert DEFAULT_AI_SCALPING_CONFIG.structure_tf is Timeframe.M15
    assert DEFAULT_AI_SCALPING_CONFIG.direction_tf is Timeframe.H1


def _bos(direction: str) -> MagicMock:
    br = MagicMock()
    br.direction = direction
    br.trend_direction = direction
    br.bias = direction
    return br


def _ob(
    *,
    bias: str,
    high: str = "2612",
    low: str = "2608",
    timeframe: Timeframe | None = Timeframe.M15,
) -> MagicMock:
    zone = MagicMock()
    zone.high_price = Price.of(high)
    zone.low_price = Price.of(low)
    zone.timeframe = timeframe
    zone.formed_at = datetime.now(UTC)
    quality = MagicMock()
    quality.displacement_ratio = Decimal("1.8")
    quality.freshness_bars = 2
    block = MagicMock()
    block.state = "ACTIVE"
    block.bias = bias
    block.side = bias
    block.quality = quality
    block.zone = zone
    block.timeframe = timeframe
    return block


def test_tier_a_full_sniper_is_take() -> None:
    snap = _snap(
        fvgs=[_fvg(side="BULLISH", high="2612", low="2608")],
        bos=[_bos("UP")],
        sweeps=[MagicMock(side="LOW")],
    )
    out = _sniper(
        snap,
        _dir(TradeDirection.BUY, buy=82, sell=18),
        mid=Decimal("2610"),
        bid=Decimal("2609.90"),
        ask=Decimal("2610.10"),
        stop_loss=Decimal("2604"),
    )
    assert out.passed is True
    assert out.action == "BUY"
    assert out.diagnostics["sniper_tier"] == "A"
    assert out.diagnostics["setup_state"] == "TAKE"
    assert out.diagnostics["entry_state"] == "RETEST"


def test_tier_b_confirmed_scalp_without_momentum() -> None:
    """Liquidity + structure without momentum is Tier B, not a forced trade."""
    snap = _snap(
        fvgs=[_fvg(side="BEARISH", high="4628", low="4624")],
        bos=[_bos("DOWN")],
    )
    out = _sniper(
        snap,
        _dir(TradeDirection.SELL),
        pa_score=20,
        momentum=0,
        min_momentum=65,
    )
    assert out.passed is True
    assert out.action == "SELL"
    assert out.diagnostics["sniper_tier"] == "B"
    assert out.pillars["displacement_or_momentum"] is False
    assert out.pillars["not_chasing"] is True


def test_tier_c_micro_scalp_requires_tight_spread() -> None:
    snap = _snap(bos=[_bos("UP")], sweeps=[MagicMock(side="LOW")])
    tight = _sniper(
        snap,
        _dir(TradeDirection.BUY, buy=82, sell=18),
        mid=Decimal("2610"),
        bid=Decimal("2609.95"),
        ask=Decimal("2610.05"),
        stop_loss=Decimal("2604"),
        spread_score=90,
        momentum=75,
        pa_score=70,
    )
    wide = _sniper(
        snap,
        _dir(TradeDirection.BUY, buy=82, sell=18),
        mid=Decimal("2610"),
        bid=Decimal("2609.95"),
        ask=Decimal("2610.05"),
        stop_loss=Decimal("2604"),
        spread_score=40,
        momentum=75,
        pa_score=70,
    )
    assert tight.passed is True
    assert tight.diagnostics["sniper_tier"] == "C"
    assert wide.passed is True
    assert wide.diagnostics["sniper_tier"] == "B"


def test_inside_fvg_is_retest_not_chase() -> None:
    snap = _snap(fvgs=[_fvg(side="BEARISH", high="4628.00", low="4624.00")])
    out = _sniper(
        snap,
        _dir(TradeDirection.SELL),
        bid=Decimal("4626.00"),
        ask=Decimal("4626.20"),
        mid=Decimal("4626.10"),
        atr=Decimal("5.61"),
        atr_timeframe="M5",
    )
    assert out.passed is True
    assert out.diagnostics["entry_state"] == "RETEST"
    assert out.primary_reason != "WAIT_CHASE"
    chase = out.diagnostics.get("chase") or {}
    assert chase.get("zone_timeframe") in {"M15", Timeframe.M15.value}
    assert chase.get("atr_timeframe") == "M5"
    assert chase.get("entry_state") == "RETEST"


def test_m5_execution_fvg_uses_m5_atr_not_m15() -> None:
    """Originating M5 zone must use M5 ATR — a 10-point extension is a chase."""
    snap = _snap(
        fvgs=[
            _fvg(
                side="BEARISH",
                high="4628.00",
                low="4624.00",
                timeframe=Timeframe.M5,
            )
        ]
    )
    out = _sniper(
        snap,
        _dir(TradeDirection.SELL),
        bid=Decimal("4614.00"),
        ask=Decimal("4614.20"),
        mid=Decimal("4614.10"),
        atr=Decimal("5.61"),
        atr_timeframe="M5",
    )
    assert out.passed is False
    assert out.primary_reason == "WAIT_CHASE"
    assert out.diagnostics["entry_state"] == "EXTENDED"
    chase = out.diagnostics.get("chase") or {}
    assert chase.get("zone_timeframe") in {"M5", Timeframe.M5.value}
    assert chase.get("atr_timeframe") == "M5"
    assert Decimal(str(chase.get("normalized_extension") or "0")) > Decimal("1.5")


def test_genuine_chase_documents_zone_and_atr() -> None:
    out = _sniper(
        _snap(fvgs=[_fvg(side="BEARISH", high="4648", low="4644")]),
        _dir(TradeDirection.SELL),
    )
    assert out.primary_reason == "WAIT_CHASE"
    chase = out.diagnostics.get("chase") or {}
    assert chase.get("zone_timeframe") in {"M15", Timeframe.M15.value}
    assert chase.get("atr_timeframe") == "M5"
    assert chase.get("atr_value")
    assert chase.get("zone_distance")
    assert chase.get("normalized_extension")
    assert chase.get("entry_state") == "EXTENDED"


def test_ob_retest_uses_originating_timeframe() -> None:
    snap = _snap(
        order_blocks=[
            _ob(bias="BUY", high="2612", low="2608", timeframe=Timeframe.H1)
        ],
        bos=[_bos("UP")],
        sweeps=[MagicMock(side="LOW")],
    )
    out = _sniper(
        snap,
        _dir(TradeDirection.BUY, buy=82, sell=18),
        mid=Decimal("2610"),
        bid=Decimal("2609.90"),
        ask=Decimal("2610.10"),
        stop_loss=Decimal("2604"),
        atr=Decimal("5.61"),
        atr_timeframe="M5",
    )
    assert out.passed is True
    assert out.diagnostics["zone_source"] == "ob"
    assert out.diagnostics["entry_state"] == "RETEST"
    chase = out.diagnostics.get("chase") or {}
    assert chase.get("zone_timeframe") in {"H1", Timeframe.H1.value}


def test_ob_missing_timeframe_scales_m5_atr_to_m15_not_false_chase() -> None:
    """M15 OB without TF metadata must not use raw M5 1.5×ATR as chase."""
    from app.domain.institutional_trading.ai_scalping.sniper_entry import _atr_for_zone

    m5 = Decimal("5.61")
    scaled = _atr_for_zone(
        m5, atr_timeframe="M5", zone_timeframe=None, source="ob"
    )
    assert scaled > m5
    snap = _snap(
        order_blocks=[_ob(bias="BUY", high="2612", low="2608", timeframe=None)],
        bos=[_bos("UP")],
        sweeps=[MagicMock(side="LOW")],
    )
    out = _sniper(
        snap,
        _dir(TradeDirection.BUY, buy=82, sell=18),
        mid=Decimal("2622"),
        bid=Decimal("2621.90"),
        ask=Decimal("2622.10"),
        stop_loss=Decimal("2604"),
        atr=m5,
        atr_timeframe="M5",
    )
    assert out.primary_reason != "WAIT_CHASE"
    chase = out.diagnostics.get("chase") or {}
    assert Decimal(str(chase.get("atr_value") or "0")) == scaled


def test_genuine_ob_chase_still_rejects() -> None:
    snap = _snap(
        order_blocks=[_ob(bias="BUY", high="2612", low="2608", timeframe=None)],
        bos=[_bos("UP")],
        sweeps=[MagicMock(side="LOW")],
    )
    out = _sniper(
        snap,
        _dir(TradeDirection.BUY, buy=82, sell=18),
        mid=Decimal("2645"),
        bid=Decimal("2644.90"),
        ask=Decimal("2645.10"),
        stop_loss=Decimal("2604"),
        atr=Decimal("5.61"),
        atr_timeframe="M5",
    )
    assert out.passed is False
    assert out.primary_reason == "WAIT_CHASE"
    assert out.diagnostics["entry_state"] == "EXTENDED"


def test_setup_forming_never_executes() -> None:
    snap = _snap(fvgs=[_fvg(side="BEARISH", high="4628", low="4624")])
    out = _sniper(
        snap,
        _dir(TradeDirection.SELL),
        pa_score=20,
        momentum=0,
        min_momentum=65,
        expected_rr=Decimal("0.40"),
        min_expected_rr=MIN_RR,
    )
    assert out.passed is False
    assert out.action == "WAIT"
    assert out.diagnostics["setup_state"] in {"SETUP_FORMING", "WAIT"}
    assert out.diagnostics.get("sniper_tier") is None


def test_operator_regime_labels_are_display_only() -> None:
    from app.domain.institutional_trading.ai_scalping.regime import (
        operator_regime_label,
    )

    assert operator_regime_label("strong_trend", direction="BUY") == "TREND_UP"
    assert operator_regime_label("strong_trend", direction="SELL") == "TREND_DOWN"
    assert operator_regime_label("range") == "RANGE"
    assert operator_regime_label("breakout") == "BREAKOUT"
    assert operator_regime_label("expansion") == "HIGH_VOLATILITY"
    assert operator_regime_label("compression") == "LOW_LIQUIDITY"
    assert (
        operator_regime_label("range", setup_family="fvg_retest") == "RETEST"
    )
    assert operator_regime_label("range", no_trade=True) == "NO_TRADE"


def test_opportunity_threshold_stays_at_seventy() -> None:
    assert OPPORTUNITY_SCORE_THRESHOLD == 70


def test_signal_center_exposes_tier_and_keeps_risk_not_reached() -> None:
    from app.application.services.signal_center_service import _row_from_score

    row = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "BUY",
            "signal_action": "WAIT",
            "opportunity_score": 81,
            "opportunity_threshold": 70,
            "buy_score": 72,
            "sell_score": 31,
            "reject": True,
            "reject_reason": "WAIT_CHASE",
            "operator_regime": "TREND_DOWN",
            "sniper_entry": {
                "passed": False,
                "action": "WAIT",
                "setup_state": "INVALIDATED",
                "primary_reason": "WAIT_CHASE",
                "sniper_tier": None,
                "entry_state": "EXTENDED",
                "zone_timeframe": "M15",
                "atr_timeframe": "M5",
                "zone_atr": "9.72",
                "normalized_extension": "2.40",
            },
            "quote_age_seconds": 0.4,
            "market_data_live": True,
        }
    )
    assert row["pipeline"]["opportunity_gate"] == "PASS"
    assert row["pipeline"]["sniper"] == "WAIT"
    assert row["pipeline"]["entry_state"] == "EXTENDED"
    assert row["pipeline"]["market_regime"] == "TREND_DOWN"
    assert row["pipeline"]["risk"] == "NOT_REACHED"
    assert row["pipeline"]["safety"] == "NOT_REACHED"
    assert row["pipeline"]["oms"] == "NOT_REACHED"
