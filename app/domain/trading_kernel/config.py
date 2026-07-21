"""Trading Kernel V1 — configurable policies (XAUUSD only)."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.domain.trading.gold_only import GOLD_SYMBOL


@dataclass
class KernelConfig:
    """Kernel policy knobs — never bypasses Risk/Safety, never order_send."""

    version: str = "trading-kernel-v1.0.0"
    symbol: str = GOLD_SYMBOL
    max_events: int = 2000
    max_cycles: int = 200
    require_risk_engine: bool = True
    require_safety_engine: bool = True
    max_spread: Decimal = Decimal("2.00")
    min_confidence: Decimal = Decimal("55")
    deterministic_replay: bool = True
    plugins_isolated: bool = True
    allow_bypass_risk: bool = False
    allow_bypass_safety: bool = False
    allow_order_send: bool = False
    feature_flags: dict[str, bool] = field(
        default_factory=lambda: {
            "kernel_enabled": True,
            "kernel_replay_mode": True,
            "kernel_deterministic": True,
            "kernel_plugins": True,
            "kernel_certification": True,
            "kernel_alpha_stage": True,
            "kernel_decision_stage": True,
        }
    )

    def __post_init__(self) -> None:
        self.symbol = GOLD_SYMBOL
        self.allow_bypass_risk = False
        self.allow_bypass_safety = False
        self.allow_order_send = False
        self.plugins_isolated = True
        self.require_risk_engine = True
        self.require_safety_engine = True

    def update(self, updates: dict[str, object]) -> KernelConfig:
        locked = {
            "allow_bypass_risk",
            "allow_bypass_safety",
            "allow_order_send",
            "symbol",
            "version",
            "plugins_isolated",
            "require_risk_engine",
            "require_safety_engine",
        }
        data = self.to_dict()
        for key, value in updates.items():
            if key in locked or value is None:
                continue
            if key == "feature_flags" and isinstance(value, dict):
                flags = dict(data["feature_flags"])  # type: ignore[arg-type]
                for fk, fv in value.items():
                    if isinstance(fv, bool):
                        # Never allow flags that imply bypass/execution.
                        if fk in {
                            "bypass_risk",
                            "bypass_safety",
                            "order_send",
                        }:
                            continue
                        flags[str(fk)] = fv
                data["feature_flags"] = flags
            elif key in data:
                data[key] = value
        return KernelConfig(
            max_events=int(data["max_events"]),
            max_cycles=int(data["max_cycles"]),
            max_spread=Decimal(str(data["max_spread"])),
            min_confidence=Decimal(str(data["min_confidence"])),
            deterministic_replay=bool(data["deterministic_replay"]),
            feature_flags=dict(data["feature_flags"]),  # type: ignore[arg-type]
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "symbol": self.symbol,
            "max_events": self.max_events,
            "max_cycles": self.max_cycles,
            "require_risk_engine": True,
            "require_safety_engine": True,
            "max_spread": str(self.max_spread),
            "min_confidence": str(self.min_confidence),
            "deterministic_replay": self.deterministic_replay,
            "plugins_isolated": True,
            "allow_bypass_risk": False,
            "allow_bypass_safety": False,
            "allow_order_send": False,
            "feature_flags": dict(self.feature_flags),
        }


DEFAULT_KERNEL_CONFIG = KernelConfig()
