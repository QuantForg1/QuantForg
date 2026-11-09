"""Exness/HFM demo credential adapters — no invented servers."""

from __future__ import annotations

from services.mt5_worker_agent.broker_demo_adapters import (
    classify_environment,
    missing_credential_keys,
    normalize_broker_slug,
    resolve_demo_credentials,
    server_matches_broker,
)


def test_normalize_broker_aliases() -> None:
    assert normalize_broker_slug("Exness") == "exness"
    assert normalize_broker_slug("HFMarkets") == "hfm"
    assert normalize_broker_slug("hotforex") == "hfm"
    assert normalize_broker_slug("unknown") is None


def test_server_matches_broker_patterns() -> None:
    assert server_matches_broker(broker_slug="exness", server="Exness-MT5Trial9")
    assert server_matches_broker(broker_slug="hfm", server="HFMarketsGlobal-Demo")
    assert not server_matches_broker(
        broker_slug="exness", server="HFMarketsGlobal-Demo"
    )
    assert not server_matches_broker(broker_slug="hfm", server="Exness-MT5Real1")


def test_classify_environment() -> None:
    assert classify_environment("Exness-MT5Trial12") == "demo"
    assert classify_environment("HFMarketsGlobal-Demo") == "demo"
    assert classify_environment("Exness-MT5Real8") == "live"


def test_resolve_requires_all_fields(monkeypatch) -> None:
    monkeypatch.delenv("QF_DEMO_EXNESS_LOGIN", raising=False)
    monkeypatch.delenv("QF_DEMO_EXNESS_PASSWORD", raising=False)
    monkeypatch.delenv("QF_DEMO_EXNESS_SERVER", raising=False)
    monkeypatch.delenv("QF_DEMO_LOGIN", raising=False)
    monkeypatch.delenv("QF_DEMO_PASSWORD", raising=False)
    monkeypatch.delenv("QF_DEMO_SERVER", raising=False)
    assert resolve_demo_credentials("exness") is None
    missing = missing_credential_keys("exness")
    assert any("LOGIN" in m for m in missing)


def test_resolve_exness_bundle(monkeypatch) -> None:
    monkeypatch.setenv("QF_DEMO_EXNESS_LOGIN", "1001")
    monkeypatch.setenv("QF_DEMO_EXNESS_PASSWORD", "lab-only")
    monkeypatch.setenv("QF_DEMO_EXNESS_SERVER", "Exness-MT5Trial9")
    bundle = resolve_demo_credentials("exness")
    assert bundle is not None
    assert bundle.broker_slug == "exness"
    assert bundle.server == "Exness-MT5Trial9"
    pub = bundle.public_dict()
    assert "password" not in pub or pub.get("password_included") == "false"
    assert "lab-only" not in str(pub)
