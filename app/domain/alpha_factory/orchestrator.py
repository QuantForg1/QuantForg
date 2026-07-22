"""Alpha Factory orchestrator — research isolation; never production."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from app.domain.alpha_factory.config import (
    DEFAULT_ALPHA_FACTORY_CONFIG,
    AlphaFactoryConfig,
)
from app.domain.alpha_factory.modules import (
    alpha_score,
    benchmark_engine,
    experiment_history,
    paper_trading_pipeline,
    promotion_report,
    promotion_workflow,
    replay_engine,
    research_dashboard,
    research_workspace,
    strategy_laboratory,
)
from app.domain.alpha_factory.types import AlphaFactoryInput, ModuleResult
from app.domain.trading.gold_only import GOLD_SYMBOL


@dataclass
class AlphaFactory:
    config: AlphaFactoryConfig = field(
        default_factory=lambda: DEFAULT_ALPHA_FACTORY_CONFIG
    )
    history: list[dict[str, Any]] = field(default_factory=list)

    def status(self) -> dict[str, object]:
        return {
            **self.config.to_dict(),
            "modules": [
                "research_workspace",
                "strategy_laboratory",
                "replay_engine",
                "paper_trading_pipeline",
                "benchmark_engine",
                "promotion_workflow",
                "experiment_history",
                "research_dashboard",
                "alpha_score",
                "promotion_report",
            ],
            "capabilities": {
                "xauusd_only": True,
                "outside_production": True,
                "never_order_send": True,
                "never_modify_live_strategy": True,
                "never_modify_risk_engine": True,
                "never_modify_safety_engine": True,
                "never_modify_decision_engine": True,
                "never_modify_execution_pipeline": True,
                "never_modify_auto_trading": True,
                "never_automatic_promotion": True,
                "never_fabricate_metrics": True,
                "append_only_history": True,
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
        return {"status": "available" if rows else "empty", "items": rows}

    def evaluate(self, inp: AlphaFactoryInput) -> dict[str, Any]:
        audit_id = f"af_{uuid4().hex[:12]}"
        flags = self.config.feature_flags
        modules: dict[str, ModuleResult] = {}

        if flags.get("research_workspace", True):
            modules["research_workspace"] = research_workspace(
                inp, self.config
            )
        if flags.get("strategy_laboratory", True):
            modules["strategy_laboratory"] = strategy_laboratory(
                inp, self.config
            )
        if flags.get("replay_engine", True):
            modules["replay_engine"] = replay_engine(inp, self.config)
        if flags.get("paper_trading_pipeline", True):
            modules["paper_trading_pipeline"] = paper_trading_pipeline(
                inp, self.config
            )
        if flags.get("benchmark_engine", True):
            modules["benchmark_engine"] = benchmark_engine(inp, self.config)
        if flags.get("promotion_workflow", True):
            modules["promotion_workflow"] = promotion_workflow(
                inp, self.config
            )
        if flags.get("experiment_history", True):
            modules["experiment_history"] = experiment_history(
                inp, self.config
            )
        if flags.get("alpha_score", True):
            modules["alpha_score"] = alpha_score(inp, self.config)
        if flags.get("research_dashboard", True):
            modules["research_dashboard"] = research_dashboard(dict(modules))
        if flags.get("promotion_report", True):
            modules["promotion_report"] = promotion_report(
                inp, dict(modules)
            )

        lab = modules.get("strategy_laboratory")
        dash = modules.get("research_dashboard")
        certified = int((lab.details or {}).get("certified_count") or 0) if lab else 0
        certified_list = []
        if lab and isinstance((lab.details or {}).get("strategies"), list):
            certified_list = [
                s
                for s in lab.details["strategies"]
                if s.get("certified") is True
            ]

        result = {
            "version": self.config.version,
            "symbol": GOLD_SYMBOL,
            "audit_id": audit_id,
            "modules": {k: v.to_dict() for k, v in modules.items()},
            "research_summary": {
                "active_experiments": (
                    len((dash.details or {}).get("active_experiments") or [])
                    if dash
                    else 0
                ),
                "promotion_stage": (
                    (dash.details or {}).get("promotion_stage")
                    if dash
                    else None
                ),
                "alpha_score": (
                    str(modules["alpha_score"].score)
                    if modules.get("alpha_score")
                    and modules["alpha_score"].score is not None
                    else None
                ),
                "outside_production": True,
            },
            "certified_strategies": {
                "count": certified,
                "items": certified_list[:50],
                "note": "Certification is research metadata — not live enablement",
            },
            "outside_production": True,
            "advisory_only": True,
            "never_order_send": True,
            "modifies_live_strategy": False,
            "modifies_risk_engine": False,
            "modifies_safety_engine": False,
            "modifies_decision_engine": False,
            "modifies_execution_pipeline": False,
            "modifies_auto_trading": False,
            "automatic_promotion": False,
            "promise_profitability": False,
            "explainable": True,
            "auditable": True,
        }
        self.history.insert(
            0,
            {
                "audit_id": audit_id,
                "active": result["research_summary"]["active_experiments"],
                "certified": certified,
                "stage": result["research_summary"]["promotion_stage"],
            },
        )
        if len(self.history) > self.config.max_history:
            self.history = self.history[: self.config.max_history]
        return result


def input_from_dict(data: dict[str, Any]) -> AlphaFactoryInput:
    return AlphaFactoryInput(
        action=str(data.get("action") or "evaluate"),
        experiment=(
            data.get("experiment")
            if isinstance(data.get("experiment"), dict)
            else None
        ),
        experiments=(
            data.get("experiments")
            if isinstance(data.get("experiments"), list)
            else None
        ),
        strategy=(
            data.get("strategy")
            if isinstance(data.get("strategy"), dict)
            else None
        ),
        strategies=(
            data.get("strategies")
            if isinstance(data.get("strategies"), list)
            else None
        ),
        replay=(
            data.get("replay") if isinstance(data.get("replay"), dict) else None
        ),
        paper=(
            data.get("paper") if isinstance(data.get("paper"), dict) else None
        ),
        benchmarks=(
            data.get("benchmarks")
            if isinstance(data.get("benchmarks"), list)
            else None
        ),
        promotion=(
            data.get("promotion")
            if isinstance(data.get("promotion"), dict)
            else None
        ),
        history_event=(
            data.get("history_event")
            if isinstance(data.get("history_event"), dict)
            else None
        ),
        score_inputs=(
            data.get("score_inputs")
            if isinstance(data.get("score_inputs"), dict)
            else None
        ),
        author=str(data["author"]) if data.get("author") else None,
    )
