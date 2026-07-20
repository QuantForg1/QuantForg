"""Quant AI Decision Engine service — SHOULD WE TRADE OR WAIT?

Never order_send. Never bypasses EXECUTION_ENABLED. Paper mode by default.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from app.application.services.mt5_market_data import MT5MarketDataService
from app.application.services.news_intelligence import NewsIntelligenceService
from app.application.services.portfolio_sync import PortfolioSyncService
from app.application.use_cases.mt5 import GetMT5StatusUseCase
from app.domain.decision_engine.explanation import build_explanation
from app.domain.decision_engine.mtf import REQUIRED_TFS, summarize_mtf
from app.domain.decision_engine.paper_tracker import get_paper_tracker
from app.domain.decision_engine.risk_limits import assess_decision_risk
from app.domain.decision_engine.scoring import compute_trade_score
from app.domain.market_context.engine import MarketContextEngine
from app.domain.market_data.timeframe import Timeframe
from app.domain.quant_ai.market_structure import analyze_symbol_structure
from app.infrastructure.intelligence.runtime import TtlCache
from core.config.settings import get_settings

_CACHE = TtlCache(ttl_seconds=12.0, max_items=64)

_USD_CLUSTER = {"EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF", "USDJPY"}


def _security() -> dict[str, Any]:
    settings = get_settings()
    return {
        "advisory_only": True,
        "autonomous_trading": False,
        "never_submits_orders": True,
        "never_bypasses_execution_enabled": True,
        "default_mode": "paper",
        "live_execution_disabled": True,
        "execution_enabled": bool(getattr(settings, "execution_enabled", False)),
        "promises_profit": False,
    }


def _dec(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True, slots=True)
class DecisionEngineService:
    status: GetMT5StatusUseCase
    market_data: MT5MarketDataService
    portfolio_sync: PortfolioSyncService
    market_context: MarketContextEngine
    news: NewsIntelligenceService

    async def evaluate(
        self,
        *,
        user_id: UUID,
        symbol: str = "XAUUSD",
        mode: str = "paper",
        record_paper: bool = True,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Produce WAIT (default) or TRADE_IDEA — never sends orders."""
        from app.domain.trading.gold_only import resolve_trading_symbol

        code = resolve_trading_symbol(symbol)
        mode = "paper" if mode != "live" else "live"
        cache_key = f"de:{user_id}:{code}:{mode}"
        if not force_refresh:
            cached = _CACHE.get(cache_key)
            if cached is not None:
                return cast("dict[str, Any]", cached)

        st = await self.status.execute(user_id=user_id)
        sec = _security()

        if not st.connected:
            unavailable_payload = {
                "status": "unavailable",
                "symbol": code,
                "decision": "WAIT",
                "reason": "MT5 not connected — cannot evaluate live market structure",
                "trade_score": 0,
                "confidence_pct": 0,
                "mode": mode,
                **sec,
            }
            _CACHE.set(cache_key, unavailable_payload)
            return unavailable_payload

        ctx = self.market_context.build("FX", symbol_code=code)
        session = ctx.session.value
        session_ok = str(ctx.liquidity_level.value).lower() not in {"low", "illiquid"}

        frames: dict[str, dict[str, Any]] = {}
        for tf_name in REQUIRED_TFS:
            candles = self._load_candles(
                code, tf_name, 220 if tf_name in {"H1", "H4", "D1"} else 160
            )
            bid = ask = None
            if tf_name == "H1":
                try:
                    tick = self.market_data.latest_tick(code)
                    bid, ask = float(tick.bid), float(tick.ask)
                except Exception:  # noqa: S110 - optional tick unavailable
                    pass
            frames[tf_name] = analyze_symbol_structure(
                symbol=code,
                candles=candles,
                bid=bid,
                ask=ask,
                session=session,
            )

        primary = frames.get("H1") or next(
            (
                frames[t]
                for t in REQUIRED_TFS
                if frames.get(t, {}).get("status") == "available"
            ),
            {"status": "unavailable"},
        )
        mtf = summarize_mtf(frames)

        news_risk = self._news_risk(code)
        account, positions = self._account_positions()
        correlation_risk = self._correlation_risk(positions)
        portfolio_heat = self._portfolio_heat(account, positions)
        dd_pct = None
        if account:
            bal = _dec(account.get("balance")) or 0
            eq = _dec(account.get("equity")) or 0
            if bal > 0 and eq < bal:
                dd_pct = (bal - eq) / bal * 100.0

        spread = _dec(primary.get("spread"))
        atr = _dec(primary.get("atr"))
        score = compute_trade_score(
            mtf=mtf,
            structure=primary,
            spread_ok=spread is not None and (spread <= atr * 0.15 if atr else True),
            volatility=primary.get("volatility"),
            session_ok=session_ok,
            news_risk=news_risk,
            correlation_risk=correlation_risk,
            portfolio_heat=portfolio_heat,
            execution_quality=None,  # never invent — set only if loaded later
        )

        bias = mtf.get("bias") if mtf.get("aligned") else primary.get("trend")
        risk = assess_decision_risk(
            account=account,
            positions=positions,
            atr=_dec(primary.get("atr")),
            price=_dec(primary.get("price")),
            side=bias,
            max_drawdown_pct=dd_pct,
        )

        decision = score["decision"]
        if decision == "TRADE_IDEA" and not risk.get("accepted", False):
            decision = "WAIT"
            score = {
                **score,
                "decision": "WAIT",
                "bias_to_wait": True,
                "penalties": list(score.get("penalties") or [])
                + list(risk.get("rejects") or []),
            }

        # Live mode still NEVER sends — only annotates that EE gate would apply
        live_gate = {
            "can_forward_to_execution_engine": False,
            "reason": (
                "Live forwarding disabled in Decision Engine — EXECUTION_ENABLED and "
                "safety gates required separately"
            ),
        }
        if mode == "live":
            if not sec["execution_enabled"]:
                live_gate = {
                    "can_forward_to_execution_engine": False,
                    "reason": "EXECUTION_ENABLED=false — live path blocked",
                }
            elif decision != "TRADE_IDEA":
                live_gate = {
                    "can_forward_to_execution_engine": False,
                    "reason": "Decision is WAIT — nothing to forward",
                }
            else:
                live_gate = {
                    "can_forward_to_execution_engine": False,
                    "reason": (
                        "Decision Engine never submits orders. "
                        "A TRADE_IDEA must be manually reviewed; "
                        "OMS/EE remain authoritative."
                    ),
                }

        explanation = build_explanation(
            decision=decision,
            score=score,
            mtf=mtf,
            structure=primary,
            risk=risk,
            news_risk=news_risk,
        )

        payload: dict[str, Any] = {
            "status": "available",
            "symbol": code,
            "mode": mode,
            "decision": decision,
            "trade_score": score["trade_score"],
            "confidence_pct": score["confidence_pct"],
            "risk_level": score["risk_level"],
            "expected_rr": risk.get("expected_rr"),
            "recommended_sl": risk.get("suggested_stop")
            or primary.get("suggested_stop"),
            "recommended_tp": risk.get("suggested_tp") or primary.get("suggested_tp"),
            "lot_size": risk.get("lot_size"),
            "analysis": {
                "trend": primary.get("trend"),
                "market_structure": primary.get("market_regime"),
                "support": primary.get("support"),
                "resistance": primary.get("resistance"),
                "liquidity": primary.get("liquidity_zones"),
                "volatility": primary.get("volatility"),
                "spread": primary.get("spread"),
                "session": session,
                "session_liquidity": ctx.liquidity_level.value,
                "news_risk": news_risk,
                "correlation_risk": correlation_risk,
                "portfolio_exposure": portfolio_heat,
                "execution_quality": None,
            },
            "multi_timeframe": mtf,
            "score_detail": score,
            "risk": risk,
            "explanation": explanation,
            "live_gate": live_gate,
            "broker": {
                "connected": st.connected,
                "latency_ms": st.latency_ms,
                "status": st.status,
            },
            "data_source": "mt5_candles|mt5_ticks|portfolio|calendar",
            **sec,
        }

        if mode == "paper" and record_paper:
            tracker = get_paper_tracker()
            # Simulate a tiny advisory PnL marker only when an idea is accepted;
            # this is still not an order.
            sim_pnl = None
            if decision == "TRADE_IDEA" and risk.get("expected_rr"):
                # Neutral placeholder outcome not invented as market data —
                # leave None until user/simulator updates; record signal only.
                sim_pnl = None
            tracker.record(
                user_id=user_id,
                symbol=code,
                decision=decision,
                side=str(bias) if bias else None,
                score=float(score["trade_score"]),
                confidence=float(score["confidence_pct"]),
                expected_rr=_dec(risk.get("expected_rr")),
                simulated_pnl=sim_pnl,
                meta={"session": session, "news_risk": news_risk},
            )

        _CACHE.set(cache_key, payload)
        return payload

    async def dashboard(
        self, *, user_id: UUID, symbol: str = "XAUUSD"
    ) -> dict[str, Any]:
        from app.domain.trading.gold_only import resolve_trading_symbol

        decision = await self.evaluate(
            user_id=user_id,
            symbol=resolve_trading_symbol(symbol),
            mode="paper",
            record_paper=True,
        )
        tracker = get_paper_tracker()
        return {
            "status": "available",
            "module": "decision_engine",
            "version": "4.0",
            "decision": decision,
            "paper": {
                "performance": tracker.performance(user_id),
                "recent": tracker.list_for_user(user_id, limit=25),
            },
            "reports": tracker.reports(user_id),
            **_security(),
        }

    def paper_performance(self, user_id: UUID) -> dict[str, Any]:
        return {**get_paper_tracker().performance(user_id), **_security()}

    def reports(self, user_id: UUID) -> dict[str, Any]:
        return {**get_paper_tracker().reports(user_id), **_security()}

    def record_paper_outcome(
        self,
        *,
        user_id: UUID,
        signal_id: str,
        simulated_pnl: float,
    ) -> dict[str, Any]:
        """Attach observed paper PnL to an existing recorded idea — no broker calls."""
        updated = get_paper_tracker().update_pnl(user_id, signal_id, simulated_pnl)
        if not updated:
            return {
                "status": "unavailable",
                "reason": "Signal not found",
                **_security(),
            }
        return {"status": "available", "signal": updated, **_security()}

    # --- helpers ---------------------------------------------------------

    def _load_candles(
        self, symbol: str, timeframe: str, count: int
    ) -> list[dict[str, Any]]:
        try:
            tf = Timeframe.parse(timeframe)
        except Exception:
            tf = Timeframe.H1
        try:
            rates = self.market_data.historical_candles(
                symbol, tf, count=count, start_pos=0
            )
        except Exception:
            return []
        rows: list[dict[str, Any]] = []
        for r in rates:
            ot = r.open_time
            rows.append(
                {
                    "open": float(r.open),
                    "high": float(r.high),
                    "low": float(r.low),
                    "close": float(r.close),
                    "volume": float(r.tick_volume or 0),
                    "time": ot.isoformat() if ot else None,
                    "_sort": ot.timestamp() if ot else 0.0,
                }
            )
        rows.sort(key=lambda c: float(c.get("_sort") or 0))
        for c in rows:
            c.pop("_sort", None)
        return rows

    def _account_positions(
        self,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        account: dict[str, Any] = {}
        positions: list[dict[str, Any]] = []
        try:
            snap = self.portfolio_sync.account_snapshot()
            account = {
                "equity": _dec(snap.equity),
                "balance": _dec(snap.balance),
                "margin": _dec(snap.margin),
                "free_margin": _dec(snap.free_margin),
                "leverage": snap.leverage,
            }
        except Exception:
            account = {}
        try:
            for p in self.portfolio_sync.list_positions():
                positions.append(
                    {
                        "symbol": p.symbol,
                        "volume": _dec(p.volume),
                        "profit": _dec(getattr(p, "profit", 0)),
                    }
                )
        except Exception:
            positions = []
        return account, positions

    def _news_risk(self, symbol: str) -> str:
        try:
            events = self.news.economic_events(limit=20)
        except Exception:
            return "low"
        high = 0
        moderate = 0
        for e in events:
            impact = str(getattr(e, "impact", "") or "").lower()
            if impact in {"high", "3", "red"}:
                high += 1
            elif impact in {"medium", "moderate", "2", "orange"}:
                moderate += 1
        if high >= 1:
            return "high"
        if moderate >= 2:
            return "moderate"
        _ = symbol
        return "low"

    def _correlation_risk(self, positions: list[dict[str, Any]]) -> str:
        usd = sum(
            abs(_dec(p.get("volume")) or 0)
            for p in positions
            if str(p.get("symbol") or "").upper() in _USD_CLUSTER
        )
        n = len([p for p in positions if (_dec(p.get("volume")) or 0) > 0])
        if n >= 3 and usd >= 1.5:
            return "high"
        if n >= 2 and usd >= 0.5:
            return "moderate"
        return "low"

    def _portfolio_heat(
        self, account: dict[str, Any], positions: list[dict[str, Any]]
    ) -> str:
        n = len(positions)
        equity = _dec(account.get("equity")) or 0
        floating = sum(_dec(p.get("profit")) or 0 for p in positions)
        if n >= 4 or (equity > 0 and floating / equity <= -0.02):
            return "hot"
        if n >= 2:
            return "warm"
        return "cool"
