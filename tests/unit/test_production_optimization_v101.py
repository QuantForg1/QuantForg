"""v1.0.1 production optimization analytics tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.domain.execution_intelligence.analytics import (
    compute_execution_analytics,
    percentile,
)
from app.domain.execution_intelligence.broker_quality import compute_broker_quality
from app.domain.execution_intelligence.trend_analytics import (
    compute_regime_analytics,
    compute_risk_trends,
    compute_session_analytics,
)
from app.domain.institutional_trading.operations.alerts import AlertService
from app.domain.institutional_trading.operations.models import (
    AlertKind,
    AlertSeverity,
)
from app.domain.institutional_trading.session_filter import classify_session_utc
from app.domain.market_context.enums import MarketSession


def test_percentile_p50_p99() -> None:
    vals = [10.0, 20.0, 30.0, 40.0, 100.0]
    assert percentile(vals, 50) == 30.0
    assert percentile([], 50) is None
    assert percentile(vals, 99) is not None


def test_execution_analytics_percentiles_and_abnormal() -> None:
    attempts = [
        {
            "request_id": "a1",
            "outcome": "success",
            "latency_ms": 40,
            "submitted_at": "2026-07-22T10:00:00+00:00",
            "filled_at": "2026-07-22T10:00:00.050+00:00",
            "price": 2350.2,
            "request_snapshot": {"price": 2350.0, "spread": "0.3"},
        },
        {
            "request_id": "a2",
            "outcome": "rejected",
            "latency_ms": 900,
            "created_at": "2026-07-22T11:00:00+00:00",
        },
        {
            "request_id": "a3",
            "outcome": "success",
            "latency_ms": 55,
            "price": 2351.0,
            "request_snapshot": {"price": 2350.9},
        },
    ]
    fills = [
        {"requested_price": 2350.0, "fill_price": 2350.2, "slippage": 0.2},
        {"requested_price": 2350.9, "fill_price": 2351.0, "slippage": 0.1},
    ]
    out = compute_execution_analytics(attempts=attempts, fills=fills)
    assert out["status"] == "available"
    m = out["metrics"]
    assert m["order_latency_ms_p50"] is not None
    assert m["order_latency_ms_p95"] is not None
    assert m["order_latency_ms_p99"] is not None
    assert m["abnormal_execution_count"] >= 1
    assert out["trades"]


def test_risk_session_regime_trends() -> None:
    now = datetime.now(UTC)
    trades = [
        {
            "net_pnl": 12.0,
            "closed_at": (now - timedelta(hours=2)).isoformat(),
            "opened_at": (now - timedelta(hours=3)).isoformat(),
            "session": "london",
            "regime": "trend",
            "r_multiple": 1.2,
        },
        {
            "net_pnl": -5.0,
            "closed_at": (now - timedelta(hours=1)).isoformat(),
            "opened_at": (now - timedelta(hours=2)).isoformat(),
            "session": "london",
            "regime": "trend",
            "r_multiple": -0.5,
        },
        {
            "net_pnl": 8.0,
            "closed_at": now.isoformat(),
            "session": "new_york",
            "regime": "range",
            "r_multiple": 0.8,
        },
    ]
    risk = compute_risk_trends(trades)
    assert risk["status"] == "available"
    assert risk["trends"]["consecutive_wins_max"] >= 1
    assert risk["trends"]["average_r"] is not None

    sessions = compute_session_analytics(trades)
    assert sessions["sessions"]["london"]["trade_count"] == 2
    assert sessions["overall"]["profit_factor"] is not None

    regimes = compute_regime_analytics(trades)
    assert regimes["regimes"]["trend"]["trade_count"] == 2
    assert regimes["regimes"]["range"]["trade_count"] == 1
    assert regimes["regimes"]["news"]["trade_count"] == 0


def test_broker_quality_score() -> None:
    q = compute_broker_quality(
        fill_rate=0.9,
        reject_rate=0.05,
        avg_slippage=0.1,
        latency_p95_ms=80,
        reconnect_count=1,
        connected=True,
        attempt_count=20,
    )
    assert q["status"] == "available"
    assert q["score"] is not None
    assert 0 <= q["score"] <= 100


def test_alert_grouping_and_cooldown() -> None:
    svc = AlertService(cooldown=timedelta(minutes=15))
    a1 = svc.raise_alert(
        kind=AlertKind.HIGH_LATENCY,
        severity=AlertSeverity.WARNING,
        message="slow",
    )
    a2 = svc.raise_alert(
        kind=AlertKind.HIGH_LATENCY,
        severity=AlertSeverity.WARNING,
        message="still slow",
    )
    assert a1.id == a2.id
    assert a2.occurrence_count >= 2
    grouped = svc.grouped()
    assert any(g["kind"] == AlertKind.HIGH_LATENCY.value for g in grouped)


def test_sydney_session_classifier() -> None:
    # 22:00 UTC weekday → Sydney
    ts = datetime(2026, 7, 22, 22, 0, tzinfo=UTC)
    assert classify_session_utc(ts) == MarketSession.SYDNEY
