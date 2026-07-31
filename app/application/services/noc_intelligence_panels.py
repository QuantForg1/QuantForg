"""NOC intelligence panels — observe-only aggregation of live production data."""

from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


def build_intelligence_panels(
    *,
    runtime_scan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build Ranking / Queue / Exposure / Analytics / Replay / Probability panels."""
    scan = runtime_scan if isinstance(runtime_scan, dict) else None
    if scan is None:
        try:
            from app.application.services.institutional_multi_asset_scanner import (
                get_last_multi_asset_scan,
            )

            scan = get_last_multi_asset_scan()
        except Exception:
            scan = None

    # Opportunity Ranking
    ranking_rows = []
    if isinstance(scan, dict):
        ranking_rows = list(scan.get("opportunity_ranked") or [])
        if not ranking_rows:
            for row in scan.get("noc_rows") or []:
                if isinstance(row, dict):
                    ranking_rows.append(
                        {
                            "symbol": row.get("symbol"),
                            "opportunity_score": row.get("opportunity_score"),
                            "quality": row.get("quality"),
                            "confidence": row.get("confidence"),
                            "direction": row.get("direction") or row.get("decision"),
                            "eligible": row.get("eligible"),
                            "blocking_gate": row.get("blocking_gate"),
                            "estimated_probability": row.get("estimated_probability"),
                        }
                    )

    # Trade Queue
    queue: dict[str, Any] = {}
    try:
        from app.domain.institutional_trading.ai_scalping import (
            institutional_trade_queue as itq,
        )

        queue = itq.snapshot_trade_queue()
        if not queue.get("candidates") and isinstance(scan, dict):
            queue = dict(scan.get("trade_queue") or queue)
    except Exception:
        logger.exception("noc_trade_queue_failed")
        queue = {"candidates": [], "size": 0}

    # Portfolio Exposure
    exposure: dict[str, Any] = {}
    try:
        from app.application.services.institutional_ite_runtime import (
            get_ite_runtime,
        )
        from app.domain.institutional_trading.ai_scalping import (
            portfolio_exposure_intelligence as pei,
        )

        positions = None
        rt = get_ite_runtime()
        if rt is not None:
            engine = getattr(getattr(rt, "position_management", None), "engine", None)
            positions = getattr(engine, "_positions", None)
        exposure = pei.build_portfolio_exposure(positions)
    except Exception:
        logger.exception("noc_exposure_failed")
        exposure = {"open_positions": 0, "fabricated": False}

    # Performance Analytics
    analytics: dict[str, Any] = {}
    try:
        from app.domain.institutional_trading.ai_scalping.performance_analytics import (
            build_performance_analytics,
        )

        analytics = build_performance_analytics()
    except Exception:
        logger.exception("noc_analytics_failed")
        analytics = {"trades": 0, "fabricated": False}

    # Replay Library
    replay: dict[str, Any] = {"items": [], "count": 0}
    try:
        from app.domain.institutional_trading.ai_scalping import (
            institutional_replay_viewer as irv,
        )

        replay = irv.list_institutional_replays(limit=25)
    except Exception:
        logger.exception("noc_replay_failed")
        try:
            from app.domain.institutional_trading.performance_lab.trade_replay import (
                get_trade_replay_store,
            )

            items = get_trade_replay_store().list(limit=25)
            replay = {"items": items, "count": len(items), "fabricated": False}
        except Exception:
            logger.exception("noc_replay_fallback_failed")

    # Execution Probability (best / selected)
    probability: dict[str, Any] = {}
    try:
        best = None
        if isinstance(scan, dict):
            best = scan.get("best")
        if isinstance(best, dict) and best.get("probability"):
            probability = dict(best.get("probability") or {})
        elif isinstance(queue.get("candidates"), list) and queue["candidates"]:
            top = queue["candidates"][0]
            probability = dict(top.get("probability") or {})
            probability.setdefault(
                "probability_of_success", top.get("estimated_probability")
            )
        probability["symbol"] = (
            (best or {}).get("symbol")
            if isinstance(best, dict)
            else (queue.get("selected_symbol") or None)
        )
        probability["fabricated"] = False
    except Exception:
        probability = {"fabricated": False}

    # --- Execution Intelligence Layer panels ---
    execution_optimizer: dict[str, Any] = {}
    try:
        from app.domain.institutional_trading.ai_scalping.execution_optimizer import (
            get_last_execution_optimizer,
        )

        execution_optimizer = get_last_execution_optimizer() or {
            "fabricated": False,
            "note": "awaiting_first_optimizer_evaluation",
        }
    except Exception:
        logger.exception("noc_execution_optimizer_failed")
        execution_optimizer = {"fabricated": False}

    smart_routing: dict[str, Any] = {}
    try:
        from app.domain.institutional_trading.ai_scalping.smart_order_routing import (
            get_last_smart_routing,
        )

        smart_routing = get_last_smart_routing() or {"fabricated": False}
    except Exception:
        smart_routing = {"fabricated": False}

    execution_quality: dict[str, Any] = {}
    try:
        from app.domain.institutional_trading.ai_scalping.execution_quality import (
            get_execution_quality_store,
        )
        from app.domain.institutional_trading.ai_scalping.execution_quality_analytics import (  # noqa: E501
            get_execution_quality_analytics_store,
        )

        execution_quality = {
            "rolling": get_execution_quality_store().snapshot(),
            "analytics": get_execution_quality_analytics_store().snapshot(limit=15),
            "fabricated": False,
        }
    except Exception:
        logger.exception("noc_execution_quality_failed")
        execution_quality = {"fabricated": False}

    lifecycle: dict[str, Any] = {}
    try:
        from app.domain.institutional_trading.ai_scalping import (
            trade_lifecycle_timeline as tlt,
        )

        lifecycle = tlt.get_trade_lifecycle_store().snapshot()
    except Exception:
        logger.exception("noc_lifecycle_failed")
        lifecycle = {"active": [], "recent": [], "fabricated": False}

    position_monitor: dict[str, Any] = {}
    try:
        from app.domain.institutional_trading.ai_scalping.institutional_position_monitor import (  # noqa: E501
            get_last_position_monitor,
        )

        position_monitor = get_last_position_monitor() or {
            "rows": [],
            "open_positions": 0,
            "fabricated": False,
        }
    except Exception:
        position_monitor = {"rows": [], "fabricated": False}

    ops_intel: dict[str, Any] = {}
    try:
        from app.domain.institutional_trading.ai_scalping.operational_intelligence import (  # noqa: E501
            build_operational_intelligence,
        )

        ops_intel = build_operational_intelligence()
    except Exception:
        logger.exception("noc_ops_intel_failed")
        ops_intel = {"warnings": [], "fabricated": False}

    daily_report: dict[str, Any] = {}
    try:
        from app.domain.institutional_trading.ai_scalping.execution_daily_reporting import (  # noqa: E501
            build_execution_daily_report,
        )

        daily_report = build_execution_daily_report()
    except Exception:
        daily_report = {"fabricated": False}

    return {
        "opportunity_ranking": {
            "rows": ranking_rows,
            "best_symbol": scan.get("best_symbol") if isinstance(scan, dict) else None,
            "as_of": scan.get("as_of") if isinstance(scan, dict) else None,
            "observe_only": True,
        },
        "trade_queue": queue,
        "portfolio_exposure": exposure,
        "performance_analytics": analytics,
        "replay_library": replay,
        "execution_probability": probability,
        "execution_optimizer": execution_optimizer,
        "smart_order_routing": smart_routing,
        "execution_quality": execution_quality,
        "lifecycle_timeline": lifecycle,
        "position_monitor": position_monitor,
        "operational_intelligence": ops_intel,
        "daily_execution_report": daily_report,
        "broker_performance": {
            "fill_rate": (execution_quality.get("rolling") or {}).get("fill_rate"),
            "reject_rate": (execution_quality.get("rolling") or {}).get("reject_rate"),
            "requote_rate": (execution_quality.get("rolling") or {}).get(
                "requote_rate"
            ),
            "avg_latency_ms": (execution_quality.get("rolling") or {}).get(
                "avg_latency_ms"
            ),
            "avg_slippage": (execution_quality.get("rolling") or {}).get(
                "avg_slippage"
            ),
            "fabricated": False,
            "source": "execution_quality_store",
        },
        "flags": {
            "observe_only": True,
            "forced_trades": False,
            "fabricated": False,
            "governed_by_existing_ai_and_risk": True,
        },
    }
