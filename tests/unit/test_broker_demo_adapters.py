"""Six-broker MT5 credential adapters — no invented servers."""

from __future__ import annotations

from services.mt5_worker_agent.broker_demo_adapters import (
    classify_environment,
    missing_credential_keys,
    normalize_broker_slug,
    resolve_credentials,
    resolve_demo_credentials,
    server_matches_broker,
    supported_brokers,
)


def test_supported_six_plus_weltrade() -> None:
    assert set(supported_brokers()) == {
        "exness",
        "hfm",
        "ic-markets",
        "pepperstone",
        "fp-markets",
        "xm",
        "weltrade",
    }


def test_normalize_broker_aliases() -> None:
    assert normalize_broker_slug("Exness") == "exness"
    assert normalize_broker_slug("HFMarkets") == "hfm"
    assert normalize_broker_slug("icmarkets") == "ic-markets"
    assert normalize_broker_slug("fpmarkets") == "fp-markets"
    assert normalize_broker_slug("unknown") is None


def test_server_matches_broker_patterns() -> None:
    assert server_matches_broker(broker_slug="exness", server="Exness-MT5Trial9")
    assert server_matches_broker(broker_slug="hfm", server="HFMarketsGlobal-Demo")
    assert server_matches_broker(broker_slug="ic-markets", server="ICMarketsSC-MT5-2")
    assert server_matches_broker(
        broker_slug="pepperstone", server="Pepperstone-MT5-Demo"
    )
    assert server_matches_broker(broker_slug="fp-markets", server="FPMarkets-Live")
    assert server_matches_broker(broker_slug="xm", server="XMGlobal-MT5")
    assert not server_matches_broker(
        broker_slug="exness", server="HFMarketsGlobal-Demo"
    )


def test_classify_environment() -> None:
    assert classify_environment("Exness-MT5Trial12") == "demo"
    assert classify_environment("HFMarketsGlobal-Demo") == "demo"
    assert classify_environment("Exness-MT5Real8") == "live"
    # Ambiguous XM server must not invent live from name alone.
    assert classify_environment("XMGlobal-MT5") == "demo"


def test_resolve_account_environment_demo_request_not_flipped_to_live() -> None:
    from services.mt5_worker_agent.broker_demo_adapters import (
        account_type_mismatch,
        resolve_account_environment,
    )

    env, source = resolve_account_environment(
        requested="demo",
        credential_environment="demo",
        server="XMGlobal-MT5",
        trade_mode=None,
    )
    assert env == "demo"
    assert "demo" in source
    env_tm, src_tm = resolve_account_environment(
        requested="demo",
        credential_environment="demo",
        server="XMGlobal-MT5",
        trade_mode=0,
    )
    assert env_tm == "demo"
    assert src_tm == "mt5_account_trade_mode"
    live_env, live_src = resolve_account_environment(
        requested="demo",
        credential_environment="demo",
        server="XMGlobal-MT5",
        trade_mode=2,
    )
    assert live_env == "live"
    assert live_src == "mt5_account_trade_mode"
    assert (
        account_type_mismatch(requested="demo", resolved=live_env, trade_mode=2)
        == "demo_request_authenticated_live_account"
    )


def test_resolve_requires_all_fields(monkeypatch) -> None:
    for env in (
        "QF_DEMO_EXNESS_LOGIN",
        "QF_DEMO_EXNESS_PASSWORD",
        "QF_DEMO_EXNESS_SERVER",
        "QF_DEMO_LOGIN",
        "QF_DEMO_PASSWORD",
        "QF_DEMO_SERVER",
    ):
        monkeypatch.delenv(env, raising=False)
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
    assert pub.get("auth_material_present") == "true"
    assert "password" not in str(pub).lower()
    assert "lab-only" not in str(pub)


def test_resolve_does_not_reuse_generic_demo_for_other_broker(monkeypatch) -> None:
    for env in (
        "QF_DEMO_EXNESS_LOGIN",
        "QF_DEMO_EXNESS_PASSWORD",
        "QF_DEMO_EXNESS_SERVER",
        "QF_DEMO_XM_LOGIN",
        "QF_DEMO_XM_PASSWORD",
        "QF_DEMO_XM_SERVER",
    ):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setenv("QF_DEMO_LOGIN", "999")
    monkeypatch.setenv("QF_DEMO_PASSWORD", "shared")
    monkeypatch.setenv("QF_DEMO_SERVER", "Generic-Demo")
    assert resolve_demo_credentials("exness") is None
    assert resolve_demo_credentials("xm") is None


def test_resolve_live_requires_live_material(monkeypatch) -> None:
    monkeypatch.delenv("QF_LIVE_IC_MARKETS_LOGIN", raising=False)
    monkeypatch.delenv("QF_LIVE_IC_MARKETS_PASSWORD", raising=False)
    monkeypatch.delenv("QF_LIVE_IC_MARKETS_SERVER", raising=False)
    monkeypatch.setenv("QF_DEMO_IC_MARKETS_LOGIN", "1")
    monkeypatch.setenv("QF_DEMO_IC_MARKETS_PASSWORD", "x")
    monkeypatch.setenv("QF_DEMO_IC_MARKETS_SERVER", "ICMarkets-Demo")
    assert resolve_credentials("ic-markets", environment="live") is None
