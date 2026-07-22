"""Hydrate IVP / LLP / RMIP / PRC evaluate payloads from read-only feeds."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.domain.integration_sprint_v1.config import MISSING
from app.domain.integration_sprint_v1.feeds import IntegrationFeeds


def _deal_to_trade(deal: dict[str, Any]) -> dict[str, Any]:
    pnl = deal.get("profit") or deal.get("pnl") or deal.get("result")
    return {
        "id": str(deal.get("ticket") or deal.get("id") or ""),
        "pnl": pnl,
        "net_pnl": pnl,
        "result": pnl,
        "entry_context": deal.get("comment") or deal.get("entry_context"),
        "exit_context": deal.get("exit_context"),
        "market_regime": deal.get("regime") or deal.get("market_regime"),
        "session": deal.get("session"),
        "spread": deal.get("spread"),
        "volatility": deal.get("volatility"),
        "liquidity": deal.get("liquidity"),
        "risk_usage": deal.get("risk_usage"),
        "decision_explanation": deal.get("decision_explanation"),
        "execution_latency": deal.get("execution_latency")
        or deal.get("latency_ms"),
        "source": "mt5_trade_feed",
        "immutable": True,
    }


def hydrate_ivp(
    feeds: IntegrationFeeds, overrides: dict[str, Any] | None = None
) -> dict[str, Any]:
    overrides = overrides or {}
    trade_snap = feeds.mt5_trade_feed()
    trades: list[dict[str, Any]] = []
    if trade_snap.available and isinstance(trade_snap.payload, list):
        trades = [_deal_to_trade(d) for d in trade_snap.payload if isinstance(d, dict)]

    body: dict[str, Any] = {
        "completed_trades": trades or None,
        "feed_status": {
            "mt5_trade_feed": trade_snap.health.to_dict(),
            "missing": MISSING if not trades else None,
        },
    }
    # Caller overrides win — preserve existing API contract
    for k, v in overrides.items():
        if v is not None:
            body[k] = v
    if not body.get("completed_trades"):
        body["completed_trades"] = overrides.get("completed_trades")
    return body


def hydrate_llp(
    feeds: IntegrationFeeds, overrides: dict[str, Any] | None = None
) -> dict[str, Any]:
    overrides = overrides or {}
    trade_snap = feeds.mt5_trade_feed()
    journal_snap = feeds.execution_journal_feed()
    analytics = feeds.analytics_feed()
    trades: list[dict[str, Any]] = []
    if trade_snap.available and isinstance(trade_snap.payload, list):
        trades = [_deal_to_trade(d) for d in trade_snap.payload if isinstance(d, dict)]

    live_results = None
    if analytics.available and isinstance(analytics.payload, dict):
        live_results = {
            "trade_count": analytics.payload.get("trade_count"),
            "source": "analytics_feed",
        }

    body: dict[str, Any] = {
        "completed_trades": trades or None,
        "live_results": live_results,
        "feed_status": {
            "mt5_trade_feed": trade_snap.health.to_dict(),
            "execution_journal_feed": journal_snap.health.to_dict(),
        },
    }
    for k, v in overrides.items():
        if v is not None:
            body[k] = v
    return body


def hydrate_rmip(
    feeds: IntegrationFeeds, overrides: dict[str, Any] | None = None
) -> dict[str, Any]:
    overrides = overrides or {}
    cal = feeds.economic_calendar_provider()
    market = feeds.mt5_market_data_feed()
    warehouse = feeds.historical_data_warehouse()

    events = None
    if cal.available and isinstance(cal.payload, list):
        events = cal.payload

    vol_obs = None
    if market.available and isinstance(market.payload, dict):
        tick = market.payload.get("tick") or {}
        # Only report fields present — never invent ATR/ADR
        vol_obs = {
            "spread_expansion": tick.get("spread") or tick.get("ask_bid_spread"),
            "as_of": market.payload.get("as_of"),
            "source": "mt5_market_data_feed",
        }
        # Strip Nones
        vol_obs = {k: v for k, v in vol_obs.items() if v is not None}

    body: dict[str, Any] = {
        "economic_events": events,
        "clock_utc": datetime.now(UTC).isoformat(),
        "volatility_observations": vol_obs or None,
        "feed_status": {
            "economic_calendar_provider": cal.health.to_dict(),
            "mt5_market_data_feed": market.health.to_dict(),
            "historical_data_warehouse": warehouse.health.to_dict(),
            "missing_calendar": MISSING if not events else None,
        },
    }
    for k, v in overrides.items():
        if v is not None:
            body[k] = v
    return body


def hydrate_prc(
    feeds: IntegrationFeeds, overrides: dict[str, Any] | None = None
) -> dict[str, Any]:
    overrides = overrides or {}
    account = feeds.broker_account_feed()
    market = feeds.mt5_market_data_feed()
    trades = feeds.mt5_trade_feed()
    research_store = feeds.durable_storage_feed()

    reliability = None
    if account.available and isinstance(account.payload, dict):
        mt5_h = account.payload.get("mt5_health") or {}
        reliability = {
            "mt5_synchronization_ok": bool(
                mt5_h.get("connected") or mt5_h.get("ok") or mt5_h.get("healthy")
            )
            if mt5_h
            else None,
            "source": "broker_account_feed",
        }
        # Drop Nones — never invent uptime numbers
        reliability = {k: v for k, v in reliability.items() if v is not None}

    data = None
    if market.available:
        # Do not invent integrity PASS — only report that a tick was observed.
        data = {
            "source": "mt5_market_data_feed",
            "market_tick_observed": True,
        }

    research = {
        "ivp_evidence_ok": None,
        "llp_evidence_ok": None,
        "source": "durable_storage",
        "store": research_store.payload if research_store.available else MISSING,
    }

    body: dict[str, Any] = {
        "reliability": reliability,
        "data": data,
        "research": research,
        "feed_status": {
            "broker_account_feed": account.health.to_dict(),
            "mt5_market_data_feed": market.health.to_dict(),
            "mt5_trade_feed": trades.health.to_dict(),
        },
    }
    for k, v in overrides.items():
        if v is not None:
            body[k] = v
    return body
