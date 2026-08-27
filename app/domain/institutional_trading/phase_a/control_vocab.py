"""Canonical ALLOW / REDUCE / BLOCK / HALT mapping — compatibility layer."""

from __future__ import annotations

from enum import Enum
from typing import Any


class FinalControlState(str, Enum):
    ALLOW = "ALLOW"
    REDUCE = "REDUCE"
    BLOCK = "BLOCK"
    HALT = "HALT"


def map_to_final_control_state(
    *,
    halt_mode: str | None = None,
    burst_latched: bool = False,
    recon_blocking: bool = False,
    market_data_allow: bool = True,
    risk_decision: str | None = None,
    safety_allowed: bool | None = None,
    first_blocking_gate: str | None = None,
) -> tuple[FinalControlState, str | None]:
    """Resolve one canonical state without removing existing systems."""
    hm = str(halt_mode or "ACTIVE").upper()
    if hm in {"HALT_NEW_ENTRIES", "HALT_ALL_TRADING"}:
        return FinalControlState.HALT, first_blocking_gate or f"KILL_SWITCH:{hm}"
    if burst_latched:
        return FinalControlState.HALT, first_blocking_gate or "EXECUTION_REJECT_BURST"
    if recon_blocking:
        return (
            FinalControlState.BLOCK,
            first_blocking_gate or "UNKNOWN_ORDER_RECONCILIATION",
        )
    if not market_data_allow:
        return FinalControlState.BLOCK, first_blocking_gate or "STALE_MARKET_DATA"
    if safety_allowed is False:
        return FinalControlState.BLOCK, first_blocking_gate or "SAFETY"
    rd = str(risk_decision or "").upper()
    if rd in {"REJECT", "BLOCKED", "BLOCK"}:
        return FinalControlState.BLOCK, first_blocking_gate or "RISK_REJECT"
    if rd in {"REDUCE_SIZE", "REDUCE"}:
        return FinalControlState.REDUCE, first_blocking_gate
    if first_blocking_gate:
        return FinalControlState.BLOCK, first_blocking_gate
    return FinalControlState.ALLOW, None


def final_control_to_dict(
    state: FinalControlState, gate: str | None
) -> dict[str, Any]:
    return {
        "final_control_state": state.value,
        "first_blocking_gate": gate or None,
    }
