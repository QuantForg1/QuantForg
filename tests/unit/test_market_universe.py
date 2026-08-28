"""Market-universe research layer — discovery, classification, isolation."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.application.services.research_universe_scanner import (
    evaluate_injected_contexts,
)
from app.domain.institutional_trading.operations.probability_selector import (
    OPPORTUNITY_SCORE_THRESHOLD,
)
from app.domain.market_universe.analytics import performance_report
from app.domain.market_universe.asset_profiles import profile_for
from app.domain.market_universe.classification import classify_instrument
from app.domain.market_universe.config_audit import build_configuration_audit
from app.domain.market_universe.constants import (
    FROZEN_DIRECTIONAL_EDGE,
    FROZEN_OPPORTUNITY_THRESHOLD,
    INSUFFICIENT_SAMPLE,
    UNKNOWN,
)
from app.domain.market_universe.correlation_research import analyze_correlation_exposure
from app.domain.market_universe.data_quality import evaluate_data_quality
from app.domain.market_universe.identity import (
    canonical_desk,
    same_economic_instrument,
)
from app.domain.market_universe.oos import (
    assert_no_lookahead,
    candidate_research_record,
    chronological_split,
    walk_forward_windows,
)
from app.domain.market_universe.opportunity_board import build_opportunity_board
from app.domain.market_universe.registry import build_registry
from app.domain.market_universe.report import build_market_universe_report
from app.domain.market_universe.scheduler import research_scan_order
from app.domain.market_universe.sessions import named_session, session_for_instrument
from app.domain.market_universe.shadow_wall import (
    ResearchExecutionBlocked,
    scan_package_isolation,
    submit_order,
)

pytestmark = [pytest.mark.unit]

ROOT = Path(__file__).resolve().parents[2]


def _rows() -> list[dict[str, object]]:
    return [
        {
            "code": "EURUSD_I",
            "description": "Euro vs US Dollar",
            "path": "Forex\\Majors\\EURUSD",
            "trade_mode": 4,
            "digits": 5,
            "currency_base": "EUR",
            "currency_profit": "USD",
        },
        {
            "code": "XAUUSD_I",
            "description": "Gold",
            "trade_mode": 4,
            "digits": 3,
            "path": "Metals\\XAUUSD",
        },
        {"code": "XAUUSD", "description": "Gold", "trade_mode": 4, "digits": 3},
        {
            "code": "BTCUSD",
            "description": "Bitcoin",
            "trade_mode": 4,
            "digits": 2,
            "path": "Crypto\\BTCUSD",
        },
        {"code": "ETHUSD", "description": "Ethereum", "trade_mode": 4, "digits": 2},
        {
            "code": "NDXUSD",
            "description": "US 100",
            "trade_mode": 4,
            "digits": 1,
            "path": "Indices\\NDX",
        },
        {
            "code": "XTIUSD",
            "description": "WTI",
            "trade_mode": 4,
            "digits": 2,
            "path": "Energies\\WTI",
        },
        {"code": "EURRUB", "description": "Euro Ruble", "trade_mode": 4, "digits": 5},
        {"code": "NAS100", "description": "Nas", "trade_mode": 4, "digits": 1},
        {"code": "GBPUSD_I", "trade_mode": 3, "digits": 5, "path": "Forex\\Majors"},
    ]


def test_canonical_aliases_collapse_gold_forms() -> None:
    assert canonical_desk("XAUUSD") == "XAUUSD"
    assert canonical_desk("XAUUSD_i") == "XAUUSD"
    assert canonical_desk("XAUUSD_I") == "XAUUSD"
    assert same_economic_instrument("XAUUSD", "XAUUSD_i")
    assert same_economic_instrument("BTCUSD", "BTCUSD_I")
    assert not same_economic_instrument("EURUSD", "GBPUSD")


def test_classification_prefers_broker_metadata() -> None:
    result = classify_instrument(
        "FOOBAR",
        broker_row={"path": "Forex\\Exotics\\FOOBAR", "description": "mystery"},
    )
    assert result.asset_class == "FOREX"
    assert result.classification_source == "BROKER_METADATA"


def test_classification_symbol_rules_and_energy() -> None:
    assert classify_instrument("EURUSD").asset_class == "FOREX"
    assert classify_instrument("XAUUSD_I").asset_class == "METALS"
    assert classify_instrument("BTCUSD").asset_class == "CRYPTO"
    assert classify_instrument("NDXUSD").asset_class == "INDICES"
    assert classify_instrument("XTIUSD").asset_class == "ENERGY"
    assert classify_instrument("XBRUSD").asset_class == "ENERGY"


def test_manual_override_is_explicit() -> None:
    result = classify_instrument(
        "EURUSD",
        manual_overrides={"EURUSD": ("ENERGY", "test override documented")},
    )
    assert result.asset_class == "ENERGY"
    assert result.classification_source == "MANUAL_OVERRIDE"
    assert "test override" in result.classification_reason


def test_registry_collapses_aliases_and_counts_classes() -> None:
    snap = build_registry(_rows())
    desks = {i["canonical_symbol"] for i in snap["instruments"]}
    assert "XAUUSD" in desks
    assert snap["counts"]["METALS"] >= 1
    assert snap["counts"]["FOREX"] >= 1
    assert snap["counts"]["CRYPTO"] >= 1
    assert snap["counts"]["INDICES"] >= 1
    assert snap["counts"]["ENERGY"] >= 1
    gold_forms = next(
        i for i in snap["instruments"] if i["canonical_symbol"] == "XAUUSD"
    )
    forms = {f.upper() for f in gold_forms["broker_forms"]}
    assert "XAUUSD_I" in forms
    assert "XAUUSD" in forms
    assert snap["authorizes_trade"] is False


def test_stale_and_missing_data_are_not_zero_opportunity() -> None:
    stale = evaluate_data_quality(
        bid=1.1,
        ask=1.2,
        quote_age_seconds=120,
    )
    assert stale.state == "STALE"
    assert stale.opportunity_score == UNKNOWN
    missing = evaluate_data_quality()
    assert missing.state == "NO_DATA"
    assert missing.opportunity_score == UNKNOWN
    closed = evaluate_data_quality(trade_mode="closeonly", bid=1, ask=1)
    assert closed.state == "MARKET_CLOSED"


def test_crypto_is_24_7_forex_is_not() -> None:
    crypto = session_for_instrument("BTCUSD", asset_class="CRYPTO")
    assert crypto["is_24_7"] is True
    assert crypto["session"] == "24/7"
    fx = session_for_instrument("EURUSD", asset_class="FOREX")
    assert fx["is_24_7"] is False
    assert named_session() in {
        "sydney",
        "tokyo",
        "london",
        "new_york",
        "london_ny_overlap",
    }


def test_opportunity_board_does_not_authorize_and_keeps_unknown() -> None:
    board = build_opportunity_board(
        [
            {
                "symbol": "XAUUSD_i",
                "direction": "BUY",
                "opportunity_score": 74,
                "directional_edge": 8,
                "setup_state": "WAIT",
            },
            {
                "symbol": "EURUSD_I",
                "data_state": "NO_DATA",
            },
        ]
    )
    assert board["authorizes_trade"] is False
    assert board["ranking_is_research_only"] is True
    gold = board["top_opportunities"][0]
    assert gold["canonical_symbol"] == "XAUUSD"
    assert gold["opportunity_score"] == 74
    eurusd = next(r for r in board["rows"] if r["canonical_symbol"] == "EURUSD")
    assert eurusd["opportunity_score"] == UNKNOWN
    assert gold["live_execution_eligible"] is False
    assert all(r["canonical_symbol"] != "EURUSD" for r in board["top_opportunities"])


def test_asset_profiles_do_not_weaken_gates() -> None:
    for cls in ("FOREX", "CRYPTO", "METALS", "INDICES", "ENERGY", "OTHER", "UNKNOWN"):
        p = profile_for(cls)
        assert p["weakens_risk"] is False
        assert p["weakens_safety"] is False
        assert p["authorizes_execution"] is False
        assert p["ALLOW_LIVE_PROMOTION"] is False


def test_correlation_flags_usd_cluster() -> None:
    result = analyze_correlation_exposure(["EURUSD", "GBPUSD", "XAUUSD"])
    assert "CORRELATED_EXPOSURE" in result["flags"]
    assert "USD_CONCENTRATION" in result["flags"]
    assert result["bypasses_risk"] is False


def test_scheduler_never_bypasses_safety_and_caps_batch() -> None:
    snap = build_registry(_rows())
    plan = research_scan_order(snap["instruments"], max_batch=4)
    assert plan["priority_never_bypasses_safety"] is True
    assert plan["batch_size"] <= 4
    assert plan["ALLOW_LIVE_PROMOTION"] is False


def test_shadow_cannot_execute() -> None:
    with pytest.raises(ResearchExecutionBlocked):
        submit_order(symbol="EURUSD")
    iso = scan_package_isolation()
    assert iso["isolated"] is True
    assert iso["ALLOW_LIVE_PROMOTION"] is False


def test_research_scanner_has_no_oms_flag() -> None:
    out = evaluate_injected_contexts(
        [{"symbol": "EURUSD_I", "opportunity_score": 80, "directional_edge": 6}]
    )
    assert out["forwarded_to_oms"] is False
    assert out["would_submit_order"] is False
    assert out["ALLOW_LIVE_PROMOTION"] is False


def test_lookahead_is_rejected() -> None:
    row = candidate_research_record(
        {"candidate_id": "A", "symbol": "EURUSD", "future_pnl": 12, "opportunity": 71}
    )
    assert row["lookahead_blocked"] is True
    assert "future_pnl" in row["lookahead_fields"]
    with pytest.raises(ValueError, match="LOOKAHEAD"):
        assert_no_lookahead({"future_bos": True})


def test_oos_is_chronological_and_insufficient_below_20() -> None:
    small = chronological_split([{"timestamp": f"2026-01-0{i}"} for i in range(1, 8)])
    assert small["status"] == INSUFFICIENT_SAMPLE
    assert small["shuffled"] is False
    rows = [{"timestamp": f"2026-01-{i:02d}", "i": i} for i in range(1, 41)]
    split = chronological_split(rows)
    assert split["n"] == 40
    assert split["train"][0]["i"] == 1
    assert split["oos"][-1]["i"] == 40
    assert split["automatic_promotion"] is False
    wf = walk_forward_windows(rows, window=20, step=10)
    assert wf["shuffled"] is False
    assert wf["windows"]


def test_analytics_require_n_and_matched_only() -> None:
    report = performance_report(
        [
            {
                "match_class": "UNMATCHED_BROKER_ACTIVITY",
                "net_pnl": 100,
                "symbol": "EURUSD",
            }
        ]
    )
    assert report["STRATEGY_MATCHED_SAMPLE"] == 0
    assert report["OVERALL"]["sample_size"] == 0
    assert (
        "n=" in str(report["OVERALL"]["WIN_RATE_DISPLAY"]).lower()
        or report["OVERALL"]["WIN_RATE"] == UNKNOWN
    )


def test_canonical_identity_fields_for_gold_broker_form() -> None:
    identity = canonical_desk("XAUUSD_i")
    classified = classify_instrument("XAUUSD_i")
    assert identity == "XAUUSD"
    assert classified.asset_class == "METALS"


def test_config_audit_frozen_gates() -> None:
    audit = build_configuration_audit()
    by_name = {r["SETTING"]: r for r in audit["rows"]}
    assert by_name["OPPORTUNITY_SCORE_THRESHOLD"]["EFFECTIVE_VALUE"] == 70
    assert by_name["DIRECTION_EDGE_MARGIN"]["EFFECTIVE_VALUE"] == 5
    assert by_name["FORCE_FIRST_TRADE"]["EFFECTIVE_VALUE"] is False
    assert by_name["ALLOW_LIVE_PROMOTION"]["EFFECTIVE_VALUE"] is False
    assert audit["silently_normalizes_conflicts"] is False


def test_live_opportunity_and_edge_unchanged() -> None:
    assert OPPORTUNITY_SCORE_THRESHOLD == 70
    assert FROZEN_OPPORTUNITY_THRESHOLD == 70
    assert FROZEN_DIRECTIONAL_EDGE == 5
    from app.domain.institutional_trading.ai_scalping.config import (
        DEFAULT_AI_SCALPING_CONFIG,
    )

    assert int(DEFAULT_AI_SCALPING_CONFIG.direction_edge_margin) == 5


def test_report_unknowns_and_safety_block() -> None:
    report = build_market_universe_report(broker_rows=_rows())
    assert report["1_MARKET_UNIVERSE_COUNT"] >= 5
    assert report["2_FOREX_COUNT"] >= 1
    assert report["3_CRYPTO_COUNT"] >= 1
    assert report["4_METALS_COUNT"] >= 1
    assert report["6_ENERGY_COUNT"] >= 1
    safety = report["30_PRODUCTION_SAFETY_AUDIT"]
    assert safety["SHADOW_CAN_EXECUTE"] is False
    assert safety["LIVE_ORDER_SENT"] is False
    assert safety["xauusd_canonical"] == "XAUUSD"


def test_research_package_has_no_order_send_path() -> None:
    pkg = ROOT / "app" / "domain" / "market_universe"
    for path in pkg.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert "gateway_client" not in mod
                assert "institutional_oms" not in mod
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if path.name == "shadow_wall.py":
                    continue
                assert node.func.id != "order_send"


def test_gold_only_scan_universe_not_expanded_by_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.application.services.institutional_multi_asset_scanner import (
        resolve_scan_universe,
    )
    from app.domain.institutional_trading.ai_scalping.config import (
        DEFAULT_AI_SCALPING_CONFIG,
    )
    from app.domain.trading.gold_only import is_gold_symbol

    monkeypatch.setattr(
        "app.domain.trading.gold_only.gold_only_enabled",
        lambda: True,
    )
    uni = resolve_scan_universe(
        DEFAULT_AI_SCALPING_CONFIG,
        broker_symbol_rows=_rows(),
    )
    assert uni
    assert all(is_gold_symbol(s) for s in uni)


def test_injected_catalogue_is_never_labeled_live() -> None:
    from app.application.services.market_universe_service import build_snapshot
    from app.domain.market_universe.broker_catalogue import discover_live_catalogue
    from app.domain.market_universe.constants import (
        CATALOGUE_INJECTED,
        CATALOGUE_LIVE_BROKER,
        CATALOGUE_UNAVAILABLE,
    )

    empty = discover_live_catalogue(None)
    assert empty["catalogue_source"] == CATALOGUE_UNAVAILABLE
    assert empty["invented"] is False
    assert empty["rows"] == ()

    class _Adapter:
        def symbols(self) -> list[dict[str, object]]:
            return [
                {
                    "code": "EURUSD_i",
                    "description": "Euro vs US Dollar",
                    "path": "Forex\\Majors",
                    "trade_mode": "full",
                    "digits": 5,
                }
            ]

    live = discover_live_catalogue(_Adapter())
    assert live["catalogue_source"] == CATALOGUE_LIVE_BROKER
    assert live["count"] == 1
    snap = build_snapshot(broker_rows=_rows())
    assert snap["catalogue_source"] == CATALOGUE_INJECTED
    assert snap["fixture_presented_as_live"] is False
    assert snap["authorizes_trade"] is False


def test_classification_confidence_and_unknown_other() -> None:
    meta = classify_instrument(
        "FOOBAR",
        broker_row={"path": "Forex\\Exotics\\FOOBAR"},
    )
    assert meta.classification_source == "BROKER_METADATA"
    assert meta.classification_confidence == "HIGH"
    rule = classify_instrument("EURUSD")
    assert rule.classification_source == "SYMBOL_RULE"
    mystery = classify_instrument("FOO")
    assert mystery.asset_class == "UNKNOWN"
    assert mystery.classification_confidence == "UNKNOWN"


def test_error_and_unknown_data_states_are_not_zero_opportunity() -> None:
    err = evaluate_data_quality(fetch_error=True, bid=1.1, ask=1.2)
    assert err.state == "ERROR"
    assert err.opportunity_score == UNKNOWN
    unk = evaluate_data_quality(unknown=True)
    assert unk.state == "UNKNOWN"
    assert unk.opportunity_score == UNKNOWN
    closed = evaluate_data_quality(market_open=False, bid=1, ask=1)
    assert closed.state == "MARKET_CLOSED"


def test_buy_sell_symmetry_never_defaults_to_buy() -> None:
    out = evaluate_injected_contexts(
        [
            {"symbol": "EURUSD_I", "opportunity_score": 80, "directional_edge": 6},
            {
                "symbol": "GBPUSD",
                "opportunity_score": 72,
                "directional_edge": 7,
                "direction": "SELL",
                "core_buy": 40,
                "core_sell": 61,
            },
        ]
    )
    assert out["never_prefer_buy_only"] is True
    wait_row = next(r for r in out["rows"] if r["canonical_symbol"] == "EURUSD")
    sell_row = next(r for r in out["rows"] if r["canonical_symbol"] == "GBPUSD")
    assert wait_row["direction"] == "WAIT"
    assert wait_row["selected_side"] == "WAIT"
    assert sell_row["direction"] == "SELL"
    board = build_opportunity_board(out["rows"])
    assert board["never_prefer_buy_only"] is True
    assert board["authorizes_trade"] is False


def test_virtual_replay_lookahead_same_bar_and_sl_wins() -> None:
    from app.domain.market_universe.virtual_replay import evaluate_virtual_bar

    leaked = evaluate_virtual_bar(
        entry_timestamp="2026-01-01T00:00:00+00:00",
        bar_timestamp="2026-01-01T00:01:00+00:00",
        direction="BUY",
        sl=1.0,
        tp=2.0,
        high=2.1,
        low=0.9,
        features={"future_close": 1.5},
    )
    assert leaked["status"] == "LOOKAHEAD_REJECTED"
    assert leaked["would_submit_order"] is False
    same = evaluate_virtual_bar(
        entry_timestamp="2026-01-01T00:00:00+00:00",
        bar_timestamp="2026-01-01T00:00:00+00:00",
        direction="BUY",
        sl=1.0,
        tp=2.0,
        high=2.1,
        low=0.9,
    )
    assert same["status"] == "SAME_BAR_OR_EARLIER_REJECTED"
    both = evaluate_virtual_bar(
        entry_timestamp="2026-01-01T00:00:00+00:00",
        bar_timestamp="2026-01-01T00:05:00+00:00",
        direction="BUY",
        sl=1.0,
        tp=2.0,
        high=2.1,
        low=0.9,
    )
    assert both["exit_reason"] == "SL"
    assert both["would_submit_order"] is False


def test_bounded_concurrency_isolates_failures() -> None:
    from app.domain.market_universe.concurrency import map_isolated

    def _fn(item: int) -> int:
        if item == 2:
            raise RuntimeError("boom")
        return item * 10

    rows = map_isolated([1, 2, 3], _fn, max_workers=2)
    states = {r["state"] for r in rows}
    assert "ERROR" in states
    assert "OK" in states
    assert len(rows) == 3


def test_scorecard_never_auto_live() -> None:
    from app.domain.market_universe.readiness import instrument_scorecard

    card = instrument_scorecard(
        {"data_quality": {"state": "LIVE"}, "canonical_symbol": "EURUSD"},
        scored={"opportunity_score": 88, "directional_edge": 12},
        shadow_n=80,
    )
    assert card["PROMOTION_STATUS"] != "LIVE_ELIGIBLE"
    assert card["authorizes_trade"] is False
    assert card["ALLOW_LIVE_PROMOTION"] is False
    assert card["LIVE_ELIGIBLE"] is False
    assert card["CAPABILITY_STATE"] != "LIVE_ELIGIBLE"
    assert card["CAPABILITY_LIVE_DISABLED"] is True


def test_research_router_requires_auth() -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.presentation.middleware.error_handler import register_exception_handlers
    from app.presentation.routers.market_universe import router

    application = FastAPI()
    register_exception_handlers(application)
    application.include_router(router, prefix="/api/v1")
    client = TestClient(application)
    for path in (
        "/api/v1/market-universe/snapshot",
        "/api/v1/market-universe/opportunities",
        "/api/v1/market-universe/shadow",
        "/api/v1/market-universe/performance",
        "/api/v1/market-universe/instrument/EURUSD",
        "/api/v1/market-universe/by-class",
        "/api/v1/market-universe/by-session",
        "/api/v1/market-universe/by-regime",
        "/api/v1/market-universe/correlation",
        "/api/v1/market-universe/health",
    ):
        response = client.get(path)
        assert response.status_code in {401, 403}
    post = client.post("/api/v1/market-universe/refresh")
    assert post.status_code in {401, 403}


def test_no_data_is_not_ranked_as_opportunity() -> None:
    board = build_opportunity_board(
        [
            {
                "symbol": "EURUSD_I",
                "data_state": "NO_DATA",
                "opportunity_score": 90,
            },
            {
                "symbol": "GBPUSD",
                "data_state": "LIVE",
                "opportunity_score": 74,
                "directional_edge": 8,
                "direction": "SELL",
            },
        ]
    )
    assert board["ranks_live_data_only"] is True
    assert board["top_opportunities"][0]["canonical_symbol"] == "GBPUSD"
    assert board["authorizes_trade"] is False


def test_promotion_gate_never_reaches_live() -> None:
    from app.domain.market_universe.promotion import promotion_gate

    gate = promotion_gate(
        research_status="QUALIFIED",
        human_authorized=True,
        risk_reviewed=True,
        safety_reviewed=True,
        oos_positive=True,
        n=80,
    )
    assert gate["LIVE_ELIGIBLE"] is False
    assert gate["DISCOVERY_TO_OMS"] is False
    assert gate["SHADOW_TO_OMS"] is False
    assert gate["RESEARCH_TO_LIVE"] is False
    assert gate["authorizes_trade"] is False


def test_portfolio_observation_does_not_bypass_risk() -> None:
    from app.domain.market_universe.correlation_research import (
        analyze_portfolio_exposure,
    )

    result = analyze_portfolio_exposure(
        ["EURUSD", "GBPUSD", "AUDUSD"],
        directions=["BUY", "BUY", "BUY"],
        open_positions=[{"symbol": "XAUUSD_i"}],
    )
    assert result["bypasses_risk"] is False
    assert result["live_risk_unchanged"] is True
    assert "DIRECTIONAL_CONCENTRATION" in result["flags"]
    assert result["open_positions"] == 1


def test_score_injected_snapshots_isolates_failures_and_skips_oms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.application.services.research_universe_scanner import (
        score_injected_snapshots,
    )

    class _Verdict:
        def to_dict(self) -> dict[str, object]:
            return {
                "opportunity_score": 80,
                "directional_edge": 8,
                "direction": "BUY",
                "symbol": "EURUSD",
            }

    def _fake_score(*_args: object, **_kwargs: object) -> _Verdict:
        return _Verdict()

    monkeypatch.setattr(
        "app.domain.institutional_trading.ai_scalping.scoring.score_scalping_setup",
        _fake_score,
    )
    out = score_injected_snapshots(
        [
            {"symbol": "EURUSD", "snapshot": object()},
            {"symbol": "BAD"},
        ]
    )
    assert out["forwarded_to_oms"] is False
    assert out["would_submit_order"] is False
    assert out["n"] >= 1
    assert out["errors"]


def test_mock_adapter_is_never_live_broker() -> None:
    from app.domain.market_universe.broker_catalogue import discover_live_catalogue
    from app.domain.market_universe.constants import (
        CATALOGUE_LIVE_BROKER,
        CATALOGUE_UNAVAILABLE,
    )
    from app.infrastructure.brokers.mt5.adapter import MT5Adapter
    from app.infrastructure.brokers.mt5.client import MockMT5Client

    result = discover_live_catalogue(
        MT5Adapter(client=MockMT5Client(), execution_enabled=False)
    )
    assert result["catalogue_source"] == CATALOGUE_UNAVAILABLE
    assert result["catalogue_source"] != CATALOGUE_LIVE_BROKER
    assert result["invented"] is False
    assert result["rows"] == ()
    assert result["populates_production_universe"] is False
    assert result["error"] == "mock_mt5_client_not_live_broker"
    assert result["adapter_kind"] == "MOCK"


def test_unavailable_catalogue_counts_are_not_broker_zeros() -> None:
    from app.application.services.market_universe_service import build_snapshot
    from app.domain.market_universe.constants import CATALOGUE_UNAVAILABLE
    from app.domain.market_universe.report import build_market_universe_report

    snap = build_snapshot()
    assert snap["catalogue_source"] == CATALOGUE_UNAVAILABLE
    assert snap["global_market_status"]["FOREX"] == CATALOGUE_UNAVAILABLE
    assert snap["global_market_status"]["CRYPTO"] == CATALOGUE_UNAVAILABLE
    report = build_market_universe_report(catalogue_source=CATALOGUE_UNAVAILABLE)
    assert report["2_FOREX_COUNT"] == CATALOGUE_UNAVAILABLE
    assert report["1_MARKET_UNIVERSE_COUNT"] == CATALOGUE_UNAVAILABLE
    assert report["28_DATA_QUALITY"]["broker_symbols_found"] == CATALOGUE_UNAVAILABLE


def test_research_opportunity_tiers_are_display_only() -> None:
    from app.domain.market_universe.opportunity_tiers import research_opportunity_tier

    assert research_opportunity_tier(92) == "EXTREME"
    assert research_opportunity_tier(81) == "VERY_HIGH"
    assert research_opportunity_tier(70) == "HIGH"
    assert research_opportunity_tier(65) == "MODERATE"
    assert research_opportunity_tier(40) == "LOW"
    assert research_opportunity_tier(None) == UNKNOWN
    assert research_opportunity_tier(UNKNOWN) == UNKNOWN
    board = build_opportunity_board(
        [
            {
                "symbol": "EURUSD",
                "data_state": "LIVE",
                "opportunity_score": 81,
                "directional_edge": 6,
                "direction": "SELL",
            }
        ]
    )
    row = board["top_opportunities"][0]
    assert row["opportunity_tier"] == "VERY_HIGH"
    assert row["opportunity_tier_is_display_only"] is True
    assert row["frozen_opportunity_threshold"] == 70
    assert row["authorizes_trade"] is False
    assert row["LIVE_ELIGIBLE"] is False
    assert row["capability_state"] != "LIVE_ELIGIBLE"


def test_research_rank_omits_missing_and_excludes_stale() -> None:
    from app.domain.market_universe.ranking import compute_research_rank

    missing = compute_research_rank({"data_state": "LIVE"})
    assert missing["rankable"] is False
    assert missing["research_rank_score"] == UNKNOWN
    measured = compute_research_rank(
        {
            "data_state": "LIVE",
            "opportunity_score": 74,
            "directional_edge": 8,
            "RR": 1.2,
        }
    )
    assert measured["rankable"] is True
    assert measured["research_rank_components"]["quality"] == 74
    assert measured["research_rank_components"]["directional_edge"] == 8
    stale = build_opportunity_board(
        [
            {
                "symbol": "BTCUSD",
                "data_state": "STALE",
                "opportunity_score": 99,
                "directional_edge": 20,
                "direction": "BUY",
            },
            {
                "symbol": "EURUSD",
                "data_state": "LIVE",
                "opportunity_score": 71,
                "directional_edge": 5,
                "direction": "SELL",
            },
        ]
    )
    assert stale["top_opportunities"][0]["canonical_symbol"] == "EURUSD"


def test_expansion_architecture_cannot_reach_oms() -> None:
    from app.domain.market_universe.expansion_architecture import (
        describe_layers,
        symbol_may_reach_oms,
    )

    layers = describe_layers()
    assert layers["ALLOW_LIVE_PROMOTION"] is False
    assert layers["layers_merged"] is False
    assert layers["EXPANSION"]["may_reach_oms"] is False
    assert layers["RESEARCH"]["may_call_oms"] is False
    assert symbol_may_reach_oms("EURUSD") is False
    assert layers["CORE"]["broker_symbol"] == "XAUUSD_i"


def test_promotion_sample_gate_never_live() -> None:
    from app.domain.market_universe.promotion import research_sample_gate

    early = research_sample_gate(20)
    assert early["status"] == "EARLY_QUALIFICATION"
    assert early["LIVE_ELIGIBLE"] is False
    strong = research_sample_gate(100)
    assert strong["status"] == "STRONGER_EVIDENCE"
    assert strong["automatic_promotion"] is False
    tiny = research_sample_gate(0)
    assert tiny["status"] == "INSUFFICIENT_SAMPLE"


def test_regime_normalize_does_not_invent() -> None:
    from app.domain.market_universe.regime_research import normalize_research_regime

    assert normalize_research_regime("trending") == "TREND"
    assert normalize_research_regime(None) == UNKNOWN
    assert normalize_research_regime("") == UNKNOWN


def test_failure_isolation_does_not_stop_other_symbols() -> None:
    from app.domain.market_universe.concurrency import map_isolated

    def _fn(symbol: str) -> str:
        if symbol == "BTCUSD":
            raise RuntimeError("broken")
        return symbol

    out = map_isolated(["EURUSD", "BTCUSD", "XAUUSD"], _fn, max_workers=1)
    states = {str(r["item"]): r["state"] for r in out}
    assert states["BTCUSD"] == "ERROR"
    assert states["EURUSD"] == "OK"
    assert states["XAUUSD"] == "OK"


def test_classification_precedence_manual_then_broker_then_rule() -> None:
    manual = classify_instrument(
        "EURUSD",
        broker_row={"path": "Forex\\Majors"},
        manual_overrides={"EURUSD": ("OTHER", "documented")},
    )
    assert manual.classification_source == "MANUAL_OVERRIDE"
    broker = classify_instrument("ZZZUSD", broker_row={"path": "Crypto\\ZZZ"})
    assert broker.classification_source == "BROKER_METADATA"
    rule = classify_instrument("XAUUSD_i")
    assert rule.classification_source == "SYMBOL_RULE"
    assert rule.asset_class == "METALS"


class _CatalogueClient:
    def symbols(self) -> list[dict[str, object]]:
        return [
            {
                "code": "EURUSD_I",
                "path": "Forex\\Majors",
                "trade_mode": 4,
                "digits": 5,
            },
            {
                "code": "BTCUSD",
                "path": "Crypto\\BTC",
                "trade_mode": 4,
                "digits": 2,
            },
        ]


class _RuntimeAdapter:
    client = _CatalogueClient()
    execution_enabled = False

    def symbols(self) -> list[dict[str, object]]:
        return self.client.symbols()


def test_runtime_adapter_catalogue_is_live_broker_not_mock() -> None:
    from app.domain.market_universe.broker_catalogue import discover_live_catalogue
    from app.domain.market_universe.constants import CATALOGUE_LIVE_BROKER

    result = discover_live_catalogue(_RuntimeAdapter())
    assert result["catalogue_source"] == CATALOGUE_LIVE_BROKER
    assert result["invented"] is False
    assert result["count"] == 2
    codes = {r["code"] for r in result["rows"]}
    assert "EURUSD_I" in codes
    assert "BTCUSD" in codes


def test_unavailable_cache_does_not_pin_when_adapter_arrives() -> None:
    from app.application.services.market_universe_service import (
        MarketUniverseService,
        reset_market_universe_cache_for_tests,
    )
    from app.domain.market_universe.constants import (
        CATALOGUE_LIVE_BROKER,
        CATALOGUE_UNAVAILABLE,
    )

    reset_market_universe_cache_for_tests()
    svc = MarketUniverseService()
    first = svc.snapshot()
    assert first["catalogue_source"] == CATALOGUE_UNAVAILABLE
    second = svc.snapshot(mt5_adapter=_RuntimeAdapter())
    assert second["catalogue_source"] == CATALOGUE_LIVE_BROKER
    assert second["global_market_status"]["FOREX"] != CATALOGUE_UNAVAILABLE
    reset_market_universe_cache_for_tests()


def test_research_signal_is_not_live_order() -> None:
    from app.domain.market_universe.research_signals import build_research_signals

    out = build_research_signals(
        [
            {
                "symbol": "EURUSD",
                "broker_symbol": "EURUSD_I",
                "canonical_symbol": "EURUSD",
                "asset_class": "FOREX",
                "direction": "SELL",
                "opportunity_score": 74,
                "directional_edge": 6,
                "setup_state": "WAIT",
            }
        ]
    )
    assert out["kind"] == "RESEARCH_SIGNAL"
    assert out["not"] == "LIVE_ORDER"
    assert out["would_submit_order"] is False
    assert out["forwarded_to_oms"] is False
    assert out["n"] == 1
    signal = out["signals"][0]
    assert signal["signal_id"].startswith("RS-")
    assert len(signal["decision_hash"]) == 16
    again = build_research_signals(
        [
            {
                "symbol": "EURUSD",
                "broker_symbol": "EURUSD_I",
                "canonical_symbol": "EURUSD",
                "asset_class": "FOREX",
                "direction": "SELL",
                "opportunity_score": 74,
                "directional_edge": 6,
                "setup_state": "WAIT",
                "features_as_of": "T0",
            }
        ]
    )
    same = build_research_signals(
        [
            {
                "symbol": "EURUSD",
                "broker_symbol": "EURUSD_I",
                "canonical_symbol": "EURUSD",
                "asset_class": "FOREX",
                "direction": "SELL",
                "opportunity_score": 74,
                "directional_edge": 6,
                "setup_state": "WAIT",
                "features_as_of": "T0",
            }
        ]
    )
    assert again["signals"][0]["decision_hash"] == same["signals"][0]["decision_hash"]
    missing = build_research_signals([{"symbol": "GBPUSD", "direction": "BUY"}])
    assert missing["n"] == 0


def test_position_candidate_requires_known_levels_and_blocks_submit() -> None:
    from app.domain.market_universe.position_candidates import build_position_candidates

    incomplete = build_position_candidates(
        [{"symbol": "EURUSD", "direction": "BUY", "opportunity_score": 80}]
    )
    assert incomplete["n"] == 0
    assert incomplete["would_submit_order"] is False
    complete = build_position_candidates(
        [
            {
                "symbol": "EURUSD",
                "direction": "BUY",
                "entry": 1.1,
                "sl": 1.09,
                "tp": 1.12,
            }
        ]
    )
    assert complete["n"] == 1
    assert complete["candidates"][0]["mt5_ticket"] is None
    assert complete["would_submit_order"] is False


def test_observations_are_not_strategy_matched() -> None:
    from app.domain.market_universe.observations import (
        list_observations,
        record_observations,
        reset_observations_for_tests,
    )

    reset_observations_for_tests()
    record_observations(
        [
            {
                "symbol": "EURUSD",
                "canonical_symbol": "EURUSD",
                "opportunity_score": 71,
                "direction": "SELL",
            }
        ]
    )
    payload = list_observations()
    assert payload["counted_as_fills"] is False
    assert payload["counted_as_strategy_matched"] is False
    assert payload["hypothetical_pnl"] is False
    assert payload["n"] == 1
    reset_observations_for_tests()


def test_registry_discovery_is_not_capped_by_probe_limit() -> None:
    from app.domain.market_universe.constants import MAX_HISTORY_PROBE_SYMBOLS

    rows = [
        {"code": f"T{i:03d}USD", "path": "Forex\\Majors", "trade_mode": 4}
        for i in range(40)
    ]
    registry = build_registry(rows)
    universe = int(registry["counts"]["universe"])
    assert universe >= 40
    assert universe > MAX_HISTORY_PROBE_SYMBOLS
    assert len(registry["instruments"]) >= 40


def test_live_execution_enabled_only_for_gold_desk() -> None:
    registry = build_registry(_rows())
    by_desk = {str(i["canonical_symbol"]): i for i in registry["instruments"]}
    gold = by_desk.get("XAUUSD") or {}
    forex = by_desk.get("EURUSD") or {}
    crypto = by_desk.get("BTCUSD") or {}
    assert gold.get("live_execution_enabled") is True
    assert gold.get("live_execution_eligible") is False
    assert gold.get("authorizes_trade") is False
    assert forex.get("live_execution_enabled") is False
    assert crypto.get("live_execution_enabled") is False


def test_capability_state_never_returns_live_eligible() -> None:
    from app.domain.market_universe.promotion import capability_state

    for status in (
        "DISCOVERED",
        "DATA_READY",
        "ANALYZED",
        "QUALIFIED",
        "SHADOW",
        "MEANINGFUL_RESEARCH",
        "PROMOTION_CANDIDATE",
        "LIVE_ELIGIBLE",
        "UNKNOWN",
    ):
        assert capability_state(status) != "LIVE_ELIGIBLE"


def test_opportunity_board_data_status_filter() -> None:
    board = build_opportunity_board(
        [
            {
                "symbol": "EURUSD",
                "data_state": "LIVE",
                "opportunity_score": 74,
                "directional_edge": 6,
                "direction": "SELL",
            },
            {
                "symbol": "GBPUSD",
                "data_state": "STALE",
                "opportunity_score": 80,
                "directional_edge": 8,
                "direction": "BUY",
            },
        ],
        filters={"data_status": "LIVE"},
    )
    symbols = {str(r.get("canonical_symbol") or r.get("symbol")) for r in board["rows"]}
    assert "EURUSD" in symbols
    assert "GBPUSD" not in symbols


def test_mock_catalogue_counts_are_not_numeric_zeros() -> None:
    from app.application.services.market_universe_service import build_snapshot
    from app.domain.market_universe.constants import (
        CATALOGUE_LIVE_BROKER,
        CATALOGUE_UNAVAILABLE,
    )
    from app.infrastructure.brokers.mt5.adapter import MT5Adapter
    from app.infrastructure.brokers.mt5.client import MockMT5Client

    snap = build_snapshot(
        mt5_adapter=MT5Adapter(client=MockMT5Client(), execution_enabled=False)
    )
    assert snap["catalogue_source"] == CATALOGUE_UNAVAILABLE
    assert snap["catalogue_source"] != CATALOGUE_LIVE_BROKER
    assert snap["global_market_status"]["FOREX"] == CATALOGUE_UNAVAILABLE
    assert snap["global_market_status"]["FOREX"] != 0
    assert snap["research_signals"]["n"] == CATALOGUE_UNAVAILABLE
    assert snap["observability"]["second_gateway"] is False
    assert snap["observability"]["discovery_uncapped"] is True
    assert snap["invented"] is False


def test_di_unavailable_does_not_construct_second_gateway(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.application.services.market_universe_service import (
        build_snapshot,
        reset_runtime_adapter_fallback_for_tests,
        resolve_runtime_mt5_adapter,
    )
    from app.domain.market_universe.constants import (
        CATALOGUE_LIVE_BROKER,
        CATALOGUE_UNAVAILABLE,
    )

    reset_runtime_adapter_fallback_for_tests()

    class _Empty:
        app_env = "development"
        mt5_gateway_base_url = ""
        mt5_gateway_caller_token = ""
        mt5_connect_timeout_seconds = 5.0

    monkeypatch.setattr(
        "core.di.container.get_container",
        lambda: (_ for _ in ()).throw(RuntimeError("no di")),
    )
    monkeypatch.setattr("core.config.settings.get_settings", lambda: _Empty())
    adapter, diag = resolve_runtime_mt5_adapter()
    assert adapter is None
    assert diag["error"] == "di_unavailable"
    assert diag["reason"] == "gateway_credentials_unavailable"
    assert diag["second_gateway_created"] is False
    assert diag["token_exposed"] is False
    snap = build_snapshot(mt5_adapter=adapter, adapter_resolution=diag)
    assert snap["catalogue_source"] == CATALOGUE_UNAVAILABLE
    assert snap["catalogue_source"] != CATALOGUE_LIVE_BROKER
    assert snap["invented"] is False
    assert snap["reason"] == "gateway_credentials_unavailable"
    assert snap["global_market_status"]["FOREX"] == CATALOGUE_UNAVAILABLE


def test_credentials_without_di_do_not_construct_second_gateway(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.application.services.market_universe_service import (
        build_snapshot,
        reset_runtime_adapter_fallback_for_tests,
        resolve_runtime_mt5_adapter,
    )
    from app.domain.market_universe.constants import (
        CATALOGUE_LIVE_BROKER,
        CATALOGUE_UNAVAILABLE,
    )

    reset_runtime_adapter_fallback_for_tests()
    constructed = {"n": 0}

    class _LiveSettings:
        app_env = "development"
        mt5_gateway_base_url = "https://gateway.example"
        mt5_gateway_caller_token = "caller-token"
        mt5_connect_timeout_seconds = 5.0

    class _ForbiddenGateway:
        def __init__(self, **_kwargs: object) -> None:
            constructed["n"] += 1
            raise AssertionError("must not construct a second GatewayMT5Client")

    monkeypatch.setattr(
        "core.di.container.get_container",
        lambda: (_ for _ in ()).throw(RuntimeError("no di")),
    )
    monkeypatch.setattr("core.config.settings.get_settings", lambda: _LiveSettings())
    monkeypatch.setattr(
        "app.infrastructure.brokers.mt5.gateway_client.GatewayMT5Client",
        _ForbiddenGateway,
    )
    adapter, diag = resolve_runtime_mt5_adapter()
    assert adapter is None
    assert constructed["n"] == 0
    assert diag["error"] == "di_unavailable"
    assert diag["reason"] == "di_not_initialised"
    assert diag["second_gateway_created"] is False
    assert diag["gateway_url_configured"] is True
    assert diag["gateway_token_configured"] is True
    assert diag["token_exposed"] is False
    snap = build_snapshot(mt5_adapter=adapter, adapter_resolution=diag)
    assert snap["catalogue_source"] == CATALOGUE_UNAVAILABLE
    assert snap["catalogue_source"] != CATALOGUE_LIVE_BROKER
    assert snap["invented"] is False
    assert snap["reason"] == "di_not_initialised"
    reset_runtime_adapter_fallback_for_tests()


def test_di_gateway_adapter_is_live_broker_not_mock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.application.services.market_universe_service import (
        build_snapshot,
        resolve_runtime_mt5_adapter,
    )
    from app.domain.market_universe.constants import CATALOGUE_LIVE_BROKER
    from app.infrastructure.brokers.mt5.client import MockMT5Client

    class _Container:
        mt5_adapter = _RuntimeAdapter()

    monkeypatch.setattr("core.di.container.get_container", lambda: _Container())
    adapter, diag = resolve_runtime_mt5_adapter()
    assert adapter is _Container.mt5_adapter
    assert diag["di_initialised"] is True
    assert diag["second_gateway_created"] is False
    assert diag["execution_enabled"] is False
    assert not isinstance(getattr(adapter, "client", None), MockMT5Client)
    snap = build_snapshot(mt5_adapter=adapter, adapter_resolution=diag)
    assert snap["catalogue_source"] == CATALOGUE_LIVE_BROKER
    assert snap["reason"] is None
    assert snap["global_market_status"]["FOREX"] != 0
    assert snap["would_submit_order"] is False
    assert snap["invented"] is False


def test_di_mock_adapter_is_unavailable_not_live_broker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.application.services.market_universe_service import (
        build_snapshot,
        resolve_runtime_mt5_adapter,
    )
    from app.domain.market_universe.constants import (
        CATALOGUE_LIVE_BROKER,
        CATALOGUE_UNAVAILABLE,
    )
    from app.infrastructure.brokers.mt5.adapter import MT5Adapter
    from app.infrastructure.brokers.mt5.client import MockMT5Client

    class _Container:
        mt5_adapter = MT5Adapter(client=MockMT5Client(), execution_enabled=False)

    monkeypatch.setattr("core.di.container.get_container", lambda: _Container())
    adapter, diag = resolve_runtime_mt5_adapter()
    assert adapter is None
    assert diag["is_mock"] is True
    assert diag["error"] == "mock_mt5_client_not_live_broker"
    assert diag["second_gateway_created"] is False
    snap = build_snapshot(mt5_adapter=adapter, adapter_resolution=diag)
    assert snap["catalogue_source"] == CATALOGUE_UNAVAILABLE
    assert snap["catalogue_source"] != CATALOGUE_LIVE_BROKER
    assert snap["invented"] is False
    assert snap["global_market_status"]["FOREX"] != 0


def test_disconnected_gateway_catalogue_is_unavailable_not_zero() -> None:
    from app.application.services.market_universe_service import build_snapshot
    from app.domain.market_universe.broker_catalogue import discover_live_catalogue
    from app.domain.market_universe.constants import (
        CATALOGUE_LIVE_BROKER,
        CATALOGUE_UNAVAILABLE,
    )

    class _Disconnected:
        execution_enabled = False
        client = type("GatewayMT5Client", (), {})()

        def symbols(self) -> list[object]:
            raise RuntimeError("MT5 gateway session not connected")

    result = discover_live_catalogue(_Disconnected())
    assert result["catalogue_source"] == CATALOGUE_UNAVAILABLE
    assert result["catalogue_source"] != CATALOGUE_LIVE_BROKER
    snap = build_snapshot(mt5_adapter=_Disconnected())
    assert snap["catalogue_source"] == CATALOGUE_UNAVAILABLE
    assert snap["global_market_status"]["FOREX"] == CATALOGUE_UNAVAILABLE
    assert snap["global_market_status"]["FOREX"] != 0


def test_global_opportunity_unavailable_when_catalogue_unavailable() -> None:
    from app.application.services.market_universe_service import build_snapshot
    from app.domain.market_universe.constants import CATALOGUE_UNAVAILABLE

    snap = build_snapshot()
    opp = snap["global_opportunity"]
    assert opp["value"] == CATALOGUE_UNAVAILABLE
    assert opp["status"] == CATALOGUE_UNAVAILABLE
    assert opp["authorizes_trade"] is False
    assert opp["fabricated"] is False
    assert snap["NEWS_CONTEXT"] == UNKNOWN


def test_shadow_virtual_requires_levels_and_rejects_same_bar() -> None:
    from app.domain.market_universe.position_candidates import build_position_candidates
    from app.domain.market_universe.shadow_virtual import (
        apply_future_bar,
        record_from_candidates,
        reset_shadow_virtual_for_tests,
    )

    reset_shadow_virtual_for_tests()
    incomplete = build_position_candidates(
        [{"symbol": "EURUSD", "direction": "BUY", "opportunity_score": 80}]
    )
    recorded = record_from_candidates(incomplete)
    assert recorded["n"] == 0
    complete = build_position_candidates(
        [
            {
                "symbol": "EURUSD",
                "direction": "BUY",
                "entry": 1.1,
                "sl": 1.09,
                "tp": 1.12,
            }
        ]
    )
    recorded = record_from_candidates(complete)
    assert recorded["n"] == 1
    assert recorded["trades"][0]["kind"] == "SHADOW_VIRTUAL_TRADE"
    assert recorded["trades"][0]["ledger"] == "RESEARCH_SHADOW_ONLY"
    assert recorded["would_submit_order"] is False
    trade_id = recorded["trades"][0]["trade_id"]
    same = apply_future_bar(
        trade_id=trade_id,
        bar_timestamp=recorded["trades"][0]["virtual_entry_timestamp"],
        high=1.13,
        low=1.08,
    )
    assert same["status"] == "SAME_BAR_OR_EARLIER_REJECTED"
    later = apply_future_bar(
        trade_id=trade_id,
        bar_timestamp="2099-01-01T00:00:00+00:00",
        high=1.13,
        low=1.08,
    )
    assert later["exit_reason"] == "SL"
    assert later["would_submit_order"] is False
    reset_shadow_virtual_for_tests()


def test_refresh_does_not_expand_live_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.application.services.market_universe_service import (
        MarketUniverseService,
        reset_market_universe_cache_for_tests,
    )
    from app.domain.market_universe.constants import CATALOGUE_LIVE_BROKER
    from app.domain.trading.gold_only import (
        autonomous_execution_symbols,
        is_gold_symbol,
    )

    monkeypatch.setattr(
        "app.domain.trading.gold_only.gold_only_enabled",
        lambda: True,
    )
    reset_market_universe_cache_for_tests()
    before = autonomous_execution_symbols()
    snap = MarketUniverseService().refresh(mt5_adapter=_RuntimeAdapter())
    after = autonomous_execution_symbols()
    assert before == after
    assert after
    assert all(is_gold_symbol(s) for s in after)
    assert snap["catalogue_source"] == CATALOGUE_LIVE_BROKER
    assert snap["research_universe_is_not_execution_universe"] is True
    assert snap["would_submit_order"] is False
    assert snap["observability"]["second_gateway"] is False
    assert snap["observability"]["second_scanner"] is False
    assert snap["layers"]["CORE"]["broker_symbol"] == "XAUUSD_i"
    reset_market_universe_cache_for_tests()


def test_market_universe_router_registered_in_bootstrap() -> None:
    from app.main import _ROUTER_SPECS
    from app.presentation.routers import market_universe as mu

    names = [name for name, _path in _ROUTER_SPECS]
    assert "market_universe" in names
    spec = dict(_ROUTER_SPECS)
    assert spec["market_universe"] == "app.presentation.routers.market_universe"
    assert mu.router.prefix == "/market-universe"
    paths = {getattr(route, "path", "") for route in mu.router.routes}
    for required in (
        "/snapshot",
        "/opportunities",
        "/shadow",
        "/performance",
        "/by-class",
        "/by-session",
        "/by-regime",
        "/correlation",
        "/health",
        "/refresh",
        "/instrument/{symbol}",
    ):
        assert any(required in path for path in paths)
