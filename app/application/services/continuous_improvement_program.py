"""Continuous Improvement Program — application facade."""

from __future__ import annotations

from typing import Any

from app.domain.continuous_improvement.platform import (
    build_continuous_improvement_noc_panels,
    build_continuous_improvement_program,
)

__all__ = [
    "build_continuous_improvement_noc_panels",
    "build_continuous_improvement_program",
]


async def build_program() -> dict[str, Any]:
    return await build_continuous_improvement_program()


async def build_noc_panels() -> dict[str, Any]:
    return await build_continuous_improvement_noc_panels()
