"""Application service — Institutional Trading Brain V3."""

from __future__ import annotations

from typing import Any

from app.domain.trading_brain_v3 import TradingBrainV3
from app.domain.trading_brain_v3.config import (
    DEFAULT_BRAIN_CONFIG,
    TradingBrainConfig,
)
from app.domain.trading_brain_v3.orchestrator import input_from_dict


class TradingBrainV3Service:
    def __init__(self, config: TradingBrainConfig | None = None) -> None:
        self._brain = TradingBrainV3(config or DEFAULT_BRAIN_CONFIG)

    def status(self) -> dict[str, object]:
        return self._brain.status()

    def policies(self) -> dict[str, object]:
        return self._brain.config.to_dict()

    def update_policies(self, updates: dict[str, Any]) -> dict[str, object]:
        return self._brain.update_policies(updates)

    def history(self, *, limit: int = 50) -> dict[str, Any]:
        return self._brain.list_history(limit=limit)

    def evaluate(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._brain.evaluate(input_from_dict(payload))
