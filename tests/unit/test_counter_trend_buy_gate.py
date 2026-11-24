from app.domain.institutional_trading.ai_scalping.strategies.soe_intelligence import (
    counter_trend_buy_reason,
    evidence_intelligence_reason,
)


def test_sell_and_neutral_buy_unaffected() -> None:
    assert (
        counter_trend_buy_reason({"direction": "SELL", "htf_bias": "bearish"}) is None
    )
    assert counter_trend_buy_reason({"direction": "BUY"}) is None
    assert counter_trend_buy_reason(None) is None


def test_bearish_bias_buy_needs_strong_evidence() -> None:
    weak = {
        "direction": "BUY",
        "htf_bias": "bearish",
        "structure_score": 60,
        "mtf_alignment": 80,
    }
    assert counter_trend_buy_reason(weak) is not None
    strong = {
        "direction": "BUY",
        "htf_bias": "bearish",
        "structure_score": 80,
        "mtf_alignment": 80,
    }
    assert counter_trend_buy_reason(strong) is None


def test_ltf_sell_lean_triggers_gate() -> None:
    score = {
        "direction": "BUY",
        "ltf_buy_score": 40,
        "ltf_sell_score": 55,
        "structure_score": 65,
        "mtf_alignment": 70,
    }
    assert counter_trend_buy_reason(score) is not None
    assert evidence_intelligence_reason(score) is not None
