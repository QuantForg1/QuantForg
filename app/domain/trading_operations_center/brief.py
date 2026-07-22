"""Daily trading brief — pre-session advisory pack."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any


def _today(raw: Any) -> str:
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw.isoformat()
    if isinstance(raw, datetime):
        return raw.astimezone(UTC).date().isoformat()
    if raw:
        return str(raw)[:10]
    return datetime.now(UTC).date().isoformat()


def build_daily_brief(
    *,
    trading_date: Any = None,
    expected_sessions: list[str] | None = None,
    high_impact_news: list[dict[str, Any]] | None = None,
    calendar_available: bool | None = None,
    market_regime: str | None = None,
    volatility_expectation: str | None = None,
    evidence_status: dict[str, Any] | None = None,
    open_alerts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Generate pre-day brief from supplied facts only."""
    sessions = list(expected_sessions or ["london", "new_york", "overlap"])
    news = [n for n in (high_impact_news or []) if isinstance(n, dict)]
    cal_ok = calendar_available
    if cal_ok is None:
        cal_ok = len(news) > 0

    news_block: dict[str, Any]
    if cal_ok:
        news_block = {
            "status": "available" if news else "empty",
            "items": news,
            "count": len(news),
            "note": "From supplied economic calendar only — never fabricated",
        }
    else:
        news_block = {
            "status": "unavailable",
            "items": [],
            "count": 0,
            "note": "Economic calendar not available — high-impact news omitted",
        }

    evidence = dict(evidence_status or {})
    alerts = [a for a in (open_alerts or []) if isinstance(a, dict)]

    return {
        "status": "available",
        "trading_date": _today(trading_date),
        "expected_sessions": sessions,
        "high_impact_news": news_block,
        "current_market_regime": market_regime or None,
        "volatility_expectation": volatility_expectation or None,
        "evidence_status": evidence
        if evidence
        else {
            "status": "unknown",
            "note": "Evidence status not supplied",
        },
        "open_operational_alerts": alerts,
        "open_alert_count": len(alerts),
        "advisory_only": True,
        "note": "Brief uses supplied ops/evidence/calendar facts only",
    }
