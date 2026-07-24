"""RC validation metrics — consecutive days, uptime, latency, errors."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_trading.release_candidate.config import (
    DEFAULT_RC1_CONFIG,
)
from core.logging import get_logger

logger = get_logger(__name__)


def build_rc_validation() -> dict[str, Any]:
    """Track evidence for release candidate validation. Observational only."""
    metrics: dict[str, Any] = {
        "consecutive_successful_trading_days": 0,
        "system_uptime_pct": None,
        "gateway_uptime_pct": None,
        "oms_uptime_pct": None,
        "database_uptime_pct": None,
        "average_latency_ms": None,
        "average_slippage": None,
        "error_rate": None,
        "broker_rejects": None,
        "retry_rate": None,
    }

    try:
        from app.domain.institutional_trading.reliability.platform import (
            get_reliability_platform,
        )

        platform = get_reliability_platform()
        dash = platform.dashboard() if hasattr(platform, "dashboard") else {}
        if isinstance(dash, dict):
            metrics["system_uptime_pct"] = dash.get("uptime_pct", dash.get("system_uptime_pct"))
            net = dash.get("network") or {}
            if isinstance(net, dict):
                metrics["gateway_uptime_pct"] = net.get("gateway_uptime_pct", net.get("uptime_pct"))
            metrics["error_rate"] = dash.get("error_rate")
    except Exception:
        logger.exception("rc_validation_reliability_failed")

    try:
        from app.domain.institutional_trading.ai_validation import (
            get_execution_quality_monitor,
        )

        eq = get_execution_quality_monitor().snapshot()
        if isinstance(eq, dict):
            metrics["average_latency_ms"] = eq.get("avg_latency_ms", eq.get("latency_ms"))
            metrics["average_slippage"] = eq.get("avg_slippage", eq.get("slippage"))
            metrics["broker_rejects"] = eq.get("broker_rejects", eq.get("rejects"))
            metrics["retry_rate"] = eq.get("retry_rate")
    except Exception:
        pass

    try:
        from app.domain.institutional_trading.production_hardening.performance import (
            get_live_performance_monitor,
        )

        mon = get_live_performance_monitor().snapshot()
        if isinstance(mon, dict):
            metrics["consecutive_successful_trading_days"] = int(
                mon.get("consecutive_successful_days")
                or mon.get("consecutive_days")
                or 0
            )
            if metrics["oms_uptime_pct"] is None:
                metrics["oms_uptime_pct"] = mon.get("oms_uptime_pct")
            if metrics["database_uptime_pct"] is None:
                metrics["database_uptime_pct"] = mon.get("database_uptime_pct")
    except Exception:
        pass

    days = int(metrics["consecutive_successful_trading_days"] or 0)
    evidence_ok = days >= DEFAULT_RC1_CONFIG.min_consecutive_trading_days

    return {
        "metrics": metrics,
        "evidence": {
            "min_days": DEFAULT_RC1_CONFIG.min_consecutive_trading_days,
            "recommended_days": DEFAULT_RC1_CONFIG.recommended_evidence_days,
            "meets_minimum": evidence_ok,
            "message": (
                f"Need ≥{DEFAULT_RC1_CONFIG.min_consecutive_trading_days} consecutive "
                f"successful trading days (prefer {DEFAULT_RC1_CONFIG.recommended_evidence_days}). "
                f"Current: {days}."
            ),
        },
        "affects_production": False,
    }
