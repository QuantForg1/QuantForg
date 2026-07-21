"""Application service — Research & Validation Platform."""

from __future__ import annotations

from typing import Any

from app.domain.research_validation_platform import ResearchValidationPlatform
from app.domain.research_validation_platform.config import (
    DEFAULT_RVP_CONFIG,
    ResearchValidationConfig,
)


class ResearchValidationService:
    def __init__(self, config: ResearchValidationConfig | None = None) -> None:
        self._platform = ResearchValidationPlatform(
            config or DEFAULT_RVP_CONFIG
        )

    def status(self) -> dict[str, object]:
        return self._platform.status()

    def policies(self) -> dict[str, object]:
        return self._platform.config.to_dict()

    def update_policies(self, updates: dict[str, Any]) -> dict[str, object]:
        return self._platform.update_policies(updates)

    def registry(self) -> dict[str, Any]:
        return self._platform.list_registry()

    def register(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._platform.register_strategy(payload)

    def replay_load(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._platform.replay_load(payload)

    def replay_step(self) -> dict[str, Any]:
        return self._platform.replay_step()

    def walk_forward(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._platform.walk_forward(payload)

    def paper(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._platform.paper(payload)

    def compare(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._platform.compare(payload)

    def certify(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._platform.certify(payload)

    def record_version(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._platform.record_version(payload)

    def versions(
        self, *, strategy_key: str | None = None, limit: int = 50
    ) -> dict[str, Any]:
        return self._platform.list_versions(
            strategy_key=strategy_key, limit=limit
        )

    def rollback(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._platform.rollback(payload)

    def rollback_audit(self, *, limit: int = 50) -> dict[str, Any]:
        return self._platform.rollback_audit(limit=limit)

    def observatory(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._platform.observatory(payload)

    def release(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._platform.release(payload)
