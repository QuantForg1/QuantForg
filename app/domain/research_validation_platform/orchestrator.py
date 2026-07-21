"""Research & Validation Platform orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.research_validation_platform.certification import (
    evaluate_release_governance,
    run_certification_pipeline,
)
from app.domain.research_validation_platform.comparison import compare_strategies
from app.domain.research_validation_platform.config import (
    DEFAULT_RVP_CONFIG,
    ResearchValidationConfig,
)
from app.domain.research_validation_platform.governance import (
    RollbackEngine,
    VersionGovernance,
)
from app.domain.research_validation_platform.labs import (
    HistoricalReplayLab,
    run_paper_environment,
    run_walk_forward,
)
from app.domain.research_validation_platform.observatory import build_observatory
from app.domain.research_validation_platform.registry import StrategyRegistry
from app.domain.trading.gold_only import GOLD_SYMBOL


@dataclass
class ResearchValidationPlatform:
    config: ResearchValidationConfig = field(
        default_factory=lambda: DEFAULT_RVP_CONFIG
    )
    registry: StrategyRegistry = field(default_factory=StrategyRegistry)
    versions: VersionGovernance = field(default_factory=VersionGovernance)
    certifications: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.replay = HistoricalReplayLab(self.config)
        self.versions.max_versions = self.config.max_versions
        self.rollback_engine = RollbackEngine(
            self.versions, max_audit=self.config.max_audit
        )

    def status(self) -> dict[str, object]:
        return {
            **self.config.to_dict(),
            "modules": [
                "strategy_registry",
                "historical_replay_lab",
                "walk_forward_validation",
                "paper_trading_environment",
                "strategy_comparison_dashboard",
                "certification_pipeline",
                "strategy_version_governance",
                "rollback_engine",
                "performance_observatory",
                "release_governance",
            ],
            "registry": self.registry.list(),
            "replay": self.replay.status(),
            "capabilities": {
                "xauusd_only": True,
                "live_execution_pipeline_unchanged": True,
                "never_order_send": True,
                "validation_reproducible": True,
                "versions_traceable": True,
                "certification_mandatory_before_production": True,
                "rollback_preserves_audit": True,
                "thresholds_configurable": True,
                "symbol": GOLD_SYMBOL,
            },
            "recent_certifications": self.certifications[:10],
        }

    def update_policies(self, updates: dict[str, object]) -> dict[str, object]:
        self.config = self.config.update(updates)
        self.replay.config = self.config
        self.versions.max_versions = self.config.max_versions
        self.rollback_engine.max_audit = self.config.max_audit
        return self.config.to_dict()

    def register_strategy(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.registry.register(payload)

    def list_registry(self) -> dict[str, Any]:
        return self.registry.list()

    def replay_load(self, payload: dict[str, Any]) -> dict[str, Any]:
        bars = payload.get("bars") if isinstance(payload.get("bars"), list) else []
        return self.replay.load(
            strategy_key=str(payload.get("strategy_key") or "unknown"),
            bars=bars,
            version=str(payload["version"]) if payload.get("version") else None,
        )

    def replay_step(self) -> dict[str, Any]:
        return self.replay.step()

    def walk_forward(self, payload: dict[str, Any]) -> dict[str, Any]:
        return run_walk_forward(payload, self.config)

    def paper(self, payload: dict[str, Any]) -> dict[str, Any]:
        return run_paper_environment(payload, self.config)

    def compare(self, payload: dict[str, Any]) -> dict[str, Any]:
        runs = payload.get("runs") if isinstance(payload.get("runs"), list) else []
        return compare_strategies(
            runs, max_comparisons=self.config.max_comparisons
        )

    def certify(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = run_certification_pipeline(payload, self.config)
        if result.get("certified") is True:
            key = str(result.get("strategy_key") or "")
            if key:
                self.registry.set_status(key, "certified")
        self.certifications.insert(0, {
            "certification_id": result.get("certification_id"),
            "strategy_key": result.get("strategy_key"),
            "version": result.get("version"),
            "certified": result.get("certified"),
        })
        if len(self.certifications) > 100:
            self.certifications = self.certifications[:100]
        return result

    def record_version(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.versions.record(payload)

    def list_versions(
        self, *, strategy_key: str | None = None, limit: int = 50
    ) -> dict[str, Any]:
        return self.versions.list(strategy_key=strategy_key, limit=limit)

    def rollback(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.rollback_engine.rollback(payload)

    def rollback_audit(self, *, limit: int = 50) -> dict[str, Any]:
        return self.rollback_engine.audit(limit=limit)

    def observatory(self, payload: dict[str, Any]) -> dict[str, Any]:
        return build_observatory(payload)

    def release(self, payload: dict[str, Any]) -> dict[str, Any]:
        return evaluate_release_governance(payload, self.config)
