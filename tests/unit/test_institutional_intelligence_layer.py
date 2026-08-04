"""Unit tests — Institutional Intelligence Layer (ranking / queue / probability / exposure)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.domain.institutional_trading.ai_scalping.execution_probability import (
    estimate_execution_probability,
)
from app.domain.institutional_trading.ai_scalping.institutional_trade_queue import (
    clear_selection,
    peek_next_eligible,
    rebuild_trade_queue,
    select_for_risk,
    snapshot_trade_queue,
)
from app.domain.institutional_trading.ai_scalping.opportunity_ranking import (
    compute_opportunity_score,
    rank_by_opportunity_score,
)
from app.domain.institutional_trading.ai_scalping.performance_analytics import (
    build_performance_analytics,
)
from app.domain.institutional_trading.ai_scalping.portfolio_exposure_intelligence import (
    build_portfolio_exposure,
)


def _eligible_score(
    symbol: str,
    *,
    quality: int = 85,
    confidence: int = 84,
    rr: float = 1.8,
) -> dict:
    return {
        "symbol": symbol,
        "direction": "BUY",
        "reject": False,
        "trade_quality": quality,
        "ai_confidence": confidence,
        "expected_rr": rr,
        "mtf_alignment": 70,
        "liquidity": 65,
        "spread_score": 72,
        "factors": {
            "session": 70,
            "trend_strength": 68,
            "bos": 60,
            "choch": 55,
            "order_block": 58,
            "fvg": 52,
            "volatility": 70,
            "news": 80,
        },
        "volatility_decision": {"passed": True, "band": "normal"},
    }


@pytest.mark.unit
def test_opportunity_score_includes_all_institutional_components() -> None:
    score = _eligible_score("XAUUSD")
    score["probability"] = estimate_execution_probability(score)
    score["estimated_probability"] = score["probability"]["probability_of_success"]
    opp = compute_opportunity_score(score)
    assert 0 <= opp["opportunity_score"] <= 100
    assert opp["eligible"] is True
    comps = opp["components"]
    for key in (
        "ai_quality",
        "confidence",
        "mtf_alignment",
        "liquidity",
        "volatility",
        "spread_quality",
        "session_quality",
        "news_risk",
        "trend_strength",
        "structure_quality",
        "order_block_quality",
        "fvg_quality",
        "risk_reward",
        "execution_probability",
    ):
        assert key in comps
        assert 0 <= comps[key] <= 100
    assert sum(opp["weights"].values()) == 100
    assert opp["fabricated"] is False


@pytest.mark.unit
def test_rejected_scores_are_ineligible_but_visible() -> None:
    row = _eligible_score("EURUSD")
    row["reject"] = True
    row["reject_reason"] = "valid_volatility"
    row["direction"] = "NONE"
    opp = compute_opportunity_score(row)
    assert opp["eligible"] is False
    assert opp["opportunity_score"] >= 0


@pytest.mark.unit
def test_rank_orders_eligible_by_opportunity_score() -> None:
    low = _eligible_score("EURUSD", quality=82, confidence=82, rr=1.2)
    high = _eligible_score("XAUUSD", quality=90, confidence=88, rr=2.2)
    rejected = _eligible_score("GBPUSD")
    rejected["reject"] = True
    rejected["direction"] = "NONE"
    ranked = rank_by_opportunity_score([low, high, rejected])
    assert ranked[0]["symbol"] == "XAUUSD"
    assert ranked[0]["opportunity_eligible"] is True


@pytest.mark.unit
def test_execution_probability_from_ai_only() -> None:
    score = _eligible_score("NAS100", quality=88, confidence=86, rr=2.0)
    prob = estimate_execution_probability(score)
    assert 0.05 <= prob["probability_of_success"] <= 0.95
    assert abs(prob["probability_of_success"] + prob["probability_of_failure"] - 1.0) < 1e-6
    assert prob["estimated_rr"] == 2.0
    assert prob["expected_holding_time_minutes"] is not None
    assert "low" in prob["confidence_interval"]
    assert prob["source"] == "existing_ai_outputs_only"
    assert prob["fabricated"] is False


@pytest.mark.unit
def test_trade_queue_independent_symbols_multi_select() -> None:
    clear_selection()
    rebuild_trade_queue(
        [
            _eligible_score("XAUUSD", quality=90, confidence=88),
            _eligible_score("EURUSD", quality=84, confidence=83),
            {**_eligible_score("GBPUSD"), "reject": True, "direction": "NONE"},
        ]
    )
    snap = snapshot_trade_queue()
    assert snap["eligible_count"] >= 2
    assert snap["one_to_risk_only"] is False
    assert snap["independent_symbols_allowed"] is True
    assert snap["forced_trades"] is False
    first = select_for_risk("XAUUSD")
    assert first is not None
    assert first["symbol"] == "XAUUSD"
    # Independent symbol may also reach Risk (multi-asset concurrent)
    second = select_for_risk("EURUSD")
    assert second is not None
    assert second["symbol"] == "EURUSD"
    # Same symbol cannot be selected twice in one scan window
    assert select_for_risk("XAUUSD") is None
    clear_selection()
    nxt = peek_next_eligible(exclude_symbols={"XAUUSD"})
    assert nxt is not None
    assert nxt["symbol"] == "EURUSD"


@pytest.mark.unit
def test_portfolio_exposure_from_real_positions_only() -> None:
    positions = [
        SimpleNamespace(symbol="XAUUSD", side="buy", volume=0.10),
        SimpleNamespace(symbol="EURUSD", side="sell", volume=0.20),
        SimpleNamespace(symbol="NAS100", side="buy", volume=0.05),
    ]
    exp = build_portfolio_exposure(positions)
    assert exp["open_positions"] == 3
    assert exp["long_exposure"] == pytest.approx(0.15)
    assert exp["short_exposure"] == pytest.approx(0.20)
    assert exp["net_exposure"] == pytest.approx(-0.05)
    assert "sector_exposure" in exp
    assert "correlation_risk" in exp
    assert exp["fabricated"] is False
    assert exp["enforcement"] == "existing_PRE_and_risk_limits"


@pytest.mark.unit
def test_performance_analytics_never_fabricates() -> None:
    snap = build_performance_analytics()
    assert snap["fabricated"] is False
    assert snap["source"] == "real_completed_trades_only"
    assert "win_rate" in snap
    assert "average_rr" in snap
    assert "profit_factor" in snap
    assert "sharpe" in snap


@pytest.mark.unit
def test_noc_intelligence_panels_shape() -> None:
    from app.application.services.noc_intelligence_panels import (
        build_intelligence_panels,
    )

    panels = build_intelligence_panels(
        runtime_scan={
            "as_of": "2026-07-31T00:00:00Z",
            "best_symbol": None,
            "opportunity_ranked": [
                {
                    "symbol": "XAUUSD",
                    "opportunity_score": 77,
                    "quality": 85,
                    "confidence": 84,
                    "eligible": False,
                    "blocking_gate": "valid_volatility",
                    "estimated_probability": 0.62,
                }
            ],
            "trade_queue": {"candidates": [], "size": 0},
            "best": None,
        }
    )
    assert "opportunity_ranking" in panels
    assert "trade_queue" in panels
    assert "portfolio_exposure" in panels
    assert "performance_analytics" in panels
    assert "replay_library" in panels
    assert "execution_probability" in panels
    assert panels["flags"]["forced_trades"] is False
    assert panels["flags"]["fabricated"] is False
    assert panels["opportunity_ranking"]["rows"][0]["symbol"] == "XAUUSD"
