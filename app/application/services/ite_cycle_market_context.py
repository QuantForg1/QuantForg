"""Build live ITE cycle inputs from MT5 — diagnostics + real Decision path.

Does not change Risk/Safety/Ops mode. Never fabricates bars or account facts.
If market data cannot be loaded, returns an explicit failure reason.
"""

from __future__ import annotations

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

_TF_COUNTS: tuple[tuple[Timeframe, int], ...] = (
    (Timeframe.H4, 180),
    (Timeframe.H1, 300),
    (Timeframe.M15, 300),
    (Timeframe.M5, 400),
    (Timeframe.M1, 500),
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
            "symbol": (
                getattr(self.snapshot, "symbol", None)
                if self.snapshot is not None
                else None
            ),
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


async def build_ite_cycle_market_context(
    mt5_adapter: Any | None,
    *,
    symbol: str = GOLD_SYMBOL,
    position_engine: Any | None = None,
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
                Decimal(str(diag["spread"])) if diag.get("spread") is not None else None
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

    # Multi-symbol: broker terminal may use USTEC/DJ30/DE40 instead of
    # NAS100/US30/GER40 — try candidates before failing the scan.
    from app.domain.institutional_trading.ai_scalping.asset_class import (
        broker_symbol_candidates,
    )

    symbol_candidates = broker_symbol_candidates(symbol) or (symbol,)
    resolved_symbol = symbol
    bars_by_tf: dict[Timeframe, list[Candle]] = {}
    bars_loaded: dict[str, int] = {}
    last_bar_exc: Exception | None = None
    for candidate in symbol_candidates:
        bars_by_tf = {}
        bars_loaded = {}
        try:
            for tf, count in _TF_COUNTS:
                rates = mt5_adapter.copy_rates_from_pos(candidate, tf, 0, count)
                candles = [_rate_to_candle(r) for r in (rates or [])]
                bars_by_tf[tf] = candles
                bars_loaded[tf.value] = len(candles)
                diag["bars"][tf.value] = {
                    "requested": count,
                    "loaded": len(candles),
                    "ok": len(candles) >= 50,
                }
                if len(candles) < 50:
                    raise RuntimeError(
                        f"Insufficient {tf.value} bars for analysis "
                        f"(got {len(candles)}, need ≥50)"
                    )
            resolved_symbol = candidate
            last_bar_exc = None
            break
        except Exception as exc:
            last_bar_exc = exc
            continue
    if last_bar_exc is not None or not bars_by_tf:
        logger.warning(
            "ite_cycle_bars_load_failed",
            error=str(last_bar_exc),
            symbol=symbol,
            tried=list(symbol_candidates),
        )
        return _fail(
            f"Market data load failed: {last_bar_exc}",
            bars=bars_loaded,
            broker_symbol_tried=list(symbol_candidates),
        )
    if resolved_symbol != symbol:
        diag["broker_symbol_resolved"] = resolved_symbol
        diag["requested_symbol"] = symbol
        symbol = resolved_symbol
        diag["symbol"] = symbol

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
                ts.isoformat()
                if ts is not None and hasattr(ts, "isoformat")
                else str(ts or "")
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

    try:
        from app.application.services.mt5_position_truth import force_sync_positions

        # Force Sync Positions — never trust a cached open count alone.
        sync = force_sync_positions(
            mt5_adapter,
            symbol=symbol,
            position_engine=position_engine,
        )
        open_positions = int(sync.mt5_positions)
        diag["positions"] = open_positions
        diag["mt5_positions"] = sync.mt5_positions
        diag["internal_positions"] = sync.internal_positions
        diag["position_truth_repaired"] = sync.repaired
        diag["position_tickets"] = list(sync.tickets)
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

    # Book facts for duplicate / add-on guards (all symbols on MT5)
    open_directions: list[str] = []
    open_entries: list[Decimal] = []
    book_facts_ok = False
    try:
        rows = mt5_adapter.list_positions()
        for p in rows or []:
            side = str(getattr(p, "side", "") or "").strip().upper()
            if side in {"BUY", "SELL"}:
                open_directions.append(side)
            try:
                entry_px = Decimal(str(getattr(p, "open_price", 0) or 0))
            except Exception:
                entry_px = Decimal("0")
            if entry_px > 0:
                open_entries.append(entry_px)
        diag["open_directions"] = list(open_directions)
        diag["open_entries"] = [str(e) for e in open_entries]
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
            get_live_account_risk_tracker,
        )
        from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG

        login = int(diag.get("login") or 0)
        balance = Decimal(str(diag.get("balance") or 0))
        deals: list[Any] | None = None
        deals_fetch_ok = False
        try:
            day_start = datetime.now(UTC).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            hist = getattr(mt5_adapter, "history_deals", None)
            if callable(hist):
                deals = list(
                    hist(
                        date_from=day_start,
                        date_to=datetime.now(UTC) + timedelta(days=1),
                    )
                )
                deals_fetch_ok = True
            else:
                client = _client_of(mt5_adapter)
                hist_c = getattr(client, "history_deals", None)
                if callable(hist_c):
                    deals = list(
                        hist_c(
                            date_from=day_start,
                            date_to=datetime.now(UTC) + timedelta(days=1),
                        )
                    )
                    deals_fetch_ok = True
                else:
                    diag["history_deals"] = "UNAVAILABLE"
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
        else:
            # Still refresh HWM from live equity; never invent flat daily PnL.
            peak_equity = tracker.observe_equity(login=login, equity=equity)
            if balance > peak_equity:
                peak_equity = tracker.observe_equity(login=login, equity=balance)
            max_dd = Decimal(str(DEFAULT_ITE_CONFIG.max_daily_loss_pct))
            # Fail closed: trip daily-loss gate until deals can be read.
            daily_pnl = -(equity * max_dd / Decimal("100"))
            diag["daily_pnl_fail_closed"] = True
            logger.warning(
                "ite_cycle_daily_pnl_fail_closed",
                reason="history_deals_unavailable",
                daily_pnl=str(daily_pnl),
            )
        diag["peak_equity"] = str(peak_equity)
        diag["daily_pnl"] = str(daily_pnl)
        diag["daily_pnl_trusted"] = daily_pnl_trusted
    except Exception as exc:
        logger.warning("ite_cycle_live_risk_resolve_failed", error=str(exc))
        diag["live_risk_resolve"] = f"ERROR: {exc}"
        diag["daily_pnl_fail_closed"] = True
        from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG

        max_dd = Decimal(str(DEFAULT_ITE_CONFIG.max_daily_loss_pct))
        daily_pnl = -(equity * max_dd / Decimal("100"))
        daily_pnl_trusted = False

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
    atr_dec = Decimal(str(atr)) if atr is not None else None

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
    )

    # Sizing diagnostics (observational) — live broker volume_min/step when available.
    from decimal import ROUND_DOWN

    from app.domain.institutional_trading.atr import stop_distance_from_atr
    from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG
    from app.domain.trading.xauusd_specs import CONTRACT_SIZE, VOLUME_MIN, VOLUME_STEP

    stop_dist = stop_distance_from_atr(atr_dec)
    risk_pct = DEFAULT_ITE_CONFIG.risk_per_trade_pct
    risk_budget = (equity * (risk_pct / Decimal("100"))).quantize(Decimal("0.01"))
    contract_size = CONTRACT_SIZE
    lot_step = VOLUME_STEP
    min_lot = VOLUME_MIN
    specs_source = "xauusd_specs_fallback"
    try:
        client = getattr(mt5_adapter, "client", None) or getattr(
            mt5_adapter, "_client", None
        )
        if client is not None and hasattr(client, "symbol_info"):
            spec = client.symbol_info(symbol)
            if spec is not None:
                vmin = Decimal(str(getattr(spec, "volume_min", None) or VOLUME_MIN))
                vstep = Decimal(str(getattr(spec, "volume_step", None) or VOLUME_STEP))
                cs = Decimal(str(getattr(spec, "contract_size", None) or CONTRACT_SIZE))
                if vmin > 0:
                    min_lot = vmin
                if vstep > 0:
                    lot_step = vstep
                if cs > 0:
                    contract_size = cs
                specs_source = "live_broker"
    except Exception as exc:
        logger.debug("ite_cycle_live_lot_specs_failed", error=str(exc))

    raw_lots: Decimal | None = None
    calc_lots: Decimal | None = None
    sizing_status = "unavailable"
    if stop_dist is not None and stop_dist > 0 and contract_size > 0:
        raw_lots = risk_budget / (stop_dist * contract_size)
        quantized = raw_lots.quantize(lot_step, rounding=ROUND_DOWN)
        if quantized < min_lot:
            calc_lots = Decimal("0")
            sizing_status = "below_min_lot"
        else:
            calc_lots = quantized
            sizing_status = "tradable"

    diag["atr"] = str(atr_dec) if atr_dec is not None else None
    diag["stop_distance"] = str(stop_dist) if stop_dist is not None else None
    diag["risk_budget"] = str(risk_budget)
    diag["risk_pct"] = str(risk_pct)
    diag["raw_lots"] = str(raw_lots) if raw_lots is not None else None
    diag["calculated_lots"] = str(calc_lots) if calc_lots is not None else None
    diag["broker_min_lot"] = str(min_lot)
    diag["broker_lot_step"] = str(lot_step)
    diag["contract_size"] = str(contract_size)
    diag["lot_specs_source"] = specs_source
    diag["sizing_status"] = sizing_status

    diag["reason"] = "market context ready"
    diag["snapshot"] = "OK"
    # Terminal AutoTrading — must not hardcode False when /health reports true.
    mt5_at = _read_mt5_autotrading_enabled(mt5_adapter, diag)
    if mt5_at is None:
        # Unknown → fail-closed for safety gate (same as orchestrator).
        diag["mt5_autotrading_enabled"] = False
        diag["mt5_autotrading_source"] = "unknown_fail_closed"
        mt5_at = False
    return IteCycleMarketContext(
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
    )
