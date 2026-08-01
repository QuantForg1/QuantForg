"""Live Trading Evidence Program — application facade."""

from __future__ import annotations

from typing import Any

from app.domain.live_trading_evidence.platform import (
    build_live_trading_evidence_noc_panels,
    build_live_trading_evidence_program,
)

__all__ = [
    "build_live_trading_evidence_noc_panels",
    "build_live_trading_evidence_program",
]


async def build_program() -> dict[str, Any]:
    return await build_live_trading_evidence_program()


async def build_noc_panels() -> dict[str, Any]:
    return await build_live_trading_evidence_noc_panels()
