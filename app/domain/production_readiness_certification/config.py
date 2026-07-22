"""Production Readiness Certification — read-only certification config."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.domain.trading.gold_only import GOLD_SYMBOL

VERDICTS = ("PASS", "WATCH", "FAIL")


@dataclass
class PrcConfig:
    version: str = "prc-v1.0.0"
    symbol: str = GOLD_SYMBOL
    pass_threshold: Decimal = Decimal("80")
    watch_threshold: Decimal = Decimal("60")
    max_history: int = 300
    # Hard locks — certify only
    allow_order_send: bool = False
    allow_place_trades: bool = False
    allow_change_strategies: bool = False
    allow_modify_risk_engine: bool = False
    allow_modify_safety_engine: bool = False
    allow_modify_decision_engine: bool = False
    allow_modify_execution_pipeline: bool = False
    allow_modify_auto_trading: bool = False
    allow_change_configuration_automatically: bool = False
    invent_evidence: bool = False
    feature_flags: dict[str, bool] = field(
        default_factory=lambda: {
            "reliability_certification": True,
            "risk_certification": True,
            "execution_certification": True,
            "decision_certification": True,
            "data_certification": True,
            "research_certification": True,
            "operational_certification": True,
            "readiness_dashboard": True,
            "human_signoff_package": True,
            "continuous_certification": True,
        }
    )

    def __post_init__(self) -> None:
        self.symbol = GOLD_SYMBOL
        self.allow_order_send = False
        self.allow_place_trades = False
        self.allow_change_strategies = False
        self.allow_modify_risk_engine = False
        self.allow_modify_safety_engine = False
        self.allow_modify_decision_engine = False
        self.allow_modify_execution_pipeline = False
        self.allow_modify_auto_trading = False
        self.allow_change_configuration_automatically = False
        self.invent_evidence = False

    def update(self, updates: dict[str, object]) -> PrcConfig:
        locked = {
            "allow_order_send",
            "allow_place_trades",
            "allow_change_strategies",
            "allow_modify_risk_engine",
            "allow_modify_safety_engine",
            "allow_modify_decision_engine",
            "allow_modify_execution_pipeline",
            "allow_modify_auto_trading",
            "allow_change_configuration_automatically",
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
        return PrcConfig(
            pass_threshold=Decimal(str(data["pass_threshold"])),
            watch_threshold=Decimal(str(data["watch_threshold"])),
            max_history=int(data["max_history"]),
            feature_flags=dict(data["feature_flags"]),  # type: ignore[arg-type]
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "symbol": self.symbol,
            "pass_threshold": str(self.pass_threshold),
            "watch_threshold": str(self.watch_threshold),
            "max_history": self.max_history,
            "allow_order_send": False,
            "allow_place_trades": False,
            "allow_change_strategies": False,
            "allow_modify_risk_engine": False,
            "allow_modify_safety_engine": False,
            "allow_modify_decision_engine": False,
            "allow_modify_execution_pipeline": False,
            "allow_modify_auto_trading": False,
            "allow_change_configuration_automatically": False,
            "invent_evidence": False,
            "feature_flags": dict(self.feature_flags),
            "read_only": True,
            "certifies_only": True,
            "verdicts": list(VERDICTS),
        }


DEFAULT_PRC_CONFIG = PrcConfig()
