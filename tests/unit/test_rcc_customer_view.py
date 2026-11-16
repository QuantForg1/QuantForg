"""Robot Control Center customer view: truthful status, no owner policy."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest

from app.application.services import robot_control_service as rc

READY = {"state": rc.ROBOT_READY, "source": "worker"}


@pytest.mark.parametrize(
    ("control", "conn", "entitled", "enabled", "code"),
    [
        (rc.RUNNING, READY, True, True, rc.ROBOT_RUNNING),
        (rc.RUNNING, READY, True, False, rc.WAITING),
        (rc.RUNNING, READY, True, None, rc.WAITING),
        (rc.RUNNING, READY, False, True, rc.WAITING),
        (rc.RUNNING, READY, None, True, rc.WAITING),
        (rc.RUNNING, {"state": rc.UNAVAILABLE}, True, True, rc.WAITING),
        (rc.RUNNING, {"state": rc.NOT_CONNECTED}, True, True, rc.WAITING),
        (rc.RUNNING, {"state": "SOMETHING_NEW"}, True, True, rc.WAITING),
        (rc.PAUSED, READY, True, True, rc.PAUSED),
        (rc.STOPPED, READY, True, True, rc.STOPPED),
        (rc.EMERGENCY_STOPPED, READY, True, True, rc.EMERGENCY_STOPPED),
    ],
)
def test_running_only_with_full_evidence(
    control: str,
    conn: dict[str, Any],
    entitled: bool | None,
    enabled: bool | None,
    code: str,
) -> None:
    out = rc.robot_status(
        control_state=control,
        connection=conn,
        entitled=entitled,
        execution_enabled=enabled,
    )
    assert out["code"] == code
    if code != rc.ROBOT_RUNNING:
        assert out["label"] != "Running"


OWNER_TOKENS = ("OWNER", "1.5", "1.50", "0.45", "RR", "QUALITY", "SPREAD", "07:00")


@pytest.mark.parametrize(
    "reason",
    [
        "OWNER_MIN_RR: rr 1.21 < 1.50 after spread",
        "OWNER_MAX_SPREAD: 0.61 > 0.45",
        "OWNER_QUALITY: 62 < 75",
        "OWNER_SESSION: outside 07:00-17:00 UTC",
        "GUARD_MAX_RISK 9%",
    ],
)
def test_block_reasons_are_sanitized(reason: str) -> None:
    out = rc.activity_outcome("blocked", reason)
    assert out == "Blocked by risk checks"
    for tok in OWNER_TOKENS:
        assert tok not in out.upper()


def test_activity_categories() -> None:
    assert rc.activity_outcome("filled", None) == "Executed"
    assert rc.activity_outcome("blocked", "SUBSCRIPTION_INACTIVE") == (
        "Blocked: subscription inactive"
    )
    assert rc.activity_outcome("weird", None) == "Recorded"


def test_recent_activity_never_returns_block_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _DB:
        @staticmethod
        def fetch(*_a: Any) -> list[dict[str, Any]]:
            return [
                {
                    "broker_account_id": "a",
                    "state": "blocked",
                    "block_reason": "OWNER_MIN_RR: rr 1.21 < 1.50",
                    "planned_volume": "0.01",
                    "broker_ticket": None,
                    "payload": json.dumps(
                        {"symbol": "XAUUSD", "side": "buy", "rr": 1.21}
                    ),
                    "created_at": datetime(2026, 11, 16, tzinfo=UTC),
                }
            ]

    monkeypatch.setattr(rc, "_db", lambda: _DB)
    from uuid import uuid4

    rows = rc.recent_activity(user_id=uuid4())
    blob = json.dumps(rows)
    assert "OWNER" not in blob and "1.5" not in blob and "rr" not in rows[0]
    assert rows[0]["outcome"] == "Blocked by risk checks"
    assert rows[0]["symbol"] == "XAUUSD" and rows[0]["side"] == "BUY"


def test_public_event_drops_readiness_details() -> None:
    from app.presentation.routers.robot_control import _public_event

    out = _public_event(
        {
            "action": "resume",
            "readiness": {"ready": False, "checks": {"x": 1}, "reasons": ["a"]},
            "at": "t",
        }
    )
    assert "readiness" not in out and out["verified"] is False


def test_customer_api_payload_has_no_owner_policy() -> None:
    import inspect

    from app.presentation.routers import robot_control

    src = inspect.getsource(robot_control.my_robot_accounts) + inspect.getsource(
        robot_control._strategy
    )
    for tok in ("OWNER_", "owner_limits", "min_reward_risk", "max_spread"):
        assert tok not in src
