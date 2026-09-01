"""Build live ITE cycle inputs from MT5 — diagnostics + real Decision path.

Does not change Risk/Safety/Ops mode. Never fabricates bars or account facts.
If market data cannot be loaded, returns an explicit failure reason.
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
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

_CYCLE_LOCK = threading.Lock()
_CYCLE_ACTIVE = False
_CYCLE_CTX: dict[str, IteCycleMarketContext] = {}


def begin_cycle_market_snapshot() -> None:
    """Start a same-cycle read window. Previous-cycle snapshots are dropped."""
    global _CYCLE_ACTIVE, _CYCLE_CTX
    with _CYCLE_LOCK:
        _CYCLE_ACTIVE = True
        _CYCLE_CTX = {}


def end_cycle_market_snapshot() -> None:
    """End the cycle window — never reuse market context across cycles."""
    global _CYCLE_ACTIVE, _CYCLE_CTX
    with _CYCLE_LOCK:
        _CYCLE_ACTIVE = False
        _CYCLE_CTX = {}


def peek_cycle_market_context(symbol: str | None) -> IteCycleMarketContext | None:
    key = str(symbol or "").strip().upper()
    if not key:
        return None
    with _CYCLE_LOCK:
        if not _CYCLE_ACTIVE:
            return None
        return _CYCLE_CTX.get(key)


def _remember_cycle_market_context(
    ctx: IteCycleMarketContext, *symbols: str | None
) -> None:
    if not ctx.ok:
        return
    with _CYCLE_LOCK:
        if not _CYCLE_ACTIVE:
            return
        for raw in symbols:
            key = str(raw or "").strip().upper()
            if key:
                _CYCLE_CTX[key] = ctx


def unbind_cycle_gateway_reads(mt5_adapter: Any | None) -> None:
    client = _client_of(mt5_adapter) if mt5_adapter is not None else None
    end = getattr(client, "end_cycle_reads", None)
    if callable(end):
        end()
    end_cycle_market_snapshot()


def bind_cycle_gateway_reads(mt5_adapter: Any | None) -> None:
    begin_cycle_market_snapshot()
    client = _client_of(mt5_adapter) if mt5_adapter is not None else None
    begin = getattr(client, "begin_cycle_reads", None)
    if callable(begin):
        begin()


def refresh_execution_gateway_reads(mt5_adapter: Any | None) -> None:
    client = _client_of(mt5_adapter) if mt5_adapter is not None else None
    fn = getattr(client, "require_fresh_execution_reads", None)
    if callable(fn):
        fn()


async def _offload_sync(
    fn: Any,
    /,
    *args: Any,
    research_io: bool = False,
    **kwargs: Any,
) -> Any:
    """Run blocking MT5/gateway I/O off the asyncio event loop.

    Production bug: sync httpx gateway calls inside ``async`` market context
    starved login/health. Trading decisions are unchanged — only the thread
    that performs I/O moves.

    LIVE ITE / scanner work uses the bounded ITE I/O pool.
    Research-mode scoring uses ``asyncio.to_thread`` so a multi-symbol
    research batch cannot saturate the 5-worker ITE pool (4 symbols × 5
    timeframes) and leave LIVE non-gold desks stuck as UNKNOWN stubs.
    """
    import asyncio
    from functools import partial

    if research_io:
        if kwargs:
            return await asyncio.to_thread(partial(fn, *args, **kwargs))
        return await asyncio.to_thread(fn, *args)

    from app.application.services.blocking_io_offload import offload_blocking

    return await offload_blocking(fn, *args, **kwargs)

_TF_COUNTS: tuple[tuple[Timeframe, int], ...] = (
    (Timeframe.H4, 180),
    (Timeframe.H1, 300),
    (Timeframe.M15, 300),
    (Timeframe.M5, 400),
    (Timeframe.M1, 500),
)
_MIN_BARS = 50
_SCALP_REQUIRED_TFS: tuple[Timeframe, ...] = (
    Timeframe.H1,
    Timeframe.M15,
    Timeframe.M5,
    Timeframe.M1,
)


def _scalping_stack() -> bool:
    """LIVE default is scalping (H1→M1). Swing still requires the H4 stack."""
    try:
        from app.domain.institutional_trading.ai_scalping.config import (
            scalping_ite_config,
        )

        return bool(scalping_ite_config().is_scalping())
    except Exception:
        return True


def _tf_plan() -> tuple[
    tuple[tuple[Timeframe, int], ...],
    tuple[tuple[Timeframe, int], ...],
]:
    """Required vs optional candle fetches. One optional TF must not fail the desk."""
    by_tf = {tf: n for tf, n in _TF_COUNTS}
    if _scalping_stack():
        required = tuple(
            (tf, by_tf[tf]) for tf in _SCALP_REQUIRED_TFS if tf in by_tf
        )
        optional = (
            ((Timeframe.H4, by_tf[Timeframe.H4]),) if Timeframe.H4 in by_tf else ()
        )
        return required, optional
    return _TF_COUNTS, ()


def _symbol_context_not_ready(code: str, detail: str) -> str:
    extra = str(detail or "").strip()
    if extra:
        return f"SYMBOL_CONTEXT_NOT_READY:{code}:{extra}"
    return f"SYMBOL_CONTEXT_NOT_READY:{code}"
# Cap concurrent candle fetches below TRADING_READ_LIMIT (6).
_TF_GATE_LIMIT = 4
_tf_fetch_gate: asyncio.Semaphore | None = None
_tf_fetch_gate_loop: asyncio.AbstractEventLoop | None = None


def _tf_fetch_semaphore() -> asyncio.Semaphore:
    """Loop-local gate — module Semaphore binds to the first pytest loop."""
    global _tf_fetch_gate, _tf_fetch_gate_loop
    loop = asyncio.get_running_loop()
    if _tf_fetch_gate is None or _tf_fetch_gate_loop is not loop:
        _tf_fetch_gate = asyncio.Semaphore(_TF_GATE_LIMIT)
        _tf_fetch_gate_loop = loop
    return _tf_fetch_gate


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
    reused: bool = False
    snapshot_built_at: str | None = None

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
            "symbol": (
                getattr(self.snapshot, "symbol", None)
                if self.snapshot is not None
                else None
            ),
            "diagnostics": dict(self.diagnostics),
            "reused": bool(self.reused),
            "snapshot_built_at": self.snapshot_built_at,
        }


def _market_data_failure_fields(
    error_text: str,
    *,
    logical_symbol: str,
    canonical_broker_symbol: str | None,
) -> dict[str, Any]:
    """Classify a bars-load exception without rewriting the HTTP status."""
    import re

    text = str(error_text or "")
    match = re.search(r"HTTP\s+(\d{3})", text, flags=re.IGNORECASE)
    http_status = int(match.group(1)) if match else None
    endpoint_match = re.search(r"Gateway\s+(\S+)", text)
    host_match = re.search(r"https?://[^/\s:]+", text)
    fields: dict[str, Any] = {
        "logical_symbol": logical_symbol,
        "canonical_broker_symbol": canonical_broker_symbol,
        "http_status": http_status,
        "endpoint": endpoint_match.group(1) if endpoint_match else None,
        "gateway_host": host_match.group(0) if host_match else None,
        "timestamp": datetime.now(UTC).isoformat(),
        "next_action": "FAIL_CLOSED",
        "reason_prefix": "Market data load failed",
    }
    if http_status == 530 or "CLOUDFLARE_ORIGIN_UNREACHABLE" in text:
        fields["failure_class"] = "MARKET_DATA_ORIGIN_UNREACHABLE"
        fields["reason_prefix"] = "CLOUDFLARE_ORIGIN_UNREACHABLE"
    elif http_status == 503 or "GATEWAY_MARKET_DATA_UNAVAILABLE" in text:
        fields["failure_class"] = "GATEWAY_MARKET_DATA_UNAVAILABLE"
        fields["reason_prefix"] = "GATEWAY_MARKET_DATA_UNAVAILABLE"
    elif http_status in {502, 504} or "CLOUD_EDGE_ORIGIN_ERROR" in text:
        fields["failure_class"] = "CLOUD_EDGE_ORIGIN_ERROR"
        fields["reason_prefix"] = "CLOUD_EDGE_ORIGIN_ERROR"
    else:
        fields["failure_class"] = "MARKET_DATA_UNAVAILABLE"
    return fields


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
    return getattr(mt5_adapter, "client", None) or getattr(mt5_adapter, "_client", None)


def _read_mt5_autotrading_enabled(
    mt5_adapter: Any, diag: dict[str, Any]
) -> bool | None:
    """Read terminal AutoTrading from gateway /health — never invent True.

    Returns None when unknown (caller may fail-closed). Live gateway exposes
    ``mt5.mt5_autotrading_enabled`` / ``mt5.terminal_trade_allowed``.
    """
    client = _client_of(mt5_adapter)
    payload: dict[str, Any] | None = None
    health_fn = getattr(client, "gateway_health", None)
    if callable(health_fn):
        try:
            raw = health_fn()
            if isinstance(raw, dict):
                payload = raw
        except Exception as exc:
            diag["autotrading_health_error"] = str(exc)
    if payload is None:
        try:
            from app.application.services.institutional_live_probes import (
                _http_get_json,
            )
            from core.config.settings import get_settings

            base = (get_settings().mt5_gateway_base_url or "").rstrip("/")
            if base:
                _ok, _lat, _code, body, _cf = _http_get_json(f"{base}/health")
                if isinstance(body, dict):
                    payload = body
                    diag["autotrading_health_via"] = "public_/health"
        except Exception as exc:
            diag["autotrading_public_health_error"] = str(exc)
    if payload is None:
        return None
    mt5_raw = payload.get("mt5")
    mt5 = mt5_raw if isinstance(mt5_raw, dict) else {}
    for key in (
        "mt5_autotrading_enabled",
        "terminal_trade_allowed",
        "autotrading_enabled",
        "autotrading",
    ):
        if key in mt5 and mt5.get(key) is not None:
            val = bool(mt5.get(key))
            diag["mt5_autotrading_enabled"] = val
            diag["mt5_autotrading_source"] = f"mt5.{key}"
            return val
        if key in payload and payload.get(key) is not None:
            val = bool(payload.get(key))
            diag["mt5_autotrading_enabled"] = val
            diag["mt5_autotrading_source"] = key
            return val
    if mt5.get("trade_allowed") is not None:
        val = bool(mt5.get("trade_allowed"))
        diag["mt5_autotrading_enabled"] = val
        diag["mt5_autotrading_source"] = "mt5.trade_allowed"
        return val
    return None


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


def _load_history_deals(
    mt5_adapter: Any,
    *,
    date_from: datetime,
    date_to: datetime,
) -> tuple[bool, list[Any] | None, str | None]:
    """Sync Gateway history fetch — caller must offload this off the event loop."""
    hist = getattr(mt5_adapter, "history_deals", None)
    if callable(hist):
        return True, list(hist(date_from=date_from, date_to=date_to)), None
    client = _client_of(mt5_adapter)
    hist_c = getattr(client, "history_deals", None)
    if callable(hist_c):
        return True, list(hist_c(date_from=date_from, date_to=date_to)), None
    return False, None, "UNAVAILABLE"


async def build_ite_cycle_market_context(
    mt5_adapter: Any | None,
    *,
    symbol: str = GOLD_SYMBOL,
    position_engine: Any | None = None,
    reuse_cycle: bool = True,
    research_mode: bool = False,
    purpose: str = "execution",
) -> IteCycleMarketContext:
    """Load multi-TF bars + account for one cycle.

    ``research_mode=True`` loads market data for research scoring across
    catalogue symbols without changing gold-only LIVE execution gates.
    Research never authorizes OMS / order_send.

    ``purpose="scan"`` skips per-symbol history/position/health stampedes so
    the bounded multi-market scan can finish inside the cycle budget. The
    execution path still loads the full account bundle.
    """
    import time

    if reuse_cycle and not research_mode:
        cached = peek_cycle_market_context(symbol)
        if cached is not None and cached.ok:
            logger.warning(
                "ite_cycle_market_context_reused",
                symbol=symbol,
                snapshot_built_at=cached.snapshot_built_at,
                original_latency_ms=round(float(cached.latency_ms or 0.0), 1),
            )
            return IteCycleMarketContext(
                ok=cached.ok,
                snapshot=cached.snapshot,
                account=cached.account,
                reason=cached.reason,
                market_data_live=cached.market_data_live,
                account_trading_enabled=cached.account_trading_enabled,
                mt5_autotrading_enabled=cached.mt5_autotrading_enabled,
                symbol_tradable=cached.symbol_tradable,
                no_broker_restrictions=cached.no_broker_restrictions,
                spread=cached.spread,
                latency_ms=cached.latency_ms,
                bars_loaded=cached.bars_loaded,
                diagnostics={
                    **dict(cached.diagnostics or {}),
                    "market_context_reused": True,
                },
                reused=True,
                snapshot_built_at=cached.snapshot_built_at,
            )

    t0 = time.perf_counter()
    diag: dict[str, Any] = {
        "symbol": symbol,
        "timeframes": [tf.value for tf, _ in _TF_COUNTS],
        "connection": "UNKNOWN",
        "account": "UNKNOWN",
        "research_mode": bool(research_mode),
        "research_io_isolated": bool(research_mode),
        "authorizes_trade": False if research_mode else None,
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
                Decimal(str(diag["spread"])) if diag.get("spread") is not None else None
            ),
        )

    if mt5_adapter is None:
        return _fail(
            "MT5 adapter unavailable — cannot load market snapshot",
            connection="NO_ADAPTER",
        )

    async def _io(fn: Any, /, *args: Any, **kwargs: Any) -> Any:
        return await _offload_sync(
            fn, *args, research_io=bool(research_mode), **kwargs
        )

    session_err = await _io(_ensure_gateway_session, mt5_adapter, diag)
    if session_err:
        return _fail(session_err)

    # Catalogue-only resolution: Weltrade exposes XAUUSD_i / EURUSD_i.
    # Never request unsuffixed desk aliases once the catalogue has the
    # institutional form (bare AUDUSD is 503 on this broker).
    from app.domain.institutional_trading.ai_scalping.universe_discovery import (
        catalogue_ordered_candidates,
        fetch_broker_symbol_rows,
    )

    logical_symbol = (symbol or "").strip()
    diag["logical_symbol"] = logical_symbol
    try:
        from app.domain.trading.gold_only import gold_only_enabled, is_gold_symbol

        # Research mode loads catalogue market data for intelligence only.
        # LIVE autonomous execution remains gold-clamped elsewhere.
        if gold_only_enabled() and not research_mode:
            from app.domain.trading.gold_only import (
                canonical_gold_execution_symbol,
                is_bare_gold_symbol,
            )

            if logical_symbol and not is_gold_symbol(logical_symbol):
                return _fail(
                    f"DISABLED_AUTONOMOUS_SYMBOL: autonomous universe is gold-only, "
                    f"rejected {logical_symbol}",
                    next_action="NO_EXECUTABLE_FOCUS",
                )
            if not logical_symbol or is_bare_gold_symbol(logical_symbol):
                logical_symbol = canonical_gold_execution_symbol(logical_symbol)
                diag["logical_symbol"] = logical_symbol
                diag["symbol"] = logical_symbol
        elif research_mode:
            diag["research_gold_gate_bypassed"] = True
    except Exception:
        logger.exception("gold_only_market_context_gate_failed")
    diag["canonical_broker_symbol"] = None
    broker_rows: tuple[dict[str, Any], ...] = ()
    try:
        broker_rows = await _io(fetch_broker_symbol_rows, mt5_adapter)
    except Exception:
        broker_rows = ()
    symbol_candidates = (
        catalogue_ordered_candidates(logical_symbol, broker_symbol_rows=broker_rows)
        if broker_rows
        else ()
    )
    if not symbol_candidates:
        return _fail(
            f"SYMBOL_CATALOGUE_RESOLUTION_FAILED: no catalogue broker symbol "
            f"for {logical_symbol or 'unknown'}",
            logical_symbol=logical_symbol,
            canonical_broker_symbol=None,
            next_action="FAIL_CLOSED",
        )
    canonical_symbol = symbol_candidates[0]
    diag["canonical_broker_symbol"] = canonical_symbol
    diag["requested_symbol"] = logical_symbol
    diag["context_purpose"] = str(purpose or "execution")
    bars_by_tf: dict[Timeframe, list[Candle]] = {}
    bars_loaded: dict[str, int] = {}
    required_tfs, optional_tfs = _tf_plan()
    diag["required_timeframes"] = [tf.value for tf, _ in required_tfs]
    diag["optional_timeframes"] = [tf.value for tf, _ in optional_tfs]
    last_bar_exc: Exception | None = None
    failed_required_tf: Timeframe | None = None

    async def _one_tf(
        tf: Timeframe, count: int
    ) -> tuple[Timeframe, list[Candle], BaseException | None]:
        try:
            async with _tf_fetch_semaphore():
                rates = await _io(
                    mt5_adapter.copy_rates_from_pos,
                    canonical_symbol,
                    tf,
                    0,
                    count,
                )
            return tf, [_rate_to_candle(r) for r in (rates or [])], None
        except Exception as exc:
            return tf, [], exc

    plan = list(required_tfs) + list(optional_tfs)
    required_set = {tf for tf, _ in required_tfs}
    loaded = await asyncio.gather(*[_one_tf(tf, n) for tf, n in plan])
    for tf, candles, exc in loaded:
        bars_loaded[tf.value] = len(candles)
        diag["bars"][tf.value] = {
            "requested": dict(plan).get(tf, 0),
            "loaded": len(candles),
            "ok": len(candles) >= _MIN_BARS and exc is None,
            "required": tf in required_set,
            "error": type(exc).__name__ if exc else None,
        }
        if tf not in required_set:
            if exc is None and len(candles) >= _MIN_BARS:
                bars_by_tf[tf] = candles
            else:
                logger.warning(
                    "optional_timeframe_unavailable",
                    timeframe=tf.value,
                    error=str(exc) if exc else f"bars={len(candles)}",
                )
            continue
        bars_by_tf[tf] = candles
        if failed_required_tf is not None:
            continue
        if exc is not None:
            last_bar_exc = exc if isinstance(exc, Exception) else Exception(str(exc))
            failed_required_tf = tf
        elif len(candles) < _MIN_BARS:
            last_bar_exc = RuntimeError(
                f"Insufficient {tf.value} bars for analysis "
                f"(got {len(candles)}, need ≥{_MIN_BARS})"
            )
            failed_required_tf = tf
    if last_bar_exc is not None or not bars_by_tf:
        err_text = str(last_bar_exc or "no bars")
        md_fields = _market_data_failure_fields(
            err_text,
            logical_symbol=logical_symbol,
            canonical_broker_symbol=canonical_symbol,
        )
        tf_code = (
            failed_required_tf.value if failed_required_tf is not None else "BARS"
        )
        if "Insufficient" in err_text:
            reason = _symbol_context_not_ready(
                f"INSUFFICIENT_{tf_code}_DATA", err_text
            )
        elif md_fields.get("failure_class"):
            reason = _symbol_context_not_ready(
                str(md_fields.get("failure_class")), f"{tf_code}:{err_text}"
            )
        else:
            reason = _symbol_context_not_ready(
                f"MISSING_TIMEFRAME_{tf_code}", err_text
            )
        logger.warning(
            "ite_cycle_bars_load_failed",
            error=err_text,
            tried=list(symbol_candidates),
            required_timeframe=tf_code,
            **md_fields,
        )
        md_fields.pop("reason_prefix", None)
        return _fail(
            reason,
            bars=bars_loaded,
            broker_symbol_tried=list(symbol_candidates),
            **md_fields,
        )
    if canonical_symbol != logical_symbol:
        diag["broker_symbol_resolved"] = canonical_symbol
        symbol = canonical_symbol
        diag["symbol"] = symbol

    diag["bars"] = {
        k: v if isinstance(v, dict) else {"loaded": v, "ok": int(v) >= 50}
        for k, v in {**bars_loaded, **diag["bars"]}.items()
    }

    spread: Decimal | None = None
    market_data_live = False
    quote_bid: Decimal | None = None
    quote_ask: Decimal | None = None
    quote_age_seconds: float | None = None
    try:
        tick = await _io(mt5_adapter.latest_tick, symbol)
        if tick is not None:
            bid = Decimal(str(getattr(tick, "bid", 0) or 0))
            ask = Decimal(str(getattr(tick, "ask", 0) or 0))
            vol = getattr(tick, "volume", None)
            ts = getattr(tick, "timestamp", None)
            diag["bid"] = str(bid)
            diag["ask"] = str(ask)
            diag["volume"] = str(vol) if vol is not None else None
            diag["server_time"] = (
                ts.isoformat()
                if ts is not None and hasattr(ts, "isoformat")
                else str(ts or "")
            )
            if ts is not None and hasattr(ts, "tzinfo"):
                try:
                    from datetime import UTC as _UTC

                    moment = datetime.now(_UTC)
                    qt = ts if ts.tzinfo is not None else ts.replace(tzinfo=_UTC)
                    quote_age_seconds = max(0.0, (moment - qt).total_seconds())
                    diag["quote_age_seconds"] = quote_age_seconds
                except Exception:
                    quote_age_seconds = None
            if ask > 0 and bid > 0:
                spread = ask - bid
                market_data_live = True
                quote_bid = bid
                quote_ask = ask
                diag["ticks"] = "LIVE"
                diag["spread"] = str(spread)
            else:
                diag["ticks"] = "INVALID"
        else:
            diag["ticks"] = "EMPTY"
    except Exception as exc:
        logger.info("ite_cycle_tick_failed", error=str(exc))
        diag["ticks"] = f"ERROR: {exc}"

    tick_state = str(diag.get("ticks") or "UNKNOWN")
    if not market_data_live:
        if tick_state == "EMPTY":
            return _fail(
                _symbol_context_not_ready("MISSING_TICK", canonical_symbol),
                ticks=tick_state,
                bars=bars_loaded,
            )
        if tick_state == "INVALID":
            return _fail(
                _symbol_context_not_ready("INVALID_TICK", canonical_symbol),
                ticks=tick_state,
                bars=bars_loaded,
            )
        if tick_state.startswith("ERROR"):
            return _fail(
                _symbol_context_not_ready("TICK_ERROR", tick_state),
                ticks=tick_state,
                bars=bars_loaded,
            )

    try:
        snapshot = await InstitutionalTradingAnalysisService().analyze_bars(
            bars_by_tf,
            as_of=datetime.now(UTC),
            spread=spread,
            symbol=symbol,
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

    from app.application.services.mt5_position_truth import force_sync_positions

    client_for_reads = _client_of(mt5_adapter)
    orders_fn = getattr(client_for_reads, "list_orders", None) or getattr(
        mt5_adapter, "list_orders", None
    )
    specs_fn = (
        getattr(client_for_reads, "symbol_info", None)
        if client_for_reads is not None
        else None
    )
    day_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    health_diag_box: dict[str, Any] = {}
    skip_account_bundle = str(purpose or "execution").strip().lower() == "scan"
    bundled = await asyncio.gather(
        _io(mt5_adapter.account_info),
        (
            _io(lambda: None)
            if skip_account_bundle
            else _io(
                force_sync_positions,
                mt5_adapter,
                symbol=symbol,
                position_engine=position_engine,
                fresh=True,
            )
        ),
        (
            _io(lambda: (False, None, "SKIPPED_SCAN"))
            if skip_account_bundle
            else _io(
                _load_history_deals,
                mt5_adapter,
                date_from=day_start,
                date_to=datetime.now(UTC) + timedelta(days=1),
            )
        ),
        (
            _io(lambda: "N/A")
            if skip_account_bundle or not callable(orders_fn)
            else _io(orders_fn)
        ),
        (
            _io(lambda: None)
            if skip_account_bundle
            else _io(_read_mt5_autotrading_enabled, mt5_adapter, health_diag_box)
        ),
        (
            _io(specs_fn, symbol)
            if callable(specs_fn)
            else _io(lambda: None)
        ),
        return_exceptions=True,
    )
    pre_info, pre_sync, pre_deals, pre_orders, pre_health, pre_specs = bundled
    diag["read_parallel"] = True

    equity = Decimal("0")
    free_margin: Decimal | None = None
    open_positions = 0
    account_positions = 0
    account_trading_enabled = False
    try:
        if isinstance(pre_info, Exception):
            raise pre_info
        info = pre_info
        equity = Decimal(str(getattr(info, "equity", 0) or 0))
        balance = Decimal(str(getattr(info, "balance", 0) or 0))
        margin = Decimal(str(getattr(info, "margin", 0) or 0))
        leverage = int(getattr(info, "leverage", 0) or 0)
        free_raw = getattr(info, "free_margin", None)
        if free_raw is not None:
            free_margin = Decimal(str(free_raw))
        floating_pnl = Decimal(str(getattr(info, "profit", 0) or 0))
        # Account environment (demo|contest|real|unknown) ≠ symbol trade mode.
        account_mode = str(getattr(info, "trade_mode", "") or "").strip().lower()
        if account_mode not in {"demo", "contest", "real", "unknown"}:
            account_mode = account_mode or "unknown"
        trade_allowed = getattr(info, "trade_allowed", None)
        if trade_allowed is not None:
            account_trading_enabled = bool(trade_allowed)
            diag["account_trading_source"] = f"trade_allowed:{account_trading_enabled}"
        else:
            # Unknown trade_allowed: enable when account mode is a known tradable
            # environment (demo/contest/real) or equity proves a live book.
            account_trading_enabled = account_mode in {"demo", "contest", "real"}
            if (
                not account_trading_enabled
                and equity > 0
                and account_mode
                in {
                    "",
                    "unknown",
                }
            ):
                account_trading_enabled = True
                diag["account_trading_source"] = "equity_fallback_unknown_mode"
            else:
                diag["account_trading_source"] = (
                    f"account_mode:{account_mode or 'empty'}"
                )
        diag["account_trading_enabled"] = account_trading_enabled
        diag["account_mode"] = account_mode
        diag["account_trade_allowed"] = trade_allowed
        diag["account"] = "OK"
        diag["terminal"] = str(getattr(info, "server", "") or "")
        diag["balance"] = str(balance)
        diag["equity"] = str(equity)
        diag["margin"] = str(margin)
        diag["free_margin"] = str(free_margin) if free_margin is not None else None
        diag["floating_pnl"] = str(floating_pnl)
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

    book_rows: list[Any] = []
    try:
        if isinstance(pre_sync, Exception):
            raise pre_sync
        sync = pre_sync
        account_positions = int(getattr(sync, "mt5_positions", 0) or 0)
        open_positions = int(getattr(sync, "quantforg_positions", 0) or 0)
        diag["positions"] = open_positions
        diag["mt5_positions"] = account_positions
        diag["account_positions"] = account_positions
        diag["quantforg_positions"] = open_positions
        diag["internal_positions"] = getattr(sync, "internal_positions", 0)
        diag["position_truth_repaired"] = getattr(sync, "repaired", False)
        qf_tickets = getattr(sync, "quantforg_tickets", None) or getattr(
            sync, "tickets", ()
        )
        diag["position_tickets"] = list(qf_tickets or [])
        from app.domain.institutional_trading.ai_scalping.config import (
            DEFAULT_AI_SCALPING_CONFIG,
        )

        cap_max = int(
            getattr(DEFAULT_AI_SCALPING_CONFIG, "max_positions_per_symbol", 2) or 2
        )
        cap_used = int(open_positions or 0)
        diag["capacity_used"] = cap_used
        diag["capacity_max"] = cap_max
        diag["capacity_available"] = max(0, cap_max - cap_used)
        diag["capacity_label"] = (
            "FULL"
            if cap_used >= cap_max
            else (f"{max(0, cap_max - cap_used)} SLOT" if cap_max - cap_used == 1 else f"{max(0, cap_max - cap_used)} SLOTS")
        )
        diag["position_cap_identity"] = 260720
        book_rows = list(getattr(sync, "rows", ()) or ())
    except Exception as exc:
        logger.warning("ite_cycle_positions_failed", error=str(exc))
        diag["positions"] = f"ERROR: {exc}"
        diag["positions_sync_failed"] = True
        # Fail-closed for new entries — never treat a sync error as flat book.
        engine_n = 0
        if position_engine is not None:
            try:
                engine_n = len(getattr(position_engine, "_positions", {}) or {})
            except Exception:
                engine_n = 0
        open_positions = max(int(engine_n), 1)
        diag["positions_fail_closed_count"] = open_positions
        account_positions = open_positions
        diag["account_positions"] = account_positions

    # Book facts for duplicate / add-on guards — QuantForg gold identity only.
    open_directions: list[str] = []
    open_entries: list[Decimal] = []
    book_facts_ok = False
    try:
        from app.domain.institutional_trading.operations.quantforg_position_cap import (
            book_facts_from_positions,
            filter_quantforg_positions,
        )

        rows = book_rows
        owned = filter_quantforg_positions(rows or [], symbol=symbol)
        dirs, entries = book_facts_from_positions(owned)
        open_directions = list(dirs)
        open_entries = list(entries)
        diag["open_directions"] = list(open_directions)
        diag["open_entries"] = [str(e) for e in open_entries]
        from app.domain.institutional_trading.operations.quantforg_position_cap import (
            live_capacity_tickets,
        )

        live_tix = live_capacity_tickets(owned, symbol=symbol)
        open_positions = len(live_tix)
        diag["positions"] = open_positions
        diag["quantforg_positions"] = open_positions
        cap_max = int(diag.get("capacity_max") or 2)
        diag["capacity_used"] = open_positions
        diag["capacity_available"] = max(0, cap_max - open_positions)
        diag["capacity_label"] = (
            "FULL"
            if open_positions >= cap_max
            else (
                f"{max(0, cap_max - open_positions)} SLOT"
                if cap_max - open_positions == 1
                else f"{max(0, cap_max - open_positions)} SLOTS"
            )
        )
        diag["position_tickets"] = list(live_tix)
        profits = []
        for row in owned:
            try:
                from decimal import Decimal as _Dec

                profits.append(_Dec(str(getattr(row, "profit", 0) or 0)))
            except Exception:
                continue
        cap_left = int(diag.get("capacity_available") or 0)
        all_winners = bool(profits) and all(p > 0 for p in profits)
        diag["scale_in_eligible"] = bool(
            open_positions > 0 and cap_left > 0 and all_winners
        )
        if open_positions <= 0:
            diag["scale_in_block_reason"] = "NO_OPEN_POSITION"
        elif cap_left <= 0:
            diag["scale_in_block_reason"] = "MAX_POSITIONS_REACHED"
        elif not all_winners:
            diag["scale_in_block_reason"] = "LOSING_POSITION_NO_SCALE_IN"
        else:
            diag["scale_in_block_reason"] = None
        book_facts_ok = True
        # Open book reported but no parseable sides/entries → treat as incomplete
        if open_positions > 0 and not open_directions and not open_entries:
            book_facts_ok = False
            diag["book_facts_incomplete"] = True
    except Exception as exc:
        logger.warning("ite_cycle_position_book_facts_failed", error=str(exc))
        diag["open_directions"] = f"ERROR: {exc}"
        diag["book_facts_incomplete"] = True
        book_facts_ok = False

    # Authoritative peak HWM + daily PnL from MT5 deals (not floating profit alone)
    peak_equity = equity
    daily_pnl = Decimal("0")
    daily_pnl_trusted = False
    try:
        from app.application.services.live_account_risk_tracker import (
            LiveAccountRiskTracker,
            get_live_account_risk_tracker,
        )
        from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG

        login = int(diag.get("login") or 0)
        balance = Decimal(str(diag.get("balance") or 0))
        deals: list[Any] | None = None
        deals_fetch_ok = False
        try:
            if isinstance(pre_deals, Exception):
                raise pre_deals
            deals_fetch_ok, deals, deals_note = pre_deals
            if deals_note:
                diag["history_deals"] = deals_note
        except Exception as exc:
            logger.warning("ite_cycle_history_deals_failed", error=str(exc))
            diag["history_deals"] = f"ERROR: {exc}"
            deals = None
            deals_fetch_ok = False

        tracker = get_live_account_risk_tracker()
        if deals_fetch_ok and deals is not None:
            peak_equity, daily_pnl = tracker.resolve_for_risk(
                login=login,
                equity=equity,
                balance=balance,
                deals=deals,
            )
            daily_pnl_trusted = True
            try:
                resolved = LiveAccountRiskTracker.session_pnl_resolution(
                    list(deals),
                    ending_balance=balance,
                )
                diag["session_trade_pnl"] = str(resolved["session_trade_pnl"])
                diag["pre_deposit_trade_pnl"] = str(
                    resolved["pre_deposit_trade_pnl"]
                )
                diag["post_deposit_trade_pnl"] = str(
                    resolved["post_deposit_trade_pnl"]
                )
                diag["new_capital_detected"] = bool(
                    resolved["new_capital_detected"]
                )
                if resolved.get("capital_baseline"):
                    diag["capital_baseline"] = resolved["capital_baseline"]
            except Exception as exc:
                logger.warning("ite_cycle_deposit_baseline_failed", error=str(exc))
        else:
            # Still refresh HWM from live equity; never invent flat daily PnL.
            peak_equity = tracker.observe_equity(login=login, equity=equity)
            if balance > peak_equity:
                peak_equity = tracker.observe_equity(login=login, equity=balance)
            # Fail closed this cycle. Do not write a fabricated -40% PnL onto
            # the account object — that value was treated as trusted by the
            # execution bridge and could arm a durable daily-loss latch.
            daily_pnl = Decimal("0")
            diag["daily_pnl_fail_closed"] = True
            logger.warning(
                "ite_cycle_daily_pnl_fail_closed",
                reason="history_deals_unavailable",
            )
        diag["peak_equity"] = str(peak_equity)
        diag["daily_pnl"] = str(daily_pnl) if daily_pnl_trusted else None
        diag["daily_pnl_trusted"] = daily_pnl_trusted
    except Exception as exc:
        logger.warning("ite_cycle_live_risk_resolve_failed", error=str(exc))
        diag["live_risk_resolve"] = f"ERROR: {exc}"
        diag["daily_pnl_fail_closed"] = True
        daily_pnl = Decimal("0")
        daily_pnl_trusted = False
        diag["daily_pnl"] = None
        diag["daily_pnl_trusted"] = False

    try:
        from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG
        from app.domain.institutional_trading.operations.control_plane import (
            get_control_plane,
        )
        from app.domain.institutional_trading.operations.daily_loss_lock import (
            sync_utc_daily_loss_lock,
        )

        lock = sync_utc_daily_loss_lock(
            get_control_plane(),
            daily_pnl=daily_pnl,
            equity=equity,
            balance=Decimal(str(diag.get("balance") or 0)),
            max_daily_loss_pct=Decimal(str(DEFAULT_ITE_CONFIG.max_daily_loss_pct)),
            trusted=bool(daily_pnl_trusted),
            floating_pnl=Decimal(str(diag.get("floating_pnl") or 0)),
        )
        diag.update(lock)
        if daily_pnl_trusted and diag.get("new_capital_detected"):
            diag["deposit_verification"] = "verified"
        elif daily_pnl_trusted and lock.get("daily_loss_exceeded"):
            diag["deposit_verification"] = "required"
        elif daily_pnl_trusted:
            diag["deposit_verification"] = "not_applicable"
        diag["max_daily_loss_limit_pct"] = str(DEFAULT_ITE_CONFIG.max_daily_loss_pct)
    except Exception as exc:
        logger.warning("ite_cycle_daily_loss_lock_sync_failed", error=str(exc))

    try:
        if isinstance(pre_orders, Exception):
            raise pre_orders
        if pre_orders == "N/A":
            diag["orders"] = "N/A"
        else:
            diag["orders"] = len(pre_orders or [])
    except Exception as exc:
        diag["orders"] = f"ERROR: {exc}"

    mid = None
    if quote_bid is not None and quote_ask is not None:
        mid = (quote_bid + quote_ask) / Decimal("2")
    elif quote_bid is not None:
        mid = quote_bid
    if mid is not None and mid <= 0:
        mid = None

    atr = None
    try:
        atr = getattr(snapshot, "entry_atr", None) or getattr(snapshot, "atr", None)
    except Exception:
        atr = None
    atr_dec = Decimal(str(atr)) if atr is not None else None
    try:
        entry_atr = getattr(snapshot, "entry_atr", None)
        analysis_atr = getattr(snapshot, "atr", None)
        if entry_atr is not None:
            diag["entry_atr"] = str(entry_atr)
        if analysis_atr is not None:
            diag["analysis_atr"] = str(analysis_atr)
            if "atr" not in diag:
                diag["atr"] = str(analysis_atr)
        if atr_dec is not None:
            diag["stop_atr"] = str(atr_dec)
    except Exception:
        pass

    open_n = open_positions if isinstance(open_positions, int) else 0
    # Incomplete book with opens: clear sides so pipeline fail-closes add-ons
    if open_n > 0 and not book_facts_ok:
        open_directions = []
        open_entries = []
        diag["book_facts_incomplete"] = True

    account = AccountRiskState(
        equity=equity,
        peak_equity=peak_equity if peak_equity > 0 else equity,
        daily_pnl=daily_pnl,
        weekly_pnl=Decimal("0"),
        open_positions=open_n,
        already_in_trade=open_n > 0,
        account_open_positions=int(diag.get("account_positions") or open_n),
        consecutive_losses=0,
        cooldown_active=False,
        cooldown_remaining_minutes=0,
        market_open=market_data_live,
        atr=atr_dec,
        mid_price=mid,
        free_margin=free_margin,
        open_directions=tuple(open_directions),
        open_entries=tuple(open_entries),
        balance=Decimal(str(diag.get("balance") or equity or 0)),
        used_margin=Decimal(str(diag.get("margin") or 0)),
        floating_pnl=Decimal(str(diag.get("floating_pnl") or 0)),
        leverage=(
            Decimal(str(diag.get("leverage")))
            if diag.get("leverage") not in (None, 0, "0")
            else None
        ),
        bid=quote_bid,
        ask=quote_ask,
        quote_age_seconds=quote_age_seconds,
    )

    # Sizing diagnostics (observational) — live broker volume_min/step when available.
    from app.domain.institutional_trading.ai_scalping.config import (
        DEFAULT_AI_SCALPING_CONFIG,
    )
    from app.domain.institutional_trading.atr import stop_distance_from_atr
    from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG
    from app.domain.trading.xauusd_specs import (
        CONTRACT_SIZE,
        VOLUME_MAX,
        VOLUME_MIN,
        VOLUME_STEP,
    )

    stop_dist = stop_distance_from_atr(
        atr_dec, multiplier=DEFAULT_AI_SCALPING_CONFIG.stop_atr_mult
    )
    risk_pct = DEFAULT_ITE_CONFIG.risk_per_trade_pct
    risk_budget = (equity * (risk_pct / Decimal("100"))).quantize(Decimal("0.01"))
    contract_size = CONTRACT_SIZE
    lot_step = VOLUME_STEP
    min_lot = VOLUME_MIN
    max_lot = VOLUME_MAX
    tick_size = None
    tick_value = None
    specs_source = "xauusd_specs_fallback"
    try:
        spec = None if isinstance(pre_specs, Exception) else pre_specs
        if spec is not None:
            vmin = Decimal(str(getattr(spec, "volume_min", None) or VOLUME_MIN))
            vstep = Decimal(str(getattr(spec, "volume_step", None) or VOLUME_STEP))
            vmax = Decimal(str(getattr(spec, "volume_max", None) or VOLUME_MAX))
            cs = Decimal(str(getattr(spec, "contract_size", None) or CONTRACT_SIZE))
            if vmin > 0:
                min_lot = vmin
            if vstep > 0:
                lot_step = vstep
            if vmax > 0:
                max_lot = vmax
            if cs > 0:
                contract_size = cs
            specs_source = "live_broker"
            trade_mode = str(getattr(spec, "trade_mode", "") or "")
            trade_allowed = getattr(spec, "trade_allowed", None)
            spec_market_open = getattr(spec, "market_open", None)
            diag["symbol_trade_mode"] = trade_mode
            diag["symbol_trade_allowed"] = trade_allowed
            diag["symbol_market_open"] = spec_market_open
            diag["trade_mode"] = trade_mode
            diag["trade_allowed"] = trade_allowed
            ts = getattr(spec, "trade_tick_size", None) or getattr(
                spec, "tick_size", None
            )
            tv = getattr(spec, "trade_tick_value", None) or getattr(
                spec, "tick_value", None
            )
            if ts not in (None, "", 0, "0"):
                tick_size = Decimal(str(ts))
            if tv not in (None, "", 0, "0"):
                tick_value = Decimal(str(tv))
    except Exception as exc:
        logger.debug("ite_cycle_live_lot_specs_failed", error=str(exc))

    raw_lots: Decimal | None = None
    calc_lots: Decimal | None = None
    sizing_status = "unavailable"
    if stop_dist is not None and stop_dist > 0 and contract_size > 0:
        from app.domain.institutional_trading.operations.min_lot_feasibility import (
            STATUS_BELOW_MIN,
            STATUS_EXCEEDS_BUDGET,
            STATUS_INVALID_SPEC,
            normalize_lots_against_broker,
        )

        raw_lots = risk_budget / (stop_dist * contract_size)
        norm = normalize_lots_against_broker(
            calculated_lot=raw_lots,
            min_lot=min_lot,
            lot_step=lot_step,
            max_lot=max_lot,
            equity=equity,
            stop_distance=stop_dist,
            contract_size=contract_size,
            risk_budget=risk_budget,
            tick_size=tick_size,
            tick_value=tick_value,
        )
        calc_lots = norm.normalized_lot if norm.approved else Decimal("0")
        sizing_status = norm.sizing_status
        diag.update(norm.to_observability())
        from app.domain.institutional_trading.operations.min_lot_feasibility import (
            CODE_MIN_LOT_EXCEEDS_RISK_BUDGET,
            EXEC_WAITING_FOR_SETUP,
            NOT_TRADEABLE,
            TRADEABLE,
            evaluate_setup_tradeability,
        )

        trade = evaluate_setup_tradeability(
            stop_distance=stop_dist,
            equity=equity,
            min_lot=min_lot,
            lot_step=lot_step,
            max_lot=max_lot,
            contract_size=contract_size,
            tick_size=tick_size,
            tick_value=tick_value,
        )
        trade_obs = trade.to_observability()
        trade_obs.pop("risk_budget", None)
        diag.update(trade_obs)
        if not norm.approved:
            diag["rejection_reason"] = norm.block_reason
            diag["signal_state"] = "VALID_SIGNAL"
            diag["execution_state"] = "EXECUTION_BLOCKED"
            if norm.sizing_status in {STATUS_BELOW_MIN, STATUS_EXCEEDS_BUDGET}:
                diag["block_reason"] = norm.block_reason
            if norm.block_reason == CODE_MIN_LOT_EXCEEDS_RISK_BUDGET:
                diag["execution_status"] = EXEC_WAITING_FOR_SETUP
                diag["tradeability"] = NOT_TRADEABLE
        else:
            diag["rejection_reason"] = None
            diag["block_reason"] = None
            if trade.tradeability == TRADEABLE:
                diag["execution_status"] = TRADEABLE
        if sizing_status == STATUS_INVALID_SPEC:
            diag["signal_state"] = "VALID_SIGNAL"
            diag["execution_state"] = "EXECUTION_BLOCKED"

    diag["atr"] = str(atr_dec) if atr_dec is not None else None
    diag["stop_distance"] = str(stop_dist) if stop_dist is not None else None
    diag["risk_budget"] = str(diag.get("risk_budget") or risk_budget)
    diag["risk_amount"] = str(diag.get("estimated_risk_amount") or risk_budget)
    diag["risk_pct"] = str(risk_pct)
    diag["raw_lots"] = str(raw_lots) if raw_lots is not None else None
    diag["raw_volume"] = str(raw_lots) if raw_lots is not None else None
    diag["calculated_lots"] = str(calc_lots) if calc_lots is not None else None
    diag["calculated_lot"] = str(diag.get("calculated_lot") or raw_lots or "")
    diag["normalized_volume"] = str(diag.get("normalized_lot") or calc_lots or "")
    diag["final_volume"] = str(calc_lots) if calc_lots is not None else None
    diag["broker_min_lot"] = str(diag.get("broker_min_lot") or min_lot)
    diag["volume_min"] = str(min_lot)
    diag["broker_lot_step"] = str(diag.get("broker_lot_step") or lot_step)
    diag["volume_step"] = str(lot_step)
    diag["broker_max_lot"] = str(diag.get("broker_max_lot") or max_lot)
    diag["volume_max"] = str(max_lot)
    diag["contract_size"] = str(contract_size)
    diag["lot_specs_source"] = specs_source
    diag["sizing_status"] = sizing_status
    if "rejection_reason" not in diag:
        diag["rejection_reason"] = None

    from app.application.services.market_closed_cooldown import is_market_closed_cooled
    from app.domain.institutional_trading.operations.broker_session_truth import (
        overlay_snapshot_session,
        resolve_from_diagnostics,
    )

    utc_sess = str(diag.get("trading_session") or "off_hours")
    session_obs = resolve_from_diagnostics(
        diag,
        utc_session=utc_sess,
        symbol_tradable=bool(market_data_live),
        market_data_live=bool(market_data_live),
        cooled=is_market_closed_cooled(symbol),
    )
    snapshot = overlay_snapshot_session(
        snapshot, broker_open=session_obs.broker_session_open
    )
    diag.update(session_obs.to_dict())
    diag["broker_session_open"] = session_obs.broker_session_open
    sess = getattr(snapshot, "session", None)
    diag["session_allowed"] = bool(getattr(sess, "allowed", False))

    diag["reason"] = "market context ready"
    diag["snapshot"] = "OK"
    diag.update(health_diag_box)
    if isinstance(pre_health, Exception):
        mt5_at = None
        diag["autotrading_health_error"] = str(pre_health)
    else:
        mt5_at = pre_health
    if mt5_at is None:
        # Unknown → fail-closed for safety gate (same as orchestrator).
        diag["mt5_autotrading_enabled"] = False
        diag["mt5_autotrading_source"] = "unknown_fail_closed"
        mt5_at = False
    built_at = datetime.now(UTC).isoformat()
    ctx = IteCycleMarketContext(
        ok=True,
        snapshot=snapshot,
        account=account,
        reason="market context ready",
        market_data_live=market_data_live,
        account_trading_enabled=account_trading_enabled,
        mt5_autotrading_enabled=bool(mt5_at),
        symbol_tradable=market_data_live,
        # Known account + trading enabled ⇒ no restriction evidence; else fail closed
        no_broker_restrictions=bool(account_trading_enabled),
        spread=spread,
        latency_ms=(time.perf_counter() - t0) * 1000.0,
        bars_loaded=bars_loaded,
        diagnostics=diag,
        reused=False,
        snapshot_built_at=built_at,
    )
    _remember_cycle_market_context(
        ctx,
        symbol,
        logical_symbol,
        canonical_symbol,
        diag.get("canonical_broker_symbol"),
        diag.get("logical_symbol"),
    )
    return ctx
