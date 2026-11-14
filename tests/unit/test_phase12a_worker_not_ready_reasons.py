"""Phase 12A — worker not_ready_reasons / dispatch_ready observability."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.multi_account.worker_lifecycle import WorkerLifecycleState
from app.domain.multi_account.worker_runtime import WorkerRuntime

pytestmark = [pytest.mark.unit]


def _worker(**kwargs: object) -> WorkerRuntime:
    base: dict[str, object] = {
        "worker_id": uuid4(),
        "worker_code": "w-test",
        "user_id": uuid4(),
        "broker_account_id": uuid4(),
        "host_id": uuid4(),
        "lifecycle": WorkerLifecycleState.PROVISIONING,
    }
    base.update(kwargs)
    return WorkerRuntime(**base)  # type: ignore[arg-type]


def test_not_ready_reasons_for_stale_unverified() -> None:
    now = datetime.now(UTC)
    w = _worker(
        lifecycle=WorkerLifecycleState.ERROR,
        last_heartbeat_at=now - timedelta(hours=24),
        last_error="heartbeat_stale",
        account_login_verified="",
        server_verified="",
    )
    reasons = w.not_ready_reasons(now=now, stale_after=timedelta(seconds=45))
    assert "lifecycle_error" in reasons
    assert "heartbeat_stale" in reasons
    assert "login_not_verified" in reasons
    assert "server_not_verified" in reasons
    assert w.public_status()["dispatch_ready"] is False


def test_revoked_worker_blocked() -> None:
    w = _worker(lifecycle=WorkerLifecycleState.REVOKED)
    reasons = w.not_ready_reasons(revoked=True)
    assert "revoked" in reasons
    assert w.public_status()["dispatch_ready"] is False


def test_ready_verified_fresh_is_dispatch_ready() -> None:
    now = datetime.now(UTC)
    w = _worker(
        lifecycle=WorkerLifecycleState.READY,
        last_heartbeat_at=now,
        account_login_verified="12345",
        server_verified="Demo-Server",
        trade_allowed=True,
    )
    assert w.not_ready_reasons(now=now) == []
    status = w.public_status()
    assert status["ready"] is True
    assert status["dispatch_ready"] is True
    assert status["not_ready_reasons"] == []
