"""Institutional Alpha Engine application service — scan / dashboard / mode."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Any

from app.domain.institutional_trading.alpha_engine import (
    DEFAULT_ALPHA_CONFIG,
    DEFAULT_ALPHA_UNIVERSE,
    InstitutionalAlphaConfig,
    SymbolMarketFacts,
    correlation_matrix,
    get_alpha_analytics_store,
    get_smart_recovery,
    scan_universe,
)
from app.domain.institutional_trading.ai_scalping.session_intelligence import (
    assess_session,
)
from core.logging import get_logger

logger = get_logger(__name__)

_ACTIVE_CONFIG = replace(DEFAULT_ALPHA_CONFIG)


def get_alpha_config() -> InstitutionalAlphaConfig:
    return _ACTIVE_CONFIG


def set_alpha_enabled(enabled: bool, *, universe: tuple[str, ...] | None = None) -> InstitutionalAlphaConfig:
    global _ACTIVE_CONFIG
    _ACTIVE_CONFIG = replace(
        _ACTIVE_CONFIG,
        enabled=bool(enabled),
        universe=universe or _ACTIVE_CONFIG.universe or DEFAULT_ALPHA_UNIVERSE,
    )
    logger.warning(
        "institutional_alpha_mode",
        enabled=_ACTIVE_CONFIG.enabled,
        universe=list(_ACTIVE_CONFIG.universe),
    )
    return _ACTIVE_CONFIG


def _facts_from_runtime_symbol(
    symbol: str,
    *,
    mt5_adapter: Any | None,
    session: str,
    fallback_confidence: int = 55,
) -> SymbolMarketFacts:
    """Build ranking facts from live MT5 when available — never invent prices."""
    mid = None
    spread = None
    atr = None
    direction = "NONE"
    reasons: list[str] = []
    trend = momentum = liquidity = volatility = fallback_confidence
    conf = fallback_confidence

    if mt5_adapter is not None:
        try:
            tick = mt5_adapter.latest_tick(symbol)
            if tick is not None:
                bid = Decimal(str(getattr(tick, "bid", 0) or 0))
                ask = Decimal(str(getattr(tick, "ask", 0) or 0))
                if bid > 0 and ask > 0:
                    mid = (bid + ask) / Decimal("2")
                    spread = ask - bid
                    reasons.append(f"{symbol} tick live")
        except Exception as exc:
            reasons.append(f"{symbol} tick unavailable: {exc}")

        try:
            # Lightweight ATR proxy from M5 bars when present
            from app.domain.market_data.timeframe import Timeframe

            rates = mt5_adapter.copy_rates_from_pos(symbol, Timeframe.M5, 0, 40)
            if rates and len(rates) >= 20:
                ranges = []
                for r in rates[-20:]:
                    hi = Decimal(str(getattr(r, "high", 0) or 0))
                    lo = Decimal(str(getattr(r, "low", 0) or 0))
                    if hi > lo:
                        ranges.append(hi - lo)
                if ranges:
                    atr = sum(ranges) / Decimal(len(ranges))
                    # Momentum from last vs prior mid closes
                    c0 = Decimal(str(getattr(rates[-1], "close", 0) or 0))
                    c1 = Decimal(str(getattr(rates[-10], "close", 0) or 0))
                    if c0 > 0 and c1 > 0:
                        chg = (c0 - c1) / c1
                        if chg > Decimal("0.0005"):
                            direction = "BUY"
                            momentum = 70
                            trend = 68
                        elif chg < Decimal("-0.0005"):
                            direction = "SELL"
                            momentum = 70
                            trend = 68
                        else:
                            momentum = 45
                            trend = 45
                    volatility = 65 if atr and mid and (atr / mid) > Decimal("0.001") else 50
                    reasons.append(f"{symbol} M5 structure sampled")
        except Exception as exc:
            reasons.append(f"{symbol} bars unavailable: {exc}")

    sess = assess_session(session)
    if mid is None:
        # Prefer No Trade — keep direction NONE when no live mid
        direction = "NONE"
        conf = max(0, conf - 20)
        reasons.append("No live mid — not executable")

    # Liquidity heuristic: tight relative spread → higher
    liquidity = 55
    if spread is not None and mid is not None and mid > 0:
        rel = float(spread / mid)
        liquidity = 85 if rel < 0.0002 else (65 if rel < 0.0008 else 40)

    # Confidence blend
    if direction in {"BUY", "SELL"} and mid is not None:
        conf = min(100, int((trend + momentum + liquidity + sess.stars * 12) / 4))

    rr = Decimal("1.5")
    if volatility >= 65:
        rr = Decimal("1.8")

    return SymbolMarketFacts(
        symbol=symbol,
        mid=mid,
        spread=spread,
        atr=atr,
        session=session,
        trend_strength=trend,
        momentum=momentum,
        liquidity=liquidity,
        volatility=volatility,
        ai_confidence=conf,
        expected_rr=rr,
        direction=direction,
        reasons=tuple(reasons),
    )


def run_alpha_scan(
    *,
    mt5_adapter: Any | None = None,
    open_symbols: list[str] | None = None,
    session: str = "london",
    daily_risk_used_pct: Decimal = Decimal("0"),
    account_exposure_pct: Decimal = Decimal("0"),
    drawdown_pct: Decimal = Decimal("0"),
    config: InstitutionalAlphaConfig | None = None,
) -> dict[str, Any]:
    cfg = config or get_alpha_config()
    facts = [
        _facts_from_runtime_symbol(sym, mt5_adapter=mt5_adapter, session=session)
        for sym in cfg.universe
    ]
    result = scan_universe(
        facts,
        open_symbols=open_symbols or (),
        daily_risk_used_pct=daily_risk_used_pct,
        account_exposure_pct=account_exposure_pct,
        drawdown_pct=drawdown_pct,
        config=cfg,
    )
    return result.to_dict()


def build_alpha_dashboard(
    *,
    mt5_adapter: Any | None = None,
    open_symbols: list[str] | None = None,
    session: str = "london",
    equity: Decimal | None = None,
    daily_pnl: Decimal | None = None,
) -> dict[str, Any]:
    cfg = get_alpha_config()
    open_syms = list(open_symbols or [])
    exposure = Decimal("0")
    if equity and equity > 0 and open_syms:
        # Approximate: each open leg counts toward exposure bucket
        exposure = (Decimal(len(open_syms)) * Decimal("1.0")).quantize(Decimal("0.01"))
    daily_risk = Decimal("0")
    if equity and equity > 0 and daily_pnl is not None and daily_pnl < 0:
        daily_risk = (abs(daily_pnl) / equity * Decimal("100")).quantize(Decimal("0.01"))

    scan = run_alpha_scan(
        mt5_adapter=mt5_adapter,
        open_symbols=open_syms,
        session=session,
        daily_risk_used_pct=daily_risk,
        account_exposure_pct=exposure,
    )
    analytics = get_alpha_analytics_store().summary()
    matrix = correlation_matrix(list(cfg.universe), config=cfg)
    conf_by_symbol = {
        o["symbol"]: o["ai_confidence"] for o in scan.get("opportunities", [])
    }
    return {
        "enabled": cfg.enabled,
        "config": cfg.to_dict(),
        "opportunity_ranking": scan.get("opportunities", []),
        "selected": scan.get("selected", []),
        "correlation_blocks": scan.get("correlation_blocks", []),
        "correlation_matrix": matrix,
        "ai_confidence_by_symbol": conf_by_symbol,
        "portfolio_risk_pct": scan.get("portfolio_risk_pct"),
        "daily_risk_used_pct": str(daily_risk),
        "recovery": get_smart_recovery().snapshot(),
        "analytics": analytics,
        "performance": {
            "daily": analytics.get("daily_pnl"),
            "weekly": analytics.get("weekly_pnl"),
            "monthly": analytics.get("monthly_pnl"),
            "win_rate": analytics.get("win_rate"),
            "avg_rr": analytics.get("avg_rr"),
            "avg_hold_minutes": analytics.get("avg_hold_minutes"),
        },
        "scan": scan,
    }
