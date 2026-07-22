"""Application service — Production Readiness Certification."""

from __future__ import annotations

from typing import Any

from app.domain.production_readiness_certification import (
    ProductionReadinessCertification,
)
from app.domain.production_readiness_certification.config import (
    DEFAULT_PRC_CONFIG,
    PrcConfig,
)
from app.domain.production_readiness_certification.orchestrator import (
    input_from_dict,
)


class ProductionReadinessCertificationService:
    def __init__(self, config: PrcConfig | None = None) -> None:
        self._system = ProductionReadinessCertification(
            config or DEFAULT_PRC_CONFIG
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
