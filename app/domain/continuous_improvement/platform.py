"""Assemble Institutional Live Validation & Continuous Improvement Program."""

from __future__ import annotations

from typing import Any

from app.domain.continuous_improvement import PROGRAM_VERSION
from app.domain.continuous_improvement.auto_reports import build_auto_reports
from app.domain.continuous_improvement.continuous_validation import (
    build_continuous_validation,
)
from app.domain.continuous_improvement.historical_trends import (
    build_historical_trends,
)
from app.domain.continuous_improvement.learning_review import build_learning_review
from app.domain.continuous_improvement.models import HARD_LOCKS
from app.domain.continuous_improvement.operational_scorecard import (
    build_operational_scorecard,
)
from app.domain.continuous_improvement.persistence import utc_iso
from app.domain.continuous_improvement.release_confidence import (
    build_release_confidence,
)
from app.domain.continuous_improvement.trading_effectiveness import (
    build_trading_effectiveness,
)


async def build_continuous_improvement_program() -> dict[str, Any]:
    validation = build_continuous_validation(record_history=True)
    trading = build_trading_effectiveness()
    learning = build_learning_review()
    release = build_release_confidence(validation=validation)
    scorecard = build_operational_scorecard(
        validation=validation,
        trading=trading,
        release=release,
        learning=learning,
    )
    trends = build_historical_trends(validation=validation, trading=trading)
    reports = build_auto_reports(
        validation=validation,
        trading=trading,
        learning=learning,
        release=release,
        scorecard=scorecard,
    )
    return {
        "as_of": utc_iso(),
        "program_version": PROGRAM_VERSION,
        "continuous_validation": validation,
        "trading_effectiveness": trading,
        "learning_review": learning,
        "release_confidence": release,
        "operational_scorecard": scorecard,
        "historical_trends": trends,
        "auto_reports": reports,
        "flags": {
            **HARD_LOCKS,
            "program_version": PROGRAM_VERSION,
        },
        "fabricated": False,
        "migrations_pending": False,
        "migration_status": "No migrations pending.",
    }


async def build_continuous_improvement_noc_panels() -> dict[str, Any]:
    pack = await build_continuous_improvement_program()
    val = pack.get("continuous_validation") or {}
    trade = pack.get("trading_effectiveness") or {}
    learn = pack.get("learning_review") or {}
    score = pack.get("operational_scorecard") or {}
    trends = pack.get("historical_trends") or {}
    release = pack.get("release_confidence") or {}
    return {
        "production_validation": {
            "overall": val.get("overall"),
            "ok_count": val.get("ok_count"),
            "target_count": val.get("target_count"),
            "history_count": val.get("history_count"),
            "observe_only": True,
        },
        "trading_effectiveness": {
            "signals_generated": trade.get("signals_generated"),
            "signals_rejected": trade.get("signals_rejected"),
            "trades_closed": trade.get("trades_closed"),
            "win_rate": trade.get("win_rate"),
            "profit_factor": trade.get("profit_factor"),
            "expectancy": trade.get("expectancy"),
            "measured_count": trade.get("measured_count"),
            "observe_only": True,
        },
        "learning_review": {
            "success_patterns": len(learn.get("top_success_patterns") or []),
            "failure_patterns": len(learn.get("top_failure_patterns") or []),
            "blocking_gates": len(learn.get("most_common_blocking_gates") or []),
            "recommendations": len(learn.get("recommendations") or []),
            "operator_review_only": True,
        },
        "operational_scorecard": {
            "overall_score": score.get("overall_score"),
            "categories": {
                k: (v or {}).get("score")
                for k, v in (score.get("categories") or {}).items()
            },
            "observe_only": True,
        },
        "historical_trends": {
            "windows": trends.get("windows") or [],
            "validation_trends": {
                w: {
                    "sample_count": (row or {}).get("sample_count"),
                    "avg_ok_ratio_percent": (row or {}).get("avg_ok_ratio_percent"),
                }
                for w, row in (trends.get("validation_trends") or {}).items()
            },
            "observe_only": True,
        },
        "release_confidence": {
            "confidence": release.get("confidence"),
            "deployments": release.get("deployment_count"),
            "rollbacks": release.get("rollback_count"),
            "observe_only": True,
        },
        "flags": {
            "observe_only": True,
            "never_modifies_trading": True,
            "fabricates_metrics": False,
            "program_version": PROGRAM_VERSION,
        },
        "fabricated": False,
    }
