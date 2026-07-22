"""Application service — Institutional Edge Engine."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_edge_engine import InstitutionalEdgeEngine
from app.domain.institutional_edge_engine.config import (
    DEFAULT_IEE_CONFIG,
    IeeConfig,
)
from app.domain.institutional_edge_engine.orchestrator import input_from_dict


class InstitutionalEdgeEngineService:
    def __init__(self, config: IeeConfig | None = None) -> None:
        self._system = InstitutionalEdgeEngine(config or DEFAULT_IEE_CONFIG)

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
