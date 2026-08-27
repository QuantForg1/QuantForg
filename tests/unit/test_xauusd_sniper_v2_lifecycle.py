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
from app.domain.institutional_trading.ai_scalping.scoring import AiScalpingScore
from app.domain.institutional_trading.ai_scalping.sniper_entry import (
    evaluate_sniper_entry,
)
from app.domain.institutional_trading.config import MAX_DAILY_LOSS_PCT
from app.domain.institutional_trading.decision_models import TradeDirection
from app.domain.institutional_trading.operations.daily_loss_lock import (
    utc_daily_loss_exceeded,
)
from app.domain.institutional_trading.operations.execution_chain_log import (
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
    assert MAX_DAILY_LOSS_PCT == Decimal("40.0")
    assert (
        utc_daily_loss_exceeded(
            daily_pnl=Decimal("-40.00"),
            equity=Decimal("100"),
            balance=Decimal("100"),
            max_daily_loss_pct=MAX_DAILY_LOSS_PCT,
        )
        is False
    )


def test_x_daily_loss_above_40_locks() -> None:
    assert (
        utc_daily_loss_exceeded(
            daily_pnl=Decimal("-40.01"),
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
