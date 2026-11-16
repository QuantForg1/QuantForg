"""Multi-user isolation, end to end in-process (no MT5, no network).

Three customers connect DEMO accounts; the host has two slots.
- Each slot is bound to a different customer; the third waits (queued).
- Each slot's sealed envelope carries only its own customer's credentials,
  and cannot be unwrapped as another worker.
- A slot that restarts (supervisor crash) keeps its customer.
- When a slot is retired, its customer is re-queued first (oldest) and is
  never doubled onto a slot that is already serving someone.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.application.services import (
    customer_account_assignment as caa,
    worker_credential_vault as vault,
)
from app.application.services.mt5_worker_api import Mt5WorkerApiFacade
from app.application.services.mt5_worker_control_plane import Mt5WorkerControlPlane
from app.application.services.mt5_worker_credential_seal import (
    unwrap_credential_material,
)

pytestmark = [pytest.mark.unit]

TOKEN = "isolation-test-service-token-0123456789"


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> dict[str, tuple[UUID, UUID]]:
    users = {n: (uuid4(), uuid4()) for n in ("alice", "bob", "carol")}
    logins = {users[n][1]: (n, f"{1000 + i}") for i, n in enumerate(users)}
    rows = [users[n] for n in ("alice", "bob", "carol")]  # oldest first
    real_next = caa.next_unassigned_account

    def fake_next(
        *,
        taken_account_ids: set[str],
        fetch: object = None,
        taken_user_ids: set[str] | None = None,
    ):
        return real_next(
            taken_account_ids=taken_account_ids,
            taken_user_ids=taken_user_ids,
            fetch=lambda *_a: [{"user_id": u, "id": a} for u, a in rows],
        )

    def fake_vault(*, broker_account_id: UUID, user_id: UUID, **_k: object):
        name, login = logins[broker_account_id]
        assert users[name][0] == user_id  # ownership is part of the lookup
        return vault.VaultCredential(
            login=login, server="Demo-Srv", environment="demo", password=f"pw-{name}"
        )

    monkeypatch.setattr(caa, "next_unassigned_account", fake_next)
    monkeypatch.setattr(vault, "load_vault_credential", fake_vault)
    monkeypatch.setattr(vault, "assigned_account_login", lambda **_k: None)
    return users


def _api() -> Mt5WorkerApiFacade:
    return Mt5WorkerApiFacade(plane=Mt5WorkerControlPlane(service_token=TOKEN))


def test_two_slots_three_customers(world: dict[str, tuple[UUID, UUID]]) -> None:
    api = _api()
    a = api.register(host_code="h", slot_id="demo-a")
    b = api.register(host_code="h", slot_id="demo-b")
    assert a["broker_account_id"] == str(world["alice"][1])
    assert b["broker_account_id"] == str(world["bob"][1])
    # Carol waits: no slot is shared.
    assert (
        caa.next_unassigned_account(
            taken_account_ids={a["broker_account_id"], b["broker_account_id"]}
        )
        == world["carol"]
    )

    env_a = api.claim_sealed_credentials(worker_id=UUID(a["worker_id"]))
    env_b = api.claim_sealed_credentials(worker_id=UUID(b["worker_id"]))
    assert env_a["credential_source"] == "vault"
    mat_a = unwrap_credential_material(
        service_token=TOKEN,
        worker_id=a["worker_id"],
        sealed_envelope=env_a["sealed_envelope"],
    )
    mat_b = unwrap_credential_material(
        service_token=TOKEN,
        worker_id=b["worker_id"],
        sealed_envelope=env_b["sealed_envelope"],
    )
    assert (mat_a["secret"], mat_b["secret"]) == ("pw-alice", "pw-bob")
    # Bob's worker cannot open Alice's envelope.
    with pytest.raises(ValueError):
        unwrap_credential_material(
            service_token=TOKEN,
            worker_id=b["worker_id"],
            sealed_envelope=env_a["sealed_envelope"],
        )
    assert "pw-alice" not in str(env_a)  # never plaintext in the response


def test_slot_restart_keeps_its_customer(world: dict[str, tuple[UUID, UUID]]) -> None:
    api = _api()
    first = api.register(host_code="h", slot_id="demo-a")
    again = api.register(host_code="h", slot_id="demo-a")  # supervisor restarted
    assert again["worker_id"] == first["worker_id"]
    assert again["broker_account_id"] == str(world["alice"][1])


def test_retired_slot_goes_to_the_waiting_customer(
    world: dict[str, tuple[UUID, UUID]],
) -> None:
    api = _api()
    a = api.register(host_code="h", slot_id="demo-a")
    api.register(host_code="h", slot_id="demo-b")
    api.revoke(worker_id=UUID(a["worker_id"]))  # slot retired
    c = api.register(host_code="h", slot_id="demo-c")
    # Alice is unbound again and is the oldest waiting account.
    assert c["broker_account_id"] == str(world["alice"][1])
    assert c["broker_account_id"] != str(world["bob"][1])  # never doubled
