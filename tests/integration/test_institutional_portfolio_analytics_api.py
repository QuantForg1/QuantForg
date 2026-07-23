"""Integration-style tests — Institutional Portfolio Analytics sections."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.application.services.institutional_portfolio_analytics import (
    analyze_portfolio,
    build_institutional_portfolio_analytics,
)

pytestmark = pytest.mark.integration


def _minimal_trades(count: int = 8) -> list[dict]:
    trades: list[dict] = []
    for i in range(count):
        entry = datetime.now(UTC) - timedelta(days=10 - i)
        exit_ts = entry + timedelta(minutes=30)
        pnl = 10.0 if i % 2 == 0 else -4.0
        trades.append(
            {
                "id": f"api-{i}",
                "entry_time": entry.isoformat(),
                "exit_time": exit_ts.isoformat(),
                "holding_time_sec": 1800,
                "profit_loss": pnl,
                "market_session": "london",
                "volume": 0.01,
                "entry": 2300.0,
                "exit": 2300.0 + pnl,
                "spread": 0.3,
                "atr": 1.2,
                "risk_reward": 1.5,
            }
        )
    return trades


def test_build_report_periods_integration() -> None:
    payload = analyze_portfolio(_minimal_trades(), starting_equity=10_000.0)
    for period in ("daily", "weekly", "monthly", "quarterly", "yearly"):
        assert period in payload["reports"]
        report = payload["reports"][period]
        assert report["trade_count"] >= 0
        assert "analysis" in report


def test_analyze_portfolio_section_integration() -> None:
    payload = analyze_portfolio(_minimal_trades(), starting_equity=10_000.0)
    sections = payload["sections"]
    for key in (
        "dashboard",
        "risk",
        "performance",
        "behavior",
        "time",
        "equity_analytics",
        "health_score",
    ):
        assert key in sections
        assert isinstance(sections[key], dict)


def test_build_institutional_portfolio_analytics_importable() -> None:
    """Smoke import — live gateway may be unavailable in CI."""
    assert callable(build_institutional_portfolio_analytics)
