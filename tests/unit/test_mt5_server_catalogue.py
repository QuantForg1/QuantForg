"""Honest MT5 broker/server catalogue — never invent verified servers."""

from __future__ import annotations

from app.domain.broker_connectivity.mt5_server_catalogue import (
    broker_registry_rows,
    catalogue_snapshot,
    verified_servers_for_broker,
)


def test_eight_live_brokers_owner_production_connectable(monkeypatch, tmp_path) -> None:
    # Isolate from host evidence; owner-authorized LIVE set still connectable.
    empty = tmp_path / "empty_evidence.json"
    monkeypatch.setenv("QF_BROKER_VERIFICATION_EVIDENCE_PATH", str(empty))
    rows = broker_registry_rows()
    by_slug = {r["slug"]: r for r in rows}
    assert by_slug["weltrade"]["connectable"] is True
    assert by_slug["weltrade"]["connection_status"] == "production_verified"
    assert all(r["customer_selectable"] is True for r in rows)
    for slug in (
        "xm",
        "exness",
        "hfm",
        "justmarkets",
        "ic-markets",
        "pepperstone",
        "fp-markets",
    ):
        assert by_slug[slug]["connectable"] is True
        assert by_slug[slug]["display_label"] == "Verified"
        assert by_slug[slug]["verification_status"] == "VERIFIED_LIVE"
        assert by_slug[slug]["trading_readiness_display"] == "Verified"
    # Genuine MT5 trade_allowed evidence (portable LIVE verify).
    for slug in ("xm", "ic-markets", "pepperstone", "fp-markets"):
        assert by_slug[slug]["trade_allowed"] is True
        assert by_slug[slug]["trading_enabled"] is True
    # Auth OK but MT5 trade_allowed=false — never manufacture permission.
    for slug in ("exness", "hfm", "justmarkets"):
        assert by_slug[slug]["trade_allowed"] is False
        assert by_slug[slug]["trading_enabled"] is False
        assert by_slug[slug]["trading_readiness"] == "AUTH_OK_TRADE_NOT_ENABLED"
        assert by_slug[slug]["trading_readiness_display"] == "Verified"
        assert by_slug[slug]["display_label"] != "FUNDING_REQUIRED"
        assert by_slug[slug]["display_label"] != "OWNER_VERIFIED_LIVE"


def test_unverified_brokers_have_no_invented_servers() -> None:
    # Exness / HFM / JustMarkets: authenticated LIVE servers; trade_allowed false.
    hfm = verified_servers_for_broker("hfm")
    assert any(r["name"] == "HFMarketsGlobal-Live20" and r["confirmed"] for r in hfm)
    assert all(r.get("trade_allowed") is False for r in hfm)
    # FP Markets / IC Markets: CONFIRMED from Windows MT5 portable auth evidence.
    fp = verified_servers_for_broker("fp-markets")
    assert any(r["name"] == "FPMarketsSC-Live" and r["confirmed"] for r in fp)
    ic = verified_servers_for_broker("ic-markets")
    assert any(r["name"] == "ICMarketsSC-MT5-3" and r["confirmed"] for r in ic)
    jm = verified_servers_for_broker("justmarkets")
    assert len(jm) == 1
    assert jm[0]["name"] == "JustMarkets-Live7"
    assert jm[0]["evidence_classification"] == "CONFIRMED"
    assert jm[0]["confirmed"] is True
    assert jm[0].get("trading_readiness") == "AUTH_OK_TRADE_NOT_ENABLED"
    assert jm[0].get("trade_allowed") is False
    ex = verified_servers_for_broker("exness")
    assert len(ex) == 1
    assert ex[0]["name"] == "Exness-MT5Real10"
    assert ex[0]["confirmed"] is True
    assert ex[0].get("trade_allowed") is False
    xm = verified_servers_for_broker("xm")
    assert any(r["name"] == "XMGlobal-MT5 20" and r["confirmed"] for r in xm)
    pepper = verified_servers_for_broker("pepperstone")
    assert any(
        r["name"] == "PepperstoneKE-MT5-Live01" and r["confirmed"] for r in pepper
    )


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
        discovered=["Weltrade-Live-Extra", "Weltrade-Real", "Weltrade-MT5"],
    )
    names = {r["name"] for r in rows}
    assert "Weltrade-Real" in names
    # Explicit live token is accepted from discovery.
    assert "Weltrade-Live-Extra" in names
    discovered = [r for r in rows if r["name"] == "Weltrade-Live-Extra"]
    assert discovered[0]["source"] == "mt5_terminal_discovery"
    # Ambiguous Weltrade-MT5 (no demo/live/real token) is not invented as live.
    assert "Weltrade-MT5" not in names


def test_catalogue_snapshot_gateway_note() -> None:
    snap = catalogue_snapshot()
    assert snap["gateway"]["requires_windows_mt5_terminal"] is True
    assert "brokers" in snap and "servers" in snap
    assert any(r["name"] == "Exness-MT5Real10" for r in snap["servers"]["exness"])
    assert any(r["name"] == "XMGlobal-MT5 20" for r in snap["servers"]["xm"])
