"""Select highest-quality strategy opportunity — one strategy per symbol.

Selection is owned by the Strategy Orchestration Engine (SOE). This module
remains the attachment facade used by the multi-asset scanner.
"""

from __future__ import annotations

from typing import Any

from app.domain.institutional_trading.ai_scalping.strategies.models import (
    StrategyEvaluation,
)
from app.domain.institutional_trading.ai_scalping.strategies.orchestrator import (
    OrchestrationVerdict,
    orchestrate_strategies,
)


def best_strategy_for_symbol(
    evaluations: tuple[StrategyEvaluation, ...] | list[StrategyEvaluation],
    *,
    live_boosts: dict[str, float] | None = None,
    stats_snapshot: dict[str, Any] | None = None,
    score: dict[str, Any] | None = None,
) -> StrategyEvaluation | None:
    """Never attach two strategies to the same symbol — SOE picks one or none."""
    verdict = orchestrate_strategies(
        evaluations,
        live_boosts=live_boosts,
        stats_snapshot=stats_snapshot,
        score=score,
    )
    return verdict.selected


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
    live_boosts: dict[str, float] | None = None,
    stats_snapshot: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], StrategyEvaluation | None, list[StrategyEvaluation]]:
    """Annotate score rows; return (rows, global_best, per_symbol_winners)."""
    winners: list[StrategyEvaluation] = []
    out: list[dict[str, Any]] = []
    for row in scored:
        sym = str(row.get("symbol") or "").upper()
        evals = evaluations_by_symbol.get(sym) or ()
        row = dict(row)
        row["strategy_evaluations"] = [e.to_dict() for e in evals]
        verdict: OrchestrationVerdict = orchestrate_strategies(
            evals,
            live_boosts=live_boosts,
            stats_snapshot=stats_snapshot,
            score=row,
        )
        row["strategy_orchestration"] = verdict.to_dict()
        best = verdict.selected
        if best is not None and not verdict.prefer_no_trade:
            winners.append(best)
            row["strategy_id"] = best.strategy_id
            row["strategy_name"] = best.name
            row["strategy_quality"] = best.quality
            row["strategy_confidence"] = best.confidence
            row["strategy_explanation"] = best.explanation
            # Opportunity ranking soft input — does not bypass reject / Risk.
            row["strategy_rank_score"] = best.quality + best.live_rank_boost
            row["strategy_confluence_count"] = verdict.confluence_count
            row["strategy_confluence_score"] = verdict.confluence_score
            try:
                from app.domain.institutional_trading.ai_scalping.strategies.cycle_activity import (  # noqa: E501
                    record_soe_verdict,
                )
                from app.domain.institutional_trading.ai_scalping.strategies.stats import (  # noqa: E501
                    get_strategy_stats_book,
                )

                get_strategy_stats_book().record_accepted(best.strategy_id)
                record_soe_verdict(
                    decision=best.direction,
                    reasons=verdict.reasons,
                    selected_strategy_id=best.strategy_id,
                )
            except Exception:  # noqa: S110 — cycle activity must not break selection
                pass
        else:
            row["strategy_id"] = None
            row["strategy_name"] = None
            row["strategy_quality"] = None
            row["strategy_confidence"] = None
            row["strategy_explanation"] = (
                "; ".join(verdict.reasons) if verdict.reasons else None
            )
            row["strategy_rank_score"] = None
            row["strategy_confluence_count"] = verdict.confluence_count
            row["strategy_confluence_score"] = verdict.confluence_score
            # Prefer no trade: SOE veto clears opportunity eligibility so the
            # scanner cannot fall back to an unspecialized weak setup. Risk /
            # OMS / SCALPING_V1 hard gates remain unchanged authorities.
            if verdict.prefer_no_trade:
                row["soe_prefer_no_trade"] = True
                row["soe_reject_reason"] = (
                    verdict.reasons[0] if verdict.reasons else "soe_prefer_no_trade"
                )
                row["opportunity_eligible"] = False
                if not row.get("reject"):
                    row["soe_blocks_selection"] = True
                try:
                    from app.domain.institutional_trading.ai_scalping.strategies.cycle_activity import (  # noqa: E501
                        record_soe_verdict,
                    )

                    record_soe_verdict(
                        decision="NO_TRADE",
                        reasons=verdict.reasons or ("soe_prefer_no_trade",),
                    )
                except Exception:  # noqa: S110 — cycle activity must not break selection
                    pass
        out.append(row)
    global_best = select_global_best(winners)
    return out, global_best, winners
