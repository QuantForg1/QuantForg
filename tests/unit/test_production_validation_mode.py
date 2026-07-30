"""Production Validation Mode — observe-only recorder / export / acceptance."""

from __future__ import annotations

from pathlib import Path

from app.domain.institutional_trading.production_validation_mode.export import (
    export_validation_report,
)
from app.domain.institutional_trading.production_validation_mode.models import (
    StageStatus,
    ValidationStage,
)
from app.domain.institutional_trading.production_validation_mode.observe import (
    begin_validation,
    capture_signal,
    finalize,
    record_decision_reasons,
    record_gateway,
    record_mt5,
    record_oms,
    stage,
)
from app.domain.institutional_trading.production_validation_mode.recorder import (
    reset_production_validation_recorder_for_tests,
)


def test_validation_id_and_stage_timeline(tmp_path: Path) -> None:
    reset_production_validation_recorder_for_tests()
    vid = begin_validation(
        symbol="XAUUSD",
        market_session="new_york",
        execution_mode="live",
    )
    assert vid and vid.startswith("val_")

    stage(ValidationStage.SCHEDULER, ok=True, reason="tick", latency_ms=1.0)
    stage(ValidationStage.MARKET_DATA, ok=True, reason="bars ok", latency_ms=12.0)
    stage(ValidationStage.CONTEXT, ok=True, reason="snapshot ok")
    stage(ValidationStage.AI, ok=False, reason="quality below threshold")
    stage(ValidationStage.RISK, ok=True, reason="risk ok")
    stage(ValidationStage.ELIGIBILITY, ok=False, reason="Quality below threshold")

    class _Act:
        value = "NO_TRADE"

    class _Elig:
        eligible = False
        rejection_reasons = ("Quality below threshold", "Session blocked")

    class _Dec:
        action = _Act()
        reasons = ("Quality below threshold", "Spread")
        eligibility = _Elig()
        risk_reasons = ("Risk",)
        confluence = None
        confidence = 68
        quality = 68
        risk_score = 40
        estimated_rr = None
        symbol = "XAUUSD"
        id = "sig-1"

    record_decision_reasons(_Dec())
    # Never write fabricated pytest evidence into docs/production/validation/
    summary = finalize(export=False)
    assert summary is not None
    assert summary["accepted"] is False
    assert summary["final_result"] == "BLOCKED"
    assert summary["first_blocker"]
    assert "AI" in summary["first_blocker"] or "Quality" in summary["first_blocker"]

    from app.domain.institutional_trading.production_validation_mode.recorder import (
        get_production_validation_recorder,
    )

    attempt = get_production_validation_recorder().get(vid)
    assert attempt is not None
    assert "Quality below threshold" in attempt.no_trade_reasons
    assert "Session blocked" in attempt.no_trade_reasons
    assert "Spread" in attempt.no_trade_reasons
    assert "Risk" in attempt.no_trade_reasons
    # Every reason persisted individually — no single summarized blob
    assert all(isinstance(r, str) and r for r in attempt.no_trade_reasons)

    paths = export_validation_report(
        attempt,
        recorder=get_production_validation_recorder(),
        export_dir=tmp_path,
    )
    assert Path(paths["json"]).exists()
    assert Path(paths["markdown"]).exists()
    assert Path(paths["csv"]).exists()
    md = Path(paths["markdown"]).read_text(encoding="utf-8")
    assert vid in md
    assert "Pipeline Summary" in md


def test_acceptance_requires_ticket_and_buy_sell(tmp_path: Path) -> None:
    reset_production_validation_recorder_for_tests()
    vid = begin_validation(symbol="XAUUSD", market_session="london", execution_mode="live")
    assert vid

    for s in (
        ValidationStage.SCHEDULER,
        ValidationStage.MARKET_DATA,
        ValidationStage.CONTEXT,
        ValidationStage.AI,
        ValidationStage.RISK,
        ValidationStage.ELIGIBILITY,
        ValidationStage.EXECUTION_BRIDGE,
        ValidationStage.OMS,
        ValidationStage.GATEWAY,
        ValidationStage.MT5,
        ValidationStage.BROKER,
        ValidationStage.POSITION_OPEN,
    ):
        stage(s, ok=True, reason="ok", latency_ms=1.0)

    class _Act:
        value = "BUY"

    class _Elig:
        eligible = True
        rejection_reasons = ()

    class _Dec:
        action = _Act()
        reasons = ("setup ok",)
        eligibility = _Elig()
        risk_reasons = ()
        confluence = type("C", (), {"confidence": 82, "factors": {"mtf": 80}, "rejected_rules": (), "reasons": ()})()
        confidence = 82
        quality = 88
        risk_score = 20
        estimated_rr = "1.8"
        symbol = "XAUUSD"
        id = "sig-2"

    capture_signal(decision=_Dec())
    record_oms(
        payload={"symbol": "XAUUSD", "side": "BUY"},
        response={"outcome": "success", "order_ticket": 12345},
        latency_ms=40.0,
        retry_count=0,
    )
    record_gateway(
        request={"path": "/trade/order_send"},
        response={"retcode": 10009},
        http_code=200,
        gateway_latency_ms=30.0,
        order_send_latency_ms=55.0,
    )
    record_mt5(
        ticket=12345,
        retcode=10009,
        comment="done",
        execution_time_ms=55.0,
        fill_price="2350.12",
        slippage="0.02",
        broker_response={"retcode": 10009, "order": 12345},
    )

    summary = finalize(export=False)
    assert summary is not None
    assert summary["accepted"] is True
    assert summary["final_result"] == "ACCEPTED"
    assert summary["broker_ticket"] == 12345
    assert summary["first_blocker"] is None

    # Re-open: missing ticket → blocked
    reset_production_validation_recorder_for_tests()
    begin_validation(symbol="XAUUSD", execution_mode="live")
    for s in (
        ValidationStage.SCHEDULER,
        ValidationStage.MARKET_DATA,
        ValidationStage.AI,
        ValidationStage.RISK,
        ValidationStage.OMS,
        ValidationStage.GATEWAY,
        ValidationStage.MT5,
        ValidationStage.BROKER,
    ):
        stage(s, ok=True, reason="ok")
    capture_signal(decision=_Dec())
    record_mt5(ticket=None, retcode=10006, comment="reject")
    stage(ValidationStage.MT5, ok=False, reason="retcode=10006")
    summary2 = finalize(export=False)
    assert summary2 is not None
    assert summary2["accepted"] is False
    assert summary2["final_result"] == "BLOCKED"


def test_observe_hooks_never_raise() -> None:
    reset_production_validation_recorder_for_tests()
    # No active validation — hooks must be no-ops
    stage(ValidationStage.AI, ok=False, reason="x")
    record_oms(payload={"a": 1})
    record_gateway(http_code=500)
    record_mt5(retcode=1)
    assert finalize() is None


def test_dashboard_payload_fields() -> None:
    reset_production_validation_recorder_for_tests()
    begin_validation(symbol="XAUUSD", market_session="sydney", execution_mode="canary")
    stage(ValidationStage.SCHEDULER, ok=True, reason="ok")
    stage(ValidationStage.AI, ok=False, reason="Session 'sydney' not allowed")
    from app.domain.institutional_trading.production_validation_mode.recorder import (
        get_production_validation_recorder,
    )

    get_production_validation_recorder().record_no_trade_reasons(
        ["Session 'sydney' not allowed", "Eligibility"]
    )
    finalize(export=False)
    dash = get_production_validation_recorder().dashboard()
    assert dash["observe_only"] is True
    assert dash["current_session"] == "sydney"
    assert dash["last_validation_id"]
    assert dash["current_blocker"]
    assert dash["last_validation"]["no_trade_reasons"] == [
        "Session 'sydney' not allowed",
        "Eligibility",
    ]
    # StageStatus enum values present
    assert (
        dash["last_validation"]["stages"]["Scheduler"]["status"]
        == StageStatus.PASS.value
    )
