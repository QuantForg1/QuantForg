"""Application service — Adaptive Scalping Intelligence."""

from __future__ import annotations

from typing import Any

from app.domain.adaptive_scalping_intelligence import AdaptiveScalpingIntelligence
from app.domain.adaptive_scalping_intelligence.config import (
    DEFAULT_ASI_CONFIG,
    AsiConfig,
)
from app.domain.adaptive_scalping_intelligence.orchestrator import input_from_dict


class AdaptiveScalpingIntelligenceService:
    def __init__(self, config: AsiConfig | None = None) -> None:
        self._system = AdaptiveScalpingIntelligence(
            config or DEFAULT_ASI_CONFIG
        )

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
