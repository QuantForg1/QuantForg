"""ASI orchestrator — adaptive advisory intelligence, never order_send."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

from app.domain.adaptive_scalping_intelligence.config import (
    DEFAULT_ASI_CONFIG,
    AsiConfig,
)
from app.domain.adaptive_scalping_intelligence.modules import (
    build_opportunity_database,
    build_opportunity_heat_map,
    calibrate_confidence,
    capital_preservation_index,
    detect_market_personality,
    evaluate_pattern_intelligence,
    evaluate_session_intelligence,
    evaluate_time_intelligence,
    explain_decision,
    weekly_ai_coach_report,
)
from app.domain.adaptive_scalping_intelligence.types import AsiInput, ModuleResult
from app.domain.trading.gold_only import GOLD_SYMBOL


@dataclass
class AdaptiveScalpingIntelligence:
    config: AsiConfig = field(default_factory=lambda: DEFAULT_ASI_CONFIG)
    history: list[dict[str, Any]] = field(default_factory=list)

    def status(self) -> dict[str, object]:
        return {
            **self.config.to_dict(),
            "modules": [
                "market_personality",
                "session_intelligence",
                "time_intelligence",
                "scalping_opportunity_database",
                "pattern_intelligence",
                "confidence_calibration",
                "opportunity_heat_map",
                "capital_preservation_index",
                "decision_explainability",
                "weekly_ai_coach",
            ],
            "capabilities": {
                "xauusd_only": True,
                "advisory_only": True,
                "never_order_send": True,
                "never_fabricate_statistics": True,
                "never_auto_modify_trading_rules": True,
                "never_auto_modify_risk_policies": True,
                "never_bypass_risk": True,
                "never_bypass_safety": True,
                "never_bypass_decision": True,
                "never_modify_execution_pipeline": True,
                "never_modify_auto_trading_loop": True,
                "distinguish_live_vs_historical": True,
                "insufficient_history_reported": True,
                "explainable": True,
                "auditable": True,
                "promise_profitability": False,
                "symbol": GOLD_SYMBOL,
            },
            "recent": self.history[:10],
        }

    def update_policies(self, updates: dict[str, object]) -> dict[str, object]:
        self.config = self.config.update(updates)
        return self.config.to_dict()

    def list_history(self, *, limit: int = 50) -> dict[str, Any]:
        rows = self.history[: max(1, min(limit, self.config.max_history))]
        return {"status": "available" if rows else "empty", "items": rows}

    def evaluate(self, inp: AsiInput) -> dict[str, Any]:
        audit_id = f"asi_{uuid4().hex[:12]}"
        flags = self.config.feature_flags
        modules: dict[str, ModuleResult] = {}

        if flags.get("market_personality", True):
            modules["market_personality"] = detect_market_personality(
                inp, self.config
            )
        if flags.get("session_intelligence", True):
            modules["session_intelligence"] = evaluate_session_intelligence(
                inp, self.config
            )
        if flags.get("time_intelligence", True):
            modules["time_intelligence"] = evaluate_time_intelligence(
                inp, self.config
            )
        if flags.get("opportunity_database", True):
            modules["scalping_opportunity_database"] = build_opportunity_database(
                inp, self.config
            )
        if flags.get("pattern_intelligence", True):
            modules["pattern_intelligence"] = evaluate_pattern_intelligence(
                inp, self.config
            )
        if flags.get("confidence_calibration", True):
            modules["confidence_calibration"] = calibrate_confidence(
                inp, self.config
            )
        if flags.get("opportunity_heat_map", True):
            modules["opportunity_heat_map"] = build_opportunity_heat_map(
                inp, self.config
            )
        if flags.get("capital_preservation_index", True):
            modules["capital_preservation_index"] = capital_preservation_index(
                inp, self.config
            )
        if flags.get("weekly_ai_coach", True):
            modules["weekly_ai_coach"] = weekly_ai_coach_report(inp, self.config)
        if flags.get("decision_explainability", True):
            # Explain after other modules so narrative can cite them
            base = dict(modules)
            modules["decision_explainability"] = explain_decision(inp, base)

        insufficient = [
            k
            for k, v in modules.items()
            if v.status == "insufficient_history"
        ]
        available = [
            k for k, v in modules.items() if v.status == "available"
        ]
        summary = (
            "Adaptive insights available"
            if available
            else "Insufficient historical data for adaptive insights"
        )
        if insufficient and available:
            summary = (
                f"Partial insights — {len(insufficient)} modules need more history"
            )

        result = {
            "version": self.config.version,
            "symbol": GOLD_SYMBOL,
            "audit_id": audit_id,
            "summary": summary,
            "modules": {k: v.to_dict() for k, v in modules.items()},
            "insufficient_modules": insufficient,
            "available_modules": available,
            "live_vs_historical": {
                "policy": "Every module labels source as live|historical|mixed|none",
                "never_blends_without_label": True,
            },
            "advisory_only": True,
            "never_order_send": True,
            "never_fabricate_statistics": True,
            "auto_modifies_trading_rules": False,
            "auto_modifies_risk_policies": False,
            "modifies_execution_pipeline": False,
            "modifies_auto_trading_loop": False,
            "bypasses_risk": False,
            "bypasses_safety": False,
            "bypasses_decision": False,
            "promise_profitability": False,
            "explainable": True,
            "auditable": True,
            "config_snapshot": {
                "min_history_observations": self.config.min_history_observations,
                "min_calibration_samples": self.config.min_calibration_samples,
                "coach_lookback_days": self.config.coach_lookback_days,
            },
        }
        self.history.insert(
            0,
            {
                "audit_id": audit_id,
                "summary": summary,
                "available": len(available),
                "insufficient": len(insufficient),
            },
        )
        if len(self.history) > self.config.max_history:
            self.history = self.history[: self.config.max_history]
        return result


def input_from_dict(data: dict[str, Any]) -> AsiInput:
    def d(v: Any) -> Decimal | None:
        if v is None:
            return None
        try:
            return Decimal(str(v))
        except (InvalidOperation, ValueError, TypeError):
            return None

    def i(v: Any) -> int | None:
        if v is None:
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    return AsiInput(
        side=str(data.get("side") or "buy"),
        session=str(data["session"]) if data.get("session") else None,
        hour_utc=i(data.get("hour_utc")),
        weekday=str(data["weekday"]) if data.get("weekday") else None,
        regime=str(data["regime"]) if data.get("regime") else None,
        volatility=str(data["volatility"]) if data.get("volatility") else None,
        spread=d(data.get("spread")),
        personality_hint=(
            str(data["personality_hint"])
            if data.get("personality_hint")
            else None
        ),
        pattern_id=str(data["pattern_id"]) if data.get("pattern_id") else None,
        live_confidence=d(data.get("live_confidence")),
        live_opportunity=(
            data.get("live_opportunity")
            if isinstance(data.get("live_opportunity"), dict)
            else None
        ),
        capital_facts=(
            data.get("capital_facts")
            if isinstance(data.get("capital_facts"), dict)
            else None
        ),
        decision_context=(
            data.get("decision_context")
            if isinstance(data.get("decision_context"), dict)
            else None
        ),
        historical_observations=(
            data.get("historical_observations")
            if isinstance(data.get("historical_observations"), list)
            else None
        ),
        closed_trades=(
            data.get("closed_trades")
            if isinstance(data.get("closed_trades"), list)
            else None
        ),
        opportunity_catalog=(
            data.get("opportunity_catalog")
            if isinstance(data.get("opportunity_catalog"), list)
            else None
        ),
    )
