"""Adaptive Recommendations (AI v8) — operator recommendations ONLY.

Never auto-applies. Never changes floors, Risk, PRE, OMS, or MT5.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


def _iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def build_adaptive_recommendations() -> dict[str, Any]:
    """Generate human-readable recommendations from live evidence only."""
    recs: list[dict[str, Any]] = []

    patterns: dict[str, Any] = {}
    try:
        from app.domain.institutional_trading.ai_scalping.pattern_intelligence import (
            build_pattern_intelligence,
        )

        patterns = build_pattern_intelligence()
    except Exception:
        patterns = {}

    trades = int(patterns.get("trades") or 0)
    if trades >= 2 and patterns.get("best_market_regimes"):
        recs.append(
            {
                "code": "regime_expectancy",
                "severity": "info",
                "message": (
                    f"Current evidence prefers regime "
                    f"'{patterns['best_market_regimes']}' "
                    f"(highest historical win rate in sample)."
                ),
                "requires_human_approval": True,
            }
        )
    if trades >= 2 and patterns.get("worst_sessions"):
        recs.append(
            {
                "code": "session_caution",
                "severity": "info",
                "message": (
                    f"Session '{patterns['worst_sessions']}' shows weaker "
                    f"historical outcomes — review before size increases."
                ),
                "requires_human_approval": True,
            }
        )
    if trades >= 2 and patterns.get("best_symbols"):
        recs.append(
            {
                "code": "symbol_focus",
                "severity": "info",
                "message": (
                    f"Symbol '{patterns['best_symbols']}' leads sample performance; "
                    f"do not auto-promote — operator review required."
                ),
                "requires_human_approval": True,
            }
        )

    # Execution quality degradation
    try:
        from app.domain.institutional_trading.ai_scalping.execution_quality import (
            get_execution_quality_store,
        )

        eq = get_execution_quality_store().snapshot()
        lat = eq.get("avg_latency_ms")
        slip = eq.get("avg_slippage")
        reject = eq.get("reject_rate")
        samples = int(eq.get("samples") or 0)
        if samples >= 5 and lat is not None and float(lat) >= 1500:
            recs.append(
                {
                    "code": "latency_degraded",
                    "severity": "warn",
                    "message": (
                        f"Execution latency elevated (avg {lat}ms over {samples} "
                        f"samples). Investigate gateway/broker path."
                    ),
                    "requires_human_approval": True,
                }
            )
        if samples >= 5 and slip is not None and abs(float(slip)) >= 0.25:
            recs.append(
                {
                    "code": "slippage_degraded",
                    "severity": "warn",
                    "message": (
                        f"Execution quality degraded — avg slippage {slip}. "
                        f"No automatic strategy change."
                    ),
                    "requires_human_approval": True,
                }
            )
        if samples >= 8 and reject is not None and float(reject) >= 40:
            recs.append(
                {
                    "code": "reject_rate_high",
                    "severity": "warn",
                    "message": (
                        f"High rejection rate ({reject}%). Review OMS/MT5 path; "
                        f"floors remain unchanged."
                    ),
                    "requires_human_approval": True,
                }
            )
    except Exception:
        logger.debug("adaptive_rec_eq_unavailable", exc_info=True)
    try:
        from app.domain.institutional_trading.ai_scalping.execution_optimizer import (
            get_last_execution_optimizer,
        )

        opt = get_last_execution_optimizer() or {}
        if str(opt.get("final_state") or "") == "WAIT_BOUNDED" or opt.get(
            "recommendation"
        ) == "DEFER_TICK":
            recs.append(
                {
                    "code": "microstructure_wait",
                    "severity": "info",
                    "message": (
                        "Last optimizer evaluation deferred submit for a better tick "
                        f"(score={opt.get('execution_quality_score')}, "
                        f"remaining_wait_ms={opt.get('remaining_wait_ms')}, "
                        f"defer_count={opt.get('defer_count')})."
                    ),
                    "requires_human_approval": True,
                }
            )
    except Exception:
        logger.debug("adaptive_rec_optimizer_unavailable", exc_info=True)

    if not recs:
        recs.append(
            {
                "code": "insufficient_evidence",
                "severity": "info",
                "message": (
                    "Insufficient completed-trade evidence for adaptive "
                    "recommendations. Continue observing."
                ),
                "requires_human_approval": True,
            }
        )

    return {
        "as_of": _iso(),
        "recommendations": recs,
        "count": len(recs),
        "auto_applies": False,
        "modifies_strategy": False,
        "operator_controlled": True,
        "fabricated": False,
        "observe_only": True,
        "note": "Human approval required before any future strategy evolution",
    }
