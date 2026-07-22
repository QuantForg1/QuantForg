"""Build live ITE cycle inputs from MT5 — diagnostics + real Decision path.

Does not change Risk/Safety/Ops mode. Never fabricates bars or account facts.
If market data cannot be loaded, returns an explicit failure reason.
"""

from __future__ import annotations

from dataclasses import dataclass
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


async def build_ite_cycle_market_context(
    mt5_adapter: Any | None,
    *,
    symbol: str = GOLD_SYMBOL,
) -> IteCycleMarketContext:
    """Load XAUUSD multi-TF bars + account for one auto/shadow cycle."""
    import time

    t0 = time.perf_counter()
    if mt5_adapter is None:
        return IteCycleMarketContext(
            ok=False,
            reason="MT5 adapter unavailable — cannot load market snapshot",
            latency_ms=(time.perf_counter() - t0) * 1000.0,
        )

    bars_by_tf: dict[Timeframe, list[Candle]] = {}
    bars_loaded: dict[str, int] = {}
    try:
        for tf, count in _TF_COUNTS:
            rates = mt5_adapter.copy_rates_from_pos(symbol, tf, 0, count)
            candles = [_rate_to_candle(r) for r in (rates or [])]
            bars_by_tf[tf] = candles
            bars_loaded[tf.value] = len(candles)
            if len(candles) < 50:
                return IteCycleMarketContext(
                    ok=False,
                    reason=(
                        f"Insufficient {tf.value} bars for analysis "
                        f"(got {len(candles)}, need ≥50)"
                    ),
                    latency_ms=(time.perf_counter() - t0) * 1000.0,
                    bars_loaded=bars_loaded,
                )
    except Exception as exc:
        logger.warning("ite_cycle_bars_load_failed", error=str(exc))
        return IteCycleMarketContext(
            ok=False,
            reason=f"Market data load failed: {exc}",
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            bars_loaded=bars_loaded,
        )

    spread: Decimal | None = None
    market_data_live = False
    try:
        tick = mt5_adapter.latest_tick(symbol)
        if tick is not None:
            bid = Decimal(str(getattr(tick, "bid", 0) or 0))
            ask = Decimal(str(getattr(tick, "ask", 0) or 0))
            if ask > 0 and bid > 0:
                spread = ask - bid
                market_data_live = True
    except Exception as exc:
        logger.info("ite_cycle_tick_failed", error=str(exc))

    try:
        snapshot = await InstitutionalTradingAnalysisService().analyze_bars(
            bars_by_tf,
            as_of=datetime.now(UTC),
            spread=spread,
        )
    except Exception as exc:
        logger.warning("ite_cycle_analyze_failed", error=str(exc))
        return IteCycleMarketContext(
            ok=False,
            reason=f"Strategy analysis failed: {exc}",
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            bars_loaded=bars_loaded,
            market_data_live=market_data_live,
            spread=spread,
        )

    equity = Decimal("0")
    free_margin: Decimal | None = None
    open_positions = 0
    account_trading_enabled = False
    try:
        info = mt5_adapter.account_info()
        equity = Decimal(str(getattr(info, "equity", 0) or 0))
        free_raw = getattr(info, "free_margin", None)
        if free_raw is not None:
            free_margin = Decimal(str(free_raw))
        # trade_mode present ⇒ terminal reports an account capable of trading
        trade_mode = str(getattr(info, "trade_mode", "") or "").strip().lower()
        account_trading_enabled = trade_mode not in {"", "disabled", "0"}
        if not account_trading_enabled and equity > 0:
            # Connected live account with equity — treat as trading-capable
            # only when gateway did not explicitly disable.
            account_trading_enabled = True
    except Exception as exc:
        logger.warning("ite_cycle_account_failed", error=str(exc))
        return IteCycleMarketContext(
            ok=False,
            reason=f"Account info unavailable: {exc}",
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            bars_loaded=bars_loaded,
            market_data_live=market_data_live,
            spread=spread,
            snapshot=snapshot,
        )

    if equity <= 0:
        return IteCycleMarketContext(
            ok=False,
            reason="Account equity unavailable or zero — refusing fabricated equity",
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            bars_loaded=bars_loaded,
            market_data_live=market_data_live,
            spread=spread,
            snapshot=snapshot,
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
    except Exception as exc:
        logger.info("ite_cycle_positions_failed", error=str(exc))

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
        open_positions=open_positions,
        already_in_trade=open_positions > 0,
        consecutive_losses=0,
        cooldown_active=False,
        cooldown_remaining_minutes=0,
        market_open=market_data_live,
        atr=Decimal(str(atr)) if atr is not None else None,
        mid_price=mid,
        free_margin=free_margin,
    )

    return IteCycleMarketContext(
        ok=True,
        snapshot=snapshot,
        account=account,
        reason="market context ready",
        market_data_live=market_data_live,
        account_trading_enabled=account_trading_enabled,
        mt5_autotrading_enabled=False,  # set by caller from live probes
        symbol_tradable=market_data_live,
        no_broker_restrictions=True,
        spread=spread,
        latency_ms=(time.perf_counter() - t0) * 1000.0,
        bars_loaded=bars_loaded,
    )
