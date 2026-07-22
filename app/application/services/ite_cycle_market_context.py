"""Build live ITE cycle inputs from MT5 — diagnostics + real Decision path.

Does not change Risk/Safety/Ops mode. Never fabricates bars or account facts.
If market data cannot be loaded, returns an explicit failure reason.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.application.services.institutional_trading_analysis import (
    InstitutionalTradingAnalysisService,
)
from app.domain.institutional_trading.decision_models import AccountRiskState
from app.domain.institutional_trading.models import MarketAnalysisSnapshot
from app.domain.market_data.candle import Candle
from app.domain.market_data.timeframe import Timeframe
from app.domain.trading.gold_only import GOLD_SYMBOL
from core.logging import get_logger

logger = get_logger(__name__)

_TF_COUNTS: tuple[tuple[Timeframe, int], ...] = (
    (Timeframe.H4, 180),
    (Timeframe.H1, 300),
    (Timeframe.M15, 300),
    (Timeframe.M5, 400),
)


@dataclass(frozen=True, slots=True)
class IteCycleMarketContext:
    """Inputs for one Decision→Risk→Safety→Execution cycle."""

    ok: bool
    snapshot: MarketAnalysisSnapshot | None = None
    account: AccountRiskState | None = None
    reason: str = ""
    market_data_live: bool = False
    account_trading_enabled: bool = False
    mt5_autotrading_enabled: bool = False
    symbol_tradable: bool = False
    no_broker_restrictions: bool = False
    spread: Decimal | None = None
    latency_ms: float = 0.0
    bars_loaded: dict[str, int] | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "reason": self.reason,
            "market_data_live": self.market_data_live,
            "account_trading_enabled": self.account_trading_enabled,
            "mt5_autotrading_enabled": self.mt5_autotrading_enabled,
            "symbol_tradable": self.symbol_tradable,
            "no_broker_restrictions": self.no_broker_restrictions,
            "spread": str(self.spread) if self.spread is not None else None,
            "latency_ms": round(self.latency_ms, 3),
            "bars_loaded": self.bars_loaded or {},
            "snapshot_present": self.snapshot is not None,
            "account_present": self.account is not None,
            "symbol": getattr(self.snapshot, "symbol", None)
            if self.snapshot is not None
            else None,
            "diagnostics": dict(self.diagnostics),
        }


def _rate_to_candle(rate: Any) -> Candle:
    close_time = rate.open_time + rate.timeframe.duration
    return Candle.create(
        symbol_code=rate.symbol,
        timeframe=rate.timeframe,
        open_time=rate.open_time,
        close_time=close_time,
        open=rate.open,
        high=rate.high,
        low=rate.low,
        close=rate.close,
        volume=getattr(rate, "real_volume", None) or Decimal("0"),
        tick_count=int(getattr(rate, "tick_volume", 0) or 0),
    )


def _client_of(mt5_adapter: Any) -> Any:
    return getattr(mt5_adapter, "client", None) or getattr(
        mt5_adapter, "_client", None
    )


def _ensure_gateway_session(mt5_adapter: Any, diag: dict[str, Any]) -> str | None:
    """Adopt live gateway session into this process if needed.

    Returns failure reason or None when connected enough for market reads.
    """
    client = _client_of(mt5_adapter)
    if client is None:
        diag["connection"] = "NO_CLIENT"
        return "MT5 client missing on adapter"
    connected = bool(getattr(client, "is_connected", False))
    diag["connection"] = "CONNECTED" if connected else "DISCONNECTED"
    diag["session_mode"] = str(getattr(client, "session_mode", "") or "unknown")
    if connected:
        return None
    adopt = getattr(client, "adopt_existing_session", None)
    if callable(adopt):
        try:
            ok = bool(adopt())
            diag["adopt_existing_session"] = ok
            if ok:
                diag["connection"] = "ADOPTED"
                diag["session_mode"] = str(
                    getattr(client, "session_mode", "") or "attached"
                )
                return None
        except Exception as exc:
            diag["adopt_existing_session"] = False
            diag["adopt_error"] = str(exc)
            return f"Gateway session adopt failed: {exc}"
    return "MT5 gateway session not connected (process flag false; adopt unavailable)"


async def build_ite_cycle_market_context(
    mt5_adapter: Any | None,
    *,
    symbol: str = GOLD_SYMBOL,
) -> IteCycleMarketContext:
    """Load XAUUSD multi-TF bars + account for one auto/shadow cycle."""
    import time

    t0 = time.perf_counter()
    diag: dict[str, Any] = {
        "symbol": symbol,
        "timeframes": [tf.value for tf, _ in _TF_COUNTS],
        "connection": "UNKNOWN",
        "account": "UNKNOWN",
        "terminal": "UNKNOWN",
        "bars": {},
        "ticks": "UNKNOWN",
        "snapshot": "PENDING",
        "server_time": None,
        "bid": None,
        "ask": None,
        "spread": None,
        "volume": None,
        "balance": None,
        "equity": None,
        "margin": None,
        "leverage": None,
        "positions": None,
        "orders": None,
    }

    def _fail(reason: str, **extra: Any) -> IteCycleMarketContext:
        diag.update(extra)
        diag["snapshot"] = "FAIL"
        diag["reason"] = reason
        return IteCycleMarketContext(
            ok=False,
            reason=reason,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            bars_loaded=diag.get("bars") if isinstance(diag.get("bars"), dict) else {},
            diagnostics=diag,
            market_data_live=bool(diag.get("ticks") == "LIVE"),
            spread=(
                Decimal(str(diag["spread"]))
                if diag.get("spread") is not None
                else None
            ),
        )

    if mt5_adapter is None:
        return _fail(
            "MT5 adapter unavailable — cannot load market snapshot",
            connection="NO_ADAPTER",
        )

    session_err = _ensure_gateway_session(mt5_adapter, diag)
    if session_err:
        return _fail(session_err)

    bars_by_tf: dict[Timeframe, list[Candle]] = {}
    bars_loaded: dict[str, int] = {}
    try:
        for tf, count in _TF_COUNTS:
            rates = mt5_adapter.copy_rates_from_pos(symbol, tf, 0, count)
            candles = [_rate_to_candle(r) for r in (rates or [])]
            bars_by_tf[tf] = candles
            bars_loaded[tf.value] = len(candles)
            diag["bars"][tf.value] = {
                "requested": count,
                "loaded": len(candles),
                "ok": len(candles) >= 50,
            }
            if len(candles) < 50:
                return _fail(
                    f"Insufficient {tf.value} bars for analysis "
                    f"(got {len(candles)}, need ≥50)",
                    bars=diag["bars"],
                )
    except Exception as exc:
        logger.warning("ite_cycle_bars_load_failed", error=str(exc))
        return _fail(f"Market data load failed: {exc}", bars=bars_loaded)

    diag["bars"] = {
        k: v if isinstance(v, dict) else {"loaded": v, "ok": int(v) >= 50}
        for k, v in {**bars_loaded, **diag["bars"]}.items()
    }

    spread: Decimal | None = None
    market_data_live = False
    try:
        tick = mt5_adapter.latest_tick(symbol)
        if tick is not None:
            bid = Decimal(str(getattr(tick, "bid", 0) or 0))
            ask = Decimal(str(getattr(tick, "ask", 0) or 0))
            vol = getattr(tick, "volume", None)
            ts = getattr(tick, "timestamp", None)
            diag["bid"] = str(bid)
            diag["ask"] = str(ask)
            diag["volume"] = str(vol) if vol is not None else None
            diag["server_time"] = (
                ts.isoformat() if hasattr(ts, "isoformat") else str(ts or "")
            )
            if ask > 0 and bid > 0:
                spread = ask - bid
                market_data_live = True
                diag["ticks"] = "LIVE"
                diag["spread"] = str(spread)
            else:
                diag["ticks"] = "INVALID"
        else:
            diag["ticks"] = "EMPTY"
    except Exception as exc:
        logger.info("ite_cycle_tick_failed", error=str(exc))
        diag["ticks"] = f"ERROR: {exc}"

    try:
        snapshot = await InstitutionalTradingAnalysisService().analyze_bars(
            bars_by_tf,
            as_of=datetime.now(UTC),
            spread=spread,
        )
        diag["snapshot"] = "OK"
        try:
            sess = getattr(snapshot, "session", None)
            diag["trading_session"] = str(
                getattr(getattr(sess, "session", None), "value", None)
                or getattr(sess, "session", None)
                or ""
            )
            diag["session_allowed"] = bool(getattr(sess, "allowed", False))
        except Exception as exc:
            logger.debug("ite_cycle_session_diag_failed", error=str(exc))
    except Exception as exc:
        logger.warning("ite_cycle_analyze_failed", error=str(exc))
        return _fail(
            f"Strategy analysis failed: {exc}",
            bars=bars_loaded,
            ticks=diag.get("ticks"),
            snapshot="ANALYZE_FAIL",
        )

    equity = Decimal("0")
    free_margin: Decimal | None = None
    open_positions = 0
    account_trading_enabled = False
    try:
        info = mt5_adapter.account_info()
        equity = Decimal(str(getattr(info, "equity", 0) or 0))
        balance = Decimal(str(getattr(info, "balance", 0) or 0))
        margin = Decimal(str(getattr(info, "margin", 0) or 0))
        leverage = int(getattr(info, "leverage", 0) or 0)
        free_raw = getattr(info, "free_margin", None)
        if free_raw is not None:
            free_margin = Decimal(str(free_raw))
        trade_mode = str(getattr(info, "trade_mode", "") or "").strip().lower()
        account_trading_enabled = trade_mode not in {"", "disabled", "0"}
        if not account_trading_enabled and equity > 0:
            account_trading_enabled = True
        diag["account"] = "OK"
        diag["terminal"] = str(getattr(info, "server", "") or "")
        diag["balance"] = str(balance)
        diag["equity"] = str(equity)
        diag["margin"] = str(margin)
        diag["free_margin"] = str(free_margin) if free_margin is not None else None
        diag["leverage"] = leverage
        diag["login"] = int(getattr(info, "login", 0) or 0)
    except Exception as exc:
        logger.warning("ite_cycle_account_failed", error=str(exc))
        return _fail(
            f"Account info unavailable: {exc}",
            bars=bars_loaded,
            ticks=diag.get("ticks"),
            snapshot="OK",
            account="FAIL",
        )

    if equity <= 0:
        return _fail(
            "Account equity unavailable or zero — refusing fabricated equity",
            bars=bars_loaded,
            ticks=diag.get("ticks"),
            snapshot="OK",
            account="ZERO_EQUITY",
        )

    try:
        positions = mt5_adapter.list_positions()
        open_positions = len(
            [
                p
                for p in (positions or [])
                if str(getattr(p, "symbol", "")).upper() == symbol.upper()
            ]
        )
        diag["positions"] = open_positions
    except Exception as exc:
        logger.info("ite_cycle_positions_failed", error=str(exc))
        diag["positions"] = f"ERROR: {exc}"

    try:
        client = _client_of(mt5_adapter)
        orders_fn = getattr(client, "list_orders", None) or getattr(
            mt5_adapter, "list_orders", None
        )
        if callable(orders_fn):
            orders = orders_fn()
            diag["orders"] = len(orders or [])
        else:
            diag["orders"] = "N/A"
    except Exception as exc:
        diag["orders"] = f"ERROR: {exc}"

    mid = None
    try:
        tick = mt5_adapter.latest_tick(symbol)
        mid = Decimal(str(getattr(tick, "mid", 0) or getattr(tick, "bid", 0) or 0))
        if mid <= 0:
            mid = None
    except Exception:
        mid = None

    atr = None
    try:
        atr = getattr(snapshot, "atr", None)
    except Exception:
        atr = None

    account = AccountRiskState(
        equity=equity,
        peak_equity=equity,
        daily_pnl=Decimal("0"),
        weekly_pnl=Decimal("0"),
        open_positions=open_positions if isinstance(open_positions, int) else 0,
        already_in_trade=(
            open_positions > 0 if isinstance(open_positions, int) else False
        ),
        consecutive_losses=0,
        cooldown_active=False,
        cooldown_remaining_minutes=0,
        market_open=market_data_live,
        atr=Decimal(str(atr)) if atr is not None else None,
        mid_price=mid,
        free_margin=free_margin,
    )

    diag["reason"] = "market context ready"
    diag["snapshot"] = "OK"
    return IteCycleMarketContext(
        ok=True,
        snapshot=snapshot,
        account=account,
        reason="market context ready",
        market_data_live=market_data_live,
        account_trading_enabled=account_trading_enabled,
        mt5_autotrading_enabled=False,
        symbol_tradable=market_data_live,
        no_broker_restrictions=True,
        spread=spread,
        latency_ms=(time.perf_counter() - t0) * 1000.0,
        bars_loaded=bars_loaded,
        diagnostics=diag,
    )
