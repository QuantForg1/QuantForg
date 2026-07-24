"""Clean deps for Portfolio Intelligence."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.application.services.portfolio_intelligence_lab import PortfolioIntelligenceService


@lru_cache(maxsize=1)
def get_portfolio_intelligence() -> PortfolioIntelligenceService:
    return PortfolioIntelligenceService()


PortfolioIntelDep = Annotated[
    PortfolioIntelligenceService, Depends(get_portfolio_intelligence)
]
