"""Customer LIVE broker catalogue — selectable without inventing servers."""

from __future__ import annotations

from app.domain.broker_connectivity.mt5_server_catalogue import (
    broker_registry_rows,
    candidate_servers_for_broker,
    classify_server_environment_hint,
    verified_servers_for_broker,
)


def test_all_seven_brokers_customer_selectable() -> None:
    rows = broker_registry_rows()
    slugs = {r["slug"] for r in rows}
    assert slugs == {
        "weltrade",
        "xm",
        "exness",
        "hfm",
        "ic-markets",
        "pepperstone",
        "fp-markets",
    }
    assert all(r["customer_selectable"] is True for r in rows)


def test_candidates_are_unconfirmed_and_broker_scoped() -> None:
    candidates = candidate_servers_for_broker("exness")
    assert candidates
    assert all(c.get("confirmed") is False for c in candidates)
    assert all("exness" in str(c["name"]).lower() for c in candidates)
    # Never invent numbered shards as confirmed.
    assert all(c.get("verified_at") is None for c in candidates)


def test_ambiguous_xm_hint_stays_unknown_env() -> None:
    assert classify_server_environment_hint("XMGlobal-MT5") == "unknown"
    assert classify_server_environment_hint("XMGlobal-Real") == "live"
    assert classify_server_environment_hint("Exness-MT5Trial9") == "demo"


def test_weltrade_verified_retained() -> None:
    rows = verified_servers_for_broker("weltrade")
    names = {r["name"] for r in rows}
    assert "Weltrade-Real" in names
    assert "Weltrade-Demo" in names
    live = next(r for r in rows if r["name"] == "Weltrade-Real")
    assert live["environment"] == "live"
    assert live.get("confirmed") is True
