"""Research & Validation Platform — configurable thresholds (XAUUSD only)."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.domain.trading.gold_only import GOLD_SYMBOL


@dataclass
class ResearchValidationConfig:
    """All thresholds configurable — live execution hard-locked off."""

    version: str = "research-validation-platform-v1.0.0"
    symbol: str = GOLD_SYMBOL
    min_profit_factor: Decimal = Decimal("1.20")
    min_sharpe: Decimal = Decimal("0.50")
    max_drawdown_pct: Decimal = Decimal("20")
    min_trades: int = 20
    min_walkforward_score: Decimal = Decimal("55")
    min_paper_score: Decimal = Decimal("50")
    min_certification_score: Decimal = Decimal("70")
    require_certification_for_production: bool = True
    require_operator_release_approval: bool = True
    max_replay_bars: int = 5000
    max_versions: int = 200
    max_audit: int = 1000
    max_comparisons: int = 20
    allow_live_execution: bool = False
    allow_order_send: bool = False
    feature_flags: dict[str, bool] = field(
        default_factory=lambda: {
            "strategy_registry": True,
            "historical_replay": True,
            "walk_forward": True,
            "paper_trading": True,
            "comparison_dashboard": True,
            "certification_pipeline": True,
            "version_governance": True,
            "rollback_engine": True,
            "performance_observatory": True,
            "release_governance": True,
        }
    )

    def __post_init__(self) -> None:
        self.symbol = GOLD_SYMBOL
        self.allow_live_execution = False
        self.allow_order_send = False
        self.require_certification_for_production = True

    def update(self, updates: dict[str, object]) -> ResearchValidationConfig:
        locked = {
            "allow_live_execution",
            "allow_order_send",
            "symbol",
            "version",
            "require_certification_for_production",
        }
        data = self.to_dict()
        for key, value in updates.items():
            if key in locked or value is None:
                continue
            if key == "feature_flags" and isinstance(value, dict):
                flags = dict(data["feature_flags"])  # type: ignore[arg-type]
                for fk, fv in value.items():
                    if isinstance(fv, bool) and fk not in {
                        "live_execution",
                        "order_send",
                    }:
                        flags[str(fk)] = fv
                data["feature_flags"] = flags
            elif key in data:
                data[key] = value
        return ResearchValidationConfig(
            min_profit_factor=Decimal(str(data["min_profit_factor"])),
            min_sharpe=Decimal(str(data["min_sharpe"])),
            max_drawdown_pct=Decimal(str(data["max_drawdown_pct"])),
            min_trades=int(data["min_trades"]),
            min_walkforward_score=Decimal(str(data["min_walkforward_score"])),
            min_paper_score=Decimal(str(data["min_paper_score"])),
            min_certification_score=Decimal(
                str(data["min_certification_score"])
            ),
            require_operator_release_approval=bool(
                data["require_operator_release_approval"]
            ),
            max_replay_bars=int(data["max_replay_bars"]),
            max_versions=int(data["max_versions"]),
            max_audit=int(data["max_audit"]),
            max_comparisons=int(data["max_comparisons"]),
            feature_flags=dict(data["feature_flags"]),  # type: ignore[arg-type]
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "symbol": self.symbol,
            "min_profit_factor": str(self.min_profit_factor),
            "min_sharpe": str(self.min_sharpe),
            "max_drawdown_pct": str(self.max_drawdown_pct),
            "min_trades": self.min_trades,
            "min_walkforward_score": str(self.min_walkforward_score),
            "min_paper_score": str(self.min_paper_score),
            "min_certification_score": str(self.min_certification_score),
            "require_certification_for_production": True,
            "require_operator_release_approval": (
                self.require_operator_release_approval
            ),
            "max_replay_bars": self.max_replay_bars,
            "max_versions": self.max_versions,
            "max_audit": self.max_audit,
            "max_comparisons": self.max_comparisons,
            "allow_live_execution": False,
            "allow_order_send": False,
            "feature_flags": dict(self.feature_flags),
        }


DEFAULT_RVP_CONFIG = ResearchValidationConfig()
