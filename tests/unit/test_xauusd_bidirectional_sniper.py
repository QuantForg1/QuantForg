"""XAUUSD bidirectional sniper — BUY/SELL/WAIT without permanent bias.

Does not send orders. Does not bypass Risk, Safety, OMS, or MT5.
Does not flip BUY into SELL or SELL into BUY.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
)
from app.domain.institutional_trading.ai_scalping.direction import (
    DirectionDecision,
    decide_scalping_direction,
)
from app.domain.institutional_trading.ai_scalping.dynamic_sizing_v2 import (
    adaptive_protection_scale,
)
from app.domain.institutional_trading.ai_scalping.sniper_entry import (
    evaluate_sniper_entry,
)
from app.domain.institutional_trading.decision_models import (
    ConfluenceResult,
    TradeDirection,
)
from app.domain.institutional_trading.executable_direction import (
    resolve_executable_direction,
)
from app.domain.institutional_trading.operations.communication_fault import (
    should_blind_retry_order_submit,
)
from app.domain.institutional_trading.phase_a.market_data_firewall import (
    MarketDataState,
    evaluate_market_data_firewall,
)
from app.domain.market_structure.enums import TrendDirection
from app.domain.multi_agent_ai import CollaborationInput, MultiAgentSystem
from app.domain.scalping_ai_v2.reliability import DuplicateProtection
from app.domain.trading.gold_only import (
    DisabledAutonomousSymbolError,
    require_xauusd,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

ROOT = Path(__file__).resolve().parents[2]
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
) -> MagicMock:
    trend = MagicMock()
    trend.macro_bias = macro
    trend.primary = primary
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
    quality.components = {"momentum": 75, "volume": 70, "liquidity": 70}

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


def _ob(
    *,
    bias: str,
    high: str = "2652",
    low: str = "2649",
    disp: str = "1.8",
) -> MagicMock:
    zone = MagicMock()
    zone.high_price = Decimal(high)
    zone.low_price = Decimal(low)
    quality = MagicMock()
    quality.displacement_ratio = Decimal(disp)
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
) -> DirectionDecision:
    return DirectionDecision(
        direction=side,
        buy_score=buy,
        sell_score=sell,
        reasons=("fixture",),
        structure_score=70,
        factors={"h1_bias": 28},
    )


def _sniper(
    snap: MagicMock,
    direction: DirectionDecision,
    **kwargs: object,
) -> object:
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


class TestBidirectionalScores:
    def test_sell_setup_does_not_become_buy(self) -> None:
        snap = _snap(
            macro=TrendDirection.DOWN,
            primary=TrendDirection.DOWN,
            sweeps=[MagicMock(side="HIGH")],
            bos=[_break("DOWN")],
        )
        dec = decide_scalping_direction(snap)
        assert dec.direction is TradeDirection.SELL
        assert dec.sell_score > dec.buy_score
        payload = dec.to_dict()
        assert payload["bearish_score"] == dec.sell_score
        assert payload["bullish_score"] == dec.buy_score
        assert payload["never_prefer_buy_only"] is True

    def test_buy_setup_does_not_become_sell(self) -> None:
        snap = _snap(
            macro=TrendDirection.UP,
            primary=TrendDirection.UP,
            sweeps=[MagicMock(side="LOW")],
            bos=[_break("UP")],
        )
        dec = decide_scalping_direction(snap)
        assert dec.direction is TradeDirection.BUY
        assert dec.buy_score > dec.sell_score

    def test_conflicting_htf_and_ltf_wait(self) -> None:
        snap = _snap(
            macro=TrendDirection.UP,
            primary=TrendDirection.DOWN,
            sweeps=[MagicMock(side="HIGH")],
        )
        snap.trade_quality.components = {
            "momentum": 10,
            "volume": 10,
            "liquidity": 10,
        }
        dec = decide_scalping_direction(snap)
        assert dec.direction is TradeDirection.NONE
        assert abs(dec.buy_score - dec.sell_score) <= 8

    def test_equal_highs_support_sell_not_buy_bias(self) -> None:
        snap = _snap(
            macro=TrendDirection.DOWN,
            primary=TrendDirection.DOWN,
            equal_highs=[object()],
            sweeps=[],
        )
        dec = decide_scalping_direction(snap)
        assert dec.direction is TradeDirection.SELL
        assert "equal highs" in " ".join(dec.reasons).lower()

    def test_equal_lows_support_buy(self) -> None:
        snap = _snap(
            macro=TrendDirection.UP,
            primary=TrendDirection.UP,
            equal_lows=[object()],
            sweeps=[],
        )
        dec = decide_scalping_direction(snap)
        assert dec.direction is TradeDirection.BUY

    def test_never_prefer_buy_only_locked(self) -> None:
        assert DEFAULT_AI_SCALPING_CONFIG.never_prefer_buy_only is True
        assert DEFAULT_AI_SCALPING_CONFIG.allow_martingale is False


class TestSniperBuySellWait:
    def test_buy_sniper_setup(self) -> None:
        snap = _snap(
            macro=TrendDirection.UP,
            sweeps=[MagicMock(side="LOW")],
            bos=[_break("UP")],
            choch=[_break("UP")],
            order_blocks=[_ob(bias="BUY")],
        )
        out = _sniper(snap, _dir(TradeDirection.BUY, buy=82, sell=18))
        assert out.passed is True
        assert out.action == "BUY"
        assert out.primary_reason is None
        assert out.pillars["liquidity_event"] is True
        assert out.pillars["structure_confirmation"] is True

    def test_sell_sniper_setup(self) -> None:
        snap = _snap(
            macro=TrendDirection.DOWN,
            sweeps=[MagicMock(side="HIGH")],
            bos=[_break("DOWN")],
            choch=[_break("DOWN")],
            order_blocks=[_ob(bias="SELL", high="2654", low="2651")],
        )
        out = _sniper(
            snap,
            _dir(TradeDirection.SELL, buy=18, sell=82),
            stop_loss=Decimal("2658"),
        )
        assert out.passed is True
        assert out.action == "SELL"
        assert out.primary_reason is None

    def test_wait_no_edge(self) -> None:
        snap = _snap()
        out = _sniper(snap, _dir(TradeDirection.NONE, buy=40, sell=41))
        assert out.passed is False
        assert out.action == "WAIT"
        assert out.primary_reason == "WAIT_NO_DIRECTIONAL_EDGE"

    def test_conflicting_buy_sell_is_wait_not_flip(self) -> None:
        snap = _snap(sweeps=[MagicMock(side="LOW")], bos=[_break("UP")])
        buy_dir = _dir(TradeDirection.BUY, buy=80, sell=20)
        out = _sniper(snap, buy_dir, setup_family_direction="SELL")
        assert out.passed is False
        assert out.action == "WAIT"
        assert out.primary_reason == "WAIT_CONFLICTING_BUY_SELL"
        assert buy_dir.direction is TradeDirection.BUY

        sell_dir = _dir(TradeDirection.SELL, buy=20, sell=80)
        out2 = _sniper(
            _snap(sweeps=[MagicMock(side="HIGH")], bos=[_break("DOWN")]),
            sell_dir,
            setup_family_direction="BUY",
            stop_loss=Decimal("2658"),
        )
        assert out2.action == "WAIT"
        assert sell_dir.direction is TradeDirection.SELL

    def test_trend_only_is_wait(self) -> None:
        snap = _snap(macro=TrendDirection.UP, primary=TrendDirection.UP)
        out = _sniper(snap, _dir(TradeDirection.BUY))
        assert out.passed is False
        assert out.action == "WAIT"
        assert out.primary_reason == "WAIT_NO_SNIPER_TRIGGER"

    def test_bullish_liquidity_sweep(self) -> None:
        snap = _snap(sweeps=[MagicMock(side="LOW")])
        out = _sniper(snap, _dir(TradeDirection.BUY))
        assert out.pillars["liquidity_event"] is True
        assert out.action in {"BUY", "WAIT"}
        if out.passed:
            assert out.action == "BUY"

    def test_bearish_liquidity_sweep(self) -> None:
        snap = _snap(sweeps=[MagicMock(side="HIGH")])
        out = _sniper(
            snap,
            _dir(TradeDirection.SELL, buy=18, sell=82),
            stop_loss=Decimal("2658"),
        )
        assert out.pillars["liquidity_event"] is True
        if out.passed:
            assert out.action == "SELL"

    def test_bullish_bos_choch(self) -> None:
        snap = _snap(bos=[_break("UP")], choch=[_break("UP")])
        out = _sniper(snap, _dir(TradeDirection.BUY))
        assert out.pillars["structure_confirmation"] is True
        if out.passed:
            assert out.action == "BUY"

    def test_bearish_bos_choch(self) -> None:
        snap = _snap(bos=[_break("DOWN")], choch=[_break("DOWN")])
        out = _sniper(
            snap,
            _dir(TradeDirection.SELL, buy=18, sell=82),
            stop_loss=Decimal("2658"),
        )
        assert out.pillars["structure_confirmation"] is True
        if out.passed:
            assert out.action == "SELL"

    def test_bullish_displacement(self) -> None:
        snap = _snap(
            sweeps=[MagicMock(side="LOW")],
            bos=[_break("UP")],
            order_blocks=[_ob(bias="BUY", disp="2.1")],
        )
        out = _sniper(snap, _dir(TradeDirection.BUY), momentum=0, pa_score=0)
        assert out.pillars["displacement_or_momentum"] is True
        assert out.passed is True
        assert out.action == "BUY"

    def test_bearish_displacement(self) -> None:
        snap = _snap(
            sweeps=[MagicMock(side="HIGH")],
            bos=[_break("DOWN")],
            order_blocks=[_ob(bias="SELL", high="2654", low="2651", disp="2.1")],
        )
        out = _sniper(
            snap,
            _dir(TradeDirection.SELL, buy=18, sell=82),
            stop_loss=Decimal("2658"),
            momentum=0,
            pa_score=0,
        )
        assert out.pillars["displacement_or_momentum"] is True
        assert out.passed is True
        assert out.action == "SELL"

    def test_missing_invalidation_is_wait(self) -> None:
        snap = _snap(sweeps=[MagicMock(side="LOW")], bos=[_break("UP")])
        out = _sniper(snap, _dir(TradeDirection.BUY), stop_loss=None)
        assert out.passed is False
        assert out.action == "WAIT"
        assert out.primary_reason == "WAIT_NO_INVALIDATION"

    def test_insufficient_rr_is_wait(self) -> None:
        snap = _snap(sweeps=[MagicMock(side="LOW")], bos=[_break("UP")])
        out = _sniper(
            snap,
            _dir(TradeDirection.BUY),
            expected_rr=Decimal("0.40"),
            min_expected_rr=MIN_RR,
        )
        assert out.passed is False
        assert out.action == "WAIT"
        assert out.primary_reason == "WAIT_INSUFFICIENT_RR"

    def test_abnormal_spread_is_wait(self) -> None:
        snap = _snap(sweeps=[MagicMock(side="LOW")], bos=[_break("UP")])
        out = _sniper(snap, _dir(TradeDirection.BUY), spread_reject=True)
        assert out.passed is False
        assert out.action == "WAIT"
        assert out.primary_reason == "WAIT_ABNORMAL_SPREAD"

    def test_chase_buy_is_wait(self) -> None:
        snap = _snap(
            sweeps=[MagicMock(side="LOW")],
            bos=[_break("UP")],
            order_blocks=[_ob(bias="BUY", high="2652", low="2649")],
        )
        out = _sniper(
            snap,
            _dir(TradeDirection.BUY),
            mid=Decimal("2662"),
            atr=Decimal("4.00"),
        )
        assert out.passed is False
        assert out.action == "WAIT"
        assert out.primary_reason == "WAIT_CHASE"

    def test_buy_never_emitted_as_sell(self) -> None:
        snap = _snap(
            sweeps=[MagicMock(side="LOW")],
            bos=[_break("UP")],
            order_blocks=[_ob(bias="BUY")],
        )
        out = _sniper(snap, _dir(TradeDirection.BUY))
        assert out.action != "SELL"

    def test_sell_never_emitted_as_buy(self) -> None:
        snap = _snap(
            sweeps=[MagicMock(side="HIGH")],
            bos=[_break("DOWN")],
            order_blocks=[_ob(bias="SELL", high="2654", low="2651")],
        )
        out = _sniper(
            snap,
            _dir(TradeDirection.SELL, buy=18, sell=82),
            stop_loss=Decimal("2658"),
        )
        assert out.action != "BUY"


class TestExistingGatesUnchanged:
    def test_stale_market_data(self) -> None:
        stale = evaluate_market_data_firewall(
            symbol="XAUUSD",
            bid=2000.0,
            ask=2000.2,
            quote_age_seconds=200.0,
        )
        assert stale.state is MarketDataState.MARKET_DATA_STALE
        assert stale.allow_new_entry is False

    def test_non_xauusd_rejection(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "app.domain.trading.gold_only.gold_only_enabled",
            lambda: True,
        )
        with pytest.raises(DisabledAutonomousSymbolError):
            require_xauusd("EURUSD")

    def test_duplicate_signal(self) -> None:
        dup = DuplicateProtection()
        first = dup.claim("sniper-signal-1")
        second = dup.claim("sniper-signal-1")
        assert first["allowed"] is True
        assert second["allowed"] is False
        assert second["duplicate"] is True

    def test_no_blind_retry_duplicate_order(self) -> None:
        assert should_blind_retry_order_submit() is False

    def test_risk_rejection_authoritative(self) -> None:
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
                risk_engine_passed=False,
                safety_engine_passed=True,
            )
        )
        assert out["decision"] == "REJECT"
        assert out["allow_execution_path"] is False

    def test_safety_rejection_authoritative(self) -> None:
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
                risk_engine_passed=True,
                safety_engine_passed=False,
            )
        )
        assert out["decision"] == "REJECT"
        assert out["allow_execution_path"] is False

    def test_adaptive_sizing_loss_streak_reduces(self) -> None:
        scale, halt, _notes = adaptive_protection_scale(consecutive_losses=3)
        assert halt is None
        assert scale < Decimal("1")

    def test_ai_vs_confluence_conflict_is_none(self) -> None:
        exe = resolve_executable_direction(
            confluence=ConfluenceResult(
                confidence=85,
                direction=TradeDirection.SELL,
                reasons=("test",),
                rejected_rules=(),
                input_hash="sniper",
                band="tradable",
                passed=True,
                factors={},
            ),
            ai_direction="BUY",
            ai_reject=False,
            scalping=True,
        )
        assert exe.direction is TradeDirection.NONE

    def test_sniper_does_not_call_order_send(self) -> None:
        src = (
            ROOT / "app/domain/institutional_trading/ai_scalping/sniper_entry.py"
        ).read_text(encoding="utf-8")
        assert "order_send(" not in src
        assert "Execute Now" not in src
        scoring = (
            ROOT / "app/domain/institutional_trading/ai_scalping/scoring.py"
        ).read_text(encoding="utf-8")
        assert "evaluate_sniper_entry" in scoring
        assert "order_send(" not in scoring
