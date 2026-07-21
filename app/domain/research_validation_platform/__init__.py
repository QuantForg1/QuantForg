"""QuantForg Research & Validation Platform.

Institutional environment where every strategy is validated before production.
XAUUSD only. Live execution pipeline unchanged. Reproducible validations.
Traceable versions. Certification mandatory. Rollback preserves audit history.
"""

from __future__ import annotations

from app.domain.research_validation_platform.config import (
    ResearchValidationConfig,
)
from app.domain.research_validation_platform.orchestrator import (
    ResearchValidationPlatform,
)

__all__ = ["ResearchValidationConfig", "ResearchValidationPlatform"]
