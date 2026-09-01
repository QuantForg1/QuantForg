"""XAUUSD sniper v2 — two-stage detection without lowering hard gates.

Does not send orders. Does not lower opportunity 70, Risk, Safety, or OMS.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.application.services.signal_center_service import (
    _overlay_last_ite_cycle,
    _row_from_score,
)
from app.application.services.strategy_diagnostics import hourly_scan_rates
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    AiScalpingConfig,
)
from app.domain.institutional_trading.ai_scalping.direction import (
    DirectionDecision,
    decide_scalping_direction,
)
from app.domain.institutional_trading.ai_scalping.duplicate_guard import (
    may_add_scalping_trade,
)
from app.domain.institutional_trading.ai_scalping.scoring import AiScalpingScore, score_scalping_setup
from app.domain.institutional_trading.ai_scalping.sniper_entry import (
    evaluate_sniper_entry,
)
from app.domain.institutional_trading.config import MAX_DAILY_LOSS_PCT
from app.domain.institutional_trading.decision_models import TradeDirection
from app.domain.institutional_trading.operations.daily_loss_lock import (
    utc_daily_loss_exceeded,
)
from app.domain.institutional_trading.operations.execution_chain_log import (
    bridge_abort_stage,
    build_execution_handoff,
)
from app.domain.institutional_trading.operations.gold_execution_contract import (
    GoldExecutionFacts,
    evaluate_gold_execution_contract,
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

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

MIN_RR = Decimal("1.20")


def _struct(*, bos: list[object] | None = None, choch: list[object] | None = None) -> MagicMock:
    structure = MagicMock()
    structure.breaks_of_structure = list(bos or [])
    structure.changes_of_character = list(choch or [])
    structure.swings = []
    return structure


def _bos(direction: str) -> MagicMock:
    br = MagicMock()
    br.direction = direction
    br.trend_direction = direction
    return br


def _fvg(*, side: str, high: str, low: str, freshness: int = 3) -> MagicMock:
    zone = MagicMock()
    zone.high_price = Decimal(high)
    zone.low_price = Decimal(low)
    zone.timeframe = Timeframe.M15
    zone.formed_at = datetime.now(UTC)
    gap = MagicMock()
    gap.side = side
    gap.bias = None
    gap.direction = None
    gap.zone = zone
    gap.timeframe = Timeframe.M15
    gap.quality = MagicMock(freshness_bars=freshness)
    gap.lifecycle = MagicMock(detected_at=zone.formed_at)
    return gap


def _ob(
    *,
    bias: str,
    high: str = "2612",
    low: str = "2608",
    disp: str = "1.8",
    freshness: int = 3,
) -> MagicMock:
    zone = MagicMock()
    zone.high_price = Decimal(high)
    zone.low_price = Decimal(low)
    zone.timeframe = Timeframe.M5
    zone.formed_at = datetime.now(UTC)
    quality = MagicMock()
    quality.displacement_ratio = Decimal(disp)
    quality.freshness_bars = freshness
    block = MagicMock()
    block.state = "ACTIVE"
    block.bias = bias
    block.side = bias
    block.quality = quality
    block.zone = zone
    block.timeframe = Timeframe.M5
    block.formed_at = zone.formed_at
    return block


def _snap(
    *,
    macro: TrendDirection = TrendDirection.UP,
    primary: TrendDirection = TrendDirection.UP,
    entry: TrendDirection | None = None,
    execution: TrendDirection | None = None,
    m1: MagicMock | None = None,
    m5: MagicMock | None = None,
    m15: MagicMock | None = None,
    sweeps: list[object] | None = None,
    fvgs: list[object] | None = None,
    obs: list[object] | None = None,
) -> MagicMock:
    trend = MagicMock()
    trend.macro_bias = macro
    trend.primary = primary
    trend.entry = entry if entry is not None else TrendDirection.UNKNOWN
    trend.execution = execution if execution is not None else TrendDirection.UNKNOWN
    trend.alignment_score = 70
    primary_structure = m15 or _struct()
    liq = MagicMock()
    liq.sweeps = list(sweeps or [])
    liq.equal_highs = []
    liq.equal_lows = []
    liq.pools = []
    snap = MagicMock()
    snap.trend = trend
    snap.primary_structure = primary_structure
    snap.structure_by_tf = {
        "M1": m1 or _struct(),
        "M5": m5 or _struct(),
        "M15": primary_structure,
    }
    snap.liquidity = liq
    snap.order_blocks = MagicMock(order_blocks=list(obs or []))
    snap.fair_value_gaps = MagicMock(active_gaps=list(fvgs or []))
    snap.trade_quality = MagicMock(total=80, components={"momentum": 70})
    snap.session = MagicMock(session=MagicMock(value="london"), allowed=True)
    snap.spread = Decimal("0.20")
    snap.symbol = "XAUUSD_i"
    return snap


def _dir(side: TradeDirection, *, buy: int = 82, sell: int = 18) -> DirectionDecision:
    return DirectionDecision(
        direction=side,
        buy_score=buy,
        sell_score=sell,
        reasons=("fixture",),
        structure_score=70,
        factors={},
    )


def _sniper(snap: MagicMock, direction: DirectionDecision, **kwargs: object) -> object:
    defaults: dict[str, object] = {
        "mid": Decimal("2610"),
        "bid": Decimal("2609.90"),
        "ask": Decimal("2610.10"),
        "atr": Decimal("4.00"),
        "atr_timeframe": "M5",
        "expected_rr": MIN_RR,
        "min_expected_rr": MIN_RR,
        "stop_loss": Decimal("2604"),
        "pa_score": 70,
        "momentum": 70,
        "min_momentum": 55,
        "config": DEFAULT_AI_SCALPING_CONFIG,
    }
    defaults.update(kwargs)
    return evaluate_sniper_entry(snap, direction=direction, **defaults)  # type: ignore[arg-type]


def _ready(**overrides: object) -> GoldExecutionFacts:
    base = dict(
        symbol="XAUUSD_I",
        direction="BUY",
        action="BUY",
        market_open=True,
        tradable=True,
        candles_ok=True,
        bid=Decimal("2400.10"),
        ask=Decimal("2400.30"),
        quote_age_seconds=1.0,
        spread=Decimal("0.20"),
        structure_score=70,
        momentum_score=65,
        quality=80,
        confidence=75,
        pa_confluence=55,
        risk_reward=Decimal("1.20"),
        market_regime="TREND",
        volatility_ok=True,
        session_quality_ok=True,
        safety_allowed=True,
        kill_switch=False,
        execution_enabled=True,
        auto_running=True,
        account_leverage=Decimal("2000"),
        risk_eligible=True,
        approved_lots=Decimal("0.01"),
        min_lot_infeasible=False,
        portfolio_allow=True,
        optimizer_state="EXECUTE_NOW",
        oms_orders_allowed=True,
        gateway_connected=True,
        broker_connected=True,
        force_shadow=False,
        gold_only=True,
        opportunity_score=80,
        opportunity_threshold=70,
    )
    base.update(overrides)
    return GoldExecutionFacts(**base)  # type: ignore[arg-type]


def test_a_m1_trigger_m5_confirm_m15_context_is_take() -> None:
    snap = _snap(
        entry=TrendDirection.UP,
        execution=TrendDirection.UP,
        m1=_struct(bos=[_bos("UP")]),
        m5=_struct(choch=[_bos("UP")]),
        fvgs=[_fvg(side="BULLISH", high="2612", low="2608")],
    )
    out = _sniper(snap, _dir(TradeDirection.BUY))
    assert out.passed is True
    assert out.action == "BUY"
    assert out.diagnostics["setup_state"] == "TAKE"
    assert "structure" in out.diagnostics["independent_evidence"]
    assert "zone" in out.diagnostics["independent_evidence"]


def test_b_m5_trigger_m15_confirmation_is_take() -> None:
    snap = _snap(
        m5=_struct(bos=[_bos("UP")]),
        fvgs=[_fvg(side="BULLISH", high="2612", low="2608")],
    )
    out = _sniper(snap, _dir(TradeDirection.BUY), momentum=0, pa_score=20, min_momentum=65)
    assert out.passed is True
    assert out.action == "BUY"
    assert out.diagnostics["setup_state"] == "TAKE"


def test_c_m15_context_without_m1_m5_trigger_is_forming_or_wait() -> None:
    trend_only = _sniper(_snap(), _dir(TradeDirection.BUY), momentum=0, pa_score=20)
    assert trend_only.passed is False
    assert trend_only.primary_reason == "WAIT_NO_SNIPER_TRIGGER"

    early = _sniper(
        _snap(fvgs=[_fvg(side="BULLISH", high="2620", low="2616")]),
        _dir(TradeDirection.BUY),
        mid=Decimal("2605"),
        bid=Decimal("2604.90"),
        ask=Decimal("2605.10"),
        momentum=0,
        pa_score=20,
        min_momentum=65,
    )
    assert early.passed is False
    assert early.diagnostics["setup_state"] in {"SETUP_READY", "SETUP_FORMING", "WAIT"}
    assert early.action == "WAIT"


def test_d_genuine_chase_is_wait_chase() -> None:
    out = _sniper(
        _snap(fvgs=[_fvg(side="BULLISH", high="2500", low="2496")]),
        _dir(TradeDirection.BUY),
        mid=Decimal("2610"),
        bid=Decimal("2609.90"),
        ask=Decimal("2610.10"),
    )
    assert out.passed is False
    assert out.primary_reason == "WAIT_CHASE"
    assert out.diagnostics["setup_state"] == "CHASING"


def test_e_stale_data_is_wait_stale() -> None:
    firewall = evaluate_market_data_firewall(
        symbol="XAUUSD_i",
        bid=2610.0,
        ask=2610.2,
        quote_age_seconds=200.0,
    )
    assert firewall.state is MarketDataState.MARKET_DATA_STALE
    assert firewall.allow_new_entry is False

    gap = _fvg(side="BULLISH", high="2612", low="2608", freshness=80)
    gap.zone.formed_at = datetime.now(UTC) - timedelta(hours=20)
    out = _sniper(_snap(fvgs=[gap]), _dir(TradeDirection.BUY))
    assert out.passed is False
    assert out.primary_reason == "WAIT_STALE_FVG"
    assert out.diagnostics["setup_state"] == "STALE"


def test_f_conflicting_buy_sell_is_wait_conflict() -> None:
    snap = _snap(m5=_struct(bos=[_bos("UP")]), sweeps=[MagicMock(side="LOW")])
    out = _sniper(snap, _dir(TradeDirection.BUY), setup_family_direction="SELL")
    assert out.passed is False
    assert out.primary_reason == "WAIT_CONFLICTING_BUY_SELL"
    assert out.diagnostics["setup_state"] == "CONFLICT"


def test_g_valid_buy() -> None:
    snap = _snap(
        m1=_struct(bos=[_bos("UP")]),
        sweeps=[MagicMock(side="LOW")],
        fvgs=[_fvg(side="BULLISH", high="2612", low="2608")],
    )
    out = _sniper(snap, _dir(TradeDirection.BUY))
    assert out.passed is True
    assert out.action == "BUY"
    assert out.diagnostics["buy_components"]["rr"] >= 10


def test_h_valid_sell() -> None:
    snap = _snap(
        macro=TrendDirection.DOWN,
        primary=TrendDirection.DOWN,
        m1=_struct(bos=[_bos("DOWN")]),
        sweeps=[MagicMock(side="HIGH")],
        fvgs=[_fvg(side="BEARISH", high="2612", low="2608")],
    )
    out = _sniper(
        snap,
        _dir(TradeDirection.SELL, buy=18, sell=82),
        stop_loss=Decimal("2618"),
    )
    assert out.passed is True
    assert out.action == "SELL"
    assert out.diagnostics["sell_components"]["rr"] >= 10


def test_i_opportunity_below_70_is_not_eligible() -> None:
    assert OPPORTUNITY_SCORE_THRESHOLD == 70
    weak = evaluate_from_score_dict(
        {
            "direction": "SELL",
            "trade_quality": 48,
            "ai_confidence": 38,
            "structure_score": 18,
            "momentum": 40,
            "liquidity": 50,
            "spread_score": 80,
            "expected_rr": Decimal("1.20"),
            "market_regime": "range",
            "mtf_alignment": 40,
            "pa_confluence": 41,
        }
    )
    assert weak.opportunity_score < 70
    assert weak.eligible is False


def test_j_opportunity_pass_with_incomplete_sniper_does_not_take() -> None:
    snap = _snap(fvgs=[_fvg(side="BULLISH", high="2620", low="2616")])
    out = _sniper(
        snap,
        _dir(TradeDirection.BUY),
        mid=Decimal("2605"),
        bid=Decimal("2604.90"),
        ask=Decimal("2605.10"),
        momentum=0,
        pa_score=20,
        min_momentum=65,
    )
    row = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "BUY",
            "signal_action": "WAIT",
            "opportunity_score": 73,
            "opportunity_threshold": 70,
            "buy_score": 64,
            "sell_score": 31,
            "reject": True,
            "reject_reason": out.primary_reason,
            "sniper_entry": out.to_dict(),
        }
    )
    assert row["pipeline"]["opportunity_gate"] == "PASS"
    assert row["pipeline"]["sniper"] == "WAIT"
    assert row["pipeline"]["setup_state"] == "SETUP_READY"
    assert row["pipeline"]["risk"] == "NOT_REACHED"
    assert out.passed is False


def test_k_sniper_take_maps_to_decision_take() -> None:
    score = AiScalpingScore(
        confidence=80,
        trade_quality=80,
        confluence=80,
        expected_rr=Decimal("1.40"),
        expected_hold_time="2-10m",
        market_regime="weak_trend",
        momentum=70,
        liquidity=70,
        spread_score=90,
        atr_pct=Decimal("0.20"),
        direction="BUY",
        factors={},
        thresholds={},
        reasons=(),
        reject=False,
        signal_action="BUY",
        sniper_entry={"passed": True, "action": "BUY", "setup_state": "TAKE"},
    )
    payload = score.to_dict()
    assert payload["setup_state"] == "TAKE"
    assert payload["signal_action"] == "BUY"


def test_l_risk_block_stops_before_safety() -> None:
    row = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "BUY",
            "signal_action": "BUY",
            "reject": True,
            "reject_reason": "RISK_BLOCK: daily loss or size rejected",
            "sniper_entry": {"passed": True, "action": "BUY", "setup_state": "TAKE"},
        }
    )
    assert row["pipeline"]["risk"] == "BLOCK"
    assert row["pipeline"]["safety"] == "NOT_REACHED"
    assert row["pipeline"]["oms"] == "NOT_REACHED"


def test_m_safety_block_stops_before_oms() -> None:
    row = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "BUY",
            "signal_action": "BUY",
            "reject": True,
            "reject_reason": "SAFETY_BLOCK: kill switch",
            "sniper_entry": {"passed": True, "action": "BUY", "setup_state": "TAKE"},
        }
    )
    assert row["pipeline"]["risk"] == "READY"
    assert row["pipeline"]["safety"] == "BLOCK"
    assert row["pipeline"]["oms"] == "NOT_REACHED"


def test_n_oms_rejection_is_not_executed() -> None:
    over = _overlay_last_ite_cycle(
        _row_from_score(
            {
                "symbol": "XAUUSD_I",
                "direction": "BUY",
                "signal_action": "BUY",
                "reject": False,
                "sniper_entry": {"passed": True, "action": "BUY", "setup_state": "TAKE"},
            }
        ),
        {
            "forwarded_to_oms": True,
            "mt5_ticket": None,
            "abort_reason": "OMS_REJECTED",
        },
    )
    assert over.get("execution_state") != "EXECUTED"


def test_o_mt5_rejection_is_not_executed() -> None:
    over = _overlay_last_ite_cycle(
        _row_from_score(
            {
                "symbol": "XAUUSD_I",
                "direction": "BUY",
                "signal_action": "BUY",
                "reject": False,
                "sniper_entry": {"passed": True, "action": "BUY", "setup_state": "TAKE"},
            }
        ),
        {
            "forwarded_to_oms": True,
            "mt5_ticket": None,
            "abort_reason": "MT5_REJECT retcode=10016",
        },
    )
    assert over.get("execution_state") != "EXECUTED"


def test_p_real_ticket_is_executed() -> None:
    handoff = build_execution_handoff(
        take=True, forwarded_to_oms=True, mt5_ticket=424242
    )
    assert handoff["execution_confirmed"] is True


def test_q_no_ticket_is_not_executed() -> None:
    handoff = build_execution_handoff(
        take=True, forwarded_to_oms=True, mt5_ticket=None
    )
    assert handoff["execution_confirmed"] is False


def test_r_duplicate_signal_is_blocked() -> None:
    dup = DuplicateProtection()
    first = dup.claim("sniper-v2-req-1")
    again = dup.claim("sniper-v2-req-1")
    assert first["duplicate"] is False
    assert again["duplicate"] is True


def test_s_xauusd_i_is_accepted() -> None:
    assert require_xauusd("XAUUSD_i") in {"XAUUSD", "XAUUSD_I", "XAUUSD_i"}
    out = evaluate_gold_execution_contract(_ready(symbol="XAUUSD_I"))
    assert out.may_submit_oms is True


def test_t_non_xauusd_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.domain.trading.gold_only.gold_only_enabled",
        lambda: True,
    )
    with pytest.raises(DisabledAutonomousSymbolError):
        require_xauusd("EURUSD")
    out = evaluate_gold_execution_contract(_ready(symbol="EURUSD_I"))
    assert out.may_submit_oms is False
    assert out.fault_code == "DISABLED_AUTONOMOUS_SYMBOL"


def test_u_winner_only_scale_in() -> None:
    winner = may_add_scalping_trade(
        open_positions=1,
        max_open=2,
        new_confidence=90,
        best_open_confidence=80,
        new_direction="BUY",
        open_directions=("BUY",),
        require_unrealized_profit=True,
        open_profits=(Decimal("12.00"),),
    )
    assert winner.allow is True


def test_v_losing_position_cannot_scale_in() -> None:
    loser = may_add_scalping_trade(
        open_positions=1,
        max_open=2,
        new_confidence=90,
        best_open_confidence=80,
        new_direction="BUY",
        open_directions=("BUY",),
        require_unrealized_profit=True,
        open_profits=(Decimal("-4.00"),),
    )
    assert loser.allow is False


def test_w_daily_loss_at_or_below_40_is_clear() -> None:
    assert MAX_DAILY_LOSS_PCT == Decimal("80.0")
    assert (
        utc_daily_loss_exceeded(
            daily_pnl=Decimal("-40.00"),
            equity=Decimal("100"),
            balance=Decimal("100"),
            max_daily_loss_pct=MAX_DAILY_LOSS_PCT,
        )
        is False
    )


def test_x_daily_loss_above_80_locks() -> None:
    assert (
        utc_daily_loss_exceeded(
            daily_pnl=Decimal("-80.01"),
            equity=Decimal("100"),
            balance=Decimal("100"),
            max_daily_loss_pct=MAX_DAILY_LOSS_PCT,
        )
        is True
    )


def test_y_no_martingale() -> None:
    assert DEFAULT_AI_SCALPING_CONFIG.allow_martingale is False
    forced = AiScalpingConfig(allow_martingale=True)
    assert forced.allow_martingale is False


def test_z_no_revenge_sizing() -> None:
    loser = may_add_scalping_trade(
        open_positions=1,
        max_open=2,
        new_confidence=99,
        best_open_confidence=20,
        new_direction="SELL",
        open_directions=("SELL",),
        require_unrealized_profit=True,
        open_profits=(Decimal("-8.00"),),
    )
    assert loser.allow is False


def test_buy_and_sell_components_are_independent_each_cycle() -> None:
    buy_snap = _snap(
        macro=TrendDirection.UP,
        primary=TrendDirection.UP,
        entry=TrendDirection.UP,
        execution=TrendDirection.UP,
        m5=_struct(bos=[_bos("UP")]),
        sweeps=[MagicMock(side="LOW")],
    )
    sell_snap = _snap(
        macro=TrendDirection.DOWN,
        primary=TrendDirection.DOWN,
        entry=TrendDirection.DOWN,
        execution=TrendDirection.DOWN,
        m5=_struct(bos=[_bos("DOWN")]),
        sweeps=[MagicMock(side="HIGH")],
    )
    buy = decide_scalping_direction(buy_snap)
    sell = decide_scalping_direction(sell_snap)
    assert buy.direction is TradeDirection.BUY
    assert sell.direction is TradeDirection.SELL
    assert buy.buy_components["bos"] > 0
    assert sell.sell_components["bos"] > 0
    assert buy.buy_score > buy.sell_score
    assert sell.sell_score > sell.buy_score
    assert buy.factors.get("h1_bias") == 10


def test_hourly_rates_expose_forming_incomplete_and_opportunity_wait() -> None:
    rates = hourly_scan_rates(
        [
            {
                "recorded_at": "2026-08-27T14:00:00+00:00",
                "decision_action": "WAIT",
                "take": False,
                "opportunity_score": 66,
                "opportunity_threshold": 70,
                "setup_state": "SETUP_FORMING",
                "rejection": {"primary": "WAIT_SNIPER_INCOMPLETE"},
            },
            {
                "recorded_at": "2026-08-27T14:01:00+00:00",
                "decision_action": "WAIT",
                "take": False,
                "opportunity_score": 73,
                "opportunity_threshold": 70,
                "setup_state": "SETUP_READY",
                "rejection": {"primary": "WAIT_SNIPER_INCOMPLETE"},
            },
        ],
        now=datetime(2026, 8, 27, 14, 30, tzinfo=UTC),
    )
    assert rates["SETUP_FORMING_count"] == 1
    assert rates["setup_ready_count"] == 1
    assert rates["WAIT_SNIPER_INCOMPLETE_count"] == 2
    assert rates["WAIT_OPPORTUNITY_count"] == 1
    assert rates["take_count"] == 0
    assert rates["CHASING_count"] == 0
    assert rates["OMS_submissions_per_hour"] == 0.0


def test_ltf_edge_wins_when_display_totals_tie() -> None:
    """H1 BUY + M15 BUY can tie display scores without inventing a BUY scalp."""
    snap = _snap(
        macro=TrendDirection.UP,
        primary=TrendDirection.UP,
        entry=TrendDirection.DOWN,
        m5=_struct(bos=[_bos("DOWN")]),
        fvgs=[_fvg(side="BEARISH", high="2612", low="2608")],
    )
    dec = decide_scalping_direction(snap)
    assert dec.direction is TradeDirection.SELL
    assert dec.ltf_sell_score > dec.ltf_buy_score + dec.edge_margin
    assert dec.factors.get("h1_bias") == 10


def test_h1_opposite_does_not_veto_valid_m5_buy() -> None:
    snap = _snap(
        macro=TrendDirection.DOWN,
        primary=TrendDirection.DOWN,
        entry=TrendDirection.UP,
        m5=_struct(bos=[_bos("UP")]),
        fvgs=[_fvg(side="BULLISH", high="2612", low="2608")],
    )
    dec = decide_scalping_direction(snap)
    assert dec.direction is TradeDirection.BUY
    assert dec.ltf_buy_score > dec.ltf_sell_score


def test_h1_neutral_does_not_veto_valid_m5_sell() -> None:
    snap = _snap(
        macro=TrendDirection.UNKNOWN,
        primary=TrendDirection.UNKNOWN,
        entry=TrendDirection.DOWN,
        m5=_struct(bos=[_bos("DOWN")]),
        fvgs=[_fvg(side="BEARISH", high="2612", low="2608")],
    )
    dec = decide_scalping_direction(snap)
    assert dec.direction is TradeDirection.SELL


def test_no_ltf_evidence_does_not_invent_direction_from_close_totals() -> None:
    snap = _snap(macro=TrendDirection.UP, primary=TrendDirection.DOWN)
    dec = decide_scalping_direction(snap)
    assert dec.direction is TradeDirection.NONE
    assert dec.ltf_buy_score == 0
    assert dec.ltf_sell_score == 0


def test_m1_bos_is_counted_in_opportunity_bos_factor() -> None:
    snap = _snap(m1=_struct(bos=[_bos("UP")]), m15=_struct())
    dec = decide_scalping_direction(snap)
    assert dec.factors.get("bos") == 85
    with_bos = evaluate_from_score_dict(
        {
            "direction": "BUY",
            "trade_quality": 63,
            "ai_confidence": 47,
            "structure_score": dec.structure_score,
            "momentum": 52,
            "liquidity": 40,
            "spread_score": 80,
            "expected_rr": Decimal("1.20"),
            "market_regime": "range",
            "mtf_alignment": 52,
            "pa_confluence": 41,
            "factors": dec.factors,
        }
    )
    without_bos = evaluate_from_score_dict(
        {
            "direction": "NONE",
            "trade_quality": 63,
            "ai_confidence": 47,
            "structure_score": 52,
            "momentum": 52,
            "liquidity": 40,
            "spread_score": 80,
            "expected_rr": Decimal("1.20"),
            "market_regime": "range",
            "mtf_alignment": 52,
            "pa_confluence": 41,
            "factors": {"bos": 20, "choch": 20, "fvg": 25, "order_block": 20},
        }
    )
    assert with_bos.opportunity_score > without_bos.opportunity_score
    assert without_bos.opportunity_score < OPPORTUNITY_SCORE_THRESHOLD


def test_m5_bos_plus_m1_confirmation_is_one_structure_family() -> None:
    snap = _snap(
        m1=_struct(bos=[_bos("UP")]),
        m5=_struct(bos=[_bos("UP")]),
        fvgs=[_fvg(side="BULLISH", high="2612", low="2608")],
    )
    out = _sniper(snap, _dir(TradeDirection.BUY))
    assert out.passed is True
    assert out.diagnostics["independent_evidence"].count("structure") == 1
    assert "zone" in out.diagnostics["independent_evidence"]
    assert out.diagnostics["confluence_class"] in {"STANDARD", "HIGH_CONFLUENCE"}
    assert out.diagnostics.get("structure_timeframe") in {"M1", "M5"}
    assert out.diagnostics.get("signal_created_at")
    assert out.diagnostics.get("zone_age_ms") is not None


def test_ob_retest_is_valid_with_independent_structure() -> None:
    snap = _snap(
        m5=_struct(bos=[_bos("UP")]),
        obs=[_ob(bias="BUY")],
    )
    out = _sniper(snap, _dir(TradeDirection.BUY), momentum=0, pa_score=20, min_momentum=65)
    assert out.passed is True
    assert out.action == "BUY"
    assert "zone" in out.diagnostics["independent_evidence"]
    assert out.diagnostics.get("entry_state") in {"RETEST", "INSIDE", "CONTROLLED"}


def test_none_direction_with_m5_evidence_is_forming_not_take() -> None:
    snap = _snap(m5=_struct(bos=[_bos("UP")]))
    out = _sniper(snap, _dir(TradeDirection.NONE, buy=46, sell=48))
    assert out.passed is False
    assert out.action == "WAIT"
    assert out.diagnostics["setup_state"] == "SETUP_FORMING"
    assert out.primary_reason == "WAIT_NO_DIRECTIONAL_EDGE"


def test_wait_no_edge_handoff_is_strategy_not_oms() -> None:
    abort = "NO CLEAR BUY/SELL EDGE (BALANCED SCORES → REJECT)"
    assert bridge_abort_stage(abort) == "STRATEGY"
    assert bridge_abort_stage(None) == "STRATEGY"
    handoff = build_execution_handoff(
        take=False,
        forwarded_to_oms=False,
        abort_reason=abort,
    )
    assert handoff["oms_entered"] is False
    assert handoff["blocking_stage"] == "STRATEGY"
    assert handoff["execution_confirmed"] is False
    empty = build_execution_handoff(take=False, forwarded_to_oms=False)
    assert empty["oms_entered"] is False


def test_wait_overlay_does_not_paint_oms_block() -> None:
    over = _overlay_last_ite_cycle(
        _row_from_score(
            {
                "symbol": "XAUUSD_I",
                "direction": "WAIT",
                "signal_action": "WAIT",
                "opportunity_score": 65,
                "opportunity_threshold": 70,
                "buy_score": 46,
                "sell_score": 48,
                "reject": True,
                "reject_reason": "WAIT_NO_DIRECTIONAL_EDGE",
                "sniper_entry": {
                    "passed": False,
                    "action": "WAIT",
                    "setup_state": "NO_SETUP",
                    "primary_reason": "WAIT_NO_DIRECTIONAL_EDGE",
                },
            }
        ),
        {
            "forwarded_to_oms": False,
            "take": False,
            "abort_reason": "NO CLEAR BUY/SELL EDGE (BALANCED SCORES → REJECT)",
            "cycle_outcome": "waiting_next_cycle",
            "mt5_ticket": None,
            "execution_handoff": build_execution_handoff(
                take=False,
                forwarded_to_oms=False,
                abort_reason="NO CLEAR BUY/SELL EDGE (BALANCED SCORES → REJECT)",
            ),
        },
    )
    assert over["pipeline"]["oms"] == "NOT_REACHED"
    assert over["pipeline"]["final_decision"] == "WAIT"
    assert over.get("execution_state") != "EXECUTED"


def _live_like_opportunity(**factor_overrides: object) -> dict:
    factors: dict[str, object] = {
        "bos": 85,
        "choch": 20,
        "fvg": 80,
        "order_block": 20,
        "m1_bos": 85,
        "m5_bos": 85,
        "m15_bos": 20,
        "displacement": 78,
        "timing_retest": 80,
        "liquidity_sweep": 40,
        "h1_bias": 10,
        "mtf": 36,
    }
    factors.update(factor_overrides)
    return {
        "direction": "SELL",
        "trade_quality": 63,
        "ai_confidence": 56,
        "structure_score": 52,
        "momentum": 52,
        "liquidity": 40,
        "spread_score": 80,
        "expected_rr": Decimal("1.20"),
        "market_regime": "weak_trend",
        "mtf_alignment": 52,
        "pa_confluence": 50,
        "factors": factors,
    }


def test_live_like_ltf_scalp_reaches_opportunity_70() -> None:
    """M5+M1 BOS + zone + timing must not stay at 66 because H1 alignment is 52."""
    verdict = evaluate_from_score_dict(_live_like_opportunity())
    assert verdict.threshold == 70
    assert verdict.opportunity_score >= OPPORTUNITY_SCORE_THRESHOLD
    assert verdict.score_breakdown["mtf_alignment"] >= 76
    assert verdict.score_breakdown["momentum"] >= 75
    assert verdict.score_breakdown["price_action"] >= 75
    assert verdict.score_breakdown["structure"] == 85


def test_h1_low_alignment_does_not_cap_ltf_mtf() -> None:
    raw = _live_like_opportunity()
    raw["mtf_alignment"] = 28
    verdict = evaluate_from_score_dict(raw)
    assert verdict.score_breakdown["mtf_alignment"] >= 76
    assert verdict.opportunity_score >= OPPORTUNITY_SCORE_THRESHOLD


def test_fvg_and_bos_are_max_not_sum() -> None:
    verdict = evaluate_from_score_dict(_live_like_opportunity())
    assert verdict.score_breakdown["structure"] == 85
    assert verdict.score_breakdown["structure"] != 85 + 80


def test_m1_m5_bos_not_discarded_when_alignment_is_range() -> None:
    raw = _live_like_opportunity(displacement=20, timing_retest=20)
    raw["mtf_alignment"] = 52
    verdict = evaluate_from_score_dict(raw)
    assert verdict.score_breakdown["mtf_alignment"] >= 76


def test_stale_timing_does_not_receive_retest_points() -> None:
    with_timing = evaluate_from_score_dict(_live_like_opportunity())
    stale = evaluate_from_score_dict(
        _live_like_opportunity(timing_retest=20, displacement=20)
    )
    assert with_timing.score_breakdown["price_action"] > stale.score_breakdown["price_action"]
    assert stale.score_breakdown["price_action"] == 50


def test_macro_only_live_like_stays_below_70() -> None:
    verdict = evaluate_from_score_dict(
        {
            "direction": "SELL",
            "trade_quality": 63,
            "ai_confidence": 56,
            "structure_score": 52,
            "momentum": 52,
            "liquidity": 40,
            "spread_score": 80,
            "expected_rr": Decimal("1.20"),
            "market_regime": "weak_trend",
            "mtf_alignment": 52,
            "pa_confluence": 50,
            "factors": {
                "bos": 20,
                "choch": 20,
                "fvg": 25,
                "order_block": 20,
                "m1_bos": 20,
                "m5_bos": 20,
                "h1_bias": 10,
                "mtf": 24,
            },
        }
    )
    assert verdict.opportunity_score < OPPORTUNITY_SCORE_THRESHOLD
    assert verdict.eligible is False


def test_opportunity_pass_alone_does_not_authorize_execution() -> None:
    out = evaluate_gold_execution_contract(
        _ready(opportunity_score=74, action="NO_TRADE", direction="NONE")
    )
    assert out.may_submit_oms is False


def test_score_scalping_setup_uses_m1_m5_bos_not_h1_alignment() -> None:
    snap = _snap(
        macro=TrendDirection.UP,
        primary=TrendDirection.UNKNOWN,
        entry=TrendDirection.DOWN,
        execution=TrendDirection.DOWN,
        m1=_struct(bos=[_bos("DOWN")]),
        m5=_struct(bos=[_bos("DOWN")]),
        fvgs=[_fvg(side="BEARISH", high="2612", low="2608")],
    )
    snap.trade_quality.total = 63
    snap.trade_quality.components = {"momentum": 52, "liquidity": 40, "volume": 40}
    snap.entry_atr = None
    out = score_scalping_setup(
        snap,
        atr=Decimal("4.00"),
        mid=Decimal("2610"),
        bid=Decimal("2609.90"),
        ask=Decimal("2610.10"),
        symbol="XAUUSD_i",
    )
    assert out.opportunity_threshold == 70
    assert out.factors.get("m5_bos") == 85
    assert out.factors.get("m1_bos") == 85
    assert (out.opportunity_audit or {}).get("h1_context", {}).get("veto") is False
    assert out.opportunity_score >= OPPORTUNITY_SCORE_THRESHOLD
