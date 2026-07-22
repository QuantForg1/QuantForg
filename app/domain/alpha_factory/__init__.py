"""QuantForg Alpha Factory.

Isolated research environment for discovering and validating trading ideas.
Never modifies live strategy, Risk, Safety, Decision, Execution, or Auto Trading.
Never auto-promotes. Never fabricates metrics.
"""

from __future__ import annotations

from app.domain.alpha_factory.config import AlphaFactoryConfig
from app.domain.alpha_factory.orchestrator import AlphaFactory
from app.domain.alpha_factory.types import AlphaFactoryInput

__all__ = ["AlphaFactory", "AlphaFactoryConfig", "AlphaFactoryInput"]
