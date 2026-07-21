"""Application service — QuantForg Multi-Agent AI Architecture."""

from __future__ import annotations

from typing import Any

from app.domain.multi_agent_ai import MultiAgentSystem
from app.domain.multi_agent_ai.config import (
    DEFAULT_MULTI_AGENT_CONFIG,
    MultiAgentConfig,
)
from app.domain.multi_agent_ai.orchestrator import input_from_dict


class MultiAgentAIService:
    def __init__(self, config: MultiAgentConfig | None = None) -> None:
        self._system = MultiAgentSystem(config or DEFAULT_MULTI_AGENT_CONFIG)

    def status(self) -> dict[str, object]:
        return self._system.status()

    def policies(self) -> dict[str, object]:
        return self._system.config.to_dict()

    def update_policies(self, updates: dict[str, Any]) -> dict[str, object]:
        return self._system.update_policies(updates)

    def events(
        self, *, limit: int = 100, session_id: str | None = None
    ) -> dict[str, Any]:
        return self._system.list_events(limit=limit, session_id=session_id)

    def memory(
        self, *, limit: int = 50, kind: str | None = None
    ) -> dict[str, Any]:
        return self._system.list_memory(limit=limit, kind=kind)

    def store_memory(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._system.store_memory(
            kind=str(payload.get("kind") or "observation"),
            agent=str(payload.get("agent") or "operator"),
            content=payload.get("content")
            if isinstance(payload.get("content"), dict)
            else {},
            session_id=(
                str(payload["session_id"]) if payload.get("session_id") else None
            ),
        )

    def governance(self) -> dict[str, Any]:
        return self._system.governance_status()

    def collaborate(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._system.collaborate(input_from_dict(payload))
