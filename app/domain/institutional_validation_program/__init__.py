"""QuantForg Institutional Validation Program (IVP).

Read-only evidence framework that continuously evaluates whether QuantForg has
a statistically reliable trading edge. Never places trades, never modifies
strategies/execution/Risk/Safety/Decision, never auto-promotes research.
"""

from __future__ import annotations

from app.domain.institutional_validation_program.config import IvpConfig
from app.domain.institutional_validation_program.orchestrator import (
    InstitutionalValidationProgram,
)
from app.domain.institutional_validation_program.types import IvpInput

__all__ = [
    "InstitutionalValidationProgram",
    "IvpConfig",
    "IvpInput",
]
