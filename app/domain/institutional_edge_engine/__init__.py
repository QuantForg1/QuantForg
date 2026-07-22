"""QuantForg Institutional Edge Engine (IEE).

Advisory analytics that measure and explain trading edge from supplied
completed trades. Never modifies Auto Trading, Execution, Decision, Risk,
Safety, or ASI. Never fabricates metrics; reports Insufficient Data instead.
"""

from __future__ import annotations

from app.domain.institutional_edge_engine.config import IeeConfig
from app.domain.institutional_edge_engine.orchestrator import (
    InstitutionalEdgeEngine,
)
from app.domain.institutional_edge_engine.types import IeeInput

__all__ = ["IeeConfig", "IeeInput", "InstitutionalEdgeEngine"]
