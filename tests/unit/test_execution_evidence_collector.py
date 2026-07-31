"""Production Execution Evidence Collector — observe-only, never fabricates."""

from __future__ import annotations

from pathlib import Path

from app.domain.institutional_trading.execution_evidence.collector import (
    build_evidence_from_attempt,
    is_eligible_execution,
    payload_hash,
)
from app.domain.institutional_trading.execution_evidence.export import (
    WAITING_MESSAGE,
    build_acceptance_status,
    export_evidence_package,
    export_waiting_state,
    load_latest_evidence,
)
from app.domain.institutional_trading.production_validation_mode.models import (
    ValidationStage,
)
from app.domain.institutional_trading.production_validation_mode.observe import (
    begin_validation,
    capture_signal,
    finalize,
    record_gateway,
    record_mt5,
    record_oms,
    stage,
)
from app.domain.institutional_trading.production_validation_mode.recorder import (
    get_production_validation_recorder,
    reset_production_validation_recorder_for_tests,
)


def _buy_decision() -> object:
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
        confluence = type(
            "C",
            (),
            {
                "confidence": 82,
                "factors": {"mtf": 80},
                "rejected_rules": (),
                "reasons": (),
            },
        )()
        confidence = 82
        quality = 88
        risk_score = 20
        estimated_rr = "1.8"
        symbol = "XAUUSD"
        id = "sig-evidence-1"

    return _Dec()


def _pass_all_open_stages() -> None:
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
        stage(s, ok=True, reason="ok", latency_ms=1.5)


def test_payload_hash_redacts_secrets() -> None:
    h1 = payload_hash({"symbol": "XAUUSD", "password": "secret-value", "volume": 0.1})
    h2 = payload_hash({"symbol": "XAUUSD", "password": "[redacted]", "volume": 0.1})
    assert h1 and h2
    assert h1 == h2
    assert "secret-value" not in h1


def test_no_trade_not_eligible() -> None:
    reset_production_validation_recorder_for_tests()
    begin_validation(symbol="XAUUSD", market_session="sydney", execution_mode="live")
    stage(ValidationStage.AI, ok=False, reason="quality")
    finalize(export=False)
    attempt = get_production_validation_recorder().recent(limit=1)[0]
    from app.domain.institutional_trading.production_validation_mode.recorder import (
        get_production_validation_recorder as get_rec,
    )

    att = get_rec().get(attempt["validation_id"])
    assert att is not None
    assert is_eligible_execution(att) is False
    assert build_evidence_from_attempt(att) is None


def test_eligible_buy_exports_and_certificate(tmp_path: Path) -> None:
    reset_production_validation_recorder_for_tests()
    vid = begin_validation(
        symbol="XAUUSD", market_session="london", execution_mode="live"
    )
    assert vid
    _pass_all_open_stages()
    capture_signal(decision=_buy_decision())
    record_oms(
        payload={"symbol": "XAUUSD", "side": "BUY", "volume": 0.02, "password": "x"},
        response={"outcome": "success", "order_ticket": 991122},
        latency_ms=42.0,
    )
    record_gateway(
        request={"path": "/trade/order_send", "request_id": "req-abc"},
        response={"retcode": 10009, "request_id": "req-abc"},
        http_code=200,
        gateway_latency_ms=18.0,
        order_send_latency_ms=61.0,
    )
    record_mt5(
        ticket=991122,
        retcode=10009,
        comment="done",
        fill_price="2351.40",
        slippage="0.01",
        broker_response={"retcode": 10009, "order": 991122, "volume": 0.02},
    )
    summary = finalize(export=False)
    assert summary is not None
    assert summary["accepted"] is True

    attempt = get_production_validation_recorder().get(vid)
    assert attempt is not None
    package = build_evidence_from_attempt(
        attempt,
        environment="test",
        commit_sha="abc123deadbeef",
        deployment_id="deploy-test-1",
    )
    assert package is not None
    assert package.mt5_ticket == 991122
    assert package.oms_payload_hash
    assert "password" not in str(package.oms_response).lower() or "[redacted]" in str(
        package.to_dict()
    )
    assert package.certificate_eligible is True
    assert len(package.timeline) == 10

    exec_dir = tmp_path / "execution"
    cert_dir = tmp_path / "certificates"
    paths = export_evidence_package(
        package, export_dir=exec_dir, certificate_dir=cert_dir
    )
    assert Path(paths["json"]).exists()
    assert Path(paths["markdown"]).exists()
    assert Path(paths["csv"]).exists()
    assert Path(paths["certificate"]).exists()

    md = Path(paths["markdown"]).read_text(encoding="utf-8")
    assert "Execution Timeline" in md
    assert "Scheduler" in md
    assert "Position Close" in md
    assert "PASS / FAIL" in md or "| PASS |" in md or "PASS" in md

    cert = Path(paths["certificate"]).read_text(encoding="utf-8")
    assert "Production Acceptance Certificate" in cert
    assert "991122" in cert
    assert "VERIFIED" in cert
    assert "abc123deadbeef" in cert

    latest = load_latest_evidence(export_dir=exec_dir)
    assert latest["latest"]["mt5"]["ticket"] == 991122
    assert latest["status"] == "VERIFIED"

    status = build_acceptance_status(
        export_dir=exec_dir, certificate_dir=cert_dir
    )
    assert status["verified"] is True
    assert status["status"] == "VERIFIED"
    assert status["latest_broker_ticket"] == 991122
    assert status["latest_latency_ms"] == 61.0
    assert status["latest_certificate"]


def test_waiting_state_export(tmp_path: Path) -> None:
    out = tmp_path / "execution"
    paths = export_waiting_state(export_dir=out)
    assert Path(paths["json"]).exists()
    md = Path(paths["markdown"]).read_text(encoding="utf-8")
    assert WAITING_MESSAGE in md
    latest = load_latest_evidence(export_dir=out)
    assert latest["latest"] is None
    assert latest["status"] == "NOT_VERIFIED"


def test_noc_includes_production_acceptance() -> None:
    reset_production_validation_recorder_for_tests()
    begin_validation(symbol="XAUUSD", market_session="sydney", execution_mode="live")
    stage(ValidationStage.AI, ok=False, reason="Session blocked")
    finalize(export=False)

    from app.application.services.noc_command_center import build_noc_command_center

    payload = build_noc_command_center()
    assert "production_acceptance" in payload
    pa = payload["production_acceptance"]
    assert pa["observe_only"] is True
    assert pa["status"] in {"NOT VERIFIED", "VERIFIED"}
    if not pa.get("verified"):
        waiting = pa.get("message") == WAITING_MESSAGE
        empty = pa.get("latest_execution") is None
        assert waiting or empty
