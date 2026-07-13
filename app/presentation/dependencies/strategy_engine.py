"""Dependencies for the Strategy Engine (additive to Strategy Runtime)."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.application.services.strategy_engine import StrategyEngine


@lru_cache(maxsize=1)
def _engine_singleton() -> StrategyEngine:
    return StrategyEngine()


def get_strategy_engine() -> StrategyEngine:
    return _engine_singleton()


StrategyEngineDep = Annotated[StrategyEngine, Depends(get_strategy_engine)]
