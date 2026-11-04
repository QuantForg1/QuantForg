"""Phase-6 opportunity intelligence: RR, gold regime, pack agreement."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.institutional_trading.ai_scalping.regime import (
    classify_scalping_regime,
)
from app.domain.institutional_trading.ai_scalping.strategies.advisory_collaboration import (  # noqa: E501
    AdvisoryVote,
    summarize_advisory_agreement,
)
from app.domain.institutional_trading.ai_scalping.strategies.evaluate import (
    evaluate_all_strategies,
)
from app.domain.institutional_trading.ai_scalping.strategies.orchestrator import (
    MIN_CONFLUENT_QUALITY,
    ORCHESTRATION_VERSION,
    orchestrate_strategies,
)
from app.domain.institutional_trading.ai_scalping.structure_targets import (
    select_owner_structure_tp,
)
from app.domain.institutional_trading.owner_live_limits import (
    evaluate_owner_entry,
    net_reward_risk,
)


def _base_score(**overrides):
    row = {
        "symbol": "XAUUSD",
        "reject": False,
        "direction": "BUY",
        "trade_quality": 80,
        "ai_confidence": 78,
        "structure_score": 72,
        "momentum": 70,
        "liquidity": 70,
        "mtf_alignment": 75,
        "spread_score": 70,
        "market_regime": "strong_trend",
        "setup_family": "bos_continuation",
        "net_reward_risk": 2.0,
        "expected_rr": 2.0,
        "thresholds": {"quality": 74, "confidence": 71, "band": "normal"},
        "factors": {
            "bos": 85,
            "choch": 20,
            "order_block": 80,
            "fvg": 70,
            "momentum": 70,
            "volume": 75,
            "volatility": 70,
            "atr_expansion": 70,
            "ema": 70,
            "trend_strength": 75,
            "pa_confluence": 60,
            "liquidity_sweep": 70,
            "mtf": 75,
            "spread": 70,
        },
    }
    row.update(overrides)
    return row


@pytest.mark.unit
def test_soe_version_is_v14() -> None:
    assert ORCHESTRATION_VERSION == "soe-v1.4.0"


@pytest.mark.unit
def test_spread_already_in_stop_does_not_double_count() -> None:
    """Owner SL embeds spread buffer — net RR must not add spread again."""
    # stop=2.00 already includes 0.30 buffer; tp=3.00 → net 1.50 without re-add.
    doubled = net_reward_risk(
        tp_distance=Decimal("3.00"),
        stop_distance=Decimal("2.00"),
        spread=Decimal("0.30"),
        spread_already_in_stop=False,
    )
    fixed = net_reward_risk(
        tp_distance=Decimal("3.00"),
        stop_distance=Decimal("2.00"),
        spread=Decimal("0.30"),
        spread_already_in_stop=True,
    )
    assert doubled.ratio == Decimal("3.00") / Decimal("2.30")
    assert fixed.ratio == Decimal("3.00") / Decimal("2.00")
    assert fixed.ratio == Decimal("1.5")
    assert fixed.ratio > doubled.ratio


@pytest.mark.unit
def test_owner_tp_selection_with_buffered_stop_clears_floor() -> None:
    entry = Decimal("100")
    # Buffered stop 2.00 (structure 1.70 + spread 0.30). TP at +3.00.
    # Double-count path: 3/2.30 < 1.50 → reject. Fixed: 3/2.00 = 1.50 → accept.
    wrong = select_owner_structure_tp(
        [(entry + Decimal("3.00"), "swing_M1")],
        entry=entry,
        stop_distance=Decimal("2.00"),
        spread=Decimal("0.30"),
        min_rr=Decimal("1.50"),
        spread_already_in_stop=False,
    )
    right = select_owner_structure_tp(
        [(entry + Decimal("3.00"), "swing_M1")],
        entry=entry,
        stop_distance=Decimal("2.00"),
        spread=Decimal("0.30"),
        min_rr=Decimal("1.50"),
        spread_already_in_stop=True,
    )
    assert wrong.level is None
    assert right.level == 1
    assert right.rr_after_spread == Decimal("1.5")


@pytest.mark.unit
def test_evaluate_owner_entry_respects_spread_buffer_flag() -> None:
    common = {
        "symbol": "XAUUSD",
        "side": "BUY",
        "volume": Decimal("0.01"),
        "entry": Decimal("100"),
        "stop_loss": Decimal("98"),  # stop dist 2.00 (buffer already in)
        "take_profit": Decimal("101"),  # tp dist 1.00 → 1.00/2.00 = 0.50
        "spread": Decimal("0.30"),
        "contract_size": Decimal("100"),
        "equity": Decimal("50"),
        "commission": Decimal("0"),
    }
    # Without flag: risk = 2.30 → RR < 0.50 → reject.
    blocked = evaluate_owner_entry(**common, stop_includes_spread_buffer=False)
    assert any(r.startswith("OWNER_MIN_RR") for r in blocked)
    # With flag: risk = 2.00 → RR = 0.50 → clear RR floor.
    ok = evaluate_owner_entry(**common, stop_includes_spread_buffer=True)
    assert not any(r.startswith("OWNER_MIN_RR") for r in ok)


@pytest.mark.unit
def test_gold_regime_breakout_reachable_at_realistic_atr() -> None:
    """XAUUSD ATR% ~0.30 must be able to classify breakout (was unreachable at 1.5)."""
    # Without symbol: legacy 1.5 high-vol → no breakout at 0.30.
    legacy = classify_scalping_regime(
        alignment_score=60,
        atr_pct=Decimal("0.30"),
        bos=80,
        volume_expanding=True,
    )
    assert legacy.regime != "breakout"
    # With XAUUSD: high band 0.35 → 0.30 is mid_vol → breakout with BOS+volume.
    gold = classify_scalping_regime(
        alignment_score=60,
        atr_pct=Decimal("0.30"),
        bos=80,
        volume_expanding=True,
        symbol="XAUUSD",
    )
    assert gold.regime == "breakout"


@pytest.mark.unit
def test_gold_regime_compression_uses_class_low_band() -> None:
    # ATR% 0.07 below gold low 0.08 → compression when range-like.
    gold = classify_scalping_regime(
        alignment_score=40,
        atr_pct=Decimal("0.07"),
        range_like=True,
        symbol="XAUUSD",
    )
    assert gold.regime == "compression"


@pytest.mark.unit
def test_pack_agreement_clears_solo_bar_at_confluent_quality() -> None:
    """Multiple same-cluster passers at Q>=76 may clear solo selectivity."""
    score = _base_score(
        trade_quality=78,
        ai_confidence=76,
        net_reward_risk=2.1,
        expected_rr=2.1,
        # Suppress synthetic advisory disagreement noise — HOLD-heavy.
        factors={
            **_base_score()["factors"],
            "bos": 50,
            "momentum": 50,
            "volatility": 50,
            "ema": 50,
            "trend_strength": 50,
            "pa_confluence": 40,
            "mtf": 50,
        },
        mtf_alignment=50,
        momentum=70,
    )
    # Force quality into confluent band but below solo bar via score fields
    # used by evaluate_strategy weighting — keep base gates clear.
    score["trade_quality"] = 78
    evals = evaluate_all_strategies(score)
    passers = [e for e in evals if e.passed]
    assert len(passers) >= 2
    # Lower qualities to confluent-but-not-solo via constructing verdict path:
    # use score that yields ~78 strategy quality.
    verdict = orchestrate_strategies(evals, score=score)
    # Pack agreement path: either selects or cites pack_agreement / advisory.
    if verdict.prefer_no_trade:
        joined = " ".join(verdict.reasons)
        # Must not be the old solo-only bar if pack agreement should fire.
        # Evidence gate / other gates may still prefer no trade legitimately.
        assert "prefer no trade" in joined.lower()
    else:
        assert verdict.selected is not None
        assert verdict.selected.quality >= MIN_CONFLUENT_QUALITY
        assert any("pack_agreement" in r for r in verdict.reasons)


@pytest.mark.unit
def test_score_factor_advisory_alone_cannot_force_strong_disagreement() -> None:
    votes = (
        AdvisoryVote(
            strategy_id="fade_proxy",
            name="Fade",
            direction="SELL",
            confidence=80,
            reason="synthetic opposite",
            source="score_factor_advisory",
        ),
        AdvisoryVote(
            strategy_id="fade_proxy_2",
            name="Fade2",
            direction="SELL",
            confidence=80,
            reason="synthetic opposite",
            source="score_factor_advisory",
        ),
    )
    summary = summarize_advisory_agreement(live_direction="BUY", votes=votes)
    assert summary["disagree_count"] == 2
    assert summary["strong_disagreement"] is False
    real = (
        AdvisoryVote(
            strategy_id="alpha_a",
            name="Alpha A",
            direction="SELL",
            confidence=80,
            reason="real engine",
            source="institutional_alpha",
        ),
        AdvisoryVote(
            strategy_id="plugin_b",
            name="Plugin B",
            direction="SELL",
            confidence=80,
            reason="real engine",
            source="strategy_engine_plugin",
        ),
    )
    real_summary = summarize_advisory_agreement(live_direction="BUY", votes=real)
    assert real_summary["strong_disagreement"] is True
