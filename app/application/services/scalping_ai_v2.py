"""Application service — Institutional XAUUSD Scalping AI V2."""

from __future__ import annotations

from typing import Any

from app.domain.scalping_ai_v2 import ScalpingAiV2
from app.domain.scalping_ai_v2.config import (
    DEFAULT_SCALPING_CONFIG,
    ScalpingAiV2Config,
)
from app.domain.scalping_ai_v2.orchestrator import input_from_dict


class ScalpingAiV2Service:
    def __init__(self, config: ScalpingAiV2Config | None = None) -> None:
        self._system = ScalpingAiV2(config or DEFAULT_SCALPING_CONFIG)

    def status(self) -> dict[str, object]:
        return self._system.status()

    def policies(self) -> dict[str, object]:
        return self._system.config.to_dict()

    def update_policies(self, updates: dict[str, Any]) -> dict[str, object]:
        return self._system.update_policies(updates)

    def events(
        self, *, limit: int = 100, cycle_id: str | None = None
    ) -> dict[str, Any]:
        return self._system.list_events(limit=limit, cycle_id=cycle_id)

    def history(self, *, limit: int = 50) -> dict[str, Any]:
        return self._system.list_history(limit=limit)

    def cycle(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._system.run_cycle(input_from_dict(payload))
