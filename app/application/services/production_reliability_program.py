"""Production Reliability & Operational Excellence — application facade."""

from __future__ import annotations

from typing import Any

from app.domain.production_reliability.platform import (
    build_production_reliability_program,
    build_reliability_noc_panels,
)

__all__ = [
    "build_production_reliability_program",
    "build_reliability_noc_panels",
]


async def build_program() -> dict[str, Any]:
    return await build_production_reliability_program()


async def build_noc_panels() -> dict[str, Any]:
    return await build_reliability_noc_panels()
