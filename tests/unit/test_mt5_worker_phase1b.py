"""Phase 1B — isolated MT5 worker control-plane tests (no real terminals).

Mock agents are not MetaTrader sessions. LIVE submit flags remain off.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.application.services.mt5_worker_control_plane import Mt5WorkerControlPlane
from app.domain.exceptions.base import ConflictError, NotFoundError, ValidationError
from app.domain.multi_account.feature_gates import multi_account_live_submit_allowed
from app.domain.multi_account.worker_agent_protocol import MockMt5WorkerAgent
from app.domain.multi_account.worker_lifecycle import (
    WorkerLifecycleState,
    assert_not_connected_until_ready,
    can_transition,
    transition,
)
from app.domain.multi_account.worker_supervisor import restart_backoff_seconds
from core.config.settings import Settings

pytestmark = [pytest.mark.unit]


def _plane(*, investor: bool = False, fail_auth: bool = False) -> Mt5WorkerControlPlane:
    agent = MockMt5WorkerAgent(investor_password=investor, fail_auth=fail_auth)
    plane = Mt5WorkerControlPlane(agent=agent, service_token="unit-test-service-token")
    plane.register_host(host_code="win-host-1", max_terminals=4, region="eu")
    return plane


def test_flags_still_block_live_submit() -> None:
    settings = Settings(_env_file=None)
    assert settings.multi_account_live_submit_enabled is False
    assert multi_account_live_submit_allowed(settings) is False


def test_lifecycle_ready_only_after_verify_path() -> None:
    assert can_transition(WorkerLifecycleState.VERIFYING, WorkerLifecycleState.READY)
    assert not can_transition(WorkerLifecycleState.PENDING, WorkerLifecycleState.READY)
    with pytest.raises(ValidationError):
        transition(WorkerLifecycleState.PENDING, WorkerLifecycleState.READY)
    with pytest.raises(ValidationError):
        assert_not_connected_until_ready(
            WorkerLifecycleState.AUTHENTICATING, "Connected"
        )


def test_capacity_exhaustion() -> None:
    plane = _plane()
    tiny = plane.capacity.register_host(host_code="tiny", max_terminals=1)
    plane.capacity.allocate_slot(tiny.host_id)
    with pytest.raises(ConflictError, match="capacity exhausted"):
        plane.capacity.allocate_slot(tiny.host_id)


@pytest.mark.asyncio
async def test_three_users_independent_workers() -> None:
    plane = _plane()
    users = [uuid4() for _ in range(3)]
    accounts = [uuid4() for _ in range(3)]
    workers = []
    for user, acct, login in zip(
        users, accounts, ("1001", "2002", "3003"), strict=True
    ):
        w = plane.provision_worker(user_id=user, broker_account_id=acct)
        ready = await plane.connect_and_verify(
            worker_id=w.worker_id,
            user_id=user,
            login=login,
            server="Demo-Server",
            password="demo-pass",
        )
        assert ready.is_ready
        assert ready.public_status()["connected"] is True
        workers.append(ready)

    # Fail worker A only.
    failed = plane.supervisor.fail_worker(
        worker_id=workers[0].worker_id, user_id=users[0], reason="simulated_crash"
    )
    assert failed.lifecycle is WorkerLifecycleState.ERROR
    b = plane.provisioner.get(workers[1].worker_id)
    c = plane.provisioner.get(workers[2].worker_id)
    assert b is not None and b.is_ready
    assert c is not None and c.is_ready

    # Disconnect A does not stop B/C.
    await plane.disconnect(worker_id=workers[0].worker_id, user_id=users[0])
    assert plane.provisioner.active_for_user(users[0]) is None
    assert plane.provisioner.active_for_user(users[1]).is_ready
    assert plane.provisioner.active_for_user(users[2]).is_ready


@pytest.mark.asyncio
async def test_tenant_isolation_and_one_worker_per_user() -> None:
    plane = _plane()
    user_a, user_b = uuid4(), uuid4()
    acct_a, acct_b = uuid4(), uuid4()
    w_a = plane.provision_worker(user_id=user_a, broker_account_id=acct_a)
    plane.provision_worker(user_id=user_b, broker_account_id=acct_b)

    with pytest.raises(NotFoundError):
        plane.provisioner.require_owner(worker_id=w_a.worker_id, user_id=user_b)

    with pytest.raises(ConflictError, match="already has an active worker"):
        plane.provision_worker(user_id=user_a, broker_account_id=uuid4())

    # Idempotent re-provision same account.
    again = plane.provision_worker(user_id=user_a, broker_account_id=acct_a)
    assert again.worker_id == w_a.worker_id


@pytest.mark.asyncio
async def test_investor_credentials_rejected() -> None:
    plane = _plane(investor=True)
    user = uuid4()
    w = plane.provision_worker(user_id=user, broker_account_id=uuid4())
    result = await plane.connect_and_verify(
        worker_id=w.worker_id,
        user_id=user,
        login="9999",
        server="Demo",
        password="investor",
    )
    assert result.lifecycle is WorkerLifecycleState.ERROR
    assert "investor" in result.last_error or "readonly" in result.last_error
    assert result.public_status()["connected"] is False


@pytest.mark.asyncio
async def test_heartbeat_stale_and_independent_reconnect() -> None:
    plane = _plane()
    user_a, user_b = uuid4(), uuid4()
    w_a = plane.provision_worker(user_id=user_a, broker_account_id=uuid4())
    w_b = plane.provision_worker(user_id=user_b, broker_account_id=uuid4())
    await plane.connect_and_verify(
        worker_id=w_a.worker_id,
        user_id=user_a,
        login="1",
        server="S",
        password="p",
    )
    await plane.connect_and_verify(
        worker_id=w_b.worker_id,
        user_id=user_b,
        login="2",
        server="S",
        password="p",
    )
    # Make A stale only.
    stale_time = datetime.now(UTC) + timedelta(seconds=120)
    plane.supervisor.record_heartbeat(
        worker_id=w_b.worker_id, user_id=user_b, now=stale_time
    )
    stale = plane.scan_stale(now=stale_time)
    stale_ids = {s.worker_id for s in stale}
    assert w_a.worker_id in stale_ids
    assert w_b.worker_id not in stale_ids
    still_b = plane.provisioner.get(w_b.worker_id)
    assert still_b is not None and still_b.is_ready

    reconnected, delay = plane.supervisor.request_reconnect(
        worker_id=w_a.worker_id, user_id=user_a
    )
    assert reconnected.lifecycle is WorkerLifecycleState.RECONNECTING
    assert delay >= 2.0


def test_backoff_is_bounded() -> None:
    assert restart_backoff_seconds(0) == 2.0
    assert restart_backoff_seconds(10) == 60.0


@pytest.mark.asyncio
async def test_revoke_prevents_reuse_until_reprovision() -> None:
    plane = _plane()
    user = uuid4()
    acct = uuid4()
    w = plane.provision_worker(user_id=user, broker_account_id=acct)
    await plane.connect_and_verify(
        worker_id=w.worker_id,
        user_id=user,
        login="55",
        server="S",
        password="p",
    )
    revoked = plane.provisioner.revoke(worker_id=w.worker_id, user_id=user)
    assert revoked.lifecycle is WorkerLifecycleState.REVOKED
    assert plane.provisioner.active_for_user(user) is None
    # New provision after revoke is allowed (new worker id).
    w2 = plane.provision_worker(user_id=user, broker_account_id=acct)
    assert w2.worker_id != w.worker_id


def test_public_status_has_no_secret_fields() -> None:
    plane = _plane()
    user = uuid4()
    w = plane.provision_worker(user_id=user, broker_account_id=uuid4())
    status = w.public_status()
    blob = str(status).lower()
    assert "password" not in blob
    assert "secret" not in blob
    assert "token" not in blob
