"""17 Nov 2026: the owner's automatic gateway adoption re-pointed the owner's
connection at a customer's XM account, then startup rehydration bound the
owner's execution identity to it. Automatic binding now requires the login
to be one of the user's own broker accounts."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from app.application.services import broker_ownership_restore as bor

pytestmark = [pytest.mark.unit, pytest.mark.real_login_registration]


def _fetch_rows(rows: list[dict[str, Any]]) -> Any:
    def fetch(sql: str, *args: Any) -> list[dict[str, Any]]:
        assert "broker_accounts" in sql and "user_id" in sql
        return rows

    return fetch


def test_registered_login_passes() -> None:
    assert bor.login_registered_to_user(
        uuid4(), 12439799, fetch=_fetch_rows([{"x": 1}])
    )


def test_unregistered_login_is_refused() -> None:
    assert not bor.login_registered_to_user(uuid4(), 450397410, fetch=_fetch_rows([]))


def test_unreadable_registry_fails_closed() -> None:
    def broken(*_a: Any) -> Any:
        raise RuntimeError("db down")

    assert not bor.login_registered_to_user(uuid4(), 450397410, fetch=broken)
    assert not bor.login_registered_to_user(uuid4(), 0, fetch=_fetch_rows([{"x": 1}]))


def test_rehydrate_refuses_owner_claim_on_unregistered_login(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = uuid4()
    import app.infrastructure.persistence.direct_postgres as dp

    monkeypatch.setattr(dp, "direct_postgres_available", lambda: True)
    monkeypatch.setattr(
        dp,
        "fetch",
        lambda sql, *_a: (
            [{"user_id": str(owner), "email": bor.DESIGNATED_OWNER_EMAIL}]
            if "mt5_connections" in sql
            else []
        ),
    )
    bound: list[Any] = []
    monkeypatch.setattr(bor, "bind_execution_account", lambda **kw: bound.append(kw))
    out = bor.rehydrate_designated_owner_binding(450397410)
    assert out == {"bound": False, "reason": "login_not_registered_to_owner"}
    assert bound == []


def test_another_users_account_is_detected_and_fails_closed() -> None:
    uid = uuid4()
    assert bor.login_registered_to_another_user(
        uid, 12439799, "Weltrade-Real", fetch=_fetch_rows([{"x": 1}])
    )
    assert not bor.login_registered_to_another_user(
        uid, 12439799, "Weltrade-Real", fetch=_fetch_rows([])
    )

    def broken(*_a: Any) -> Any:
        raise RuntimeError("db down")

    assert bor.login_registered_to_another_user(uid, 1, "x", fetch=broken)
