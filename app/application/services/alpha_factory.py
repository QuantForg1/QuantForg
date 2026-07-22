"""Application service — Alpha Factory."""

from __future__ import annotations

from typing import Any

from app.domain.alpha_factory import AlphaFactory
from app.domain.alpha_factory.config import (
    DEFAULT_ALPHA_FACTORY_CONFIG,
    AlphaFactoryConfig,
)
from app.domain.alpha_factory.orchestrator import input_from_dict


class AlphaFactoryService:
    def __init__(self, config: AlphaFactoryConfig | None = None) -> None:
        self._system = AlphaFactory(config or DEFAULT_ALPHA_FACTORY_CONFIG)

    def status(self) -> dict[str, object]:
        return self._system.status()

    def policies(self) -> dict[str, object]:
        return self._system.config.to_dict()

    def update_policies(self, updates: dict[str, Any]) -> dict[str, object]:
        return self._system.update_policies(updates)

    def history(self, *, limit: int = 50) -> dict[str, Any]:
        return self._system.list_history(limit=limit)

    def evaluate(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._system.evaluate(input_from_dict(payload))
