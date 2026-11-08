"""Desk preference defaults and validation on UserSettings."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.dto.platform import SettingsDTO
from app.domain.entities.platform import UserSettings
from app.domain.exceptions.base import ValidationError


@pytest.mark.unit
def test_user_settings_desk_defaults() -> None:
    settings = UserSettings.create_default(user_id=uuid4())
    assert settings.default_symbol == "XAUUSD"
    assert settings.default_timeframe == "M15"
    assert settings.date_format == "ymd"
    assert settings.time_format == "24h"
    assert settings.dashboard_prefs == {}
    assert settings.trading_ui_prefs == {}


@pytest.mark.unit
def test_settings_dto_includes_desk_fields() -> None:
    user_id = uuid4()
    settings = UserSettings.create_default(user_id=user_id)
    settings.update_fields(
        default_symbol="eurusd",
        default_timeframe="h1",
        date_format="dmy",
        time_format="12h",
        dashboard_prefs={"terminal": {"dense": True}},
    )
    dto = SettingsDTO.from_entity(settings)
    assert dto.default_symbol == "EURUSD"
    assert dto.default_timeframe == "H1"
    assert dto.date_format == "dmy"
    assert dto.time_format == "12h"
    assert dto.dashboard_prefs == {"terminal": {"dense": True}}


@pytest.mark.unit
def test_user_settings_rejects_invalid_timeframe() -> None:
    settings = UserSettings.create_default(user_id=uuid4())
    with pytest.raises(ValidationError):
        settings.update_fields(default_timeframe="H2")


@pytest.mark.unit
def test_user_settings_rejects_empty_symbol() -> None:
    settings = UserSettings.create_default(user_id=uuid4())
    with pytest.raises(ValidationError):
        settings.update_fields(default_symbol="   ")
