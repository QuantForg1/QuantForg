"""Execution quality gate before canary/live promotion."""

from __future__ import annotations

from typing import Any


def evaluate_execution_quality(
    *,
    spread_ok: bool,
    quote_fresh: bool,
    gateway_rtt_ms: float | None,
    mt5_rtt_ms: float | None,
    slippage_ok: bool,
    fill_quality_ok: bool,
    order_ack_ok: bool,
    reconciliation_ok: bool,
    max_gateway_rtt_ms: float = 2000.0,
    max_mt5_rtt_ms: float = 2000.0,
) -> dict[str, Any]:
    reasons: list[str] = []
    if not spread_ok:
        reasons.append("spread")
    if not quote_fresh:
        reasons.append("stale_quote")
    if gateway_rtt_ms is None or gateway_rtt_ms > max_gateway_rtt_ms:
        reasons.append("gateway_rtt")
    if mt5_rtt_ms is None or mt5_rtt_ms > max_mt5_rtt_ms:
        reasons.append("mt5_rtt")
    if not slippage_ok:
        reasons.append("slippage")
    if not fill_quality_ok:
        reasons.append("fill_quality")
    if not order_ack_ok:
        reasons.append("order_ack")
    if not reconciliation_ok:
        reasons.append("reconciliation")
    if reasons:
        return {
            "result": "EXECUTION_GATE_FAILED",
            "why_blocked": ",".join(reasons),
            "promotable": False,
        }
    return {
        "result": "EXECUTION_GATE_PASSED",
        "why_blocked": None,
        "promotable": True,
    }
