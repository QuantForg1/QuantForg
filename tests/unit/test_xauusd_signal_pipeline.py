"""XAUUSD signal pipeline — WAIT visibility, mapping, persistence.

Does not send orders. Does not lower sniper / opportunity / risk gates.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.application.services.institutional_multi_asset_scanner import (
    _noc_row_from_score,
    _store_last_scan,
)
from app.application.services.signal_center_service import (
    _execution_classification,
    _row_from_score,
    list_live_signals,
)
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
)
from app.domain.institutional_trading.ai_scalping.direction import (
    DirectionDecision,
    decide_scalping_direction,
)
from app.domain.institutional_trading.ai_scalping.sniper_entry import (
    evaluate_sniper_entry,
)
from app.domain.institutional_trading.decision_models import TradeDirection
from app.domain.institutional_trading.phase_a.market_data_firewall import (
    MarketDataState,
    evaluate_market_data_firewall,
)
from app.domain.market_structure.enums import TrendDirection
from app.domain.trading.gold_only import (
    CANONICAL_GOLD_BROKER_DISPLAY,
    GOLD_SYMBOL,
    canonical_gold_execution_symbol,
    is_bare_gold_symbol,
    is_gold_symbol,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _trend_snap(*, macro: TrendDirection, primary: TrendDirection) -> MagicMock:
    trend = MagicMock()
    trend.macro_bias = macro
    trend.primary = primary
    trend.alignment_score = 80
    structure = MagicMock()
    structure.breaks_of_structure = []
    structure.changes_of_character = []
    structure.swings = []
    liq = MagicMock()
    liq.sweeps = []
    liq.pools = []
    liq.equal_highs = []
    liq.equal_lows = []
    snap = MagicMock()
    snap.trend = trend
    snap.primary_structure = structure
    snap.liquidity = liq
    snap.order_blocks = MagicMock(order_blocks=[])
    snap.fair_value_gaps = MagicMock(active_gaps=[])
    snap.trade_quality = MagicMock(total=80, components={"momentum": 70})
    snap.session = MagicMock(session=MagicMock(value="london"), allowed=True)
    snap.spread = Decimal("0.20")
    snap.symbol = "XAUUSD_i"
    return snap


def _dir(side: TradeDirection, *, buy: int, sell: int) -> DirectionDecision:
    return DirectionDecision(
        direction=side,
        buy_score=buy,
        sell_score=sell,
        reasons=("fixture",),
        structure_score=70,
        factors={"h1_bias": 28},
    )


def _break(direction: str) -> MagicMock:
    br = MagicMock()
    br.direction = direction
    br.bias = direction
    return br


def _ob(*, bias: str) -> MagicMock:
    zone = MagicMock()
    zone.high_price = Decimal("2652")
    zone.low_price = Decimal("2649")
    quality = MagicMock()
    quality.displacement_ratio = Decimal("1.8")
    block = MagicMock()
    block.state = "ACTIVE"
    block.bias = bias
    block.side = bias
    block.quality = quality
    block.zone = zone
    return block


def test_xauusd_i_is_canonical_execution_symbol() -> None:
    assert GOLD_SYMBOL == "XAUUSD"
    assert CANONICAL_GOLD_BROKER_DISPLAY == "XAUUSD_i"
    assert is_gold_symbol("XAUUSD_i")
    assert is_gold_symbol("XAUUSD_I")
    assert is_bare_gold_symbol("XAUUSD")
    assert not is_bare_gold_symbol("XAUUSD_i")
    assert canonical_gold_execution_symbol("XAUUSD_i") == "XAUUSD_i"
    assert canonical_gold_execution_symbol("XAUUSD") == "XAUUSD_i"


def test_fresh_xauusd_quote_passes_firewall() -> None:
    verdict = evaluate_market_data_firewall(
        symbol="XAUUSD_i",
        bid=2650.10,
        ask=2650.40,
        quote_age_seconds=1.0,
    )
    assert verdict.state is MarketDataState.MARKET_DATA_VALID
    assert verdict.allow_new_entry is True


def test_stale_xauusd_quote_is_rejected() -> None:
    stale = evaluate_market_data_firewall(
        symbol="XAUUSD_i",
        bid=2650.10,
        ask=2650.40,
        quote_age_seconds=200.0,
    )
    assert stale.state is MarketDataState.MARKET_DATA_STALE
    assert stale.allow_new_entry is False


def test_buy_and_sell_scores_are_independent() -> None:
    buy_snap = _trend_snap(macro=TrendDirection.UP, primary=TrendDirection.UP)
    buy_snap.liquidity.sweeps = [MagicMock(side="LOW")]
    buy_snap.primary_structure.breaks_of_structure = [_break("UP")]
    sell_snap = _trend_snap(macro=TrendDirection.DOWN, primary=TrendDirection.DOWN)
    sell_snap.liquidity.sweeps = [MagicMock(side="HIGH")]
    sell_snap.primary_structure.breaks_of_structure = [_break("DOWN")]
    buy_lean = decide_scalping_direction(buy_snap)
    sell_lean = decide_scalping_direction(sell_snap)
    assert buy_lean.buy_score > buy_lean.sell_score
    assert sell_lean.sell_score > sell_lean.buy_score
    assert buy_lean.direction is TradeDirection.BUY
    assert sell_lean.direction is TradeDirection.SELL


def test_wait_when_no_sniper_trigger() -> None:
    snap = _trend_snap(macro=TrendDirection.UP, primary=TrendDirection.UP)
    out = evaluate_sniper_entry(
        snap,
        direction=_dir(TradeDirection.BUY, buy=80, sell=20),
        mid=Decimal("2650"),
        atr=Decimal("4.00"),
        expected_rr=Decimal("1.20"),
        min_expected_rr=Decimal("1.20"),
        stop_loss=Decimal("2646"),
        pa_score=70,
        momentum=70,
        min_momentum=55,
        config=DEFAULT_AI_SCALPING_CONFIG,
    )
    assert out.passed is False
    assert out.action == "WAIT"
    assert out.primary_reason == "WAIT_NO_SNIPER_TRIGGER"


def test_valid_buy_sniper_setup() -> None:
    snap = _trend_snap(macro=TrendDirection.UP, primary=TrendDirection.UP)
    snap.liquidity.sweeps = [MagicMock(side="LOW")]
    snap.primary_structure.breaks_of_structure = [_break("UP")]
    snap.primary_structure.changes_of_character = [_break("UP")]
    snap.order_blocks.order_blocks = [_ob(bias="BUY")]
    out = evaluate_sniper_entry(
        snap,
        direction=_dir(TradeDirection.BUY, buy=82, sell=18),
        mid=Decimal("2650"),
        atr=Decimal("4.00"),
        expected_rr=Decimal("1.40"),
        min_expected_rr=Decimal("1.20"),
        stop_loss=Decimal("2646"),
        pa_score=70,
        momentum=70,
        min_momentum=55,
        config=DEFAULT_AI_SCALPING_CONFIG,
    )
    assert out.passed is True
    assert out.action == "BUY"


def test_valid_sell_sniper_setup() -> None:
    snap = _trend_snap(macro=TrendDirection.DOWN, primary=TrendDirection.DOWN)
    snap.liquidity.sweeps = [MagicMock(side="HIGH")]
    snap.primary_structure.breaks_of_structure = [_break("DOWN")]
    snap.primary_structure.changes_of_character = [_break("DOWN")]
    snap.order_blocks.order_blocks = [_ob(bias="SELL")]
    out = evaluate_sniper_entry(
        snap,
        direction=_dir(TradeDirection.SELL, buy=18, sell=82),
        mid=Decimal("2650"),
        atr=Decimal("4.00"),
        expected_rr=Decimal("1.40"),
        min_expected_rr=Decimal("1.20"),
        stop_loss=Decimal("2654"),
        pa_score=70,
        momentum=70,
        min_momentum=55,
        config=DEFAULT_AI_SCALPING_CONFIG,
    )
    assert out.passed is True
    assert out.action == "SELL"


def test_low_opportunity_score_is_wait_not_safety_block() -> None:
    row = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "BUY",
            "signal_action": "WAIT",
            "trade_quality": 63,
            "ai_confidence": 50,
            "reject": True,
            "reject_reason": "opportunity_score 60 < threshold 70 - WAIT",
            "opportunity_score": 60,
            "opportunity_threshold": 70,
            "buy_score": 72,
            "sell_score": 41,
        }
    )
    assert row["direction"] == "WAIT"
    assert row["badge"] == "WAIT"
    assert row["decision"] == "WAIT"
    assert row["block_code"] != "SAFETY_BLOCK"
    assert "opportunity score below threshold" in str(row["reasoning"]).lower()
    assert row["bullish_score"] == 72
    assert row["bearish_score"] == 41


def test_sniper_wait_is_not_buy_blocked() -> None:
    cls = _execution_classification(
        direction="BUY",
        reject=True,
        reason="WAIT_NO_SNIPER_TRIGGER",
        quality=62,
        confidence=48,
        signal_action="WAIT",
    )
    assert cls["decision"] == "WAIT"
    assert cls["block_code"] == "WAIT_NO_SNIPER_TRIGGER"
    assert cls["status"] != "SAFETY_BLOCK"
    row = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "BUY",
            "signal_action": "WAIT",
            "trade_quality": 62,
            "ai_confidence": 48,
            "reject": True,
            "reject_reason": "WAIT_NO_SNIPER_TRIGGER",
            "atr": "4.12",
            "spread": "0.31",
            "bid": "2650.10",
            "ask": "2650.41",
        }
    )
    assert row["direction"] == "WAIT"
    assert row["badge"] == "WAIT"
    assert row["atr"] == "4.12"
    assert row["spread"] == "0.31"
    assert row["current_price"] == "2650.10"


def test_spread_rr_liquidity_structure_rejection_labels() -> None:
    spread = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "BUY",
            "reject": True,
            "reject_reason": "WAIT_ABNORMAL_SPREAD",
            "trade_quality": 80,
            "ai_confidence": 70,
        }
    )
    assert spread["direction"] == "WAIT"
    assert "spread" in str(spread["reasoning"]).lower()

    rr = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "SELL",
            "reject": True,
            "reject_reason": "WAIT_INSUFFICIENT_RR",
            "trade_quality": 80,
            "ai_confidence": 70,
        }
    )
    assert rr["direction"] == "WAIT"
    assert "rr" in str(rr["reasoning"]).lower()

    liq = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "BUY",
            "reject": True,
            "reject_reason": "NO_LIQUIDITY_EVENT",
            "trade_quality": 80,
            "ai_confidence": 70,
        }
    )
    assert "liquidity" in str(liq["reasoning"]).lower()

    structure = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "SELL",
            "reject": True,
            "reject_reason": "NO_STRUCTURE_CONFIRMATION",
            "trade_quality": 80,
            "ai_confidence": 70,
        }
    )
    assert "structure" in str(structure["reasoning"]).lower()


def test_risk_and_min_lot_blocks_keep_buy_direction() -> None:
    risk = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "BUY",
            "trade_quality": 78,
            "ai_confidence": 67,
            "reject": True,
            "reject_reason": "RISK_BLOCK: daily loss or size rejected",
        }
    )
    assert risk["direction"] == "BUY"
    assert risk["block_code"] == "RISK_BLOCK"

    lot = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "BUY",
            "trade_quality": 94,
            "ai_confidence": 83,
            "reject": True,
            "reject_reason": "MIN_LOT_CONSTRAINT: below broker volume_min",
        }
    )
    assert lot["direction"] == "BUY"
    assert lot["block_code"] == "MIN_LOT_CONSTRAINT"


def test_valid_buy_and_sell_rows_render_as_signals() -> None:
    buy = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "BUY",
            "signal_action": "BUY",
            "trade_quality": 88,
            "ai_confidence": 81,
            "reject": False,
            "sniper_entry": {"action": "BUY", "reasons": ["SNIPER BUY — aligned"]},
        }
    )
    sell = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "SELL",
            "signal_action": "SELL",
            "trade_quality": 88,
            "ai_confidence": 81,
            "reject": False,
            "sniper_entry": {
                "action": "SELL",
                "reasons": ["SNIPER SELL — bearish liquidity sweep + BOS"],
            },
        }
    )
    assert buy["direction"] == "BUY"
    assert "BUY" in buy["badge"]
    assert sell["direction"] == "SELL"
    assert "SELL" in sell["badge"]


def test_signal_center_merges_slim_noc_rows_with_quotes() -> None:
    _store_last_scan(
        {
            "as_of": "2026-08-26T18:00:00Z",
            "universe": ["XAUUSD_i"],
            "noc_rows": [
                {
                    "symbol": "XAUUSD_I",
                    "direction": "BUY",
                    "signal_action": "WAIT",
                    "quality": 62,
                    "confidence": 48,
                    "reject": True,
                    "reject_reason": "WAIT_NO_SNIPER_TRIGGER",
                    "decision": "WAIT",
                }
            ],
            "rows": [
                {
                    "symbol": "XAUUSD_I",
                    "direction": "BUY",
                    "signal_action": "WAIT",
                    "trade_quality": 62,
                    "ai_confidence": 48,
                    "reject": True,
                    "reject_reason": "WAIT_NO_SNIPER_TRIGGER",
                    "atr": "3.90",
                    "spread": "0.28",
                    "bid": "2649.55",
                    "ask": "2649.83",
                    "buy_score": 71,
                    "sell_score": 44,
                    "opportunity_score": 64,
                }
            ],
        }
    )
    payload = list_live_signals(enabled_only=False)
    assert payload["fabricated"] is False
    assert payload["dashboard"]["wait"] == 1
    assert payload["dashboard"]["buy_signals"] == 0
    item = payload["items"][0]
    assert item["symbol"] == "XAUUSD_I"
    assert item["direction"] == "WAIT"
    assert item["atr"] == "3.90"
    assert item["spread"] == "0.28"
    assert item["bullish_score"] == 71
    assert item["opportunity_score"] == 64


def test_signal_persistence_observe_writes_wait_row(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.application.services import signal_intelligence_service as si
    from app.application.services.institutional_multi_asset_scanner import (
        _publish_scan_observation,
    )

    written: list[list[dict]] = []
    _store_last_scan(
        {
            "as_of": "2026-08-26T18:01:00Z",
            "universe": ["XAUUSD_i"],
            "first_blocking_gate": "WAIT_NO_SNIPER_TRIGGER",
            "rows": [
                {
                    "symbol": "XAUUSD_I",
                    "direction": "BUY",
                    "signal_action": "WAIT",
                    "reject": True,
                    "reject_reason": "WAIT_NO_SNIPER_TRIGGER",
                    "trade_quality": 62,
                    "ai_confidence": 48,
                }
            ],
        }
    )
    monkeypatch.setattr(si, "_upsert_history_postgres", lambda rows: written.append(rows) or len(rows))
    monkeypatch.setattr(si, "_save_history_ops_fallback", lambda rows: None)
    obs = si.observe_live_scan()
    assert obs["fabricated"] is False
    assert obs["observed"] == 1
    assert written and written[0][0]["symbol"] == "XAUUSD_I"
    assert written[0][0]["direction"] == "WAIT"
    _publish_scan_observation(
        {
            "first_blocking_gate": "WAIT_NO_SNIPER_TRIGGER",
            "rows": written[0],
        }
    )


def test_noc_row_wait_for_sniper_reject() -> None:
    row = _noc_row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "BUY",
            "signal_action": "WAIT",
            "reject": True,
            "reject_reason": "WAIT_NO_SNIPER_TRIGGER",
            "trade_quality": 62,
            "ai_confidence": 48,
        }
    )
    assert row["decision"] == "WAIT"
    assert row["signal_action"] == "WAIT"


def test_opportunity_threshold_unchanged() -> None:
    from app.domain.institutional_trading.ai_scalping.scoring import AiScalpingScore
    from app.domain.institutional_trading.operations.opportunity_starvation import (
        opportunity_starvation_snapshot,
    )

    assert AiScalpingScore.__dataclass_fields__["opportunity_threshold"].default == 70
    snap = opportunity_starvation_snapshot()
    assert snap["adaptive_threshold_enabled"] is False
    assert int(snap.get("threshold") or 70) == 70
