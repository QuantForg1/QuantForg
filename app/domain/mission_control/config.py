"""Mission Control configuration — executive dashboard identity."""

from __future__ import annotations

from dataclasses import dataclass, field

PANEL_IDS: tuple[str, ...] = (
    "executive_status",
    "capital_overview",
    "risk_radar",
    "live_ai_decisions",
    "live_positions",
    "incident_center",
    "production_timeline",
    "system_health",
    "ai_health",
    "emergency_panel",
    "xauusd_watchlist",
    "daily_summary",
    "operator_notes",
    "global_search",
    "floating_action_bar",
)


@dataclass(frozen=True)
class MissionControlConfig:
    """Executive dashboard only — not Monitoring observability."""

    product: str = "QuantForg Mission Control"
    version: str = "1"
    symbol: str = "XAUUSD"
    is_monitoring: bool = False
    fabricates_metrics: bool = False
    max_notes: int = 200
    max_timeline: int = 40
    max_incidents: int = 20
    max_decisions: int = 15
    desk_catalog: tuple[dict[str, str], ...] = field(
        default_factory=lambda: (
            {"href": "/terminal", "label": "Terminal", "group": "execution"},
            {"href": "/ops", "label": "Ops control", "group": "emergency"},
            {"href": "/monitoring", "label": "Monitoring", "group": "observability"},
            {"href": "/risk", "label": "Risk", "group": "risk"},
            {
                "href": "/decision-intelligence",
                "label": "Decision Center",
                "group": "ai",
            },
            {"href": "/institutional-decision", "label": "AI Decision", "group": "ai"},
            {"href": "/ai-robot", "label": "AI Robot", "group": "ai"},
            {"href": "/market-intelligence", "label": "Market Intel", "group": "ai"},
            {"href": "/auto-trading", "label": "Auto Trading", "group": "execution"},
            {"href": "/book", "label": "Book", "group": "capital"},
            {"href": "/journal", "label": "Journal", "group": "ops"},
            {"href": "/gateway", "label": "Gateway", "group": "ops"},
        )
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "product": self.product,
            "version": self.version,
            "symbol": self.symbol,
            "is_monitoring": self.is_monitoring,
            "fabricates_metrics": self.fabricates_metrics,
            "panels": list(PANEL_IDS),
            "desk_catalog": list(self.desk_catalog),
        }


DEFAULT_MC_CONFIG = MissionControlConfig()
