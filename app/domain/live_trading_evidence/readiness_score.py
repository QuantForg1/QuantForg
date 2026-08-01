"""Production Readiness Score — evidence-based only; never invent numbers."""

from __future__ import annotations

from typing import Any

from app.domain.live_trading_evidence.persistence import utc_iso


def build_production_readiness_score(
    *,
    dashboard: dict[str, Any],
    trades_count: int,
    rejections_count: int,
) -> dict[str, Any]:
    """Score only from measured evidence components.

    Components contribute only when evidence exists. Overall is mean of
    available component scores — null when nothing measured.
    """
    components: list[dict[str, Any]] = []

    executed = int(dashboard.get("executed_trades") or 0)
    rejected = int(dashboard.get("rejected_trades") or rejections_count or 0)

    # Evidence depth (0-100) from presence of executed packages
    if executed > 0:
        depth = min(100.0, executed * 20.0)
        components.append(
            {
                "id": "executed_evidence",
                "score": round(depth, 1),
                "evidence": {"executed_trades": executed},
            }
        )
    else:
        components.append(
            {
                "id": "executed_evidence",
                "score": None,
                "evidence": {"executed_trades": 0, "note": "waiting"},
            }
        )

    # Rejection observability — having recorded rejections is positive for readiness
    if rejected > 0:
        components.append(
            {
                "id": "rejection_observability",
                "score": min(100.0, 40.0 + min(rejected, 30) * 2.0),
                "evidence": {"rejected_trades": rejected},
            }
        )
    else:
        components.append(
            {
                "id": "rejection_observability",
                "score": None,
                "evidence": {"rejected_trades": 0, "note": "no_samples"},
            }
        )

    # Latency evidence
    avg_lat = dashboard.get("average_latency")
    if avg_lat is not None:
        try:
            lat = float(avg_lat)
            # Lower latency → higher score; 0ms=100, 500ms+=0
            lat_score = max(0.0, min(100.0, 100.0 - (lat / 5.0)))
            components.append(
                {
                    "id": "latency",
                    "score": round(lat_score, 1),
                    "evidence": {"average_latency": lat},
                }
            )
        except (TypeError, ValueError):
            components.append(
                {
                    "id": "latency",
                    "score": None,
                    "evidence": {"average_latency": avg_lat},
                }
            )
    else:
        components.append(
            {"id": "latency", "score": None, "evidence": {"note": "unmeasured"}}
        )

    # Execution quality
    eq = dashboard.get("execution_quality")
    if eq is not None:
        try:
            components.append(
                {
                    "id": "execution_quality",
                    "score": round(max(0.0, min(100.0, float(eq))), 1),
                    "evidence": {"execution_quality": eq},
                }
            )
        except (TypeError, ValueError):
            components.append(
                {"id": "execution_quality", "score": None, "evidence": {}}
            )
    else:
        components.append(
            {
                "id": "execution_quality",
                "score": None,
                "evidence": {"note": "unmeasured"},
            }
        )

    measured = [
        c["score"] for c in components if isinstance(c.get("score"), (int, float))
    ]
    overall = round(sum(measured) / len(measured), 1) if measured else None

    status = "unknown"
    if overall is None:
        status = "awaiting_evidence"
    elif overall >= 75:
        status = "strong_evidence"
    elif overall >= 40:
        status = "partial_evidence"
    else:
        status = "thin_evidence"

    return {
        "as_of": utc_iso(),
        "score": overall,
        "status": status,
        "components": components,
        "measured_components": len(measured),
        "trades_count": trades_count,
        "rejections_count": rejections_count,
        "fabricated": False,
        "observe_only": True,
        "note": ("Score is null when no measurable evidence exists — never invented"),
    }
