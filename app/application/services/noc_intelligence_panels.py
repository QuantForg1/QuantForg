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
        "flags": {
            "observe_only": True,
            "forced_trades": False,
            "fabricated": False,
            "governed_by_existing_ai_and_risk": True,
        },
    }
