"""Verification evidence gates connectable — never invents servers or passwords."""

from __future__ import annotations

from pathlib import Path

from app.domain.broker_connectivity.broker_verification_evidence import (
    connectable_slugs_from_evidence,
    ingest_worker_report,
    load_evidence,
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


def test_catalogue_exness_hfm_not_connectable_without_evidence(
    monkeypatch, tmp_path: Path
) -> None:
    path = tmp_path / "empty.json"
    monkeypatch.setenv("QF_BROKER_VERIFICATION_EVIDENCE_PATH", str(path))
    rows = {r["slug"]: r for r in broker_registry_rows()}
    assert rows["weltrade"]["connectable"] is True
    assert rows["exness"]["connectable"] is False
    assert rows["hfm"]["connectable"] is False
    # Exness may list a DOCUMENTED observed LIVE server without being connectable.
    exness = verified_servers_for_broker("exness")
    assert all(r.get("confirmed") is False for r in exness)
    assert all(r.get("evidence_classification") == "DOCUMENTED" for r in exness)
    assert verified_servers_for_broker("hfm") == []
