"""Measurement status stays empty until a real source is connected."""

from __future__ import annotations

import pytest

from app.application.services.measurement_connections import measurement_status

pytestmark = pytest.mark.unit


def test_missing_google_credentials_stay_not_connected() -> None:
    report = measurement_status({})
    assert report["search_console"] == "not_connected"
    assert report["ga4"] == "not_connected"
    assert all(value is None for value in report["values"].values())
    assert report["exposes_tokens"] is False


def test_credentials_do_not_invent_a_metric() -> None:
    report = measurement_status(
        {
            "GOOGLE_OAUTH_CLIENT_ID": "client",
            "GOOGLE_OAUTH_CLIENT_SECRET": "secret",
            "GOOGLE_OAUTH_REFRESH_TOKEN": "token",
            "GOOGLE_SEARCH_CONSOLE_SITE_URL": "https://www.quantforg.com",
            "GA4_PROPERTY_ID": "properties/1",
        }
    )
    assert report["search_console"] == "authorized_sync_not_run"
    assert report["ga4"] == "authorized_sync_not_run"
    assert report["values"]["search_impressions"] is None
    serialized = str(report["values"])
    assert "secret" not in serialized
    assert "token" not in serialized
