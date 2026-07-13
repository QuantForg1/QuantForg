"""Official intelligence provider adapters.

Each adapter calls the vendor's documented HTTP API only when credentials
(or public access) are configured. Unconfigured providers return empty data
and ``UNCONFIGURED`` health — never fabricated payloads.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from app.domain.intelligence.providers import (
    CalendarEvent,
    NewsArticle,
    ProviderHealth,
    ProviderHealthStatus,
    ProviderKind,
    QuoteSnapshot,
    SentimentSnapshot,
)
from app.infrastructure.brokers.mt5.adapter import MT5Adapter
from app.infrastructure.intelligence.runtime import ProviderRuntime


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def _status(configured: bool, runtime: ProviderRuntime) -> ProviderHealthStatus:
    if not configured:
        return ProviderHealthStatus.UNCONFIGURED
    if runtime.metrics.failures > 0 and runtime.metrics.requests > 0:
        ratio = runtime.metrics.failures / max(1, runtime.metrics.requests)
        if ratio >= 0.5:
            return ProviderHealthStatus.UNHEALTHY
        if ratio >= 0.2:
            return ProviderHealthStatus.DEGRADED
    if runtime.metrics.rate_limited and not runtime.metrics.last_success_at:
        return ProviderHealthStatus.DEGRADED
    return ProviderHealthStatus.HEALTHY


@dataclass
class Mt5MarketDataProvider:
    adapter: MT5Adapter
    priority: int = 10
    name: str = "mt5"
    runtime: ProviderRuntime = field(default_factory=ProviderRuntime)

    def configured(self) -> bool:
        try:
            live = getattr(self.adapter, "_live_session_ref", None)
            client = getattr(self.adapter, "client", None)
            return bool(live) and bool(getattr(client, "is_connected", False))
        except Exception:  # noqa: BLE001
            return False

    def health(self) -> ProviderHealth:
        return self.runtime.metrics.to_health(
            name=self.name,
            kind=ProviderKind.MARKET_DATA,
            configured=self.configured(),
            priority=self.priority,
            status=_status(self.configured(), self.runtime),
        )

    def get_quote(self, symbol: str) -> QuoteSnapshot | None:
        if not self.configured():
            return None

        def _load() -> QuoteSnapshot | None:
            tick = self.adapter.latest_tick(symbol)
            return QuoteSnapshot(
                symbol=tick.symbol,
                bid=str(tick.bid),
                ask=str(tick.ask),
                mid=str(tick.mid),
                provider=self.name,
                as_of=tick.timestamp.isoformat()
                if getattr(tick, "timestamp", None)
                else _iso_now(),
            )

        return self.runtime.cached(
            f"mt5:quote:{symbol.upper()}",
            lambda: self.runtime.guarded(_load),
        )

    def list_quotes(self, symbols: list[str] | None = None) -> list[QuoteSnapshot]:
        if not self.configured():
            return []
        codes = symbols or [s.code for s in self.adapter.list_symbols()[:40]]
        out: list[QuoteSnapshot] = []
        for code in codes:
            q = self.get_quote(code)
            if q:
                out.append(q)
        return out


@dataclass
class BinanceMarketDataProvider:
    """Binance public market data (official REST). No invented quotes."""

    priority: int = 40
    name: str = "binance"
    runtime: ProviderRuntime = field(
        default_factory=lambda: ProviderRuntime(timeout_seconds=6.0)
    )
    enabled: bool = True

    def configured(self) -> bool:
        return self.enabled

    def health(self) -> ProviderHealth:
        return self.runtime.metrics.to_health(
            name=self.name,
            kind=ProviderKind.MARKET_DATA,
            configured=self.configured(),
            priority=self.priority,
            status=_status(self.configured(), self.runtime),
        )

    def get_quote(self, symbol: str) -> QuoteSnapshot | None:
        if not self.configured():
            return None
        sym = symbol.replace("/", "").upper()

        def _load() -> QuoteSnapshot | None:
            data = self.runtime.get_json(
                "https://api.binance.com/api/v3/ticker/bookTicker",
                params={"symbol": sym},
            )
            if not isinstance(data, dict):
                return None
            bid = str(data.get("bidPrice") or "")
            ask = str(data.get("askPrice") or "")
            if not bid or not ask:
                return None
            return QuoteSnapshot(
                symbol=sym,
                bid=bid,
                ask=ask,
                provider=self.name,
                as_of=_iso_now(),
            )

        return self.runtime.cached(f"binance:quote:{sym}", _load)

    def list_quotes(self, symbols: list[str] | None = None) -> list[QuoteSnapshot]:
        if not self.configured():
            return []
        targets = symbols or ["BTCUSDT", "ETHUSDT"]
        return [q for s in targets if (q := self.get_quote(s))]


@dataclass
class TwelveDataMarketProvider:
    api_key: str
    priority: int = 30
    name: str = "twelvedata"
    runtime: ProviderRuntime = field(default_factory=ProviderRuntime)

    def configured(self) -> bool:
        return bool(self.api_key.strip())

    def health(self) -> ProviderHealth:
        return self.runtime.metrics.to_health(
            name=self.name,
            kind=ProviderKind.MARKET_DATA,
            configured=self.configured(),
            priority=self.priority,
            status=_status(self.configured(), self.runtime),
        )

    def get_quote(self, symbol: str) -> QuoteSnapshot | None:
        if not self.configured():
            return None
        sym = symbol.strip().upper()

        def _load() -> QuoteSnapshot | None:
            data = self.runtime.get_json(
                "https://api.twelvedata.com/quote",
                params={"symbol": sym, "apikey": self.api_key},
            )
            if not isinstance(data, dict) or data.get("status") == "error":
                return None
            bid = str(data.get("bid") or data.get("close") or "")
            ask = str(data.get("ask") or data.get("close") or "")
            if not bid:
                return None
            return QuoteSnapshot(
                symbol=sym,
                bid=bid,
                ask=ask or bid,
                provider=self.name,
                as_of=str(data.get("datetime") or _iso_now()),
            )

        return self.runtime.cached(f"twelvedata:quote:{sym}", _load)

    def list_quotes(self, symbols: list[str] | None = None) -> list[QuoteSnapshot]:
        if not self.configured():
            return []
        return [q for s in (symbols or []) if (q := self.get_quote(s))]


@dataclass
class AlphaVantageMarketProvider:
    api_key: str
    priority: int = 50
    name: str = "alphavantage"
    runtime: ProviderRuntime = field(
        default_factory=lambda: ProviderRuntime(
            timeout_seconds=10.0,
        )
    )

    def __post_init__(self) -> None:
        self.runtime.limiter.rate_per_minute = 5.0

    def configured(self) -> bool:
        return bool(self.api_key.strip())

    def health(self) -> ProviderHealth:
        return self.runtime.metrics.to_health(
            name=self.name,
            kind=ProviderKind.MARKET_DATA,
            configured=self.configured(),
            priority=self.priority,
            status=_status(self.configured(), self.runtime),
        )

    def get_quote(self, symbol: str) -> QuoteSnapshot | None:
        if not self.configured():
            return None
        sym = symbol.strip().upper()

        def _load() -> QuoteSnapshot | None:
            data = self.runtime.get_json(
                "https://www.alphavantage.co/query",
                params={
                    "function": "GLOBAL_QUOTE",
                    "symbol": sym,
                    "apikey": self.api_key,
                },
            )
            if not isinstance(data, dict):
                return None
            q = data.get("Global Quote") or {}
            if not isinstance(q, dict):
                return None
            price = str(q.get("05. price") or "")
            if not price:
                return None
            return QuoteSnapshot(
                symbol=sym,
                bid=price,
                ask=price,
                provider=self.name,
                as_of=str(q.get("07. latest trading day") or _iso_now()),
            )

        return self.runtime.cached(f"av:quote:{sym}", _load)

    def list_quotes(self, symbols: list[str] | None = None) -> list[QuoteSnapshot]:
        if not self.configured():
            return []
        return [q for s in (symbols or [])[:3] if (q := self.get_quote(s))]


@dataclass
class PolygonMarketProvider:
    api_key: str
    priority: int = 35
    name: str = "polygon"
    runtime: ProviderRuntime = field(default_factory=ProviderRuntime)

    def configured(self) -> bool:
        return bool(self.api_key.strip())

    def health(self) -> ProviderHealth:
        return self.runtime.metrics.to_health(
            name=self.name,
            kind=ProviderKind.MARKET_DATA,
            configured=self.configured(),
            priority=self.priority,
            status=_status(self.configured(), self.runtime),
        )

    def get_quote(self, symbol: str) -> QuoteSnapshot | None:
        if not self.configured():
            return None
        sym = symbol.strip().upper()

        def _load() -> QuoteSnapshot | None:
            data = self.runtime.get_json(
                f"https://api.polygon.io/v2/last/nbbo/{sym}",
                params={"apiKey": self.api_key},
            )
            if not isinstance(data, dict):
                return None
            results = data.get("results") or data.get("last") or {}
            if not isinstance(results, dict):
                return None
            bid = str(results.get("bid") or results.get("B") or results.get("p") or "")
            ask = str(results.get("ask") or results.get("A") or results.get("P") or "")
            if not bid and not ask:
                return None
            return QuoteSnapshot(
                symbol=sym,
                bid=bid or ask,
                ask=ask or bid,
                provider=self.name,
                as_of=_iso_now(),
            )

        return self.runtime.cached(f"polygon:quote:{sym}", _load)

    def list_quotes(self, symbols: list[str] | None = None) -> list[QuoteSnapshot]:
        if not self.configured():
            return []
        return [q for s in (symbols or [])[:10] if (q := self.get_quote(s))]


@dataclass
class FinnhubNewsProvider:
    api_key: str
    priority: int = 20
    name: str = "finnhub"
    runtime: ProviderRuntime = field(default_factory=ProviderRuntime)

    def configured(self) -> bool:
        return bool(self.api_key.strip())

    def health(self) -> ProviderHealth:
        return self.runtime.metrics.to_health(
            name=self.name,
            kind=ProviderKind.NEWS,
            configured=self.configured(),
            priority=self.priority,
            status=_status(self.configured(), self.runtime),
        )

    def list_news(self, *, limit: int = 20) -> list[NewsArticle]:
        if not self.configured():
            return []

        def _load() -> list[NewsArticle]:
            data = self.runtime.get_json(
                "https://finnhub.io/api/v1/news",
                params={"category": "general", "token": self.api_key},
            )
            if not isinstance(data, list):
                return []
            items: list[NewsArticle] = []
            for row in data[:limit]:
                if not isinstance(row, dict):
                    continue
                title = str(row.get("headline") or row.get("title") or "").strip()
                if not title:
                    continue
                related = str(row.get("related") or "")
                symbols = tuple(s for s in related.split(",") if s.strip())
                ts = row.get("datetime")
                published = (
                    datetime.fromtimestamp(int(ts), tz=UTC).isoformat()
                    if isinstance(ts, (int, float))
                    else str(ts or "")
                )
                items.append(
                    NewsArticle(
                        id=str(row.get("id") or title)[:120],
                        title=title[:300],
                        summary=str(row.get("summary") or "")[:1000],
                        source=str(row.get("source") or "finnhub")[:120],
                        url=str(row.get("url") or "")[:500],
                        published_at=published[:64],
                        provider=self.name,
                        symbols=symbols,
                    )
                )
            return items

        return self.runtime.cached(f"finnhub:news:{limit}", _load) or []


@dataclass
class FinnhubCalendarProvider:
    api_key: str
    priority: int = 20
    name: str = "finnhub"
    runtime: ProviderRuntime = field(default_factory=ProviderRuntime)

    def configured(self) -> bool:
        return bool(self.api_key.strip())

    def health(self) -> ProviderHealth:
        return self.runtime.metrics.to_health(
            name=self.name,
            kind=ProviderKind.ECONOMIC_CALENDAR,
            configured=self.configured(),
            priority=self.priority,
            status=_status(self.configured(), self.runtime),
        )

    def list_events(
        self,
        *,
        limit: int = 20,
        as_of: datetime | None = None,
    ) -> list[CalendarEvent]:
        if not self.configured():
            return []
        moment = as_of or datetime.now(UTC)
        start = moment.date().isoformat()
        end = (moment + timedelta(days=7)).date().isoformat()

        def _load() -> list[CalendarEvent]:
            data = self.runtime.get_json(
                "https://finnhub.io/api/v1/calendar/economic",
                params={"from": start, "to": end, "token": self.api_key},
            )
            rows: list[Any]
            if isinstance(data, dict):
                rows = list(data.get("economicCalendar") or [])
            elif isinstance(data, list):
                rows = data
            else:
                return []
            events: list[CalendarEvent] = []
            for row in rows[:limit]:
                if not isinstance(row, dict):
                    continue
                title = str(row.get("event") or row.get("title") or "").strip()
                if not title:
                    continue
                events.append(
                    CalendarEvent(
                        id=str(row.get("event") or title)[:120],
                        title=title[:300],
                        country=str(row.get("country") or "")[:64],
                        impact=str(row.get("impact") or "unknown")[:32],
                        scheduled_at=str(row.get("time") or "")[:64],
                        provider=self.name,
                        actual=str(row.get("actual") or "")[:64],
                        forecast=str(row.get("estimate") or row.get("forecast") or "")[
                            :64
                        ],
                        previous=str(row.get("prev") or row.get("previous") or "")[:64],
                        currency=str(row.get("currency") or "")[:8],
                    )
                )
            return events

        return self.runtime.cached(f"finnhub:cal:{start}:{limit}", _load) or []


@dataclass
class FinnhubSentimentProvider:
    api_key: str
    priority: int = 20
    name: str = "finnhub"
    runtime: ProviderRuntime = field(default_factory=ProviderRuntime)

    def configured(self) -> bool:
        return bool(self.api_key.strip())

    def health(self) -> ProviderHealth:
        return self.runtime.metrics.to_health(
            name=self.name,
            kind=ProviderKind.SENTIMENT,
            configured=self.configured(),
            priority=self.priority,
            status=_status(self.configured(), self.runtime),
        )

    def get_sentiment(self, symbol: str) -> SentimentSnapshot | None:
        if not self.configured():
            return None
        sym = symbol.strip().upper()

        def _load() -> SentimentSnapshot | None:
            data = self.runtime.get_json(
                "https://finnhub.io/api/v1/news-sentiment",
                params={"symbol": sym, "token": self.api_key},
            )
            if not isinstance(data, dict):
                return None
            buzz = data.get("sentiment") or {}
            score = None
            if isinstance(buzz, dict):
                raw = buzz.get("bullishPercent")
                try:
                    score = float(raw) if raw is not None else None
                except (TypeError, ValueError):
                    score = None
            label = "unknown"
            if score is not None:
                label = "bullish" if score >= 0.55 else "bearish" if score <= 0.45 else "neutral"
            return SentimentSnapshot(
                symbol=sym,
                score=score,
                label=label,
                provider=self.name,
                as_of=_iso_now(),
                detail="finnhub news-sentiment",
            )

        return self.runtime.cached(f"finnhub:sent:{sym}", _load)


@dataclass
class TradingEconomicsCalendarProvider:
    api_key: str
    priority: int = 15
    name: str = "tradingeconomics"
    runtime: ProviderRuntime = field(default_factory=ProviderRuntime)

    def configured(self) -> bool:
        return bool(self.api_key.strip())

    def health(self) -> ProviderHealth:
        return self.runtime.metrics.to_health(
            name=self.name,
            kind=ProviderKind.ECONOMIC_CALENDAR,
            configured=self.configured(),
            priority=self.priority,
            status=_status(self.configured(), self.runtime),
        )

    def list_events(
        self,
        *,
        limit: int = 20,
        as_of: datetime | None = None,
    ) -> list[CalendarEvent]:
        if not self.configured():
            return []
        _ = as_of

        def _load() -> list[CalendarEvent]:
            # Official Trading Economics API client key form: key as path segment.
            data = self.runtime.get_json(
                f"https://api.tradingeconomics.com/calendar?c={self.api_key}"
            )
            if not isinstance(data, list):
                return []
            events: list[CalendarEvent] = []
            for row in data[:limit]:
                if not isinstance(row, dict):
                    continue
                title = str(row.get("Event") or row.get("event") or "").strip()
                if not title:
                    continue
                events.append(
                    CalendarEvent(
                        id=str(row.get("CalendarId") or title)[:120],
                        title=title[:300],
                        country=str(row.get("Country") or "")[:64],
                        impact=str(row.get("Importance") or row.get("impact") or "unknown")[
                            :32
                        ],
                        scheduled_at=str(row.get("Date") or row.get("date") or "")[:64],
                        provider=self.name,
                        actual=str(row.get("Actual") or "")[:64],
                        forecast=str(row.get("Forecast") or "")[:64],
                        previous=str(row.get("Previous") or "")[:64],
                        currency=str(row.get("Currency") or "")[:8],
                    )
                )
            return events

        return self.runtime.cached(f"te:cal:{limit}", _load) or []


@dataclass
class PolygonNewsProvider:
    api_key: str
    priority: int = 35
    name: str = "polygon"
    runtime: ProviderRuntime = field(default_factory=ProviderRuntime)

    def configured(self) -> bool:
        return bool(self.api_key.strip())

    def health(self) -> ProviderHealth:
        return self.runtime.metrics.to_health(
            name=self.name,
            kind=ProviderKind.NEWS,
            configured=self.configured(),
            priority=self.priority,
            status=_status(self.configured(), self.runtime),
        )

    def list_news(self, *, limit: int = 20) -> list[NewsArticle]:
        if not self.configured():
            return []

        def _load() -> list[NewsArticle]:
            data = self.runtime.get_json(
                "https://api.polygon.io/v2/reference/news",
                params={"limit": limit, "apiKey": self.api_key},
            )
            if not isinstance(data, dict):
                return []
            rows = data.get("results") or []
            items: list[NewsArticle] = []
            for row in rows[:limit]:
                if not isinstance(row, dict):
                    continue
                title = str(row.get("title") or "").strip()
                if not title:
                    continue
                tickers = row.get("tickers") or []
                symbols = tuple(str(t) for t in tickers if t) if isinstance(tickers, list) else ()
                items.append(
                    NewsArticle(
                        id=str(row.get("id") or title)[:120],
                        title=title[:300],
                        summary=str(row.get("description") or "")[:1000],
                        source=str((row.get("publisher") or {}).get("name") or "polygon")[
                            :120
                        ]
                        if isinstance(row.get("publisher"), dict)
                        else "polygon",
                        url=str(row.get("article_url") or "")[:500],
                        published_at=str(row.get("published_utc") or "")[:64],
                        provider=self.name,
                        symbols=symbols,
                    )
                )
            return items

        return self.runtime.cached(f"polygon:news:{limit}", _load) or []


@dataclass
class AlphaVantageSentimentProvider:
    api_key: str
    priority: int = 50
    name: str = "alphavantage"
    runtime: ProviderRuntime = field(default_factory=ProviderRuntime)

    def __post_init__(self) -> None:
        self.runtime.limiter.rate_per_minute = 5.0

    def configured(self) -> bool:
        return bool(self.api_key.strip())

    def health(self) -> ProviderHealth:
        return self.runtime.metrics.to_health(
            name=self.name,
            kind=ProviderKind.SENTIMENT,
            configured=self.configured(),
            priority=self.priority,
            status=_status(self.configured(), self.runtime),
        )

    def get_sentiment(self, symbol: str) -> SentimentSnapshot | None:
        if not self.configured():
            return None
        sym = symbol.strip().upper()

        def _load() -> SentimentSnapshot | None:
            data = self.runtime.get_json(
                "https://www.alphavantage.co/query",
                params={
                    "function": "NEWS_SENTIMENT",
                    "tickers": sym,
                    "apikey": self.api_key,
                    "limit": 1,
                },
            )
            if not isinstance(data, dict):
                return None
            feed = data.get("feed") or []
            if not isinstance(feed, list) or not feed:
                return None
            first = feed[0] if isinstance(feed[0], dict) else {}
            score = None
            try:
                score = float(first.get("overall_sentiment_score"))
            except (TypeError, ValueError):
                score = None
            label = str(first.get("overall_sentiment_label") or "unknown")
            return SentimentSnapshot(
                symbol=sym,
                score=score,
                label=label,
                provider=self.name,
                as_of=_iso_now(),
                detail="alphavantage NEWS_SENTIMENT",
            )

        return self.runtime.cached(f"av:sent:{sym}", _load)
