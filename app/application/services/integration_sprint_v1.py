"""Application service — Integration Sprint V1."""

from __future__ import annotations

from typing import Any

from app.domain.integration_sprint_v1.config import (
    DEFAULT_INTEGRATION_CONFIG,
    IntegrationSprintConfig,
)
from app.domain.integration_sprint_v1.orchestrator import (
    IntegrationSprintV1,
    build_feeds_from_runtime,
)


class IntegrationSprintV1Service:
    def __init__(
        self, config: IntegrationSprintConfig | None = None
    ) -> None:
        cfg = config or DEFAULT_INTEGRATION_CONFIG
        self._system = IntegrationSprintV1(
            config=cfg, feeds=build_feeds_from_runtime(cfg)
        )

    def status(self) -> dict[str, object]:
        return self._system.status()

    def policies(self) -> dict[str, object]:
        return self._system.config.to_dict()

    def update_policies(self, updates: dict[str, Any]) -> dict[str, object]:
        return self._system.update_policies(updates)

    def bus(self) -> dict[str, Any]:
        return self._system.bus_snapshot()

    def feed(self, name: str) -> dict[str, Any]:
        return self._system.feed(name)

    def hydrate(
        self, target: str, overrides: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return self._system.hydrate(target, overrides)

    def storage_append(
        self, namespace: str, record: dict[str, Any]
    ) -> dict[str, Any]:
        return self._system.storage_append(namespace, record)

    def storage_list(
        self, namespace: str, *, limit: int = 50
    ) -> dict[str, Any]:
        return self._system.storage_list(namespace, limit=limit)

    def ingest_warehouse(
        self, bars: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return self._system.ingest_warehouse(bars)
