"""Customer accounts get their own free slot automatically; never shared."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.application.services import customer_account_assignment as caa
from app.application.services.mt5_worker_api import Mt5WorkerApiFacade
from app.application.services.mt5_worker_control_plane import Mt5WorkerControlPlane

pytestmark = [pytest.mark.unit]

TOKEN = "t" * 40


class _Accounts:
    def __init__(self, rows: list[tuple[UUID, UUID]]) -> None:
        self.rows = rows  # (user_id, account_id), oldest first

    def __call__(self, _q: str, *_a: object) -> list[dict[str, object]]:
        return [{"user_id": u, "id": a} for u, a in self.rows]


@pytest.fixture
def accounts(monkeypatch: pytest.MonkeyPatch) -> _Accounts:
    acc = _Accounts([])
    real = caa.next_unassigned_account
    monkeypatch.setattr(
        caa,
        "next_unassigned_account",
        lambda *, taken_account_ids, fetch=None: real(  # noqa: ARG005
            taken_account_ids=taken_account_ids, fetch=acc
        ),
    )
    return acc


def _api() -> Mt5WorkerApiFacade:
    return Mt5WorkerApiFacade(plane=Mt5WorkerControlPlane(service_token=TOKEN))


def test_each_customer_gets_a_different_slot(accounts: _Accounts) -> None:
    alice = (uuid4(), uuid4())
    bob = (uuid4(), uuid4())
    accounts.rows = [alice, bob]
    api = _api()
    a = api.register(host_code="h1", slot_id="demo-a")
    b = api.register(host_code="h1", slot_id="demo-b")
    assert (a["user_id"], a["broker_account_id"]) == tuple(map(str, alice))
    assert (b["user_id"], b["broker_account_id"]) == tuple(map(str, bob))


def test_capacity_exhausted_means_queued_not_shared(accounts: _Accounts) -> None:
    accounts.rows = [(uuid4(), uuid4()) for _ in range(3)]
    api = _api()
    bound = {
        api.register(host_code="h1", slot_id=s)["broker_account_id"]
        for s in ("demo-a", "demo-b")
    }
    assert len(bound) == 2
    assert caa.queue_depth(taken_account_ids=bound, fetch=accounts) == 1


def test_lab_slot_is_rebound_when_a_customer_arrives(accounts: _Accounts) -> None:
    api = _api()
    first = api.register(host_code="h1", slot_id="demo-a")  # no customers: lab
    customer = (uuid4(), uuid4())
    accounts.rows = [customer]
    second = api.register(host_code="h1", slot_id="demo-a")
    assert second["worker_id"] != first["worker_id"]
    assert second["broker_account_id"] == str(customer[1])
    again = api.register(host_code="h1", slot_id="demo-a")  # idempotent now
    assert again["worker_id"] == second["worker_id"]


def test_live_accounts_not_assigned_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QF_AUTO_ASSIGN_ENVIRONMENTS", raising=False)
    assert caa.allowed_environments() == ("demo",)
    monkeypatch.setenv("QF_AUTO_ASSIGN_ENVIRONMENTS", "demo,live,bogus")
    assert caa.allowed_environments() == ("demo", "live")
