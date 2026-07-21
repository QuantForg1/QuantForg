"""Production Readiness Program — configurable health policies."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class HealthPolicies:
    """All thresholds configurable — never hard-bypass Risk/Safety."""

    max_gateway_latency_ms: float = 500.0
    max_order_latency_ms: float = 800.0
    max_journal_latency_ms: float = 1000.0
    min_health_score: float = 80.0
    require_gateway_available: bool = True
    require_mt5_connected: bool = True
    require_kill_switch_clear_for_live: bool = True
    require_risk_engine: bool = True
    require_safety_engine: bool = True
    allow_bypass_risk: bool = False
    allow_bypass_safety: bool = False
    auto_recover_gateway: bool = True
    auto_recover_mt5: bool = True
    never_retry_order_send: bool = True

    def __post_init__(self) -> None:
        # Hard locks — cannot be enabled.
        object.__setattr__(self, "allow_bypass_risk", False)
        object.__setattr__(self, "allow_bypass_safety", False)
        object.__setattr__(self, "never_retry_order_send", True)

    def update(self, updates: dict[str, Any]) -> HealthPolicies:
        locked = {
            "allow_bypass_risk",
            "allow_bypass_safety",
            "never_retry_order_send",
        }
        data = self.to_dict()
        for key, value in updates.items():
            if key in locked:
                continue
            if key in data and value is not None:
                data[key] = value
        return HealthPolicies(
            max_gateway_latency_ms=float(data["max_gateway_latency_ms"]),
            max_order_latency_ms=float(data["max_order_latency_ms"]),
            max_journal_latency_ms=float(data["max_journal_latency_ms"]),
            min_health_score=float(data["min_health_score"]),
            require_gateway_available=bool(data["require_gateway_available"]),
            require_mt5_connected=bool(data["require_mt5_connected"]),
            require_kill_switch_clear_for_live=bool(
                data["require_kill_switch_clear_for_live"]
            ),
            require_risk_engine=bool(data["require_risk_engine"]),
            require_safety_engine=bool(data["require_safety_engine"]),
            auto_recover_gateway=bool(data["auto_recover_gateway"]),
            auto_recover_mt5=bool(data["auto_recover_mt5"]),
        )

    def evaluate(self, health: dict[str, Any] | None) -> dict[str, Any]:
        if health is None:
            return {
                "status": "unavailable",
                "passed": None,
                "violations": [],
                "message": "Health snapshot unavailable",
            }
        violations: list[str] = []
        gw_lat = health.get("gateway_latency_ms")
        if gw_lat is not None and float(gw_lat) > self.max_gateway_latency_ms:
            violations.append("gateway_latency_exceeded")
        order_lat = health.get("order_latency_ms") or health.get(
            "execution_latency_ms"
        )
        if order_lat is not None and float(order_lat) > self.max_order_latency_ms:
            violations.append("order_latency_exceeded")
        journal_lat = health.get("journal_latency_ms")
        if (
            journal_lat is not None
            and float(journal_lat) > self.max_journal_latency_ms
        ):
            violations.append("journal_latency_exceeded")
        score = health.get("health_score")
        if score is not None and float(score) < self.min_health_score:
            violations.append("health_score_below_minimum")
        if self.require_gateway_available and health.get("gateway_available") is False:
            violations.append("gateway_unavailable")
        if self.require_mt5_connected and health.get("mt5_connected") is False:
            violations.append("mt5_disconnected")
        return {
            "status": "available",
            "passed": len(violations) == 0,
            "violations": violations,
            "policies": self.to_dict(),
            "observed": {
                k: health.get(k)
                for k in (
                    "gateway_latency_ms",
                    "order_latency_ms",
                    "execution_latency_ms",
                    "journal_latency_ms",
                    "health_score",
                    "gateway_available",
                    "mt5_connected",
                    "degraded",
                )
                if k in health
            },
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_gateway_latency_ms": self.max_gateway_latency_ms,
            "max_order_latency_ms": self.max_order_latency_ms,
            "max_journal_latency_ms": self.max_journal_latency_ms,
            "min_health_score": self.min_health_score,
            "require_gateway_available": self.require_gateway_available,
            "require_mt5_connected": self.require_mt5_connected,
            "require_kill_switch_clear_for_live": (
                self.require_kill_switch_clear_for_live
            ),
            "require_risk_engine": self.require_risk_engine,
            "require_safety_engine": self.require_safety_engine,
            "allow_bypass_risk": False,
            "allow_bypass_safety": False,
            "auto_recover_gateway": self.auto_recover_gateway,
            "auto_recover_mt5": self.auto_recover_mt5,
            "never_retry_order_send": True,
        }


DEFAULT_HEALTH_POLICIES = HealthPolicies()


@dataclass
class ProductionReadinessConfig:
    product: str = "QuantForg Production Readiness Program"
    version: str = "1"
    never_changes_execution_architecture: bool = True
    never_bypasses_risk: bool = True
    never_bypasses_safety: bool = True
    fabricates_metrics: bool = False
    max_audit: int = 500
    health_policies: HealthPolicies = field(
        default_factory=HealthPolicies
    )
    panel_ids: tuple[str, ...] = (
        "pre_trade_validation",
        "post_trade_validation",
        "circuit_breakers",
        "platform_health_policies",
        "automatic_recovery",
        "incident_manager",
        "operator_playbooks",
        "deployment_verification",
        "security_hardening",
        "disaster_recovery",
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "product": self.product,
            "version": self.version,
            "never_changes_execution_architecture": (
                self.never_changes_execution_architecture
            ),
            "never_bypasses_risk": self.never_bypasses_risk,
            "never_bypasses_safety": self.never_bypasses_safety,
            "fabricates_metrics": self.fabricates_metrics,
            "panels": list(self.panel_ids),
            "health_policies": self.health_policies.to_dict(),
        }


DEFAULT_PR_CONFIG = ProductionReadinessConfig()
