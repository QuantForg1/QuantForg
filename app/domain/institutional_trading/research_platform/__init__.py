"""Institutional Research Platform v10."""

from __future__ import annotations

from app.domain.institutional_trading.research_platform.audit import get_audit_trail
from app.domain.institutional_trading.research_platform.backtesting import (
    compute_metrics,
    run_backtest_suite,
)
from app.domain.institutional_trading.research_platform.config import (
    DEFAULT_RESEARCH_CONFIG,
    ResearchPlatformConfig,
)
from app.domain.institutional_trading.research_platform.continuous_improvement import (
    get_continuous_improvement,
)
from app.domain.institutional_trading.research_platform.experiments import (
    get_experiment_store,
)
from app.domain.institutional_trading.research_platform.model_registry import (
    get_model_registry,
)
from app.domain.institutional_trading.research_platform.optimization import (
    get_optimization_studio,
)
from app.domain.institutional_trading.research_platform.promotion import (
    get_promotion_workflow,
)
from app.domain.institutional_trading.research_platform.reporting import (
    get_reporting_store,
    report_to_csv,
    report_to_pdf_text,
)
from app.domain.institutional_trading.research_platform.workspace import (
    get_research_workspace,
)

__all__ = [
    "DEFAULT_RESEARCH_CONFIG",
    "ResearchPlatformConfig",
    "compute_metrics",
    "get_audit_trail",
    "get_continuous_improvement",
    "get_experiment_store",
    "get_model_registry",
    "get_optimization_studio",
    "get_promotion_workflow",
    "get_reporting_store",
    "get_research_workspace",
    "report_to_csv",
    "report_to_pdf_text",
    "run_backtest_suite",
]
