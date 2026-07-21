"""QuantForg Multi-Agent AI Architecture.

Independent institutional agents collaborate before any trade is approved.
Risk and Safety remain authoritative. Execution pipeline unchanged.
Coordinator may reject; never bypasses. AI Memory never rewrites rules.
"""

from __future__ import annotations

from app.domain.multi_agent_ai.config import MultiAgentConfig
from app.domain.multi_agent_ai.orchestrator import MultiAgentSystem
from app.domain.multi_agent_ai.types import CollaborationInput

__all__ = [
    "CollaborationInput",
    "MultiAgentConfig",
    "MultiAgentSystem",
]
