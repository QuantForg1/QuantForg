"""LLP orchestrator — evidence collection/analysis; never production mutation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from app.domain.live_learning_program.config import (
    DEFAULT_LLP_CONFIG,
    LlpConfig,
)
from app.domain.live_learning_program.modules import (
    confidence_tracking,
    edge_evolution,
    learning_dashboard,
    live_observation_collector,
    market_behaviour_journal,
    monthly_research_review,
    operator_feedback,
    replay_comparison,
    research_recommendations,
    weekly_review,
)
from app.domain.live_learning_program.types import LlpInput, ModuleResult
from app.domain.trading.gold_only import GOLD_SYMBOL


@dataclass
class LiveLearningProgram:
    config: LlpConfig = field(default_factory=lambda: DEFAULT_LLP_CONFIG)
    history: list[dict[str, Any]] = field(default_factory=list)

    def status(self) -> dict[str, object]:
        return {
            **self.config.to_dict(),
            "modules": [
                "live_observation_collector",
                "replay_comparison",
                "operator_feedback",
                "edge_evolution",
                "market_behaviour_journal",
                "confidence_tracking",
                "weekly_review",
                "monthly_research_review",
                "learning_dashboard",
                "research_recommendations",
            ],
            "capabilities": {
                "xauusd_only": True,
                "read_only": True,
                "evidence_only": True,
                "never_order_send": True,
                "never_place_trades": True,
                "never_modify_strategy_rules": True,
                "never_modify_risk_engine": True,
                "never_modify_safety_engine": True,
                "never_modify_decision_engine": True,
                "never_modify_execution_pipeline": True,
                "never_auto_tune_parameters": True,
                "never_auto_promote_strategies": True,
                "never_fabricate_evidence": True,
                "immutable_observations": True,
                "promise_profitability": False,
                "symbol": GOLD_SYMBOL,
            },
            "recent": self.history[:10],
        }

    def update_policies(self, updates: dict[str, object]) -> dict[str, object]:
        self.config = self.config.update(updates)
        return self.config.to_dict()

    def list_history(self, *, limit: int = 50) -> dict[str, Any]:
        rows = self.history[: max(1, min(limit, self.config.max_history))]
        return {
            "status": "available" if rows else "empty",
            "items": rows,
            "append_only": True,
        }

    def evaluate(self, inp: LlpInput) -> dict[str, Any]:
        audit_id = f"llp_{uuid4().hex[:12]}"
        flags = self.config.feature_flags
        modules: dict[str, ModuleResult] = {}

        if flags.get("live_observation_collector", True):
            modules["live_observation_collector"] = live_observation_collector(
                inp, self.config
            )
        if flags.get("replay_comparison", True):
            modules["replay_comparison"] = replay_comparison(inp, self.config)
        if flags.get("operator_feedback", True):
            modules["operator_feedback"] = operator_feedback(inp, self.config)
        if flags.get("edge_evolution", True):
            modules["edge_evolution"] = edge_evolution(inp, self.config)
        if flags.get("market_behaviour_journal", True):
            modules["market_behaviour_journal"] = market_behaviour_journal(
                inp, self.config
            )
        if flags.get("confidence_tracking", True):
            modules["confidence_tracking"] = confidence_tracking(
                inp, self.config
            )
        if flags.get("weekly_review", True):
            modules["weekly_review"] = weekly_review(inp, dict(modules))
        if flags.get("monthly_research_review", True):
            modules["monthly_research_review"] = monthly_research_review(
                inp, dict(modules)
            )
        if flags.get("research_recommendations", True):
            modules["research_recommendations"] = research_recommendations(
                inp, dict(modules), self.config
            )
        if flags.get("learning_dashboard", True):
            modules["learning_dashboard"] = learning_dashboard(dict(modules))

        dash = modules.get("learning_dashboard")
        rec = modules.get("research_recommendations")
        obs = modules.get("live_observation_collector")
        summary = {
            "learning_progress": (
                (dash.details or {}).get("learning_progress") if dash else None
            ),
            "observation_count": (
                (obs.details or {}).get("observation_count") if obs else 0
            ),
            "evidence_strength_pct": (
                (dash.details or {}).get("evidence_strength_pct")
                if dash
                else None
            ),
            "coverage_pct": (
                (dash.details or {}).get("coverage_pct") if dash else None
            ),
            "research_backlog": (
                (rec.details or {}).get("recommendations") if rec else []
            ),
        }

        result = {
            "version": self.config.version,
            "symbol": GOLD_SYMBOL,
            "audit_id": audit_id,
            "modules": {k: v.to_dict() for k, v in modules.items()},
            "learning_summary": summary,
            "read_only": True,
            "evidence_only": True,
            "advisory_only": True,
            "never_order_send": True,
            "never_place_trades": True,
            "modifies_strategy_rules": False,
            "modifies_risk_engine": False,
            "modifies_safety_engine": False,
            "modifies_decision_engine": False,
            "modifies_execution_pipeline": False,
            "auto_tune_parameters": False,
            "auto_promote_strategies": False,
            "promise_profitability": False,
            "explainable": True,
            "auditable": True,
        }
        self.history.insert(
            0,
            {
                "audit_id": audit_id,
                "observation_count": summary["observation_count"],
                "learning_progress": summary["learning_progress"],
                "evidence_strength_pct": summary["evidence_strength_pct"],
            },
        )
        if len(self.history) > self.config.max_history:
            self.history = self.history[: self.config.max_history]
        return result


def input_from_dict(data: dict[str, Any]) -> LlpInput:
    return LlpInput(
        completed_trades=(
            data.get("completed_trades")
            if isinstance(data.get("completed_trades"), list)
            else None
        ),
        replay_results=(
            data.get("replay_results")
            if isinstance(data.get("replay_results"), dict)
            else None
        ),
        paper_results=(
            data.get("paper_results")
            if isinstance(data.get("paper_results"), dict)
            else None
        ),
        live_results=(
            data.get("live_results")
            if isinstance(data.get("live_results"), dict)
            else None
        ),
        operator_feedback=(
            data.get("operator_feedback")
            if isinstance(data.get("operator_feedback"), list)
            else None
        ),
        edge_score_series=(
            data.get("edge_score_series")
            if isinstance(data.get("edge_score_series"), list)
            else None
        ),
        journal_entries=(
            data.get("journal_entries")
            if isinstance(data.get("journal_entries"), list)
            else None
        ),
        confidence_pairs=(
            data.get("confidence_pairs")
            if isinstance(data.get("confidence_pairs"), list)
            else None
        ),
        period=str(data["period"]) if data.get("period") else None,
    )
