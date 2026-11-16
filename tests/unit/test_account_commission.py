"""Owner-verified per-account commission: never guessed."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.services import account_commission as ac

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _fetch(vc: object):
    return lambda *_a: [{"vc": vc}]


def test_verified_value_is_used() -> None:
    vc = {"usd_per_order": "0.70", "source": "broker_tariff_document"}
    assert ac.verified_commission_usd(
        broker_account_id=uuid4(), fetch=_fetch(vc)
    ) == Decimal("0.70")


@pytest.mark.parametrize(
    "vc",
    [
        None,
        {"usd_per_order": "0.70", "source": "guess"},
        {"usd_per_order": "-1", "source": "broker_tariff_document"},
        {"usd_per_order": "abc", "source": "account_deal_history"},
    ],
)
def test_unverified_or_invalid_is_unknown(vc: object) -> None:
    assert (
        ac.verified_commission_usd(broker_account_id=uuid4(), fetch=_fetch(vc)) is None
    )


def test_read_error_is_unknown() -> None:
    def boom(*_a: object) -> list[object]:
        raise RuntimeError("db")

    assert ac.verified_commission_usd(broker_account_id=uuid4(), fetch=boom) is None


def test_recording_requires_source_and_evidence() -> None:
    calls: list[tuple[object, ...]] = []
    with pytest.raises(ValueError):
        ac.record_verified_commission(
            broker_account_id=uuid4(),
            usd_per_order=Decimal("0"),
            source="guess",
            evidence="tariff page 2026",
            actor_id=uuid4(),
            execute=lambda *a: calls.append(a),
        )
    with pytest.raises(ValueError):
        ac.record_verified_commission(
            broker_account_id=uuid4(),
            usd_per_order=Decimal("0"),
            source="broker_tariff_document",
            evidence="short",
            actor_id=uuid4(),
            execute=lambda *a: calls.append(a),
        )
    out = ac.record_verified_commission(
        broker_account_id=uuid4(),
        usd_per_order=Decimal("0.00"),
        source="broker_support_confirmation",
        evidence="Support ticket #123 confirmed 0 USD",
        actor_id=uuid4(),
        execute=lambda *a: calls.append(a),
    )
    assert out["usd_per_order"] == "0.00" and len(calls) == 1


def test_worker_guard_uses_the_accounts_verified_commission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.application.services.multi_account_owner_guard import evaluate_worker_entry
    from tests.unit.test_multi_account_owner_guard import BUY, CAPS, NOW, _snap

    monkeypatch.setattr(ac, "verified_commission_usd", lambda **_: Decimal("0"))
    snap = _snap()
    snap.pop("commission_source")
    snap.pop("commission_usd")
    res = evaluate_worker_entry(
        snapshot=snap,
        claimed_environment=None,
        user_id=uuid4(),
        **BUY,
        entry=None,
        now=NOW,
        user_caps=CAPS,
        broker_account_id=uuid4(),
    )
    assert res.reasons == ()
    monkeypatch.setattr(ac, "verified_commission_usd", lambda **_: None)
    res = evaluate_worker_entry(
        snapshot=snap,
        claimed_environment=None,
        user_id=uuid4(),
        **BUY,
        entry=None,
        now=NOW,
        user_caps=CAPS,
        broker_account_id=uuid4(),
    )
    assert res.reasons  # unknown commission rejects
