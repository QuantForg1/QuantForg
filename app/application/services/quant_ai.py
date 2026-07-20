"""Quant AI application service — advisory analysis only (never order_send)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from app.application.services.mt5_market_data import MT5MarketDataService
from app.application.services.news_intelligence import NewsIntelligenceService
from app.application.services.portfolio_sync import PortfolioSyncService
from app.application.use_cases.mt5 import GetMT5StatusUseCase, ListMT5SymbolsUseCase
from app.domain.market_context.engine import MarketContextEngine
from app.domain.market_data.timeframe import Timeframe
from app.domain.quant_ai.correlation import correlation_from_closes
from app.domain.quant_ai.execution_ai import analyze_execution_ai
from app.domain.quant_ai.market_structure import analyze_symbol_structure
from app.domain.quant_ai.portfolio_ai import analyze_portfolio_ai, review_trade
from app.domain.quant_ai.risk_ai import analyze_risk_ai
from app.infrastructure.intelligence.runtime import TtlCache
from core.config.settings import get_settings

_QUOTE_SAMPLE = ("XAUUSD",)

_DASHBOARD_CACHE = TtlCache(ttl_seconds=15.0, max_items=64)
_CACHE_STATS = {"hits": 0, "misses": 0}


def quant_ai_cache_stats() -> dict[str, Any]:
    looked = _CACHE_STATS["hits"] + _CACHE_STATS["misses"]
    ratio = _CACHE_STATS["hits"] / looked if looked else None
    return {
        "hits": _CACHE_STATS["hits"],
        "misses": _CACHE_STATS["misses"],
        "hit_ratio": round(ratio, 4) if ratio is not None else None,
        "ttl_seconds": _DASHBOARD_CACHE.ttl_seconds,
    }


def _rate_to_candle(rate: Any) -> dict[str, Any]:
    open_time = getattr(rate, "open_time", None) or getattr(rate, "time", None)
    return {
        "open": float(rate.open),
        "high": float(rate.high),
        "low": float(rate.low),
        "close": float(rate.close),
        "volume": float(getattr(rate, "tick_volume", 0) or 0),
        "time": open_time.isoformat() if open_time is not None else None,
        "_sort": open_time.timestamp() if open_time is not None else 0.0,
    }


def _dec(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True, slots=True)
class QuantAIService:
    """Compose real MT5 / portfolio / execution facts into Quant AI views."""

    status: GetMT5StatusUseCase
    symbols: ListMT5SymbolsUseCase
    portfolio_sync: PortfolioSyncService
    market_data: MT5MarketDataService
    market_context: MarketContextEngine
    news: NewsIntelligenceService
    load_attempts: Any  # async callable(user_id, limit) -> list[dict]
    load_paper_trades: Any  # async callable(user_id) -> list[dict]

    async def dashboard(
        self,
        *,
        user_id: UUID,
        symbol: str | None = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        cache_key = f"qa:{user_id}:{symbol or ''}"
        if not force_refresh:
            cached = _DASHBOARD_CACHE.get(cache_key)
            if cached is not None:
                _CACHE_STATS["hits"] += 1
                return cast("dict[str, Any]", cached)
        _CACHE_STATS["misses"] += 1

        focus = (symbol or "XAUUSD").strip().upper()
        from app.domain.trading.gold_only import resolve_trading_symbol

        focus = resolve_trading_symbol(focus)
        status = await self.status.execute(user_id=user_id)
        broker = {
            "connected": status.connected,
            "status": status.status,
            "latency_ms": status.latency_ms,
            "server": status.server,
            "last_error": status.last_error,
        }

        account: dict[str, Any] = {}
        positions: list[dict[str, Any]] = []
        deals: list[dict[str, Any]] = []
        quotes: list[dict[str, Any]] = []

        if status.connected:
            try:
                snap = self.portfolio_sync.account_snapshot()
                account = {
                    "balance": _dec(snap.balance),
                    "equity": _dec(snap.equity),
                    "margin": _dec(snap.margin),
                    "free_margin": _dec(snap.free_margin),
                    "leverage": snap.leverage,
                    "currency": snap.currency,
                    "profit": _dec(snap.profit),
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
                        "current_price": _dec(getattr(p, "current_price", 0)),
                    }
                    for p in self.portfolio_sync.list_positions()
                ]
            except Exception:
                positions = []

            try:
                for d in self.portfolio_sync.history_deals()[:300]:
                    deals.append(
                        {
                            "ticket": d.ticket,
                            "symbol": d.symbol,
                            "side": getattr(d, "side", None),
                            "volume": _dec(d.volume),
                            "price": _dec(d.price),
                            "profit": _dec(d.profit),
                            "pnl": _dec(d.profit),
                            "time": (
                                d.time.isoformat() if getattr(d, "time", None) else None
                            ),
                            "closed_at": (
                                d.time.isoformat() if getattr(d, "time", None) else None
                            ),
                        }
                    )
            except Exception:
                deals = []

            try:
                page = await self.symbols.execute(
                    user_id=user_id,
                    codes=list(_QUOTE_SAMPLE),
                    include_quotes=True,
                    limit=len(_QUOTE_SAMPLE),
                    offset=0,
                )
                for s in page.items:
                    bid = _dec(getattr(s, "bid", None))
                    ask = _dec(getattr(s, "ask", None))
                    if bid is None or ask is None:
                        continue
                    quotes.append(
                        {
                            "symbol": s.code,
                            "bid": bid,
                            "ask": ask,
                            "spread": round(ask - bid, 6),
                        }
                    )
            except Exception:
                quotes = []

        ctx = self.market_context.build("FX", symbol_code=focus)
        session = ctx.session.value
        market_context = {
            "session": session,
            "market_state": ctx.market_state.value,
            "liquidity_level": ctx.liquidity_level.value,
            "volatility_level": ctx.volatility_level.value,
            "as_of_utc": ctx.as_of_utc.isoformat(),
        }

        structures: list[dict[str, Any]] = []
        close_map: dict[str, list[float]] = {}
        if status.connected:
            for code in _QUOTE_SAMPLE:
                analysis = self._analyze_symbol_live(code, session=session)
                if analysis.get("status") == "available":
                    structures.append(analysis)
                    analysis.get("price")
                    # Keep closes from candles for correlation later
                    candles = self._load_candles(code, Timeframe.H1, 80)
                    if candles:
                        close_map[code] = [float(c["close"]) for c in candles]
                elif code == focus:
                    structures.append(analysis)

        focus_analysis = next(
            (s for s in structures if s.get("symbol") == focus),
            (
                self._analyze_symbol_live(focus, session=session)
                if status.connected
                else {
                    "status": "unavailable",
                    "symbol": focus,
                    "reason": "MT5 session not connected",
                    "autonomous_trading": False,
                }
            ),
        )

        mtf = (
            self._multi_timeframe(focus, session=session)
            if status.connected
            else {
                "status": "unavailable",
                "reason": "MT5 session not connected",
            }
        )

        correlation = correlation_from_closes(close_map)

        paper = await self.load_paper_trades(user_id)
        trade_rows = deals if deals else paper
        portfolio = analyze_portfolio_ai(trade_rows)
        risk = analyze_risk_ai(account=account, positions=positions)

        attempts = await self.load_attempts(user_id, 100)
        fills = [
            t for t in paper if t.get("slippage") is not None or t.get("fill_price")
        ]
        execution = analyze_execution_ai(
            attempts=attempts,
            fills=fills,
            broker_latency_ms=_dec(status.latency_ms),
        )

        trade_reviews = [review_trade(t) for t in trade_rows[:25]]

        widgets = self._market_widgets(structures, quotes)

        news_items = [
            {
                "id": n.id,
                "title": n.title,
                "summary": n.summary,
                "source": n.source,
                "published_at": n.published_at,
                "symbols": list(n.symbols),
            }
            for n in self.news.news(limit=12)
        ]
        economic_events = [
            {
                "id": e.id,
                "title": e.title,
                "country": e.country,
                "impact": e.impact,
                "scheduled_at": e.scheduled_at,
                "source": e.source,
            }
            for e in self.news.economic_events(limit=12)
        ]

        settings = get_settings()
        payload = {
            "status": "available" if status.connected else "degraded",
            "module": "quant_ai",
            "version": "2.0",
            "advisory_only": True,
            "autonomous_trading": False,
            "never_submits_orders": True,
            "never_bypasses_execution_enabled": True,
            "execution_enabled": bool(getattr(settings, "execution_enabled", False)),
            "broker": broker,
            "market_context": market_context,
            "session_analysis": {
                "status": "available",
                "session": session,
                "liquidity": ctx.liquidity_level.value,
                "volatility": ctx.volatility_level.value,
                "why": {
                    "summary": f"Active session: {session}",
                    "supporting_factors": [
                        f"Market state {ctx.market_state.value}",
                        f"Liquidity {ctx.liquidity_level.value}",
                        f"Volatility profile {ctx.volatility_level.value}",
                    ],
                },
            },
            "assistant": focus_analysis,
            "multi_timeframe": mtf,
            "modules": {
                "market_overview": widgets,
                "trend_analysis": [
                    {
                        "symbol": s.get("symbol"),
                        "trend": s.get("trend"),
                        "confidence_pct": s.get("confidence_pct"),
                        "reasons": s.get("reasons"),
                    }
                    for s in structures
                ],
                "momentum_analysis": [
                    {"symbol": s.get("symbol"), "momentum": s.get("momentum")}
                    for s in structures
                ],
                "volatility_analysis": [
                    {"symbol": s.get("symbol"), "volatility": s.get("volatility")}
                    for s in structures
                ],
                "support_resistance": [
                    {
                        "symbol": s.get("symbol"),
                        "support": s.get("support"),
                        "resistance": s.get("resistance"),
                    }
                    for s in structures
                ],
                "liquidity_zones": [
                    {"symbol": s.get("symbol"), "zones": s.get("liquidity_zones")}
                    for s in structures
                ],
                "market_regime": [
                    {"symbol": s.get("symbol"), "regime": s.get("market_regime")}
                    for s in structures
                ],
                "correlation": correlation,
                "execution_quality": execution,
                "portfolio_health": portfolio,
                "risk_health": risk,
                "trade_journal_intelligence": {
                    "status": portfolio.get("status"),
                    "mistakes": portfolio.get("most_common_mistakes"),
                    "reviews": trade_reviews,
                },
            },
            "widgets": widgets,
            "news": news_items,
            "economic_events": economic_events,
            "cache": quant_ai_cache_stats(),
            "data_policy": {
                "mock": False,
                "placeholder": False,
                "sources": [
                    "mt5",
                    "broker",
                    "execution_attempts",
                    "portfolio",
                    "market_data",
                    "risk_facts",
                    "history",
                ],
            },
        }
        _DASHBOARD_CACHE.set(cache_key, payload)
        return payload

    async def symbol_brief(self, *, user_id: UUID, symbol: str) -> dict[str, Any]:
        status = await self.status.execute(user_id=user_id)
        code = symbol.strip().upper()
        if not status.connected:
            return {
                "status": "unavailable",
                "symbol": code,
                "reason": "MT5 session not connected",
                "autonomous_trading": False,
            }
        ctx = self.market_context.build("FX", symbol_code=code)
        analysis = self._analyze_symbol_live(code, session=ctx.session.value)
        analysis["multi_timeframe"] = self._multi_timeframe(
            code, session=ctx.session.value
        )
        analysis["session_analysis"] = {
            "session": ctx.session.value,
            "liquidity": ctx.liquidity_level.value,
            "volatility": ctx.volatility_level.value,
        }
        return analysis

    async def portfolio_brief(self, *, user_id: UUID) -> dict[str, Any]:
        status = await self.status.execute(user_id=user_id)
        deals: list[dict[str, Any]] = []
        if status.connected:
            try:
                for d in self.portfolio_sync.history_deals()[:500]:
                    deals.append(
                        {
                            "symbol": d.symbol,
                            "profit": _dec(d.profit),
                            "pnl": _dec(d.profit),
                            "time": (
                                d.time.isoformat() if getattr(d, "time", None) else None
                            ),
                            "closed_at": (
                                d.time.isoformat() if getattr(d, "time", None) else None
                            ),
                        }
                    )
            except Exception:
                deals = []
        paper = await self.load_paper_trades(user_id)
        return analyze_portfolio_ai(deals if deals else paper)

    async def risk_brief(self, *, user_id: UUID) -> dict[str, Any]:
        status = await self.status.execute(user_id=user_id)
        account: dict[str, Any] = {}
        positions: list[dict[str, Any]] = []
        if status.connected:
            try:
                snap = self.portfolio_sync.account_snapshot()
                account = {
                    "balance": _dec(snap.balance),
                    "equity": _dec(snap.equity),
                    "margin": _dec(snap.margin),
                    "free_margin": _dec(snap.free_margin),
                    "leverage": snap.leverage,
                }
            except Exception:
                account = {}
            try:
                positions = [
                    {
                        "symbol": p.symbol,
                        "volume": _dec(p.volume),
                        "profit": _dec(getattr(p, "profit", 0)),
                    }
                    for p in self.portfolio_sync.list_positions()
                ]
            except Exception:
                positions = []
        return analyze_risk_ai(account=account, positions=positions)

    async def execution_brief(self, *, user_id: UUID) -> dict[str, Any]:
        status = await self.status.execute(user_id=user_id)
        attempts = await self.load_attempts(user_id, 100)
        paper = await self.load_paper_trades(user_id)
        fills = [
            t for t in paper if t.get("slippage") is not None or t.get("fill_price")
        ]
        return analyze_execution_ai(
            attempts=attempts,
            fills=fills,
            broker_latency_ms=_dec(status.latency_ms),
        )

    async def trade_review(
        self, *, user_id: UUID, trade: dict[str, Any]
    ) -> dict[str, Any]:
        _ = user_id
        return review_trade(trade)

    def _load_candles(
        self, symbol: str, timeframe: Timeframe, count: int
    ) -> list[dict[str, Any]]:
        try:
            rates = self.market_data.historical_candles(
                symbol, timeframe, count=count, start_pos=0
            )
            candles = [_rate_to_candle(r) for r in rates]
            candles.sort(key=lambda c: float(c.get("_sort") or 0.0))
            for c in candles:
                c.pop("_sort", None)
            return candles
        except Exception:
            return []

    def _analyze_symbol_live(
        self, symbol: str, *, session: str | None
    ) -> dict[str, Any]:
        candles = self._load_candles(symbol, Timeframe.H1, 220)
        bid = ask = None
        try:
            tick = self.market_data.latest_tick(symbol)
            bid = float(tick.bid)
            ask = float(tick.ask)
        except Exception:  # noqa: S110 - missing ticks are represented as unavailable
            pass
        return analyze_symbol_structure(
            symbol=symbol,
            candles=candles,
            bid=bid,
            ask=ask,
            session=session,
        )

    def _multi_timeframe(self, symbol: str, *, session: str | None) -> dict[str, Any]:
        frames = (Timeframe.M15, Timeframe.H1, Timeframe.H4, Timeframe.D1)
        by_tf: dict[str, Any] = {}
        for tf in frames:
            candles = self._load_candles(symbol, tf, 120)
            by_tf[tf.value] = analyze_symbol_structure(
                symbol=symbol,
                candles=candles,
                session=session,
            )
        available = [tf for tf, a in by_tf.items() if a.get("status") == "available"]
        if not available:
            return {
                "status": "unavailable",
                "symbol": symbol,
                "reason": "Insufficient multi-timeframe OHLC",
                "frames": by_tf,
            }
        trends = [by_tf[tf].get("trend") for tf in available]
        aligned = len(set(trends)) == 1
        return {
            "status": "available",
            "symbol": symbol,
            "aligned": aligned,
            "frames": {
                tf: {
                    "trend": by_tf[tf].get("trend"),
                    "momentum": by_tf[tf].get("momentum"),
                    "confidence_pct": by_tf[tf].get("confidence_pct"),
                    "regime": by_tf[tf].get("market_regime"),
                    "reasons": by_tf[tf].get("reasons"),
                }
                for tf in available
            },
            "why": {
                "summary": (
                    "MTF trends aligned"
                    if aligned
                    else "MTF trends diverge — caution on conviction"
                ),
                "supporting_factors": [
                    f"{tf}: {by_tf[tf].get('trend')}" for tf in available
                ],
            },
            "autonomous_trading": False,
            "advisory_only": True,
        }

    def _market_widgets(
        self,
        structures: list[dict[str, Any]],
        quotes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        movers: list[dict[str, Any]] = []
        for s in structures:
            atr = s.get("atr")
            price = s.get("price")
            if atr and price:
                movers.append(
                    {
                        "symbol": s.get("symbol"),
                        "move_pct": round(float(atr) / float(price) * 100, 4),
                        "trend": s.get("trend"),
                        "volatility": s.get("volatility"),
                    }
                )
        movers.sort(key=lambda x: float(x.get("move_pct") or 0), reverse=True)

        high_vol = [s for s in structures if s.get("volatility") == "High"]
        strong = [
            s
            for s in structures
            if s.get("trend") in {"Bullish", "Bearish"}
            and float(s.get("confidence_pct") or 0) >= 70
        ]
        weak = [
            s
            for s in structures
            if s.get("trend") == "Neutral" or float(s.get("confidence_pct") or 0) < 55
        ]
        spread_monitor = sorted(
            quotes, key=lambda q: float(q.get("spread") or 0), reverse=True
        )[:10]
        heatmap = [
            {
                "symbol": s.get("symbol"),
                "trend": s.get("trend"),
                "confidence_pct": s.get("confidence_pct"),
                "regime": s.get("market_regime"),
            }
            for s in structures
        ]
        return {
            "top_movers": movers[:8],
            "high_volatility": [
                {"symbol": s.get("symbol"), "volatility": s.get("volatility")}
                for s in high_vol
            ],
            "strong_trends": [
                {
                    "symbol": s.get("symbol"),
                    "trend": s.get("trend"),
                    "confidence_pct": s.get("confidence_pct"),
                }
                for s in strong
            ],
            "weak_trends": [
                {
                    "symbol": s.get("symbol"),
                    "trend": s.get("trend"),
                    "confidence_pct": s.get("confidence_pct"),
                }
                for s in weak
            ],
            "liquidity": {
                "note": "Session liquidity from market context; zones from OHLC swings",
                "symbols": [
                    {"symbol": s.get("symbol"), "zones": s.get("liquidity_zones")}
                    for s in structures[:6]
                ],
            },
            "spread_monitor": spread_monitor,
            "heatmap": heatmap,
            "status": "available" if structures or quotes else "unavailable",
        }
