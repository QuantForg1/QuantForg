"""Quant Studio domain — analysis-only research workspace."""

from __future__ import annotations

from app.domain.quant_studio.analytics import build_professional_analytics
from app.domain.quant_studio.marketplace import get_marketplace_store
from app.domain.quant_studio.monte_carlo import run_monte_carlo
from app.domain.quant_studio.optimizer import suggest_optimizations
from app.domain.quant_studio.strategy_review import review_strategy
from app.domain.quant_studio.visual_builder import BLOCK_CATALOG, compile_strategy_graph
from app.domain.quant_studio.walkforward import summarize_walkforward_stability

__all__ = [
    "BLOCK_CATALOG",
    "build_professional_analytics",
    "compile_strategy_graph",
    "get_marketplace_store",
    "review_strategy",
    "run_monte_carlo",
    "suggest_optimizations",
    "summarize_walkforward_stability",
]
