"""Multi-Agent AI Architecture — XAUUSD advisory collaboration only."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.domain.trading.gold_only import GOLD_SYMBOL


@dataclass
class MultiAgentConfig:
    """Configurable knobs — never bypass Risk/Safety, never order_send."""

    version: str = "multi-agent-ai-v1.0.0"
    symbol: str = GOLD_SYMBOL
    min_vote_confidence: Decimal = Decimal("55")
    quorum_agents: int = 4
    max_events: int = 2000
    max_sessions: int = 200
    max_memory: int = 500
    allow_bypass_risk: bool = False
    allow_bypass_safety: bool = False
    allow_order_send: bool = False
    allow_memory_rewrite_rules: bool = False
    feature_flags: dict[str, bool] = field(
        default_factory=lambda: {
            "agents_enabled": True,
            "confidence_voting": True,
            "ai_memory": True,
            "ai_governance": True,
            "decision_coordinator": True,
        }
    )

    def __post_init__(self) -> None:
        self.symbol = GOLD_SYMBOL
        self.allow_bypass_risk = False
        self.allow_bypass_safety = False
        self.allow_order_send = False
        self.allow_memory_rewrite_rules = False

    def update(self, updates: dict[str, object]) -> MultiAgentConfig:
        locked = {
            "allow_bypass_risk",
            "allow_bypass_safety",
            "allow_order_send",
            "allow_memory_rewrite_rules",
            "symbol",
            "version",
        }
        data = self.to_dict()
        for key, value in updates.items():
            if key in locked or value is None:
                continue
            if key == "feature_flags" and isinstance(value, dict):
                flags = dict(data["feature_flags"])  # type: ignore[arg-type]
                for fk, fv in value.items():
                    if isinstance(fv, bool) and fk not in {
                        "bypass_risk",
                        "bypass_safety",
                        "order_send",
                        "rewrite_rules",
                    }:
                        flags[str(fk)] = fv
                data["feature_flags"] = flags
            elif key in data:
                data[key] = value
        return MultiAgentConfig(
            min_vote_confidence=Decimal(str(data["min_vote_confidence"])),
            quorum_agents=int(data["quorum_agents"]),
            max_events=int(data["max_events"]),
            max_sessions=int(data["max_sessions"]),
            max_memory=int(data["max_memory"]),
            feature_flags=dict(data["feature_flags"]),  # type: ignore[arg-type]
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "symbol": self.symbol,
            "min_vote_confidence": str(self.min_vote_confidence),
            "quorum_agents": self.quorum_agents,
            "max_events": self.max_events,
            "max_sessions": self.max_sessions,
            "max_memory": self.max_memory,
            "allow_bypass_risk": False,
            "allow_bypass_safety": False,
            "allow_order_send": False,
            "allow_memory_rewrite_rules": False,
            "feature_flags": dict(self.feature_flags),
        }


DEFAULT_MULTI_AGENT_CONFIG = MultiAgentConfig()
