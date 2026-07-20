"""Market Intelligence orchestration — MT5 sync + context + news + advisor."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from app.application.services.ai_market_advisor import AiMarketAdvisor
from app.application.services.news_intelligence import NewsIntelligenceService
from app.application.services.portfolio_sync import PortfolioSyncService
from app.application.use_cases.mt5 import GetMT5StatusUseCase, ListMT5SymbolsUseCase
from app.domain.market_context.engine import MarketContextEngine
from app.infrastructure.intelligence.runtime import TtlCache

# Prefer gold when sampling quotes — never fan-out the full catalogue.
_QUOTE_SAMPLE = (
    "XAUUSD",
)

# Short TTL so concurrent dashboard/analysis/events share one broker snap.
_DASHBOARD_CACHE = TtlCache(ttl_seconds=12.0, max_items=128)
_DASHBOARD_CACHE_STATS = {"hits": 0, "misses": 0}


def _dec(value: Any) -> str:
    if value is None:
        return "0"
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def dashboard_cache_stats() -> dict[str, Any]:
    looked = _DASHBOARD_CACHE_STATS["hits"] + _DASHBOARD_CACHE_STATS["misses"]
    ratio = _DASHBOARD_CACHE_STATS["hits"] / looked if looked else None
    return {
        "hits": _DASHBOARD_CACHE_STATS["hits"],
        "misses": _DASHBOARD_CACHE_STATS["misses"],
        "hit_ratio": round(ratio, 4) if ratio is not None else None,
        "ttl_seconds": _DASHBOARD_CACHE.ttl_seconds,
    }


@dataclass(frozen=True, slots=True)
class MarketIntelligenceService:
    status: GetMT5StatusUseCase
    symbols: ListMT5SymbolsUseCase
    portfolio_sync: PortfolioSyncService
    market_context: MarketContextEngine
    news: NewsIntelligenceService
    advisor: AiMarketAdvisor

    async def dashboard(
        self,
        *,
        user_id: UUID,
        market_code: str = "FX",
        symbol: str | None = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        cache_key = f"{user_id}:{market_code}:{symbol or ''}"
        if not force_refresh:
            cached = _DASHBOARD_CACHE.get(cache_key)
            if cached is not None:
                _DASHBOARD_CACHE_STATS["hits"] += 1
                return cast("dict[str, Any]", cached)
        _DASHBOARD_CACHE_STATS["misses"] += 1

        status = await self.status.execute(user_id=user_id)
        broker = {
            "connected": status.connected,
            "status": status.status,
            "latency_ms": status.latency_ms,
            "server": status.server,
            "login": status.login,
            "login_status": status.login_status,
            "last_error": status.last_error,
        }

        account: dict[str, Any] = {}
        positions: list[dict[str, Any]] = []
        pending: list[dict[str, Any]] = []
        history_deals = 0
        history_orders = 0
        spread_movers: list[dict[str, Any]] = []
        quotes: list[dict[str, Any]] = []

        if status.connected:
            try:
                snap = self.portfolio_sync.account_snapshot()
                account = {
                    "login": snap.login,
                    "balance": _dec(snap.balance),
                    "equity": _dec(snap.equity),
                    "margin": _dec(snap.margin),
                    "free_margin": _dec(snap.free_margin),
                    "margin_level": _dec(snap.margin_level),
                    "profit": _dec(snap.profit),
                    "leverage": snap.leverage,
                    "currency": snap.currency,
                    "server": snap.server,
                }
            except Exception:
                account = {}

            try:
                positions = [
                    {
                        "ticket": p.ticket,
                        "symbol": p.symbol,
                        "side": getattr(p, "side", None) or str(getattr(p, "type", "")),
                        "volume": _dec(p.volume),
                        "profit": _dec(getattr(p, "profit", 0)),
                        "open_price": _dec(getattr(p, "open_price", 0)),
                    }
                    for p in self.portfolio_sync.list_positions()
                ]
                pending = [
                    {
                        "ticket": o.ticket,
                        "symbol": o.symbol,
                        "order_type": str(getattr(o, "order_type", "")),
                        "volume": _dec(o.volume),
                        "price": _dec(o.price),
                    }
                    for o in self.portfolio_sync.list_orders()
                ]
                history_deals = len(self.portfolio_sync.history_deals())
                history_orders = len(self.portfolio_sync.history_orders())
            except Exception:  # noqa: S110 - portfolio data is optional
                pass

            try:
                sample_codes = list(_QUOTE_SAMPLE)
                if symbol:
                    sample_codes = [symbol.strip().upper(), *sample_codes]
                page = await self.symbols.execute(
                    user_id=user_id,
                    codes=sample_codes,
                    include_quotes=True,
                    limit=len(sample_codes),
                    offset=0,
                )
                scored: list[tuple[float, dict[str, Any]]] = []
                for s in page.items:
                    bid = getattr(s, "bid", None)
                    ask = getattr(s, "ask", None)
                    if bid is None or ask is None:
                        continue
                    try:
                        spread = float(Decimal(str(ask)) - Decimal(str(bid)))
                    except Exception:  # noqa: S112 - skip an invalid quote
                        continue
                    if spread <= 0:
                        continue
                    row = {
                        "symbol": s.code,
                        "bid": str(bid),
                        "ask": str(ask),
                        "spread": f"{spread:.5f}",
                    }
                    quotes.append(row)
                    scored.append((spread, row))
                scored.sort(key=lambda x: x[0], reverse=True)
                spread_movers = [r for _, r in scored[:8]]
            except Exception:
                quotes = []
                spread_movers = []

        ctx = self.market_context.build(
            market_code,
            symbol_code=symbol,
        )
        market_context = {
            "market_code": ctx.market_code,
            "session": ctx.session.value,
            "market_state": ctx.market_state.value,
            "day_type": ctx.day_type.value,
            "liquidity_level": ctx.liquidity_level.value,
            "volatility_level": ctx.volatility_level.value,
            "timezone": ctx.timezone,
            "as_of_utc": ctx.as_of_utc.isoformat(),
            "local_time": ctx.local_time.isoformat(),
        }

        news_items = [
            {
                "id": n.id,
                "title": n.title,
                "summary": n.summary,
                "source": n.source,
                "url": n.url,
                "published_at": n.published_at,
                "symbols": list(n.symbols),
            }
            for n in self.news.news(limit=15)
        ]
        economic_events = [
            {
                "id": e.id,
                "title": e.title,
                "country": e.country,
                "impact": e.impact,
                "scheduled_at": e.scheduled_at,
                "actual": e.actual,
                "forecast": e.forecast,
                "previous": e.previous,
                "source": e.source,
            }
            for e in self.news.economic_events(limit=15)
        ]

        snapshot = {
            "broker": broker,
            "account": account,
            "positions": positions,
            "pending_orders": pending,
            "history": {
                "deals_count": history_deals,
                "orders_count": history_orders,
            },
            "market_context": market_context,
            "market": {
                "quotes_sampled": len(quotes),
                "quotes": quotes[:24],
                "spread_movers": spread_movers,
            },
            "news": news_items,
            "economic_events": economic_events,
            "providers": self.news.provider_status(),
        }
        snapshot["analysis"] = self.advisor.summarize(snapshot)
        _DASHBOARD_CACHE.set(cache_key, snapshot)
        return snapshot

    def market_context_only(
        self,
        *,
        market_code: str = "FX",
        symbol: str | None = None,
    ) -> dict[str, Any]:
        ctx = self.market_context.build(market_code, symbol_code=symbol)
        return {
            "market_code": ctx.market_code,
            "session": ctx.session.value,
            "market_state": ctx.market_state.value,
            "day_type": ctx.day_type.value,
            "liquidity_level": ctx.liquidity_level.value,
            "volatility_level": ctx.volatility_level.value,
            "timezone": ctx.timezone,
            "as_of_utc": ctx.as_of_utc.isoformat(),
            "local_time": ctx.local_time.isoformat(),
            "symbol": symbol,
        }
