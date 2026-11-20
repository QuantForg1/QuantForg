"""Observation-only market report. It cannot place or change orders."""

from app.domain.market_observation.report import (
    ObservationInput,
    build_market_observation,
)

__all__ = ["ObservationInput", "build_market_observation"]
