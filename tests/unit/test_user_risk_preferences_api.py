"""Phase 4: user risk preferences authorization and hard-ceiling bounds."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.services.user_risk_preferences_service import (
    assert_own_user,
    preference_bounds,
    protection_status,
    update_user_risk_preferences,
)
from app.domain.exceptions.auth import AuthorizationError
from app.domain.exceptions.base import ValidationError
from app.domain.multi_account.effective_risk import (
    RiskSettingProposal,
    resolve_effective_risk,
)
from app.domain.institutional_trading.owner_live_limits import OWNER_MAX_LOT

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def test_preference_bounds_expose_ceilings_not_owner_document() -> None:
    bounds = preference_bounds()
    assert "planned_risk_pct" in bounds
    assert Decimal(str(bounds["max_lot"]["max"])) == OWNER_MAX_LOT
    assert "owner_policy" not in bounds
    assert "document" not in bounds


def test_protection_status_has_no_owner_numeric_policy_block() -> None:
    rows = protection_status()
    blob = " ".join(f"{r['title']} {r['detail']}" for r in rows).lower()
    assert "0.01" not in blob
    assert "48%" not in blob
    assert "owner policy" not in blob
    assert any(r["id"] == "stop_loss" for r in rows)


def test_user_cannot_exceed_owner_max_lot() -> None:
    effective = resolve_effective_risk(
        RiskSettingProposal(
            planned_risk_pct=Decimal("1"),
            aggregate_open_risk_pct=Decimal("5"),
            max_lot=Decimal("0.05"),
            daily_loss_pct=Decimal("10"),
            max_concurrent_positions=1,
        )
    )
    assert effective.ok is False
    assert any("max_lot" in f for f in effective.rejected_fields)


def test_assert_own_user_blocks_foreign_ids() -> None:
    me = uuid4()
    other = uuid4()
    assert_own_user(me, me)
    with pytest.raises(AuthorizationError):
        assert_own_user(me, other)


def test_update_rejects_when_storage_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.application.services.user_risk_preferences_service.direct_postgres_available",
        lambda: False,
    )
    with pytest.raises(ValidationError) as exc:
        update_user_risk_preferences(
            uuid4(),
            planned_risk_pct=Decimal("1"),
            aggregate_open_risk_pct=Decimal("5"),
            max_lot=Decimal("0.01"),
            daily_loss_pct=Decimal("10"),
            max_concurrent_positions=1,
        )
    assert exc.value.code == "risk_preference_storage_unavailable"


def test_update_rejects_over_ceiling_before_write(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"execute": 0}

    def _boom(*_a, **_k):  # pragma: no cover - must not run
        called["execute"] += 1
        raise AssertionError("execute must not run for invalid prefs")

    monkeypatch.setattr(
        "app.application.services.user_risk_preferences_service.direct_postgres_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.application.services.user_risk_preferences_service.execute",
        _boom,
    )
    with pytest.raises(ValidationError) as exc:
        update_user_risk_preferences(
            uuid4(),
            planned_risk_pct=Decimal("1"),
            aggregate_open_risk_pct=Decimal("5"),
            max_lot=Decimal("1"),
            daily_loss_pct=Decimal("10"),
            max_concurrent_positions=1,
        )
    assert exc.value.code == "risk_preference_rejected"
    assert called["execute"] == 0
