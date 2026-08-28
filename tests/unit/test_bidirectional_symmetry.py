"""BUY/SELL symmetry — no HTF fade, no SELL-on-tie, no forced trades.

Does not send orders. Does not weaken Opportunity 70 or Risk 40%.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.application.services.signal_center_service import _row_from_score
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
)
from app.domain.institutional_trading.ai_scalping.direction import (
    DirectionDecision,
    decide_scalping_direction,
)
from app.domain.institutional_trading.ai_scalping.setup_scanner import (
    scan_setup_families,
)
from app.domain.institutional_trading.ai_scalping.sniper_entry import (
    evaluate_sniper_entry,
)
from app.domain.institutional_trading.config import MAX_DAILY_LOSS_PCT
from app.domain.institutional_trading.decision_models import TradeDirection
from app.domain.institutional_trading.operations.communication_fault import (
    should_blind_retry_order_submit,
)
from app.domain.institutional_trading.operations.probability_selector import (
    OPPORTUNITY_SCORE_THRESHOLD,
)
from app.domain.market_structure.enums import TrendDirection

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

MIN_RR = Decimal("1.20")


def _snap(
    *,
    macro: TrendDirection = TrendDirection.DOWN,
    primary: TrendDirection = TrendDirection.DOWN,
    alignment: int = 70,
    sweeps: list[object] | None = None,
    bos: list[object] | None = None,
    choch: list[object] | None = None,
    equal_highs: list[object] | None = None,
    equal_lows: list[object] | None = None,
    order_blocks: list[object] | None = None,
    fvgs: list[object] | None = None,
    momentum: int = 75,
) -> MagicMock:
    trend = MagicMock()
    trend.macro_bias = macro
    trend.primary = primary
    trend.entry = None
    trend.execution = None
    trend.alignment_score = alignment
    trend.why = "test"

    structure = MagicMock()
    structure.breaks_of_structure = list(bos or [])
    structure.changes_of_character = list(choch or [])
    structure.swings = []
    structure.last_swing_low = Decimal("2648")
    structure.last_swing_high = Decimal("2656")

    liq = MagicMock()
    liq.sweeps = list(sweeps or [])
    liq.pools = []
    liq.equal_highs = list(equal_highs or [])
    liq.equal_lows = list(equal_lows or [])

    quality = MagicMock()
    quality.total = 85
    quality.components = {"momentum": momentum, "volume": 70, "liquidity": 70}

    session = MagicMock()
    session.session = MagicMock(value="london")
    session.allowed = True

    snap = MagicMock()
    snap.trend = trend
    snap.primary_structure = structure
    snap.liquidity = liq
    snap.order_blocks = MagicMock(order_blocks=list(order_blocks or []))
    snap.fair_value_gaps = MagicMock(active_gaps=list(fvgs or []))
    snap.trade_quality = quality
    snap.session = session
    snap.spread = Decimal("0.20")
    snap.symbol = "XAUUSD"
    return snap


def _break(direction: str) -> MagicMock:
    br = MagicMock()
    br.direction = direction
    br.bias = direction
    return br


def _ob(*, bias: str, high: str = "2652", low: str = "2649") -> MagicMock:
    zone = MagicMock()
    zone.high_price = Decimal(high)
    zone.low_price = Decimal(low)
    quality = MagicMock()
    quality.displacement_ratio = Decimal("1.8")
    block = MagicMock()
    block.state = "ACTIVE"
    block.bias = bias
    block.side = bias
    block.quality = quality
    block.zone = zone
    return block


def _dir(
    side: TradeDirection,
    *,
    buy: int = 80,
    sell: int = 20,
    ltf_buy: int | None = None,
    ltf_sell: int | None = None,
) -> DirectionDecision:
    return DirectionDecision(
        direction=side,
        buy_score=buy,
        sell_score=sell,
        reasons=("fixture",),
        structure_score=70,
        factors={"h1_bias": 10},
        ltf_buy_score=buy if ltf_buy is None else ltf_buy,
        ltf_sell_score=sell if ltf_sell is None else ltf_sell,
        directional_edge=abs(
            (ltf_buy if ltf_buy is not None else buy)
            - (ltf_sell if ltf_sell is not None else sell)
        ),
        edge_margin=5,
    )


def _sniper(snap: MagicMock, direction: DirectionDecision, **kwargs: object) -> object:
    defaults: dict[str, object] = {
        "mid": Decimal("2650"),
        "atr": Decimal("4.00"),
        "expected_rr": MIN_RR,
        "min_expected_rr": MIN_RR,
        "stop_loss": Decimal("2646"),
        "setup_family_direction": None,
        "spread_reject": False,
        "pa_score": 70,
        "momentum": 70,
        "min_momentum": 55,
        "config": DEFAULT_AI_SCALPING_CONFIG,
    }
    defaults.update(kwargs)
    return evaluate_sniper_entry(snap, direction=direction, **defaults)  # type: ignore[arg-type]


def test_contracts_unchanged() -> None:
    assert OPPORTUNITY_SCORE_THRESHOLD == 70
    assert MAX_DAILY_LOSS_PCT == Decimal("40.0")
    assert should_blind_retry_order_submit() is False
    assert DEFAULT_AI_SCALPING_CONFIG.never_prefer_buy_only is True
    assert DEFAULT_AI_SCALPING_CONFIG.allow_martingale is False


def test_choch_and_sweep_follow_ltf_lean_not_fade() -> None:
    scan = scan_setup_families(
        alignment=50,
        bos=0,
        choch=1,
        sweeps=2,
        open_fvg=0,
        momentum=70,
        volume=70,
        liquidity=80,
        ema=50,
        buy_score=80,
        sell_score=40,
        atr_band="normal",
    )
    choch = next(c for c in scan.candidates if c.family == "choch_reversal")
    sweep = next(c for c in scan.candidates if c.family == "liquidity_sweep_reversal")
    assert choch.direction == TradeDirection.BUY.value
    assert sweep.direction == TradeDirection.BUY.value
    assert choch.direction != TradeDirection.SELL.value


def test_tie_does_not_default_reversal_to_sell() -> None:
    scan = scan_setup_families(
        alignment=50,
        bos=0,
        choch=1,
        sweeps=2,
        open_fvg=0,
        momentum=70,
        volume=70,
        liquidity=80,
        ema=50,
        buy_score=50,
        sell_score=50,
        atr_band="normal",
    )
    choch = next(c for c in scan.candidates if c.family == "choch_reversal")
    sweep = next(c for c in scan.candidates if c.family == "liquidity_sweep_reversal")
    assert choch.passed is False
    assert sweep.passed is False
    assert choch.direction != TradeDirection.SELL.value
    assert sweep.direction != TradeDirection.SELL.value


def test_momentum_does_not_follow_htf_totals() -> None:
    snap = _snap(macro=TrendDirection.DOWN, primary=TrendDirection.DOWN, bos=[], sweeps=[])
    dec = decide_scalping_direction(snap)
    joined = " ".join(dec.reasons)
    assert "Momentum confirms SELL" not in joined
    assert dec.sell_components.get("momentum", 0) == 0
    assert dec.direction is TradeDirection.NONE


def test_h1_down_does_not_veto_ltf_buy() -> None:
    snap = _snap(
        macro=TrendDirection.DOWN,
        primary=TrendDirection.UP,
        bos=[_break("UP")],
        sweeps=[MagicMock(side="LOW")],
        equal_lows=[object()],
    )
    dec = decide_scalping_direction(snap)
    assert dec.direction is TradeDirection.BUY
    assert dec.ltf_buy_score > dec.ltf_sell_score + dec.edge_margin
    scan = scan_setup_families(
        alignment=70,
        bos=1,
        choch=0,
        sweeps=1,
        open_fvg=0,
        momentum=70,
        volume=70,
        liquidity=70,
        ema=70,
        buy_score=dec.ltf_buy_score,
        sell_score=dec.ltf_sell_score,
        atr_band="normal",
    )
    if scan.best is not None:
        assert scan.best.direction != TradeDirection.SELL.value


def test_h1_up_does_not_veto_ltf_sell() -> None:
    snap = _snap(
        macro=TrendDirection.UP,
        primary=TrendDirection.DOWN,
        bos=[_break("DOWN")],
        sweeps=[MagicMock(side="HIGH")],
        equal_highs=[object()],
    )
    dec = decide_scalping_direction(snap)
    assert dec.direction is TradeDirection.SELL
    assert dec.ltf_sell_score > dec.ltf_buy_score + dec.edge_margin


def test_close_ltf_scores_are_wait_not_take() -> None:
    snap = _snap(
        macro=TrendDirection.DOWN,
        primary=TrendDirection.UP,
        equal_highs=[object()],
        equal_lows=[object()],
    )
    dec = decide_scalping_direction(snap)
    assert dec.direction is TradeDirection.NONE
    out = _sniper(snap, _dir(TradeDirection.NONE, buy=42, sell=34, ltf_buy=28, ltf_sell=24))
    assert out.passed is False
    assert out.action == "WAIT"
    assert out.primary_reason == "WAIT_NO_DIRECTIONAL_EDGE"
    assert out.primary_reason != "WAIT_CONFLICTING_BUY_SELL"


def test_standing_equal_levels_do_not_false_conflict() -> None:
    snap = _snap(equal_highs=[object()], equal_lows=[object()])
    out = _sniper(snap, _dir(TradeDirection.NONE, buy=42, sell=34, ltf_buy=28, ltf_sell=24))
    assert out.passed is False
    assert out.primary_reason == "WAIT_NO_DIRECTIONAL_EDGE"
    assert out.diagnostics.get("setup_state") in {"CONFLICT", "NO_SETUP", "SETUP_FORMING"}


def test_real_opposite_setup_family_still_waits() -> None:
    snap = _snap(sweeps=[MagicMock(side="LOW")], bos=[_break("UP")])
    out = _sniper(
        snap,
        _dir(TradeDirection.BUY, buy=80, sell=20),
        setup_family_direction="SELL",
    )
    assert out.passed is False
    assert out.primary_reason == "WAIT_CONFLICTING_BUY_SELL"


def test_buy_and_sell_take_remain_symmetric() -> None:
    buy_out = _sniper(
        _snap(
            macro=TrendDirection.UP,
            sweeps=[MagicMock(side="LOW")],
            bos=[_break("UP")],
            order_blocks=[_ob(bias="BUY")],
        ),
        _dir(TradeDirection.BUY, buy=82, sell=18),
    )
    sell_out = _sniper(
        _snap(
            macro=TrendDirection.DOWN,
            sweeps=[MagicMock(side="HIGH")],
            bos=[_break("DOWN")],
            order_blocks=[_ob(bias="SELL", high="2654", low="2651")],
        ),
        _dir(TradeDirection.SELL, buy=18, sell=82),
        stop_loss=Decimal("2658"),
    )
    assert buy_out.passed is True
    assert buy_out.action == "BUY"
    assert sell_out.passed is True
    assert sell_out.action == "SELL"


def test_wait_does_not_paint_risk_safety_or_oms() -> None:
    row = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "NONE",
            "signal_action": "WAIT",
            "opportunity_score": 64,
            "opportunity_threshold": 70,
            "buy_score": 42,
            "sell_score": 34,
            "ltf_buy_score": 28,
            "ltf_sell_score": 24,
            "reject": True,
            "reject_reason": "WAIT_NO_DIRECTIONAL_EDGE",
            "sniper_entry": {
                "passed": False,
                "action": "WAIT",
                "setup_state": "CONFLICT",
                "primary_reason": "WAIT_NO_DIRECTIONAL_EDGE",
                "ltf_buy_score": 28,
                "ltf_sell_score": 24,
                "directional_edge": 4,
                "edge_margin": 5,
            },
            "quote_age_seconds": 0.4,
            "market_data_live": True,
        }
    )
    pipe = row["pipeline"]
    assert pipe["risk"] == "NOT_REACHED"
    assert pipe["safety"] == "NOT_REACHED"
    assert pipe["optimizer"] == "NOT_REACHED"
    assert pipe["oms_status"] == "NOT_REACHED" or pipe.get("oms") == "NOT_REACHED"
    assert pipe.get("ticket") in {None, ""}
    assert pipe.get("forwarded_to_oms") in {False, None}
    assert row["first_blocker"] == "WAIT_NO_DIRECTIONAL_EDGE"


def test_risk_block_is_not_oms_block() -> None:
    row = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "SELL",
            "signal_action": "SELL",
            "opportunity_score": 81,
            "opportunity_threshold": 70,
            "reject": True,
            "reject_reason": "RISK_BLOCK: daily loss or size rejected",
            "sniper_entry": {"passed": True, "action": "SELL", "setup_state": "TAKE"},
        }
    )
    assert row["pipeline"]["risk"] == "BLOCK"
    assert row["pipeline"]["safety"] == "NOT_REACHED"
    assert row["pipeline"]["oms"] == "NOT_REACHED"


def test_safety_block_is_not_oms_block() -> None:
    row = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "BUY",
            "signal_action": "BUY",
            "opportunity_score": 81,
            "opportunity_threshold": 70,
            "reject": True,
            "reject_reason": "SAFETY_BLOCK: kill switch",
            "sniper_entry": {"passed": True, "action": "BUY", "setup_state": "TAKE"},
        }
    )
    assert row["pipeline"]["safety"] == "BLOCK"
    assert row["pipeline"]["oms"] == "NOT_REACHED"
    assert row["pipeline"].get("ticket") in {None, ""}


def test_take_without_ticket_is_not_executed() -> None:
    from app.application.services.signal_center_service import _overlay_last_ite_cycle

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
    assert over["pipeline"].get("ticket") in {None, ""}
