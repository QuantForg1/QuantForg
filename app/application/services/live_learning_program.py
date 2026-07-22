"""Application service — Live Learning Program."""

from __future__ import annotations

from typing import Any

from app.domain.live_learning_program import LiveLearningProgram
from app.domain.live_learning_program.config import (
    DEFAULT_LLP_CONFIG,
    LlpConfig,
)
from app.domain.live_learning_program.orchestrator import input_from_dict


class LiveLearningProgramService:
    def __init__(self, config: LlpConfig | None = None) -> None:
        self._system = LiveLearningProgram(config or DEFAULT_LLP_CONFIG)

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
