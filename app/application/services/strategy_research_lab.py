"""Application service — Strategy Research Lab V1."""

from __future__ import annotations

from typing import Any

from app.domain.strategy_research_lab import StrategyResearchLab
from app.domain.strategy_research_lab.config import (
    DEFAULT_LAB_CONFIG,
    StrategyLabConfig,
)


class StrategyResearchLabService:
    """Lab facade — never order_send; never affects production positions."""

    def __init__(self, config: StrategyLabConfig | None = None) -> None:
        self._lab = StrategyResearchLab(config or DEFAULT_LAB_CONFIG)

    def status(self) -> dict[str, object]:
        return self._lab.status()

    def registry(self) -> dict[str, object]:
        return self._lab.registry.to_dict()

    def compare(self, runs: list[dict[str, Any]]) -> dict[str, object]:
        return self._lab.compare(runs)

    def scorecard(self, payload: dict[str, Any]) -> dict[str, object]:
        return self._lab.scorecard(payload)

    def validate(self, payload: dict[str, Any]) -> dict[str, object]:
        return self._lab.validate(payload)

    def replay_load(self, payload: dict[str, Any]) -> dict[str, object]:
        bars = payload.get("bars") or []
        if not isinstance(bars, list):
            bars = []
        return self._lab.replay.load(
            strategy_key=str(payload.get("strategy_key") or "unknown"),
            bars=bars,
        )

    def replay_control(self, action: str) -> dict[str, object]:
        act = action.strip().lower()
        if act == "start":
            return self._lab.replay.start()
        if act == "pause":
            return self._lab.replay.pause()
        if act == "resume":
            return self._lab.replay.resume()
        if act == "step":
            return self._lab.replay.step()
        return self._lab.replay.snapshot()

    def experiment_create(self, payload: dict[str, Any]) -> dict[str, object]:
        variants = payload.get("variants") or []
        if not isinstance(variants, list):
            variants = []
        return self._lab.experiments.create_batch(
            strategy_key=str(payload.get("strategy_key") or "unknown"),
            variants=variants,
        )

    def experiment_results(self, payload: dict[str, Any]) -> dict[str, object] | None:
        results = payload.get("results") or []
        if not isinstance(results, list):
            results = []
        return self._lab.experiments.record_results(
            batch_id=str(payload.get("batch_id") or ""),
            results=results,
        )

    def experiment_list(
        self, strategy_key: str | None = None
    ) -> list[dict[str, object]]:
        return self._lab.experiments.list_batches(strategy_key=strategy_key)

    def version_record(self, payload: dict[str, Any]) -> dict[str, object]:
        params = payload.get("parameters") or {}
        if not isinstance(params, dict):
            params = {}
        return self._lab.versions.record(
            strategy_key=str(payload.get("strategy_key") or "unknown"),
            version=str(payload.get("version") or "0.0.1"),
            parameters=params,
            notes=str(payload.get("notes") or ""),
            created_by=str(payload.get("created_by") or "operator"),
        )

    def version_list(self, strategy_key: str) -> list[dict[str, object]]:
        return self._lab.versions.list_versions(strategy_key)

    def promotion_open(self, payload: dict[str, Any]) -> dict[str, object]:
        return self._lab.open_promotion(payload)

    def promotion_approve(self, payload: dict[str, Any]) -> dict[str, object] | None:
        return self._lab.approve(payload)

    def promotion_dashboard(self) -> dict[str, object]:
        return self._lab.promotion.dashboard()
