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


def test_verified_idle_keeps_connection_and_marks_released() -> None:
    calls: list[tuple[str, tuple[Any, ...]]] = []
    assert bcv.mark_idle(uuid4(), execute=lambda q, *a: calls.append((q, a)))
    assert "verified_idle" in calls[0][0]
    assert "revoked" not in calls[0][0].split("WHERE")[0]


def test_assignment_skips_verified_accounts_without_subscription() -> None:
    from app.application.services.customer_account_assignment import (
        next_unassigned_account,
    )

    seen: list[str] = []

    def fetch(query: str, *_a: Any) -> list[dict[str, Any]]:
        seen.append(query)
        return []

    assert next_unassigned_account(taken_account_ids=set(), fetch=fetch) is None
    sql = seen[0]
    assert "metadata->>'verification'" in sql
    assert "public.licenses" in sql


def test_trial_start_is_discontinued() -> None:
    import asyncio

    from app.application.services.billing_service import BillingService
    from app.domain.exceptions.base import ValidationError
    from core.config.settings import get_settings

    svc = BillingService(get_settings())
    with pytest.raises(ValidationError) as err:
        asyncio.run(
            svc.start_trial(user_id=uuid4(), email="a@b.c", email_verified=True)
        )
    assert "no longer offered" in str(err.value)


def test_removed_account_is_not_active() -> None:
    from app.application.services.customer_account_assignment import (
        account_still_active,
    )

    assert account_still_active(uuid4(), fetch=lambda *_a: []) is False
    assert (
        account_still_active(uuid4(), fetch=lambda *_a: [{"status": "revoked"}])
        is False
    )
    assert (
        account_still_active(uuid4(), fetch=lambda *_a: [{"status": "active"}]) is True
    )

    def boom(*_a: Any) -> list[dict[str, Any]]:
        raise RuntimeError("db down")

    assert account_still_active(uuid4(), fetch=boom) is True


def test_status_reports_whether_a_verifier_is_online() -> None:
    row = {
        "id": uuid4(),
        "status": "active",
        "environment": "demo",
        "external_account_id": "43420953",
        "server": "Weltrade-Demo",
        "metadata": {"verification": "verifying"},
        "slug": "weltrade",
        "name": "Weltrade",
    }

    def fetch_with(n):
        def fetch(sql, *_a):
            return [{"n": n}] if "mt5_worker_control_plane" in sql else [row]

        return fetch

    assert bcv.status_for_user(uuid4(), fetch=fetch_with(0))["verifier_online"] is False
    assert bcv.status_for_user(uuid4(), fetch=fetch_with(2))["verifier_online"] is True

    def broken(sql, *_a):
        if "mt5_worker_control_plane" in sql:
            raise RuntimeError("db down")
        return [row]

    assert bcv.status_for_user(uuid4(), fetch=broken)["verifier_online"] is None


def test_first_auth_failure_is_not_a_rejection() -> None:
    state = {"n": "0"}

    def fetch(_q, _id):
        return [{"n": state["n"]}]

    def execute(_q, _id, patch):
        import json as _json

        state["n"] = _json.loads(patch)["auth_fail_count"]

    first = bcv.count_auth_failure("a", fetch=fetch, execute=execute)
    second = bcv.count_auth_failure("a", fetch=fetch, execute=execute)
    assert first < bcv.AUTH_FAILURES_BEFORE_REJECT <= second
    assert bcv.is_auth_failure(
        "initialize_failed:(-6, 'Terminal: Authorization failed')"
    )
    assert not bcv.is_auth_failure("initialize_failed:(-10005, 'IPC timeout')")
