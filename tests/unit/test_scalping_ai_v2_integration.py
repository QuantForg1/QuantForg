"""Composition integration — Scalping AI V2 with Decision Center / Risk facts.

Does not modify live execution, Risk, Safety, or Decision Center code.
Verifies fail-closed authority and advisory-only contract.
"""

from __future__ import annotations

from decimal import Decimal

from app.application.services.decision_intelligence import (
    DecisionIntelligenceService,
)
from app.application.services.scalping_ai_v2 import ScalpingAiV2Service
from app.domain.scalping_ai_v2 import ScalpingAiV2
from app.domain.scalping_ai_v2.types import ScalpCycleInput


def test_decision_center_composition_never_bypasses() -> None:
    di = DecisionIntelligenceService()
    di_out = di.evaluate(
        {
            "side": "buy",
            "signal_present": True,
            "strategy_consensus_ok": True,
        }
    )
    assert di_out["decision"] == "HOLD"
    assert di_out["allow_execution_path"] is False

    # Scalping AI consumes Decision Center payload — still No Trade without engines
    scalp = ScalpingAiV2().run_cycle(
        ScalpCycleInput(
            side="buy",
            run_state="running",
            spread=Decimal("0.3"),
            session="london",
            confidence=Decimal("70"),
            decision_center={
                "decision": di_out["decision"],
                "allow_execution_path": di_out.get("allow_execution_path"),
            },
            decision_approved=False,
            risk_engine_passed=None,
            safety_engine_passed=None,
            opportunities=[
                {
                    "id": "x",
                    "quality_score": 80,
                    "confidence_score": 80,
                    "risk_score": 20,
                    "execution_score": 80,
                }
            ],
        )
    )
    assert scalp["recommendation"] == "No Trade"
    assert scalp["bypasses_decision_center"] is False
    assert scalp["never_order_send"] is True
    assert scalp["execution_pipeline_unchanged"] is True


def test_service_cycle_auditable_events() -> None:
    service = ScalpingAiV2Service()
    out = service.cycle(
        {
            "side": "buy",
            "spread": 0.25,
            "session": "london",
            "confidence": 75,
            "htf_bias": "bullish",
            "ltf_confirmation": "bullish",
            "bos": True,
            "stop_hunt": False,
            "opportunities": [
                {
                    "id": "y",
                    "quality_score": 80,
                    "confidence_score": 80,
                    "risk_score": 25,
                    "execution_score": 80,
                }
            ],
            "risk_engine_passed": True,
            "safety_engine_passed": True,
            "decision_approved": True,
            "broker_connected": True,
            "gateway_healthy": True,
            "market_open": True,
            "margin_available": True,
            "latency_ms": 30,
            "run_state": "running",
            "regime": "trend",
            "market_health": "good",
            "trend": "up",
            "volatility": "normal",
            "liquidity_state": "ok",
            "price": 2300,
            "atr": 5,
        }
    )
    events = service.events(cycle_id=str(out["cycle_id"]))
    assert events["status"] == "available"
    types = {e["event_type"] for e in events["events"]}
    assert "MarketUpdated" in types
    assert "CycleCompleted" in types
    assert out["auditable"] is True
