"""QuantForg Live Learning Program (LLP).

Continuously collects evidence from live, paper, replay, and operator feedback
to improve research quality. Never places trades, never modifies strategy rules,
Risk/Safety/Decision/Execution, never auto-tunes, never auto-promotes.
"""

from __future__ import annotations

from app.domain.live_learning_program.config import LlpConfig
from app.domain.live_learning_program.orchestrator import LiveLearningProgram
from app.domain.live_learning_program.types import LlpInput

__all__ = ["LiveLearningProgram", "LlpConfig", "LlpInput"]
