"""NOC Command Center — observe-only aggregator + grounded copilot."""

from __future__ import annotations

from app.application.services.noc_command_center import (
    answer_noc_copilot,
    build_noc_command_center,
)
from app.domain.institutional_trading.production_validation_mode.models import (
    ValidationStage,
)
from app.domain.institutional_trading.production_validation_mode.observe import (
    begin_validation,
    finalize,
    stage,
)
from app.domain.institutional_trading.production_validation_mode.recorder import (
    reset_production_validation_recorder_for_tests,
)


def test_noc_dashboard_shape_and_flags() -> None:
    reset_production_validation_recorder_for_tests()
    begin_validation(symbol="XAUUSD", market_session="sydney", execution_mode="live")
    stage(ValidationStage.SCHEDULER, ok=True, reason="tick")
    stage(ValidationStage.AI, ok=False, reason="Quality below threshold")
    finalize(export=False)

    payload = build_noc_command_center()
    assert payload["flags"]["observe_only"] is True
    assert payload["flags"]["never_fabricates_metrics"] is True
    assert payload["flags"]["never_exposes_secrets"] is True
    assert "header" in payload
    assert "global_health" in payload
    assert isinstance(payload["global_health"], list)
    assert len(payload["global_health"]) >= 6
    assert "pipeline" in payload
    nodes = payload["pipeline"]["nodes"]
    assert isinstance(nodes, list)
    assert len(nodes) >= 12  # full PIPELINE_ORDER rendered
    assert any(n.get("status") == "FAIL" for n in nodes)
    assert any("AI" in str(n.get("stage")) for n in nodes)
    assert "ai_engine" in payload
    assert "symbol_scan" in payload
    assert isinstance(payload["symbol_scan"], dict)
    assert "universe" in payload["symbol_scan"]
    assert payload["symbol_scan"]["governed_by_existing_ai_and_risk"] is True
    assert "execution_trace" in payload
    assert "learning" in payload
    assert "protection" in payload
    assert "validation_history" in payload
    assert isinstance(payload["alerts"], list)
    assert isinstance(payload["system_metrics"], dict)
    # Never leak secret-looking keys with raw values
    blob = str(payload)
    assert "bearer " not in blob.lower()
    assert "[redacted]" in blob or "password" not in blob.lower()


def test_copilot_grounded_no_hallucination() -> None:
    reset_production_validation_recorder_for_tests()
    begin_validation(symbol="XAUUSD", market_session="sydney", execution_mode="live")
    stage(ValidationStage.AI, ok=False, reason="Session 'sydney' not allowed")
    from app.domain.institutional_trading.production_validation_mode.recorder import (
        get_production_validation_recorder,
    )

    get_production_validation_recorder().record_no_trade_reasons(
        ["Session 'sydney' not allowed", "Quality below threshold"]
    )
    finalize(export=False)

    telemetry = build_noc_command_center()
    out = answer_noc_copilot("Why isn't QuantForg trading?", telemetry=telemetry)
    assert out["grounded"] is True
    assert out["hallucination_guard"] is True
    assert (
        "Session" in out["answer"]
        or "blocker" in out["answer"].lower()
        or "NO_TRADE" in out["answer"]
    )
    assert out["evidence"]

    empty = answer_noc_copilot("")
    assert "Ask a production" in empty["answer"]
