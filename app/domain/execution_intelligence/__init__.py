"""Execution Intelligence package."""

from __future__ import annotations

from app.domain.execution_intelligence.analytics import compute_execution_analytics
from app.domain.execution_intelligence.broker_diagnostics import (
    build_broker_diagnostics,
)
from app.domain.execution_intelligence.broker_quality import compute_broker_quality
from app.domain.execution_intelligence.checklist import evaluate_checklist
from app.domain.execution_intelligence.lifecycle import LifecycleState
from app.domain.execution_intelligence.post_trade import (
    analyze_post_trade,
    analyze_post_trades,
)
from app.domain.execution_intelligence.store import LifecycleStore
from app.domain.execution_intelligence.trend_analytics import (
    compute_regime_analytics,
    compute_risk_trends,
    compute_session_analytics,
)

__all__ = [
    "LifecycleState",
    "LifecycleStore",
    "analyze_post_trade",
    "analyze_post_trades",
    "build_broker_diagnostics",
    "compute_broker_quality",
    "compute_execution_analytics",
    "compute_regime_analytics",
    "compute_risk_trends",
    "compute_session_analytics",
    "evaluate_checklist",
]
