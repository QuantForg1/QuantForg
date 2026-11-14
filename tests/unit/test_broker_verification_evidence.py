"""Verification evidence gates connectable — never invents servers or passwords."""

from __future__ import annotations

from pathlib import Path

from app.domain.broker_connectivity.broker_verification_evidence import (
    connectable_slugs_from_evidence,
    ingest_worker_report,
    load_evidence,
    record_owner_trade_enablement,
    record_verification_failure,
    record_verification_success,
)
from app.domain.broker_connectivity.mt5_server_catalogue import (
    broker_registry_rows,
    verified_servers_for_broker,
)


def test_evidence_success_promotes_connectable(tmp_path: Path) -> None:
    path = tmp_path / "evidence.json"
    record_verification_success(
        broker_slug="exness",
        server="Exness-MT5Trial42",
        environment="demo",
        login=12345678,
        trade_allowed=True,
        market_data_ok=True,
        balance=1000.0,
        equity=1000.0,
        currency="USD",
        host_code="local-windows-1",
        slot_id="demo-a",
        path=path,
    )
    store = load_evidence(path)
    assert "exness" in store["brokers"]
    assert store["brokers"]["exness"]["connectable"] is True
    assert connectable_slugs_from_evidence(path) == {"exness"}
    # Explicit evidence path check (catalogue default path is separate).
    from app.domain.broker_connectivity.broker_verification_evidence import (
        discovered_servers_from_evidence,
    )

    assert discovered_servers_from_evidence(path)["exness"] == ["Exness-MT5Trial42"]


def test_failure_does_not_promote_connectable(tmp_path: Path) -> None:
    path = tmp_path / "evidence.json"
    record_verification_failure(
        broker_slug="hfm",
        error="login_failed",
        server="HFMarketsGlobal-Demo",
        path=path,
    )
    assert connectable_slugs_from_evidence(path) == set()
    entry = load_evidence(path)["brokers"]["hfm"]
    assert entry["connectable"] is False
    assert "password" not in str(entry).lower()


def test_ingest_strips_password_keys(tmp_path: Path) -> None:
    path = tmp_path / "evidence.json"
    ingest_worker_report(
        {
            "ok": True,
            "broker_slug": "hfm",
            "server": "HFMarketsGlobal-Demo",
            "environment": "demo",
            "login": 999001,
            "trade_allowed": True,
            "market_data_ok": True,
            "password": "MUST-NOT-PERSIST",
            "master_password": "MUST-NOT-PERSIST",
        },
        path=path,
    )
    raw = path.read_text(encoding="utf-8")
    assert "MUST-NOT-PERSIST" not in raw
    assert "HFMarketsGlobal-Demo" in raw


def test_catalogue_exness_hfm_owner_authorized_connectable(
    monkeypatch, tmp_path: Path
) -> None:
    path = tmp_path / "empty.json"
    monkeypatch.setenv("QF_BROKER_VERIFICATION_EVIDENCE_PATH", str(path))
    rows = {r["slug"]: r for r in broker_registry_rows()}
    assert rows["weltrade"]["connectable"] is True
    # Owner-authorized Production enablement — connectable even without local evidence file.
    assert rows["exness"]["connectable"] is True
    assert rows["exness"]["trade_allowed"] is True
    assert rows["exness"]["trading_enabled"] is True
    assert rows["hfm"]["connectable"] is True
    assert rows["justmarkets"]["connectable"] is True
    exness = verified_servers_for_broker("exness")
    assert all(r.get("confirmed") is True for r in exness)
    assert all(r.get("trade_allowed") is True for r in exness)
    hfm = verified_servers_for_broker("hfm")
    assert any(r["name"] == "HFMarketsGlobal-Live20" for r in hfm)


def test_owner_attestation_funding_required_does_not_enable_trading(
    tmp_path: Path,
) -> None:
    from app.domain.broker_connectivity.broker_verification_evidence import (
        record_owner_attestation,
    )

    path = tmp_path / "evidence.json"
    # Preserve a prior auth failure in the trail first.
    record_verification_failure(
        broker_slug="exness",
        error="authenticated_trading_not_enabled",
        server="Exness-MT5Real10",
        path=path,
    )
    entry = record_owner_attestation(
        broker_slug="exness",
        server="Exness-MT5Real10",
        login=409906277,
        prior_auth_error="authenticated_trading_not_enabled",
        prior_auth_at="2026-11-14T09:08:43+00:00",
        screenshot_refs=["owner_attestation/exness_portal.png"],
        path=path,
    )
    assert entry["connection_status"] == "live_verified"
    assert entry["verification_status"] == "VERIFIED_LIVE"
    assert entry["display_label"] == "Verified"
    assert entry["verification_method"] == "OWNER_ATTESTATION"
    assert entry["trading_readiness"] == "FUNDING_REQUIRED"
    assert entry["trade_allowed"] is False
    assert entry["trading_enabled"] is False
    assert entry["connectable"] is False
    assert entry["account_verified"] is True
    assert connectable_slugs_from_evidence(path) == set()
    assert len(entry["failure_history"]) >= 2
    raw = path.read_text(encoding="utf-8").lower()
    assert "master_password" not in raw
    assert "kigaliyacu" not in raw
    assert "409906277" not in path.read_text(encoding="utf-8")
    assert "***6277" in path.read_text(encoding="utf-8")


def test_owner_trade_enablement_promotes_connectable(tmp_path: Path) -> None:
    path = tmp_path / "evidence.json"
    entry = record_owner_trade_enablement(
        broker_slug="hfm",
        server="HFMarketsGlobal-Live20",
        login=261122172,
        path=path,
    )
    assert entry["connectable"] is True
    assert entry["trade_allowed"] is True
    assert entry["trading_enabled"] is True
    assert entry["verification_status"] == "VERIFIED_LIVE"
    assert entry["display_label"] == "Verified"
    assert connectable_slugs_from_evidence(path) == {"hfm"}
    assert "261122172" not in path.read_text(encoding="utf-8")
