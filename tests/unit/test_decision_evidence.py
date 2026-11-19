"""Decision evidence is a read-only projection of existing signal records."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import main
from app.application.services.decision_evidence import (
    build_decision_history,
    build_live_report,
    project_decision_report,
)
from app.application.services.entitlements import Entitlement
from app.presentation.dependencies.auth import get_current_user
from app.presentation.routers import decision_evidence as evidence_router

pytestmark = [pytest.mark.unit]

_ROW = {
    "symbol": "XAUUSD_i",
    "direction": "BUY",
    "decision": "BUY",
    "status": "QUALIFIED",
    "strategy": "scalping",
    "time_generated": "2026-11-19T18:00:00Z",
    "session": "london",
    "current_price": 2650.25,
    "trend": "up",
    "structure": 2,
    "atr": 4.5,
    "spread": 0.18,
    "reasoning": "Structure and liquidity aligned.",
    "reject": False,
    "signal_id": "sig_1",
    "pipeline": {
        "data": "LIVE",
        "data_age_seconds": 3,
        "tick_time": "2026-11-19T18:00:01Z",
        "zone_timeframe": "M5",
        "market_regime": "trend",
        "setup_state": "WAIT",
        "sniper": "WAIT",
        "opportunity_gate": "WAIT",
        "risk": "NOT_REACHED",
        "safety": "NOT_REACHED",
        "oms": "NOT_REACHED",
        "passed_predicates": [
            {
                "name": "spread",
                "passed": True,
                "actual": 0.18,
                "required": 0.4,
                "source": "tick",
            }
        ],
        "failed_predicates": [
            {
                "name": "liquidity_event",
                "passed": False,
                "actual": False,
                "required": True,
                "source": "m5",
            }
        ],
    },
}


def test_buy_is_not_an_executed_order() -> None:
    report = project_decision_report(
        _ROW,
        feed={"orders_may_submit": False, "live_authorization": "LIVE_DISABLED"},
    )
    assert report["summary"]["decision"] == "BUY"
    assert report["authorization"]["order_executed"] is False
    assert report["authorization"]["order_sent"] is False
    assert report["executes_orders"] is False
    assert "not proof" in report["order_note"]


def test_filled_lifecycle_is_the_only_execution_proof() -> None:
    row = {
        **_ROW,
        "pipeline": {
            **_ROW["pipeline"],
            "execution_lifecycle": "FILLED",
            "ticket": 1001,
        },
    }
    report = project_decision_report(row, feed={})
    assert report["authorization"]["order_executed"] is True
    assert report["authorization"]["ticket"] == "1001"


def test_order_sent_is_not_marked_executed() -> None:
    row = {
        **_ROW,
        "pipeline": {
            **_ROW["pipeline"],
            "execution_lifecycle": "ORDER_SENT",
            "ticket": 9,
        },
    }
    report = project_decision_report(row, feed={})
    assert report["authorization"]["order_sent"] is True
    assert report["authorization"]["order_executed"] is False


def test_missing_fields_stay_missing() -> None:
    report = project_decision_report(
        {"symbol": "XAUUSD_i", "direction": "WAIT", "decision": "WAIT"},
        feed={},
    )
    assert report["market"]["atr"] == "Not available"
    assert report["market"]["timeframe"] == "Not available"
    assert report["strategy"]["reason"] == "Not available"
    assert report["invalidation"]["available"] is False
    assert report["risk"]["recorded_limit"] is None
    assert any("risk limit" in item.lower() for item in report["risk"]["missing"])
    assert report["evidence"]
    assert all(item["value"] != "Not available" for item in report["evidence"])


def test_stale_market_data_is_flagged() -> None:
    row = {
        **_ROW,
        "pipeline": {**_ROW["pipeline"], "data": "STALE", "data_age_seconds": 400},
    }
    report = project_decision_report(row, feed={})
    assert report["stale"] is True
    assert report["market"]["data_state"] == "STALE"


def test_strategy_predicates_are_copied() -> None:
    report = project_decision_report(_ROW, feed={})
    assert any(line.startswith("spread") for line in report["strategy"]["satisfied"])
    assert any("liquidity_event" in line for line in report["strategy"]["unsatisfied"])
    assert report["strategy"]["reason"] == "Structure and liquidity aligned."
    assert "Opportunity gate WAIT" in report["strategy"]["unsatisfied"]


def test_invalidation_only_when_engine_recorded_it() -> None:
    assert project_decision_report(_ROW, feed={})["invalidation"]["available"] is False
    row = {
        **_ROW,
        "pipeline": {
            **_ROW["pipeline"],
            "original_invalidation": 2640.1,
            "failed_predicates": [
                {
                    "name": "invalidation_stop",
                    "passed": False,
                    "actual": "inside",
                    "required": "beyond",
                    "source": "strategy",
                }
            ],
        },
    }
    report = project_decision_report(row, feed={})
    assert report["invalidation"]["available"] is True
    assert report["invalidation"]["conditions"][0]["value"] == "2640.1"
    assert report["invalidation"]["conditions"][0]["source"].endswith(
        "original_invalidation"
    )


def test_risk_gate_not_reached_is_not_rewritten() -> None:
    report = project_decision_report(_ROW, feed={})
    risk = next(
        item for item in report["risk"]["checks"] if item["name"] == "Risk gate"
    )
    assert risk["state"] == "NOT_REACHED"
    assert risk["result"] == "not_performed"
    assert report["calculates_risk"] is False
    assert report["authorization"]["risk_approval"] == "NOT_REACHED"


def test_synthetic_row_is_labeled() -> None:
    report = project_decision_report({**_ROW, "test_synthetic": True}, feed={})
    assert report["test_synthetic"] is True


def test_empty_feed_awaits_engine_evidence() -> None:
    report = project_decision_report(None, feed={"symbol": "XAUUSD_i"})
    assert report["available"] is False
    assert report["empty_reason"] == "Awaiting engine evidence"
    assert report["summary"]["decision"] == "Not available"
    assert report["authorization"]["order_executed"] is False


def test_live_report_reads_signal_center(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_list(**kwargs: object) -> dict[str, object]:
        assert kwargs["active_only"] is False
        return {
            "items": [_ROW],
            "as_of": "2026-11-19T18:00:00Z",
            "source": "live_multi_asset_scan",
            "orders_may_submit": False,
            "live_trading_state": "DISABLED",
            "live_authorization": "LIVE_DISABLED",
            "scanner_status": "LIVE",
        }

    monkeypatch.setattr(
        "app.application.services.signal_center_service.list_live_signals",
        fake_list,
    )
    report = build_live_report("XAUUSD")
    assert report["summary"]["symbol"] == "XAUUSD_i"
    assert report["summary"]["decision"] == "BUY"
    assert report["authorization"]["orders_may_submit"] is False


def test_history_does_not_observe(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_history(**kwargs: object) -> dict[str, object]:
        seen.update(kwargs)
        return {
            "items": [
                {
                    "symbol": "XAUUSD_i",
                    "direction": "WAIT",
                    "decision": "WAIT",
                    "strategy_id": "scalping",
                    "observed_at": "2026-11-19T17:00:00Z",
                    "reject": False,
                }
            ]
        }

    monkeypatch.setattr(
        "app.application.services.signal_intelligence_service.list_signal_history",
        fake_history,
    )
    payload = build_decision_history(symbol="XAUUSD_i", limit=5)
    assert seen["observe"] is False
    assert payload["count"] == 1
    assert payload["items"][0]["decision"] == "WAIT"
    assert payload["items"][0]["report"]["market"]["atr"] == "Not available"
    assert "not reconstructed" in payload["history_note"]
    assert "not reconstructed" in payload["items"][0]["report"]["history_note"]


def test_router_is_get_only_and_customer_readable() -> None:
    methods: set[str] = set()
    for route in evidence_router.router.routes:
        methods.update(getattr(route, "methods", set()))
    assert methods <= {"GET", "HEAD"}
    names = [name for name, _path in main._ROUTER_SPECS]
    assert "decision_evidence" in names
    assert "decision_evidence" not in main._OPERATOR_ONLY_ROUTER_MODULES


def _client(role: str) -> TestClient:
    app = FastAPI()
    from app.presentation.middleware.error_handler import register_exception_handlers

    register_exception_handlers(app)
    main._register_routers(
        app,
        SimpleNamespace(api_prefix="/api/v1"),
        specs=(("decision_evidence", "app.presentation.routers.decision_evidence"),),
    )
    user = SimpleNamespace(
        id=uuid4(),
        role=role,
        email="u@example.invalid",
        display_name="u",
        status="active",
    )
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app, raise_server_exceptions=False)


def test_unpaid_customer_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.application.services.entitlements.check_trading_entitlement",
        lambda **_: Entitlement(False, "inactive", "none"),
    )

    def boom(**_kwargs: object) -> dict[str, object]:
        raise AssertionError("signal center must not be read for an unpaid customer")

    monkeypatch.setattr(
        "app.application.services.signal_center_service.list_live_signals",
        boom,
    )
    response = _client("trader").get("/api/v1/decision-evidence/report")
    assert response.status_code == 402


def test_owner_can_read_without_billing(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(**_kwargs: object) -> Entitlement:
        raise AssertionError("billing must not be read for operators")

    monkeypatch.setattr(
        "app.application.services.entitlements.check_trading_entitlement",
        boom,
    )
    monkeypatch.setattr(
        "app.application.services.signal_center_service.list_live_signals",
        lambda **_: {"items": [], "as_of": None, "source": "live_multi_asset_scan"},
    )
    response = _client("owner").get("/api/v1/decision-evidence/report?symbol=XAUUSD_i")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["empty_reason"] == "Awaiting engine evidence"
    assert body["executes_orders"] is False
