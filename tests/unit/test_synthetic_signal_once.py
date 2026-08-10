"""One-shot TEST/SYNTHETIC Signal Center inject — never live OMS/MT5."""

from __future__ import annotations

from app.application.services import signal_center_service, synthetic_signal_once
from app.application.services.institutional_multi_asset_scanner import (
    _store_last_scan,
    get_last_multi_asset_scan,
)


def test_synthetic_signal_once_projects_and_disarms(tmp_path, monkeypatch) -> None:
    state_path = tmp_path / "synthetic_signal_once_state.json"
    monkeypatch.setenv("QUANTFORG_SYNTHETIC_SIGNAL_ONCE_STATE_PATH", str(state_path))

    previous = {
        "as_of": "2026-08-10T00:00:00Z",
        "universe": ["EURUSD"],
        "rows": [
            {
                "symbol": "EURUSD",
                "direction": "NONE",
                "trade_quality": 10,
                "ai_confidence": 10,
                "reject": True,
                "reject_reason": "no setup",
            }
        ],
        "eligible_symbols": [],
        "eligible_count": 0,
        "best_symbol": None,
        "note": "prior_live_scan",
        "test_synthetic": False,
    }
    _store_last_scan(previous)

    status0 = synthetic_signal_once.status()
    assert status0["remaining"] == 0
    assert status0["injection"] == "OFF"

    armed = synthetic_signal_once.arm_once(confirmed=True)
    assert armed["ok"] is True
    assert armed["status"]["remaining"] == 1
    assert armed["status"]["injection"] == "ARMED_ONCE"

    denied = synthetic_signal_once.inject_once(confirmed=False)
    assert denied["ok"] is False
    assert denied["mt5_order_submitted"] is False

    result = synthetic_signal_once.inject_once(
        symbol="XAUUSD",
        side="BUY",
        confirmed=True,
        restore_previous=True,
    )
    assert result["ok"] is True
    assert result["created"] is True
    assert result["count"] == 1
    assert result["type"] == "TEST_SYNTHETIC"
    assert result["symbol"] == "XAUUSD"
    assert result["side"] == "BUY"
    assert str(result["signal_id"]).startswith("TEST-SYNTHETIC-")
    assert result["visible_in_signal_center"] is True
    assert result["mt5_order_submitted"] is False
    assert result["forwarded_to_oms"] is False
    assert result["execution_result"] == "TEST_ONLY_DRY_RUN"
    assert result["oms_dry_run"]["submitted"] is False
    assert result["oms_dry_run"]["mt5_order_send"] is False
    assert result["oms_dry_run"]["status"] in {"PASS", "FAIL"}
    assert result["injection_disabled"] is True
    assert result["restored_previous_scan"] is True

    item = result["signal_center_item"]
    assert item is not None
    assert item["test_synthetic"] is True
    assert "TEST" in str(item["badge"])
    assert item["direction"] == "BUY"

    # Previous scan restored — synthetic BUY must not linger.
    restored = get_last_multi_asset_scan() or {}
    assert restored.get("note") == "prior_live_scan"
    assert restored.get("test_synthetic") is False

    status1 = synthetic_signal_once.status()
    assert status1["remaining"] == 0
    assert status1["consumed"] is True
    assert status1["injection"] == "OFF"

    again = synthetic_signal_once.inject_once(
        symbol="XAUUSD", side="SELL", confirmed=True
    )
    assert again["ok"] is False
    assert "already consumed" in str(again.get("error") or "")
    assert again["mt5_order_submitted"] is False

    rearm = synthetic_signal_once.arm_once(confirmed=True)
    assert rearm["ok"] is False
    assert "cannot re-arm" in str(rearm.get("error") or "")


def test_signal_center_marks_test_synthetic_source() -> None:
    _store_last_scan(
        {
            "as_of": "2026-08-10T01:00:00Z",
            "universe": ["XAUUSD"],
            "source": "TEST_SYNTHETIC",
            "test_synthetic": True,
            "signal_id": "TEST-SYNTHETIC-UNIT",
            "note": "TEST/SYNTHETIC",
            "eligible_symbols": [],
            "eligible_count": 0,
            "best_symbol": None,
            "rows": [
                {
                    "symbol": "XAUUSD",
                    "direction": "SELL",
                    "trade_quality": 84,
                    "ai_confidence": 81,
                    "reject": False,
                    "test_synthetic": True,
                    "signal_id": "TEST-SYNTHETIC-UNIT",
                    "strategy": "TEST_SYNTHETIC",
                    "momentum": 70,
                    "structure": 75,
                }
            ],
        }
    )
    payload = signal_center_service.list_live_signals(enabled_only=False)
    assert payload["source"] == "TEST_SYNTHETIC"
    assert payload["fabricated"] is True
    assert payload["test_synthetic"] is True
    assert payload["signal_id"] == "TEST-SYNTHETIC-UNIT"
    xau = next(i for i in payload["items"] if i["symbol"] == "XAUUSD")
    assert xau["direction"] == "SELL"
    assert xau["test_synthetic"] is True
    assert xau["badge"].startswith("TEST")

