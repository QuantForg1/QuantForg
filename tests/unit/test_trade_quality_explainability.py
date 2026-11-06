"""Trade quality is a separate weighted average from the opportunity score.

The live XAUUSD scans after PR #174 published quality 47 and opportunity 76–77.
These tests lock the formulas. They do not invent the unlogged factor split.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    scalping_ite_config,
)
from app.domain.institutional_trading.models import (
    TradeQualityFactor,
    TradeQualityScore,
)
from app.domain.institutional_trading.operations.probability_selector import (
    OPPORTUNITY_WEIGHTS,
    weighted_opportunity_score,
)
from app.domain.institutional_trading.owner_live_limits import OWNER_MIN_TRADE_QUALITY
from app.domain.institutional_trading.session_filter import classify_session_utc
from app.domain.institutional_trading.trade_quality import (
    TradeQualityEvaluator,
    explain_trade_quality,
)
from app.domain.market_context.enums import MarketSession

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def test_owner_quality_floor_stays_70() -> None:
    assert OWNER_MIN_TRADE_QUALITY == 70


def test_tokyo_open_and_live_spread_are_known_quality_inputs() -> None:
    """00:09 UTC on a Friday is Tokyo. Spread 0.424 is just outside a full score."""
    moment = datetime(2026, 11, 6, 0, 9, tzinfo=UTC)
    assert moment.weekday() == 4
    assert classify_session_utc(moment) is MarketSession.TOKYO

    cfg = scalping_ite_config(scalp=DEFAULT_AI_SCALPING_CONFIG)
    spread = TradeQualityEvaluator(config=cfg)._spread(Decimal("0.424"))
    session_score = 55
    assert spread.score == 97
    assert spread.weight == 10
    known_points = session_score * 10 + spread.score * spread.weight
    assert known_points == 1520


def test_explanation_recomputes_the_published_total() -> None:
    factors = (
        TradeQualityFactor("trend", 20, 15, "alignment"),
        TradeQualityFactor("liquidity", 15, 65, "context"),
        TradeQualityFactor("order_block", 15, 20, "none active"),
        TradeQualityFactor("fair_value_gap", 15, 70, "one open"),
        TradeQualityFactor("market_structure", 15, 40, "primary"),
        TradeQualityFactor("session", 10, 55, "tokyo"),
        TradeQualityFactor("spread", 10, 97, "0.424"),
    )
    weighted = sum(f.score * f.weight for f in factors)
    total = round(weighted / 100)
    assert total == 47
    quality = TradeQualityScore(
        total=total, passed=False, band="reject", factors=factors
    )
    explained = explain_trade_quality(quality)
    assert explained["matches_published_total"] is True
    assert explained["recomputed_total"] == 47
    assert explained["weighted_sum"] == weighted
    assert sum(int(row["weight"]) for row in explained["components"]) == 100


def test_logged_opportunity_breakdown_is_not_the_quality_total() -> None:
    """The 00:09 UTC scan breakdown. Consensus is the average of 47 and 53."""
    assert round((47 + 53) / 2) == 50
    posted = {
        "structure": 85,
        "momentum": 78,
        "consensus": 50,
        "regime_fit": 58,
        "price_action": 80,
        "liquidity": 80,
        "volatility": 74,
        "execution_quality": 97,
        "mtf_alignment": 82,
        "rr_quality": 100,
    }
    score, breakdown = weighted_opportunity_score(posted, weights=OPPORTUNITY_WEIGHTS)
    assert breakdown == posted
    assert score == 77
    softer = dict(posted)
    softer["execution_quality"] = 96
    softer_score, _ = weighted_opportunity_score(softer, weights=OPPORTUNITY_WEIGHTS)
    assert softer_score == 76
    assert score != 47
