"""Intelligence Platform configuration — research only, never production."""

from __future__ import annotations

from dataclasses import dataclass, field

PANEL_IDS: tuple[str, ...] = (
    "replay_studio",
    "candle_playback",
    "decision_inspector",
    "trade_review_center",
    "ai_evaluation_dashboard",
    "research_workspace",
    "knowledge_base",
    "weekly_reports",
    "monthly_performance_reports",
    "strategy_promotion_workflow",
    "strategy_registry_foundation",
    "ai_governance_audit",
)


@dataclass(frozen=True)
class IntelligencePlatformConfig:
    product: str = "QuantForg Intelligence Platform"
    version: str = "1"
    symbol: str = "XAUUSD"
    never_submits_orders: bool = True
    never_affects_production: bool = True
    fabricates_metrics: bool = False
    max_knowledge: int = 200
    max_decisions: int = 30
    max_trades: int = 40
    max_audits: int = 40
    deep_links: tuple[dict[str, str], ...] = field(
        default_factory=lambda: (
            {"href": "/research", "label": "Research OS", "group": "workspace"},
            {"href": "/strategy-lab", "label": "Strategy Lab", "group": "lab"},
            {"href": "/trade-replay", "label": "Trade Replay", "group": "replay"},
            {
                "href": "/decision-intelligence",
                "label": "Decision Center",
                "group": "decision",
            },
            {"href": "/journal", "label": "Journal", "group": "review"},
            {"href": "/analytics", "label": "Analytics", "group": "reports"},
            {
                "href": "/mission-control",
                "label": "Mission Control",
                "group": "ops",
            },
        )
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "product": self.product,
            "version": self.version,
            "symbol": self.symbol,
            "never_submits_orders": self.never_submits_orders,
            "never_affects_production": self.never_affects_production,
            "fabricates_metrics": self.fabricates_metrics,
            "panels": list(PANEL_IDS),
            "deep_links": list(self.deep_links),
        }


DEFAULT_IP_CONFIG = IntelligencePlatformConfig()
