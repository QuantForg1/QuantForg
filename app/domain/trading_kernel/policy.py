"""Policy Engine + Feature Flags + Rule Engine for Trading Kernel."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.domain.trading_kernel.config import KernelConfig


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allowed: bool
    reasons: tuple[str, ...]
    policies: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "allowed": self.allowed,
            "reasons": list(self.reasons),
            "policies": dict(self.policies),
        }


class PolicyEngine:
    """Evaluate configurable policies — never grants Risk/Safety bypass."""

    def __init__(self, config: KernelConfig) -> None:
        self.config = config

    def evaluate(self, facts: dict[str, Any]) -> PolicyDecision:
        reasons: list[str] = []
        allowed = True
        spread = facts.get("spread")
        if spread is not None:
            try:
                sp = Decimal(str(spread))
                if sp > self.config.max_spread:
                    allowed = False
                    reasons.append(
                        f"spread {sp} exceeds max_spread {self.config.max_spread}"
                    )
                else:
                    reasons.append(f"spread {sp} within policy")
            except Exception:
                reasons.append("spread unreadable — fail closed")
                allowed = False
        conf = facts.get("confidence")
        if conf is not None:
            try:
                c = Decimal(str(conf))
                if c < self.config.min_confidence:
                    allowed = False
                    reasons.append(
                        f"confidence {c} below min {self.config.min_confidence}"
                    )
                else:
                    reasons.append(f"confidence {c} meets minimum")
            except Exception:
                reasons.append("confidence unreadable — fail closed")
                allowed = False
        if not reasons:
            reasons.append("No policy facts supplied — pass with caution")
        reasons.append("Risk/Safety bypass locked off")
        return PolicyDecision(
            allowed=allowed,
            reasons=tuple(reasons),
            policies=self.config.to_dict(),
        )


class FeatureFlagFramework:
    def __init__(self, config: KernelConfig) -> None:
        self.config = config

    def is_enabled(self, flag: str) -> bool:
        if flag in {"bypass_risk", "bypass_safety", "order_send"}:
            return False
        return bool(self.config.feature_flags.get(flag, False))

    def snapshot(self) -> dict[str, bool]:
        out = dict(self.config.feature_flags)
        out["bypass_risk"] = False
        out["bypass_safety"] = False
        out["order_send"] = False
        return out

    def set_flag(self, flag: str, enabled: bool) -> dict[str, bool]:
        if flag in {"bypass_risk", "bypass_safety", "order_send"}:
            return self.snapshot()
        self.config.feature_flags[flag] = bool(enabled)
        return self.snapshot()


@dataclass(frozen=True, slots=True)
class RuleResult:
    passed: bool
    fired: tuple[str, ...]
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "fired": list(self.fired),
            "reasons": list(self.reasons),
        }


class RuleEngine:
    """Declarative rules over supplied facts — advisory vetoes only."""

    def evaluate(self, facts: dict[str, Any], config: KernelConfig) -> RuleResult:
        fired: list[str] = []
        reasons: list[str] = []
        passed = True
        if facts.get("news_blackout") is True:
            passed = False
            fired.append("news_blackout")
            reasons.append("News blackout rule fired")
        if facts.get("kill_switch") is True:
            passed = False
            fired.append("kill_switch")
            reasons.append("Kill switch observed — kernel will HOLD")
        mode = str(facts.get("execution_mode") or "").upper()
        if mode == "HALTED":
            passed = False
            fired.append("mode_halted")
            reasons.append("Execution mode halted")
        spread = facts.get("spread")
        if spread is not None:
            try:
                if Decimal(str(spread)) > config.max_spread:
                    passed = False
                    fired.append("spread_rule")
                    reasons.append("Spread rule failed")
            except Exception:
                passed = False
                fired.append("spread_unreadable")
                reasons.append("Spread unreadable")
        if not fired:
            reasons.append("No blocking rules fired")
        return RuleResult(
            passed=passed, fired=tuple(fired), reasons=tuple(reasons)
        )
