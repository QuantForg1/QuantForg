"""Future multi-asset execution architecture — DISABLED in this phase.

Documents CORE / RESEARCH / EXPANSION layers. No new symbol may reach OMS.
Does not import gateway_client, OMS, or order_send.
"""

from __future__ import annotations

from typing import Any

from app.domain.market_universe.constants import (
    ALLOW_LIVE_PROMOTION,
    ASSET_CLASSES,
    FROZEN_DIRECTIONAL_EDGE,
    FROZEN_MIN_RR,
    FROZEN_OPPORTUNITY_THRESHOLD,
    LAYER_CORE,
    LAYER_EXPANSION,
    LAYER_RESEARCH,
)
from app.domain.trading.gold_only import CANONICAL_GOLD_BROKER_DISPLAY, GOLD_SYMBOL


def describe_layers() -> dict[str, Any]:
    """Observational layer map. Layer 2 never merges into Layer 1."""
    return {
        "advisory_only": True,
        "authorizes_trade": False,
        "ALLOW_LIVE_PROMOTION": ALLOW_LIVE_PROMOTION,
        "layers_merged": False,
        LAYER_CORE: {
            "name": LAYER_CORE,
            "live": True,
            "broker_symbol": CANONICAL_GOLD_BROKER_DISPLAY,
            "canonical_symbol": GOLD_SYMBOL,
            "asset_class": "METALS",
            "opportunity": FROZEN_OPPORTUNITY_THRESHOLD,
            "directional_edge": FROZEN_DIRECTIONAL_EDGE,
            "rr": FROZEN_MIN_RR,
            "note": "Existing XAUUSD_i production path. Unchanged.",
        },
        LAYER_RESEARCH: {
            "name": LAYER_RESEARCH,
            "live": False,
            "universe": "broker_catalogue",
            "ALLOW_LIVE_PROMOTION": False,
            "may_call_oms": False,
            "may_call_gateway_order_send": False,
            "note": "All broker instruments. Observational only.",
        },
        LAYER_EXPANSION: {
            "name": LAYER_EXPANSION,
            "live": False,
            "ALLOW_LIVE_PROMOTION": False,
            "may_reach_oms": False,
            "requires_human_authorization": True,
            "note": "Future multi-asset live. Disabled this phase.",
        },
        "ASSET_CLASS_POLICY": {
            cls: {
                "may_send_order": False,
                "ALLOW_LIVE_PROMOTION": False,
                "live": cls == "METALS",
                "note": (
                    "METALS live is gold-only via CORE, not class-wide."
                    if cls == "METALS"
                    else "No live execution this phase."
                ),
            }
            for cls in ASSET_CLASSES
            if cls != "UNKNOWN"
        },
        "SYMBOL_POLICY": {
            "default_may_send_order": False,
            "allowlist_unchanged": True,
            "new_symbol_reaches_oms": False,
        },
        "SESSION_POLICY": {
            "filters_activated_live": False,
            "research_only": True,
        },
        "RISK_BUCKET": {
            "bypasses_risk": False,
            "research_observes_only": True,
        },
        "CORRELATION_BUCKET": {
            "bypasses_risk": False,
            "research_observes_only": True,
        },
    }


def symbol_may_reach_oms(symbol: str | None) -> bool:
    """Always False for expansion. CORE live path is outside this module."""
    _ = symbol
    return False
