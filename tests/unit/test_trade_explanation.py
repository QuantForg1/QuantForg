"""Trade explanations restate catalog reasons and do not invent the rest."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.application.dto.auth import AuthUserDTO
from app.domain.trade_explanation import explain_reasons

pytestmark = [pytest.mark.unit]
_ROOT = Path(__file__).resolve().parents[2]


def test_catalog_reason_is_labeled_non_authoritative() -> None:
    report = explain_reasons(["market closed"])
    item = report["explanations"][0]
    assert item["original_reason"] == "market closed"
    assert item["sentence"] == "Market is closed."
    assert item["status"] == "verified"
    assert item["authoritative"] is False
    assert report["overrides_execution"] is False
    assert report["places_orders"] is False


def test_unknown_reason_stays_blank() -> None:
    report = explain_reasons(["alpha-scanner invented this"])
    item = report["explanations"][0]
    assert item["sentence"] is None
    assert item["status"] == "unavailable"
    assert item["original_reason"] == "alpha-scanner invented this"


def test_empty_reason_is_unavailable() -> None:
    report = explain_reasons(["", "   "])
    assert [item["status"] for item in report["explanations"]] == [
        "unavailable",
        "unavailable",
    ]
    assert all(item["sentence"] is None for item in report["explanations"])


def test_spread_template_keeps_the_original_text() -> None:
    raw = "spread 42 exceeds maximum 20"
    report = explain_reasons([raw])
    item = report["explanations"][0]
    assert raw in (item["sentence"] or "")
    assert item["original_reason"] == raw
    assert item["overrides_execution"] is False


def test_modules_do_not_send_orders() -> None:
    for relative in (
        "app/domain/trade_explanation/explain.py",
        "app/presentation/routers/trade_explanation.py",
    ):
        text = (_ROOT / relative).read_text(encoding="utf-8")
        assert "order_send" not in text


def test_flag_defaults_off_and_router_is_registered() -> None:
    from app.main import _OPERATOR_ONLY_ROUTER_MODULES, _ROUTER_SPECS
    from core.config.settings import Settings

    spec = dict(_ROUTER_SPECS)
    path = "app.presentation.routers.trade_explanation"
    assert spec["trade_explanation"] == path
    assert "trade_explanation" not in _OPERATOR_ONLY_ROUTER_MODULES
    field = Settings.model_fields["trade_explanation_enabled"]
    assert field.default is False


def _user() -> AuthUserDTO:
    return AuthUserDTO(
        id=uuid4(),
        email="a@example.invalid",
        display_name="A",
        role="trader",
        status="active",
        auth_user_id=None,
    )


@pytest.mark.asyncio
async def test_route_hidden_until_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.presentation.routers import trade_explanation as router_module

    monkeypatch.setattr(
        router_module,
        "get_settings",
        lambda: SimpleNamespace(trade_explanation_enabled=False),
    )
    with pytest.raises(HTTPException) as caught:
        await router_module.trade_explanations(_user())
    assert caught.value.status_code == 404


@pytest.mark.asyncio
async def test_enabled_route_has_no_records_and_no_orders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.presentation.routers import trade_explanation as router_module

    monkeypatch.setattr(
        router_module,
        "get_settings",
        lambda: SimpleNamespace(trade_explanation_enabled=True),
    )
    user = _user()
    report = await router_module.trade_explanations(user)
    assert report["status"] == "unavailable"
    assert report["explanations"] == []
    assert report["places_orders"] is False
    assert report["overrides_execution"] is False
    assert str(user.id) not in str(report)
