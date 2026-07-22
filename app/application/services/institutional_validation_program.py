"""Application service — Institutional Validation Program."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_validation_program import (
    InstitutionalValidationProgram,
)
from app.domain.institutional_validation_program.config import (
    DEFAULT_IVP_CONFIG,
    IvpConfig,
)
from app.domain.institutional_validation_program.orchestrator import (
    input_from_dict,
)


class InstitutionalValidationProgramService:
    def __init__(self, config: IvpConfig | None = None) -> None:
        self._system = InstitutionalValidationProgram(
            config or DEFAULT_IVP_CONFIG
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
