"""Unit tests — Institutional Portfolio Analytics (read-only)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.application.services.institutional_portfolio_analytics import (
    analyze_portfolio,
    analytics_to_csv,
    analytics_to_pdf_bytes,
    build_report,
    section_health_score,
)

pytestmark = pytest.mark.unit


def _trade(
    i: int,
    pnl: float,
    *,
    day_offset: int,
    session: str = "london",
    risk_reward: float = 1.5,
) -> dict:
    entry = datetime.now(UTC) - timedelta(days=day_offset, hours=i % 6)
    exit_ts = entry + timedelta(minutes=20 + (i % 40))
    return {
        "id": f"t{i}",
        "entry_time": entry.isoformat(),
        "exit_time": exit_ts.isoformat(),
        "holding_time_sec": int((exit_ts - entry).total_seconds()),
        "profit_loss": pnl,
        "market_session": session,
        "volume": 0.01,
        "entry": 2300.0 + i * 0.1,
        "exit": 2300.0 + i * 0.1 + pnl,
        "spread": 0.25 + (i % 3) * 0.05,
        "atr": 1.1 + (i % 5) * 0.1,
        "risk_reward": risk_reward,
    }


def _synthetic_trades(*, bullish: bool = True) -> list[dict]:
    """Wins and losses spread across several days."""
    pnls = (
        [12.0, 8.0, 15.0, 10.0, 9.0, 11.0, 14.0, 7.0, 13.0, 6.0, 5.0, 4.0]
        + [-4.0, -3.0, -5.0, -2.0]
        if bullish
        else [-12.0, -10.0, -8.0, -15.0, -6.0, -9.0, -4.0, -11.0]
        + [3.0, 2.0]
    )
    trades: list[dict] = []
    for i, pnl in enumerate(pnls):
        trades.append(
            _trade(
                i,
                pnl,
                day_offset=30 - (i % 12),
                session=["london", "new_york", "overlap"][i % 3],
                risk_reward=1.8 if pnl > 0 else 0.7,
            )
        )
    return trades


class TestAnalyzePortfolio:
    def test_core_metrics_bullish_sample(self) -> None:
        trades = _synthetic_trades(bullish=True)
        payload = analyze_portfolio(
            trades,
            starting_equity=10_000.0,
            source_meta={"ok": True},
        )

        dashboard = payload["sections"]["dashboard"]
        performance = payload["sections"]["performance"]
        risk = payload["sections"]["risk"]
        health = payload["sections"]["health_score"]

        assert dashboard["net_profit"] == pytest.approx(sum(t["profit_loss"] for t in trades), abs=0.01)
        assert performance["win_rate_pct"] == pytest.approx(
            sum(1 for t in trades if t["profit_loss"] > 0) / len(trades) * 100.0,
            abs=0.01,
        )
        assert risk["max_drawdown_pct"] is not None
        assert risk["max_drawdown_abs"] is not None
        assert health["status"] in {"GREEN", "YELLOW", "RED"}

        assert payload["mutates_engines"] is False
        assert payload["analytics_only"] is True
        assert payload["never_modifies_strategy_risk_safety_oms_execution_auto_trading_thresholds"] is True

        for period in ("daily", "weekly", "monthly", "quarterly", "yearly"):
            assert period in payload["reports"]
            assert payload["reports"][period]["period"] == period
            report = payload["reports"][period]
            assert "executive_summary" in report
            assert "performance_summary" in report
            assert "risk_summary" in report
            assert "market_summary" in report
            assert "strategy_summary" in report
            assert "recommendations" in report
            assert "operational_notes" in report
            assert performance.get("loss_rate_pct") is not None or len(trades) == 0
            assert payload["sections"]["behavior"].get("trading_frequency") in {
                "high",
                "moderate",
                "low",
                "none",
            }

    def test_health_score_levels(self) -> None:
        green = section_health_score(
            dashboard={"balance": 10_500, "equity": 10_500},
            risk={"max_drawdown_pct": 5.0, "ulcer_index": 2.0},
            performance={"win_rate_pct": 62.0, "profit_factor": 2.0, "expectancy": 8.0},
            behavior={"session_performance": {"london": {"count": 5, "win_rate": 60.0}}},
            equity_path={"trade_count": 20},
            source_meta={"ok": True},
        )
        assert green["status"] == "GREEN"

        yellow = section_health_score(
            dashboard={"balance": 9_800, "equity": 9_800},
            risk={"max_drawdown_pct": 22.0, "ulcer_index": 40.0},
            performance={"win_rate_pct": 38.0, "profit_factor": 0.7, "expectancy": -3.0},
            behavior={"session_performance": {}},
            equity_path={"trade_count": 8},
            source_meta={"ok": False},
        )
        assert yellow["status"] == "YELLOW"

        red = section_health_score(
            dashboard={"balance": 7_500, "equity": 7_500},
            risk={"max_drawdown_pct": 50.0, "ulcer_index": 70.0},
            performance={"win_rate_pct": 18.0, "profit_factor": 0.2, "expectancy": -15.0},
            behavior={"session_performance": {}},
            equity_path={"trade_count": 3},
            source_meta={"ok": False},
        )
        assert red["status"] == "RED"

    def test_bearish_sample_still_analyzes(self) -> None:
        trades = _synthetic_trades(bullish=False)
        payload = analyze_portfolio(trades, starting_equity=10_000.0)
        assert payload["sections"]["performance"]["net_profit"] < 0
        assert payload["sections"]["health_score"]["status"] in {"YELLOW", "RED"}


class TestExports:
    def test_analytics_to_csv_contains_section_headers(self) -> None:
        payload = analyze_portfolio(_synthetic_trades(), starting_equity=10_000.0)
        csv_text = analytics_to_csv(payload)
        assert csv_text.startswith("section,")
        for section in ("dashboard", "risk", "performance", "behavior", "health_score"):
            assert section in csv_text

    def test_analytics_to_pdf_bytes_starts_with_pdf(self) -> None:
        payload = analyze_portfolio(_synthetic_trades(), starting_equity=10_000.0)
        pdf = analytics_to_pdf_bytes(payload)
        assert pdf.startswith(b"%PDF")


class TestReportPeriods:
    def test_build_report_periods(self) -> None:
        trades = _synthetic_trades()
        payload = analyze_portfolio(trades, starting_equity=10_000.0)
        for period in ("daily", "weekly", "monthly", "quarterly", "yearly"):
            assert period in payload["reports"]

        base = {**payload, "closed_trades": trades, "trades": trades}
        for period in ("daily", "weekly", "monthly", "quarterly", "yearly"):
            report = build_report(base, period=period)  # type: ignore[arg-type]
            assert report["period"] == period
            assert "executive_summary" in report
            assert "performance_summary" in report
            assert "risk_summary" in report
            assert "recommendations" in report
            assert "operational_notes" in report
            assert "analysis" in report


class TestPerformanceBudget:
    def test_analyze_portfolio_completes_under_budget(self) -> None:
        import time

        trades = _synthetic_trades(bullish=True) * 8  # ~128 trades
        t0 = time.perf_counter()
        payload = analyze_portfolio(trades, starting_equity=10_000.0)
        elapsed = time.perf_counter() - t0
        assert payload["trade_count"] == len(trades)
        assert elapsed < 2.0
