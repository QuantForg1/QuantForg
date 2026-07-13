"""Dependencies for Execution Intelligence."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.application.services.execution_intelligence import ExecutionIntelligenceService
from app.domain.execution_intelligence.store import LifecycleStore


@lru_cache(maxsize=1)
def _store() -> LifecycleStore:
    return LifecycleStore()


@lru_cache(maxsize=1)
def get_execution_intelligence() -> ExecutionIntelligenceService:
    return ExecutionIntelligenceService(store=_store())


ExecutionIntelDep = Annotated[
    ExecutionIntelligenceService, Depends(get_execution_intelligence)
]
