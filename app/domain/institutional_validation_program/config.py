"""Institutional Validation Program — read-only evidence config."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.domain.trading.gold_only import GOLD_SYMBOL


@dataclass
class IvpConfig:
    version: str = "ivp-v1.0.0"
    symbol: str = GOLD_SYMBOL
    min_trades_for_evidence: int = 30
    min_trades_for_regime: int = 10
    min_trades_for_comparison: int = 15
    rolling_windows: tuple[int, ...] = (50, 100, 250)
    confidence_z: Decimal = Decimal("1.96")  # ~95% when sample allows
    max_history: int = 300
    # Hard locks — read-only
    allow_order_send: bool = False
    allow_place_trades: bool = False
    allow_modify_strategies: bool = False
    allow_modify_execution: bool = False
    allow_modify_risk_engine: bool = False
    allow_modify_safety_engine: bool = False
    allow_modify_decision_engine: bool = False
    allow_auto_promote_research: bool = False
    invent_evidence: bool = False
    promise_profitability: bool = False
    feature_flags: dict[str, bool] = field(
        default_factory=lambda: {
            "statistical_validation": True,
            "confidence_analysis": True,
            "regime_validation": True,
            "configuration_comparison": True,
            "stability_analysis": True,
            "risk_validation": True,
            "replay_vs_paper": True,
            "evidence_dashboard": True,
            "human_decision_package": True,
            "validation_history": True,
        }
    )

    def __post_init__(self) -> None:
        self.symbol = GOLD_SYMBOL
        self.allow_order_send = False
        self.allow_place_trades = False
        self.allow_modify_strategies = False
        self.allow_modify_execution = False
        self.allow_modify_risk_engine = False
        self.allow_modify_safety_engine = False
        self.allow_modify_decision_engine = False
        self.allow_auto_promote_research = False
        self.invent_evidence = False
        self.promise_profitability = False

    def update(self, updates: dict[str, object]) -> IvpConfig:
        locked = {
            "allow_order_send",
            "allow_place_trades",
            "allow_modify_strategies",
            "allow_modify_execution",
            "allow_modify_risk_engine",
            "allow_modify_safety_engine",
            "allow_modify_decision_engine",
            "allow_auto_promote_research",
            "invent_evidence",
            "promise_profitability",
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
            elif key == "rolling_windows" and isinstance(value, (list, tuple)):
                data["rolling_windows"] = [int(x) for x in value]
            elif key in data:
                data[key] = value
        return IvpConfig(
            min_trades_for_evidence=int(data["min_trades_for_evidence"]),
            min_trades_for_regime=int(data["min_trades_for_regime"]),
            min_trades_for_comparison=int(data["min_trades_for_comparison"]),
            rolling_windows=tuple(data["rolling_windows"]),  # type: ignore[arg-type]
            confidence_z=Decimal(str(data["confidence_z"])),
            max_history=int(data["max_history"]),
            feature_flags=dict(data["feature_flags"]),  # type: ignore[arg-type]
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "symbol": self.symbol,
            "min_trades_for_evidence": self.min_trades_for_evidence,
            "min_trades_for_regime": self.min_trades_for_regime,
            "min_trades_for_comparison": self.min_trades_for_comparison,
            "rolling_windows": list(self.rolling_windows),
            "confidence_z": str(self.confidence_z),
            "max_history": self.max_history,
            "allow_order_send": False,
            "allow_place_trades": False,
            "allow_modify_strategies": False,
            "allow_modify_execution": False,
            "allow_modify_risk_engine": False,
            "allow_modify_safety_engine": False,
            "allow_modify_decision_engine": False,
            "allow_auto_promote_research": False,
            "invent_evidence": False,
            "promise_profitability": False,
            "feature_flags": dict(self.feature_flags),
            "read_only": True,
        }


DEFAULT_IVP_CONFIG = IvpConfig()
