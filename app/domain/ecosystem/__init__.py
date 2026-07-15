"""QuantForg Trading Ecosystem domain package."""

from __future__ import annotations

from app.domain.ecosystem.coach import coach_from_trades
from app.domain.ecosystem.reports import build_period_report
from app.domain.ecosystem.store import LEARNING_CATALOG, get_ecosystem_store

__all__ = [
    "LEARNING_CATALOG",
    "build_period_report",
    "coach_from_trades",
    "get_ecosystem_store",
]
