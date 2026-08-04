"""Select highest-quality strategy opportunity — one strategy per symbol."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_trading.ai_scalping.strategies.models import (
    StrategyEvaluation,
)


def best_strategy_for_symbol(
    evaluations: tuple[StrategyEvaluation, ...] | list[StrategyEvaluation],
) -> StrategyEvaluation | None:
    """Never attach two strategies to the same symbol — pick the single best passer."""
    passed = [e for e in evaluations if e.passed]
    if not passed:
        return None
    return max(passed, key=lambda e: e.rank_key)


def select_global_best(
    per_symbol_best: list[StrategyEvaluation],
) -> StrategyEvaluation | None:
    """Highest quality opportunity across the universe (single winner)."""
    if not per_symbol_best:
        return None
    return max(per_symbol_best, key=lambda e: e.rank_key)


def attach_strategies_to_scores(
    scored: list[dict[str, Any]],
    *,
    evaluations_by_symbol: dict[str, tuple[StrategyEvaluation, ...]],
) -> tuple[list[dict[str, Any]], StrategyEvaluation | None, list[StrategyEvaluation]]:
    """Annotate score rows; return (rows, global_best, per_symbol_winners)."""
    winners: list[StrategyEvaluation] = []
    out: list[dict[str, Any]] = []
    for row in scored:
        sym = str(row.get("symbol") or "").upper()
        evals = evaluations_by_symbol.get(sym) or ()
        row = dict(row)
        row["strategy_evaluations"] = [e.to_dict() for e in evals]
        best = best_strategy_for_symbol(evals)
        if best is not None:
            winners.append(best)
            row["strategy_id"] = best.strategy_id
            row["strategy_name"] = best.name
            row["strategy_quality"] = best.quality
            row["strategy_confidence"] = best.confidence
            row["strategy_explanation"] = best.explanation
            # Opportunity ranking soft input — does not bypass reject
            row["strategy_rank_score"] = best.quality + best.live_rank_boost
        else:
            row["strategy_id"] = None
            row["strategy_name"] = None
            row["strategy_quality"] = None
            row["strategy_confidence"] = None
            row["strategy_explanation"] = None
            row["strategy_rank_score"] = None
            # If base was eligible but no strategy specialized-pass, keep base reject
            # state unchanged — strategies never force trades.
        out.append(row)
    global_best = select_global_best(winners)
    return out, global_best, winners
