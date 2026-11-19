"""Broker connect gives a real verdict: connected or rejected, never 'saved'."""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import pytest

from app.application.services import broker_connect_verification as bcv


@pytest.mark.parametrize(
    ("error", "code"),
    [
        ("login_failed:(-6, 'Authorization failed')", "INVALID_CREDENTIALS"),
        (
            "initialize_failed:(-6, 'Terminal: Authorization failed')",
            "INVALID_CREDENTIALS",
        ),
        ("authenticated_trading_not_enabled", "TRADING_NOT_ALLOWED"),
        ("login_account_mismatch:expected=***1 actual=***2", "INVALID_CREDENTIALS"),
    ],
)
def test_user_caused_failures_are_rejected(error: str, code: str) -> None:
    verdict = bcv.classify_failure(error)
    assert verdict is not None
    assert verdict[0] == bcv.REJECTED
    assert verdict[1] == code
    assert verdict[2]


@pytest.mark.parametrize(
    "error",
    [
        "initialize_failed:(-10001, 'IPC send failed')",
        "initialize_failed:(-10005, 'IPC timeout')",
        "authenticate_error:OSError",
        "",
    ],
)
def test_our_side_failures_keep_verifying(error: str) -> None:
    assert bcv.classify_failure(error) is None


def test_rejection_revokes_account_and_password() -> None:
    calls: list[tuple[str, tuple[Any, ...]]] = []
    account = uuid4()
    ok = bcv.mark(
        account,
        state=bcv.REJECTED,
        code="INVALID_CREDENTIALS",
        message="bad",
        fetch=lambda *_a: [],
        execute=lambda q, *a: calls.append((q, a)),
    )
    assert ok
    sql = " ".join(q for q, _ in calls)
    assert "status = 'revoked'" in sql
    assert "broker_credentials" in sql
    patch = json.loads(calls[0][1][1])
    assert patch["verification"] == "rejected"


def test_connected_marks_last_verified() -> None:
    calls: list[tuple[str, tuple[Any, ...]]] = []
    bcv.mark(
        uuid4(),
        state=bcv.CONNECTED,
        fetch=lambda *_a: [],
        execute=lambda q, *a: calls.append((q, a)),
    )
    assert len(calls) == 1
    assert "revoked" not in calls[0][0].split("WHERE")[0]
    patch = json.loads(calls[0][1][1])
    assert patch["verification"] == "connected"
    assert patch["last_verified"]


def test_status_reports_masked_account() -> None:
    row = {
        "id": uuid4(),
        "status": "revoked",
        "environment": "demo",
        "external_account_id": "49903676",
        "server": "HFMarketsGlobal-Demo",
        "metadata": {
            "verification": "rejected",
            "verification_code": "INVALID_CREDENTIALS",
            "verification_message": "MT5 rejected the login",
        },
        "updated_at": None,
        "slug": "hfm",
        "name": "HFM",
    }
    out = bcv.status_for_user(uuid4(), fetch=lambda *_a: [row])
    assert out["state"] == "rejected"
    assert out["account"] == "***3676"
    assert "49903676" not in json.dumps(out)
    assert bcv.status_for_user(uuid4(), fetch=lambda *_a: [])["state"] == "none"
