"""Marketplace catalog view — stored versions and separated lanes."""

from __future__ import annotations

import pytest

from app.domain.marketplace.catalog_view import (
    PUBLISHED_VERSIONS,
    present_catalog,
)

pytestmark = pytest.mark.unit

_PLUGIN = {
    "key": "trend_following",
    "name": "Trend following",
    "category": "trend",
    "description": "Uses supplied bars.",
    "default_params": {"ema": 20},
    "performance": {"live": 12},
}


def test_published_registry_is_empty() -> None:
    assert PUBLISHED_VERSIONS == ()


def test_missing_version_record_stays_unavailable() -> None:
    row = present_catalog(_PLUGIN)
    assert row["version"] is None
    assert row["versions"] == []
    assert row["performance"]["combined"] is None
    assert row["performance"]["lanes"]["live"]["status"] == "unavailable"
    assert row["sales_enabled"] is False
    assert row["copy_trading_enabled"] is False
    assert row["automated_deployment_enabled"] is False


def test_incomplete_version_is_rejected() -> None:
    row = present_catalog(
        _PLUGIN,
        versions=[{"strategy_key": "trend_following", "version": "1.0.0"}],
    )
    assert row["versions"] == []


def test_stored_version_keeps_notes_and_compatibility() -> None:
    stored = {
        "strategy_key": "trend_following",
        "version": "1.2.0",
        "released_at": "2026-11-19T12:00:00+00:00",
        "release_notes": "Parameter check only.",
        "compatibility": "XAUUSD M15",
        "status": "available",
        "timeframe": "M15",
        "instrument": "XAUUSD",
        "risk_characteristics": "Loses money when the trend fails.",
    }
    row = present_catalog(_PLUGIN, versions=[stored])
    assert row["version"] == "1.2.0"
    assert row["versions"][0]["release_notes"] == "Parameter check only."
    assert row["compatibility"] == "XAUUSD M15"
    assert row["risk_characteristics"].startswith("Loses money")


def test_performance_lanes_do_not_mix() -> None:
    row = present_catalog(
        _PLUGIN,
        evidence=[
            {
                "strategy_key": "trend_following",
                "lane": "demo",
                "trace_id": "deal-9",
                "summary": "Demo record",
            },
            {
                "strategy_key": "trend_following",
                "lane": "live",
                "summary": "No trace",
            },
            {
                "strategy_key": "other",
                "lane": "live",
                "trace_id": "deal-1",
                "summary": "Someone else",
            },
        ],
    )
    lanes = row["performance"]["lanes"]
    assert lanes["demo"]["status"] == "available"
    assert lanes["demo"]["records"][0]["trace_id"] == "deal-9"
    assert lanes["live"]["status"] == "unavailable"
    assert lanes["backtest"]["records"] == []
    assert row["performance"]["combined"] is None
