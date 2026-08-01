"""Trading effectiveness — real production evidence only; never fabricate."""

from __future__ import annotations

from typing import Any

from app.domain.continuous_improvement.persistence import utc_iso


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _read_diagnostics_stats() -> dict[str, Any]:
    try:
        from app.application.services.strategy_diagnostics import (
            get_strategy_diagnostics_store,
        )

        store = get_strategy_diagnostics_store()
        snap = store.snapshot() if hasattr(store, "snapshot") else None
        if isinstance(snap, dict):
            return snap.get("statistics") or {}
        if snap is not None and hasattr(snap, "statistics"):
            stats = getattr(snap, "statistics", None)
            return stats if isinstance(stats, dict) else {}
        # Some stores expose get_latest / latest
        latest = getattr(store, "latest", None)
        if callable(latest):
            row = latest()
            if isinstance(row, dict):
                return row.get("statistics") or {}
    except Exception:
        return {}
    return {}


def _read_institutional_kpis() -> dict[str, Any]:
    try:
        from app.domain.institutional_trading.ai_scalping import (
            institutional_performance_kpis as kpis_mod,
        )

        build_institutional_performance_kpis = (
            kpis_mod.build_institutional_performance_kpis
        )

        pack = build_institutional_performance_kpis()
        return pack if isinstance(pack, dict) else {}
    except Exception:
        return {}


def build_trading_effectiveness() -> dict[str, Any]:
    """Aggregate live trading effectiveness — null when unmeasured."""
    stats = _read_diagnostics_stats()
    kpis = _read_institutional_kpis()

    signals_generated = _int(
        stats.get("signals_generated")
        or stats.get("cycle_count")
        or kpis.get("signals_generated")
    )
    signals_rejected = _int(
        stats.get("signals_rejected")
        or stats.get("no_trade_count")
        or kpis.get("signals_rejected")
    )
    signals_approved = _int(
        stats.get("signals_approved")
        or stats.get("forwarded_count")
        or kpis.get("signals_approved")
    )
    trades_opened = _int(
        stats.get("trades_opened")
        or stats.get("oms_requests")
        or stats.get("trades")
        or kpis.get("trades_opened")
        or kpis.get("trade_count")
    )
    trades_closed = _int(
        stats.get("trades_closed")
        or kpis.get("trades_closed")
        or kpis.get("closed_trades")
        or kpis.get("sample_size")
    )

    win_rate = _num(
        stats.get("win_rate")
        if stats.get("win_rate") is not None
        else kpis.get("win_rate")
    )
    loss_rate: float | None = None
    if win_rate is not None:
        loss_rate = round(max(0.0, 1.0 - win_rate), 6)
    elif kpis.get("loss_rate") is not None:
        loss_rate = _num(kpis.get("loss_rate"))

    average_rr = _num(
        stats.get("average_rr")
        if stats.get("average_rr") is not None
        else kpis.get("average_rr")
    )
    profit_factor = _num(
        stats.get("profit_factor")
        if stats.get("profit_factor") is not None
        else kpis.get("profit_factor")
    )
    expectancy = _num(
        stats.get("expectancy")
        if stats.get("expectancy") is not None
        else kpis.get("expectancy")
    )

    measured_fields = [
        k
        for k, v in {
            "signals_generated": signals_generated,
            "signals_rejected": signals_rejected,
            "signals_approved": signals_approved,
            "trades_opened": trades_opened,
            "trades_closed": trades_closed,
            "win_rate": win_rate,
            "loss_rate": loss_rate,
            "average_rr": average_rr,
            "profit_factor": profit_factor,
            "expectancy": expectancy,
        }.items()
        if v is not None
    ]

    return {
        "as_of": utc_iso(),
        "signals_generated": signals_generated,
        "signals_rejected": signals_rejected,
        "signals_approved": signals_approved,
        "trades_opened": trades_opened,
        "trades_closed": trades_closed,
        "win_rate": win_rate,
        "loss_rate": loss_rate,
        "average_rr": average_rr,
        "profit_factor": profit_factor,
        "expectancy": expectancy,
        "measured_fields": measured_fields,
        "measured_count": len(measured_fields),
        "sources": {
            "strategy_diagnostics": bool(stats),
            "institutional_kpis": bool(kpis),
        },
        "note": "Null means not measured from production evidence — never fabricated",
        "fabricated": False,
        "observe_only": True,
    }
