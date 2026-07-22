"""Application service — Real Market Intelligence Platform."""

from __future__ import annotations

from typing import Any

from app.domain.real_market_intelligence_platform import (
    RealMarketIntelligencePlatform,
)
from app.domain.real_market_intelligence_platform.config import (
    DEFAULT_RMIP_CONFIG,
    RmipConfig,
)
from app.domain.real_market_intelligence_platform.orchestrator import (
    input_from_dict,
)


class RealMarketIntelligencePlatformService:
    def __init__(self, config: RmipConfig | None = None) -> None:
        self._system = RealMarketIntelligencePlatform(
            config or DEFAULT_RMIP_CONFIG
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
