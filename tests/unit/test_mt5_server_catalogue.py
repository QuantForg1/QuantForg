"""Honest MT5 broker/server catalogue — never invent verified servers."""

from __future__ import annotations

from app.domain.broker_connectivity.mt5_server_catalogue import (
    broker_registry_rows,
    catalogue_snapshot,
    verified_servers_for_broker,
)


def test_only_weltrade_is_connectable() -> None:
    rows = broker_registry_rows()
    by_slug = {r["slug"]: r for r in rows}
    assert by_slug["weltrade"]["connectable"] is True
    assert by_slug["weltrade"]["connection_status"] == "production_verified"
    for slug in ("exness", "ic-markets", "pepperstone", "xm", "fp-markets", "hfm"):
        assert slug in by_slug
        assert by_slug[slug]["connectable"] is False
        assert by_slug[slug]["connection_status"] == "not_verified"


def test_unverified_brokers_have_no_invented_servers() -> None:
    assert verified_servers_for_broker("exness") == []
    assert verified_servers_for_broker("hfm") == []
    assert verified_servers_for_broker("fp-markets") == []


def test_weltrade_verified_servers_include_source_and_timestamp() -> None:
    rows = verified_servers_for_broker("weltrade")
    assert rows
    for row in rows:
        assert row["name"]
        assert row["environment"] in {"live", "demo"}
        assert row["source"]
        assert row["verified_at"]


def test_discovered_servers_are_tagged() -> None:
    rows = verified_servers_for_broker(
        "weltrade",
        discovered=["Weltrade-MT5", "Weltrade-Real"],
    )
    names = {r["name"] for r in rows}
    assert "Weltrade-Real" in names
    assert "Weltrade-MT5" in names
    discovered = [r for r in rows if r["name"] == "Weltrade-MT5"]
    assert discovered[0]["source"] == "mt5_terminal_discovery"


def test_catalogue_snapshot_gateway_note() -> None:
    snap = catalogue_snapshot()
    assert snap["gateway"]["requires_windows_mt5_terminal"] is True
    assert "brokers" in snap and "servers" in snap
    assert snap["servers"]["exness"] == []
