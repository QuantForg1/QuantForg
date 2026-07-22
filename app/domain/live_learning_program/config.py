"""Live Learning Program — read-only evidence collection config."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.trading.gold_only import GOLD_SYMBOL

OPERATOR_TAGS = (
    "good_setup",
    "bad_setup",
    "late_entry",
    "early_exit",
    "execution_issue",
    "market_anomaly",
    "research_idea",
)

JOURNAL_DAY_TYPES = (
    "trend_days",
    "range_days",
    "news_days",
    "high_volatility",
    "low_volatility",
    "session_observations",
)


@dataclass
class LlpConfig:
    version: str = "llp-v1.0.0"
    symbol: str = GOLD_SYMBOL
    min_observations_for_edge: int = 20
    min_observations_for_calibration: int = 15
    min_evidence_for_live_change_rec: int = 100
    max_observations: int = 5_000
    max_feedback: int = 2_000
    max_journal: int = 1_000
    max_history: int = 300
    # Hard locks — evidence only
    allow_order_send: bool = False
    allow_place_trades: bool = False
    allow_modify_strategy_rules: bool = False
    allow_modify_risk_engine: bool = False
    allow_modify_safety_engine: bool = False
    allow_modify_decision_engine: bool = False
    allow_modify_execution_pipeline: bool = False
    allow_auto_tune_parameters: bool = False
    allow_auto_promote_strategies: bool = False
    invent_evidence: bool = False
    feature_flags: dict[str, bool] = field(
        default_factory=lambda: {
            "live_observation_collector": True,
            "replay_comparison": True,
            "operator_feedback": True,
            "edge_evolution": True,
            "market_behaviour_journal": True,
            "confidence_tracking": True,
            "weekly_review": True,
            "monthly_research_review": True,
            "learning_dashboard": True,
            "research_recommendations": True,
        }
    )

    def __post_init__(self) -> None:
        self.symbol = GOLD_SYMBOL
        self.allow_order_send = False
        self.allow_place_trades = False
        self.allow_modify_strategy_rules = False
        self.allow_modify_risk_engine = False
        self.allow_modify_safety_engine = False
        self.allow_modify_decision_engine = False
        self.allow_modify_execution_pipeline = False
        self.allow_auto_tune_parameters = False
        self.allow_auto_promote_strategies = False
        self.invent_evidence = False

    def update(self, updates: dict[str, object]) -> LlpConfig:
        locked = {
            "allow_order_send",
            "allow_place_trades",
            "allow_modify_strategy_rules",
            "allow_modify_risk_engine",
            "allow_modify_safety_engine",
            "allow_modify_decision_engine",
            "allow_modify_execution_pipeline",
            "allow_auto_tune_parameters",
            "allow_auto_promote_strategies",
            "invent_evidence",
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
                    if isinstance(fv, bool):
                        flags[str(fk)] = fv
                data["feature_flags"] = flags
            elif key in data:
                data[key] = value
        return LlpConfig(
            min_observations_for_edge=int(data["min_observations_for_edge"]),
            min_observations_for_calibration=int(
                data["min_observations_for_calibration"]
            ),
            min_evidence_for_live_change_rec=int(
                data["min_evidence_for_live_change_rec"]
            ),
            max_observations=int(data["max_observations"]),
            max_feedback=int(data["max_feedback"]),
            max_journal=int(data["max_journal"]),
            max_history=int(data["max_history"]),
            feature_flags=dict(data["feature_flags"]),  # type: ignore[arg-type]
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "symbol": self.symbol,
            "min_observations_for_edge": self.min_observations_for_edge,
            "min_observations_for_calibration": (
                self.min_observations_for_calibration
            ),
            "min_evidence_for_live_change_rec": (
                self.min_evidence_for_live_change_rec
            ),
            "max_observations": self.max_observations,
            "max_feedback": self.max_feedback,
            "max_journal": self.max_journal,
            "max_history": self.max_history,
            "allow_order_send": False,
            "allow_place_trades": False,
            "allow_modify_strategy_rules": False,
            "allow_modify_risk_engine": False,
            "allow_modify_safety_engine": False,
            "allow_modify_decision_engine": False,
            "allow_modify_execution_pipeline": False,
            "allow_auto_tune_parameters": False,
            "allow_auto_promote_strategies": False,
            "invent_evidence": False,
            "feature_flags": dict(self.feature_flags),
            "read_only": True,
            "evidence_only": True,
            "operator_tags": list(OPERATOR_TAGS),
            "journal_day_types": list(JOURNAL_DAY_TYPES),
        }


DEFAULT_LLP_CONFIG = LlpConfig()
