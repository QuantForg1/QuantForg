"""Strategy forensic ledger, matched-only stats, shadow isolation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.application.services.shadow_expansion_engine import (
    ALLOW_LIVE_PROMOTION,
    CANDIDATE_SPECS,
    PROMOTION_STATES,
    SHADOW_MAY_ALTER_LIVE_DECISIONS,
    SHADOW_MAY_BYPASS_OMS,
    SHADOW_MAY_BYPASS_RISK,
    SHADOW_MAY_BYPASS_SAFETY,
    SHADOW_MAY_SUBMIT_ORDERS,
    ShadowExpansionBlocked,
    alter_live_decision,
    apply_human_promotion,
    bypass_oms,
    bypass_risk,
    bypass_safety,
    detect_lookahead_fields,
    expansion_report,
    features_as_of,
    observe_shadow_cycle,
    promotion_status,
    submit_order,
    walk_forward_split,
)
from app.application.services.strategy_forensic_ledger import (
    STRATEGY_MATCHED,
    UNMATCHED,
    classify_closed_deal,
    compact_signal_row,
    list_submissions,
    persist_close,
    persist_signal,
    persist_submission,
    reset_forensic_ledger_for_tests,
)
from app.application.services.strategy_loss_forensics import (
    CANONICAL_REGIMES,
    CANONICAL_SESSIONS,
    EARLY_SIGNAL,
    HIGHER_CONFIDENCE,
    INSUFFICIENT_SAMPLE,
    LIKELY,
    LOSS_DIMENSIONS,
    MEANINGFUL_RESEARCH,
    POSSIBLE,
    PRELIMINARY,
    PROVEN,
    REJECTED,
    STRONGER_EVIDENCE,
    UNKNOWN,
    build_loss_forensics,
    cause_strength,
    classify_exit_path,
    classify_loss_contributors,
    hypothesis_report,
    sample_status,
)
from app.application.services.strategy_research_forensics import (
    build_strategy_research_forensics,
    classify_conflict_paint,
    frequency_bottleneck,
)
from app.application.services.strategy_settings_audit import (
    audit_news_protection,
    build_strategy_settings_audit,
)
from app.application.services.vps_continuity_classifier import (
    classify_gateway_listeners,
    classify_vps_continuity,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

SHADOW_SRC = (
    Path(__file__).resolve().parents[2]
    / "app"
    / "application"
    / "services"
    / "shadow_expansion_engine.py"
).read_text(encoding="utf-8")


def _cycle(**kwargs):
    row = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "symbol": "XAUUSD_i",
        "signal_id": "sig-wait",
        "decision_hash": None,
        "request_id": "req-wait",
        "buy_score": 42,
        "sell_score": 34,
        "ltf_buy_score": 28,
        "ltf_sell_score": 24,
        "directional_edge": 4,
        "opportunity_score": 64,
        "setup_state": "CONFLICT",
        "first_authoritative_blocker": "WAIT_NO_DIRECTIONAL_EDGE",
        "blocker_source": "DIRECTION",
        "forwarded_to_oms": False,
        "buy_families": ["structure", "zone"],
        "sell_families": ["structure"],
        "market_session": "london",
        "decision_action": "WAIT",
    }
    row.update(kwargs)
    return row


def test_sample_status_thresholds() -> None:
    assert sample_status(0) == INSUFFICIENT_SAMPLE
    assert sample_status(1) == EARLY_SIGNAL
    assert sample_status(9) == EARLY_SIGNAL
    assert sample_status(10) == PRELIMINARY
    assert sample_status(19) == PRELIMINARY
    assert sample_status(20) == MEANINGFUL_RESEARCH
    assert sample_status(49) == MEANINGFUL_RESEARCH
    assert sample_status(50) == STRONGER_EVIDENCE
    assert sample_status(99) == STRONGER_EVIDENCE
    assert sample_status(100) == HIGHER_CONFIDENCE


def test_unmatched_deal_without_ticket_identity(tmp_path) -> None:
    reset_forensic_ledger_for_tests(tmp_path)
    persist_signal(_cycle())
    join = classify_closed_deal(
        {"entry_ticket": 999001, "profit_loss": -12.0, "side": "buy"}
    )
    assert join["classification"] == UNMATCHED
    stats = build_loss_forensics(
        closed_trades=[{"entry_ticket": 999001, "profit_loss": -12.0, "side": "buy"}]
    )
    assert stats["matched_count"] == 0
    assert stats["unmatched_count"] == 1
    assert stats["unmatched_preview"][0]["excluded_from_strategy_statistics"] is True
    assert stats["overall"]["WIN_RATE"] == UNKNOWN
    assert stats["first_proven_loss_cause"] == INSUFFICIENT_SAMPLE
    assert stats["trading_change_justified"] is False


def test_matched_join_requires_ticket_and_identity(tmp_path) -> None:
    reset_forensic_ledger_for_tests(tmp_path)
    persist_signal(
        _cycle(
            signal_id="sig-live-1",
            decision_hash="hash-live-1",
            request_id="req-live-1",
            forwarded_to_oms=True,
            mt5_ticket=555123,
            decision_action="BUY",
            directional_edge=8,
            opportunity_score=76,
            setup_state="TAKE",
        )
    )
    unmatched = classify_closed_deal({"entry_ticket": 1, "profit_loss": 5.0})
    matched = classify_closed_deal(
        {
            "entry_ticket": 555123,
            "profit_loss": 18.0,
            "side": "buy",
            "entry_time": "2026-08-28T10:00:00+00:00",
            "exit_time": "2026-08-28T10:12:00+00:00",
        }
    )
    assert unmatched["classification"] == UNMATCHED
    assert matched["classification"] == STRATEGY_MATCHED
    assert matched["signal_id"] == "sig-live-1"
    assert matched["decision_hash"] == "hash-live-1"
    stats = build_loss_forensics(
        closed_trades=[
            {
                "entry_ticket": 555123,
                "profit_loss": 18.0,
                "side": "buy",
                "entry_time": "2026-08-28T10:00:00+00:00",
                "exit_time": "2026-08-28T10:12:00+00:00",
                "holding_time_sec": 720,
            }
        ]
    )
    assert stats["matched_count"] == 1
    assert stats["unmatched_count"] == 0
    assert stats["overall"]["status"] == EARLY_SIGNAL
    assert stats["overall"]["WIN_RATE"] == UNKNOWN
    assert "n=1" in str(stats["overall"]["WIN_RATE_DISPLAY"])


def test_time_window_join_is_not_used(tmp_path) -> None:
    reset_forensic_ledger_for_tests(tmp_path)
    persist_signal(
        _cycle(
            signal_id="sig-near",
            decision_hash="hash-near",
            request_id="req-near",
            forwarded_to_oms=True,
            mt5_ticket=777,
            recorded_at="2026-08-28T12:00:00+00:00",
        )
    )
    nearby = classify_closed_deal(
        {
            "entry_ticket": 888,
            "entry_time": "2026-08-28T12:00:05+00:00",
            "profit_loss": 9.0,
        }
    )
    assert nearby["classification"] == UNMATCHED


def test_hypotheses_insufficient_when_no_matched() -> None:
    report = hypothesis_report([])
    assert report["A_BUY_BIAS"]["verdict"] == INSUFFICIENT_SAMPLE
    assert report["Z_EXIT_LOGIC"]["verdict"] == INSUFFICIENT_SAMPLE
    assert report["A_BUY_BIAS"]["auto_changes_trading"] is False


def test_shadow_cannot_send_or_bypass() -> None:
    assert SHADOW_MAY_SUBMIT_ORDERS is False
    assert SHADOW_MAY_ALTER_LIVE_DECISIONS is False
    assert SHADOW_MAY_BYPASS_RISK is False
    assert SHADOW_MAY_BYPASS_SAFETY is False
    assert SHADOW_MAY_BYPASS_OMS is False
    for fn in (submit_order, alter_live_decision, bypass_risk, bypass_safety, bypass_oms):
        with pytest.raises(ShadowExpansionBlocked):
            fn()
    forbidden = ("order_send", "FORCE_FIRST_TRADE", "execute_now", "Execute Now")
    lower = SHADOW_SRC.lower()
    for token in forbidden:
        assert token.lower() not in lower
    assert "from app.domain.institutional_trading.execution.bridge" not in SHADOW_SRC
    assert "gateway_client" not in SHADOW_SRC
    assert "order_send" not in SHADOW_SRC.lower()


def test_shadow_observe_does_not_create_fill() -> None:
    live = observe_shadow_cycle(_cycle())
    assert live["would_submit_order"] is False
    assert live["not_a_fill"] is True
    assert live["not_a_ticket"] is True
    assert live["production_both_qualify"] is False
    assert live["inherits_opportunity_70"] is True
    assert live["inherits_edge_5"] is True
    assert "mtf_alignment" not in live["present_families"]
    assert "continuation" in live["present_families"]
    assert all(c["CORE"] is False and c["EXPANSION"] is True for c in live["candidates"])
    assert live["SHADOW_ONLY"] is True
    assert all(c["would_submit_order"] is False for c in live["candidates"])


def test_expansion_without_matched_is_insufficient() -> None:
    report = expansion_report(matched_trades=[], current_cycle=_cycle())
    assert report["never_sends_orders"] is True
    assert report["never_merges_core_and_expansion"] is True
    assert report["best_expansion_candidate"] == INSUFFICIENT_SAMPLE
    assert len(report["candidates"]) == len(CANDIDATE_SPECS)
    assert all(c["classification"] == INSUFFICIENT_SAMPLE for c in report["candidates"])
    assert all(c["can_send_orders"] is False for c in report["candidates"])
    assert all(c["auto_promote"] is False for c in report["candidates"])
    assert all(c["promotion_status"] == INSUFFICIENT_SAMPLE for c in report["candidates"])
    assert all(c["SHADOW_ONLY"] is True for c in report["candidates"])


def test_walk_forward_no_lookahead_and_insufficient_below_20() -> None:
    small = [{"exit_time": f"2026-01-0{i}T00:00:00+00:00"} for i in range(1, 6)]
    split = walk_forward_split(small)
    assert split["status"] == INSUFFICIENT_SAMPLE
    assert split["train"] == []
    assert split["lookahead"] is False

    rows = []
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    for i in range(25):
        rows.append(
            {
                "exit_time": (t0 + timedelta(days=i)).isoformat(),
                "entry_time": (t0 + timedelta(days=i, hours=-1)).isoformat(),
                "net_pnl": 1.0 if i % 2 == 0 else -0.5,
            }
        )
    ok = walk_forward_split(rows)
    assert ok["lookahead"] is False
    assert len(ok["train"]) + len(ok["validation"]) + len(ok["out_of_sample"]) == 25
    assert ok["train"][-1]["exit_time"] <= ok["out_of_sample"][0]["exit_time"]


def test_walk_forward_rejects_lookahead_leak() -> None:
    rows = []
    t0 = datetime(2026, 3, 1, tzinfo=UTC)
    for i in range(25):
        rows.append(
            {
                "exit_time": (t0 + timedelta(days=i)).isoformat(),
                "entry_time": (t0 + timedelta(days=i, hours=-2)).isoformat(),
                "net_pnl": 1.0,
            }
        )
    split = walk_forward_split(rows)
    assert split["lookahead"] is False
    assert split["train"][-1]["exit_time"] <= split["out_of_sample"][0]["exit_time"]

    corrupted = list(split["train"]) + list(split["out_of_sample"])
    # Invert two timestamps so a naive concat would leak if we did not sort.
    corrupted[0] = {
        **corrupted[0],
        "exit_time": "2026-12-31T00:00:00+00:00",
        "entry_time": "2026-12-30T00:00:00+00:00",
    }
    resorted = walk_forward_split(corrupted)
    assert resorted["lookahead"] is False
    assert resorted["train"][-1]["exit_time"] <= resorted["out_of_sample"][0]["exit_time"]


def test_mfe_mae_unknown_without_path(tmp_path) -> None:
    reset_forensic_ledger_for_tests(tmp_path)
    persist_signal(
        _cycle(
            signal_id="sig-mfe",
            decision_hash="hash-mfe",
            request_id="req-mfe",
            forwarded_to_oms=True,
            mt5_ticket=42,
        )
    )
    stats = build_loss_forensics(
        closed_trades=[
            {
                "entry_ticket": 42,
                "profit_loss": -3.0,
                "side": "sell",
            }
        ]
    )
    assert stats["overall"]["MFE"] == UNKNOWN
    assert stats["overall"]["MAE"] == UNKNOWN


def test_session_and_regime_attribution_status(tmp_path) -> None:
    reset_forensic_ledger_for_tests(tmp_path)
    persist_signal(
        _cycle(
            signal_id="sig-sess",
            decision_hash="hash-sess",
            request_id="req-sess",
            forwarded_to_oms=True,
            mt5_ticket=9,
            market_session="london",
        )
    )
    stats = build_loss_forensics(
        closed_trades=[
            {
                "entry_ticket": 9,
                "profit_loss": 2.0,
                "side": "buy",
                "market_session": "london",
                "market_regime": "range",
            }
        ]
    )
    sess = stats["SESSION_EXPECTANCY"]
    assert "london" in sess
    assert sess["london"]["status"] == EARLY_SIGNAL


def test_frequency_bottleneck_is_direction_on_live_tape() -> None:
    assert (
        frequency_bottleneck(
            {"directional_edge": 4, "opportunity_score": 64},
            {"rates_pct": {"both_qualify": 0}},
        )
        == "DIRECTION"
    )


def test_research_facade_empty_history_unknowns(tmp_path) -> None:
    reset_forensic_ledger_for_tests(tmp_path)
    payload = build_strategy_research_forensics(
        diagnostics={
            "latest": _cycle(),
        },
        deals=[],
        vps_facts={"gateway_listeners": 1, "gateway_process_running": True},
    )
    assert payload["never_sends_orders"] is True
    assert payload["live_order_sent"] is False
    assert payload["mt5_ticket"] is None
    assert payload["report"]["LIVE_ORDER_SENT"] == "NO"
    assert payload["report"]["MT5_TICKET"] == "NONE"
    assert payload["report"]["CODE_DEFECT_PROVEN"] is False
    assert payload["report"]["TRADING_CHANGE_JUSTIFIED"] is False
    assert payload["report"]["SAMPLE_SIZE"] == 0
    assert "INSUFFICIENT SAMPLE" in str(payload["report"]["WIN_RATE"])
    assert payload["sample_status"] == INSUFFICIENT_SAMPLE
    assert payload["research_workflow"]["current"] == "COLLECT"
    assert payload["research_workflow"]["max_automated_state"] == "PROMOTION_CANDIDATE"
    assert payload["production_sha"].startswith("2ca7793")
    assert payload["trade_frequency_bottleneck"] == "DIRECTION"
    assert payload["decision_matrix"]["code"] == "B"
    assert payload["decision_matrix"]["C_proven"] is False
    assert payload["decision_matrix"]["I_proven"] is False
    assert payload["conflict_paint"]["paint_is_first_blocker"] is False
    assert payload["current_shadow"]["NOT_EXECUTED"] is True
    assert payload["current_shadow"]["would_submit_order"] is False


def test_vps_duplicate_listener_and_unproven_recovery() -> None:
    assert classify_gateway_listeners(1) == "SINGLE_LISTENER"
    assert classify_gateway_listeners(2) == "DUPLICATE_LISTENERS"
    assert classify_gateway_listeners(0) == "NO_LISTENER"
    snap = classify_vps_continuity(
        {
            "gateway_listeners": 2,
            "gateway_process_running": True,
            "terminal_connected": True,
            "broker_connected": True,
            "autotrading_enabled": True,
            "market_data_fresh": True,
            "session_verified": True,
        }
    )
    assert snap["gateway_listener_class"] == "DUPLICATE_LISTENERS"
    assert snap["EXECUTION_PATH_READY"] == "NOT_READY"
    assert snap["mt5_reboot_recovery"] == "MT5_SESSION_RECOVERY_UNPROVEN"
    assert snap["never_reboots"] is True
    assert "UNPROVEN" in snap["vps_autonomy_status"] or snap["vps_autonomy_status"] != "AUTONOMOUS"


def test_buy_sell_symmetry_of_join_contract(tmp_path) -> None:
    reset_forensic_ledger_for_tests(tmp_path)
    persist_signal(
        _cycle(
            signal_id="sig-sell",
            decision_hash="hash-sell",
            request_id="req-sell",
            forwarded_to_oms=True,
            mt5_ticket=321,
            decision_action="SELL",
            candidate="SELL",
        )
    )
    persist_signal(
        _cycle(
            signal_id="sig-buy",
            decision_hash="hash-buy",
            request_id="req-buy",
            forwarded_to_oms=True,
            mt5_ticket=320,
            decision_action="BUY",
            candidate="BUY",
        )
    )
    sell = classify_closed_deal({"entry_ticket": 321, "profit_loss": -4.0, "side": "sell"})
    buy = classify_closed_deal({"entry_ticket": 320, "profit_loss": 4.0, "side": "buy"})
    assert sell["classification"] == buy["classification"] == STRATEGY_MATCHED


def test_lookahead_fields_are_stripped() -> None:
    dirty = _cycle(future_bos="BUY", next_candle_close=2400, realized_future_pnl=12)
    leaked = detect_lookahead_fields(dirty)
    assert "future_bos" in leaked
    assert "next_candle_close" in leaked
    clean = features_as_of(dirty)
    assert "future_bos" not in clean
    assert "next_candle_close" not in clean
    assert clean["opportunity_score"] == 64


def test_promotion_cannot_reach_live() -> None:
    assert promotion_status(sample_size=0, oos_positive=False, lookahead=False) == INSUFFICIENT_SAMPLE
    assert promotion_status(sample_size=25, oos_positive=False, lookahead=False) == "RESEARCH"
    with pytest.raises(ShadowExpansionBlocked):
        promotion_status(sample_size=120, oos_positive=True, lookahead=False, human_approved=True, promote_live=True)
    with pytest.raises(ShadowExpansionBlocked):
        apply_human_promotion("LIVE", approved_by="owner")
    assert apply_human_promotion("APPROVED", approved_by="owner") == "PROMOTION_CANDIDATE"
    assert promotion_status(sample_size=80, oos_positive=True, lookahead=False) == "PROMOTION_CANDIDATE"
    assert promotion_status(sample_size=80, oos_positive=True, lookahead=False) != "LIVE"


def test_loss_contributors_insufficient_without_matched() -> None:
    report = classify_loss_contributors([])
    assert report["proven_loss_cause"] == INSUFFICIENT_SAMPLE
    assert report["contributors"]["direction"]["verdict"] == INSUFFICIENT_SAMPLE
    assert report["contributors"]["exit"]["never_from_single_trade"] is True


def test_settings_audit_does_not_change_gates() -> None:
    audit = build_strategy_settings_audit()
    assert audit["never_changes_live_settings"] is True
    by_name = {r["SETTING"]: r for r in audit["settings"]}
    assert by_name["Opportunity threshold"]["LIVE_VALUE"] == 70
    assert by_name["Directional edge margin"]["LIVE_VALUE"] == 5
    assert by_name["Daily loss cap"]["LIVE_VALUE"] == "80.0"
    assert "80.0" in str(by_name["Daily loss cap"]["RECOMMENDED_FUTURE_ACTION"])


def test_research_payload_includes_disclaimer_and_audit(tmp_path) -> None:
    reset_forensic_ledger_for_tests(tmp_path)
    payload = build_strategy_research_forensics(
        diagnostics={"latest": _cycle()},
        deals=[],
        vps_facts={"gateway_listeners": 1},
    )
    assert "guarantee" in str(payload["disclaimer"]).lower()
    assert payload["settings_audit"]["never_changes_live_settings"] is True
    assert payload["report"]["WIN_RATE_N"] == 0
    assert "INSUFFICIENT SAMPLE" in str(payload["report"]["WIN_RATE"])
    assert payload["report"]["COMMIT"] == "NO"
    assert payload["report"]["DEPLOYMENT"] == "NO"
    assert payload["report"]["FIRST_PROVEN_LOSS_CAUSE"] == INSUFFICIENT_SAMPLE


def test_research_survives_shadow_and_funnel_failures(tmp_path, monkeypatch) -> None:
    reset_forensic_ledger_for_tests(tmp_path)

    def boom(*_a, **_k):
        raise RuntimeError("research layer exploded")

    monkeypatch.setattr(
        "app.application.services.strategy_research_forensics.funnel_snapshot",
        boom,
    )
    monkeypatch.setattr(
        "app.application.services.strategy_research_forensics.expansion_report",
        boom,
    )
    monkeypatch.setattr(
        "app.application.services.strategy_research_forensics.observe_shadow_cycle",
        boom,
    )
    payload = build_strategy_research_forensics(
        diagnostics={"latest": _cycle()},
        deals=[],
    )
    assert payload["never_sends_orders"] is True
    assert payload["funnel_histograms"]["failed"] is True
    assert payload["shadow_expansion"]["would_submit_order"] is False
    assert payload["current_shadow"]["would_submit_order"] is False
    assert payload["live_order_sent"] is False


def test_research_modules_cannot_reach_oms_or_mt5() -> None:
    root = Path(__file__).resolve().parents[2] / "app" / "application" / "services"
    files = (
        "strategy_forensic_ledger.py",
        "strategy_loss_forensics.py",
        "shadow_expansion_engine.py",
        "opportunity_funnel_telemetry.py",
        "strategy_research_forensics.py",
        "vps_continuity_classifier.py",
        "strategy_settings_audit.py",
        "shadow_observation_pipeline.py",
    )
    forbidden = (
        "order_send(",
        "FORCE_FIRST_TRADE",
        "execute_now",
        "from app.domain.institutional_trading.execution.bridge",
        "gateway_client",
        "ALLOW_RISK_LOCK_OVERRIDE",
        "OPPORTUNITY_SCORE_THRESHOLD =",
        "direction_edge_margin=",
    )
    for name in files:
        src = (root / name).read_text(encoding="utf-8")
        lower = src.lower()
        for token in forbidden:
            assert token.lower() not in lower, f"{name} contains {token}"
        assert "mutates_engines" in src or "never_sends_orders" in src or "advisory_only" in src.lower()


def test_decision_snapshot_is_immutable(tmp_path) -> None:
    reset_forensic_ledger_for_tests(tmp_path)
    persist_signal(
        _cycle(
            signal_id="sig-imm",
            decision_hash="hash-imm",
            request_id="req-imm",
            forwarded_to_oms=True,
            mt5_ticket=4242,
            opportunity_score=76,
            directional_edge=8,
            setup_state="TAKE",
        )
    )
    original = list_submissions()[0]
    snap = dict(original["decision_snapshot"])
    persist_submission(
        {
            **original,
            "signal_id": "sig-rewritten",
            "decision_hash": "hash-rewritten",
            "decision_snapshot": {"opportunity_score": 1, "directional_edge": 1},
            "setup_features": {"opportunity_score": 1},
        }
    )
    kept = list_submissions()[0]
    assert kept["signal_id"] == "sig-imm"
    assert kept["decision_hash"] == "hash-imm"
    assert kept["decision_snapshot"] == snap
    assert kept["decision_snapshot"]["opportunity_score"] == 76


def test_close_snapshot_is_immutable(tmp_path) -> None:
    reset_forensic_ledger_for_tests(tmp_path)
    persist_close(
        {
            "ticket": 77,
            "signal_id": "sig-close",
            "decision_hash": "hash-close",
            "request_id": "req-close",
            "decision_snapshot": {"opportunity_score": 72, "directional_edge": 6},
            "entry": 2400.0,
            "sl": 2390.0,
            "tp": 2412.0,
            "realized_pnl": -4.0,
        }
    )
    persist_close(
        {
            "ticket": 77,
            "signal_id": "sig-other",
            "decision_snapshot": {"opportunity_score": 1},
            "entry": 1.0,
            "MAE": -2.5,
            "MFE": 1.1,
            "slippage": 0.2,
        }
    )
    from app.application.services.strategy_forensic_ledger import list_closes

    row = list_closes()[0]
    assert row["signal_id"] == "sig-close"
    assert row["decision_snapshot"]["opportunity_score"] == 72
    assert row["entry"] == 2400.0
    assert row["MAE"] == -2.5
    assert row["slippage"] == 0.2


def test_ticket_without_identity_is_unmatched(tmp_path) -> None:
    reset_forensic_ledger_for_tests(tmp_path)
    persist_signal(
        _cycle(
            signal_id=None,
            decision_hash=None,
            request_id=None,
            forwarded_to_oms=True,
            mt5_ticket=111,
        )
    )
    join = classify_closed_deal({"entry_ticket": 111, "profit_loss": 9.0, "side": "buy"})
    assert join["classification"] == UNMATCHED
    assert join["reason"] == "ticket_without_identity"


def test_two_losses_never_proven() -> None:
    losses = [
        {"net_pnl": -1.0, "direction": "BUY"},
        {"net_pnl": -1.2, "direction": "SELL"},
    ]
    report = classify_loss_contributors(losses)
    for row in report["contributors"].values():
        assert row["classification"] != PROVEN
        assert row["never_proven_from_one_or_two_trades"] is True
        assert row["factor"]
        assert "sample_size" in row
        assert "loss_count" in row
        assert "loss_rate" in row
        assert "average_R" in row
        assert "expectancy" in row
        assert "confidence" in row
    assert report["proven_loss_cause"] == INSUFFICIENT_SAMPLE


def test_sessions_and_regimes_always_present(tmp_path) -> None:
    reset_forensic_ledger_for_tests(tmp_path)
    stats = build_loss_forensics(closed_trades=[])
    for name in CANONICAL_SESSIONS:
        assert name in stats["SESSION_EXPECTANCY"]
        assert stats["SESSION_EXPECTANCY"][name]["status"] == INSUFFICIENT_SAMPLE
        assert stats["SESSION_EXPECTANCY"][name]["sample_size"] == 0
    for name in CANONICAL_REGIMES:
        assert name in stats["REGIME_EXPECTANCY"]
        assert stats["REGIME_EXPECTANCY"][name]["status"] == INSUFFICIENT_SAMPLE


def test_news_protection_status_is_enumerated() -> None:
    news = audit_news_protection()
    assert news["STATUS"] in {"ACTIVE", "INACTIVE", "UNUSED", "UNWIRED", "UNKNOWN"}
    assert news["this_task_did_not_enable"] is True
    assert news["ITEConfig_default"] is False


def test_config_audit_rows_have_required_fields() -> None:
    audit = build_strategy_settings_audit()
    required = {
        "SETTING",
        "SOURCE",
        "DEFAULT",
        "LIVE_VALUE",
        "ACTUAL_CONSUMER",
        "PRODUCTION_PATH",
        "LEGACY",
        "DUPLICATED",
        "UNUSED",
        "CONFLICT",
        "RECOMMENDED_FUTURE_ACTION",
    }
    for row in audit["settings"]:
        assert required.issubset(row.keys())
        assert "SAFE_TO_CHANGE" in row
        assert "ACTUAL_EFFECT" in row
    by_name = {r["SETTING"]: r for r in audit["settings"]}
    assert by_name["Opportunity threshold"]["LIVE_VALUE"] == 70
    assert by_name["Opportunity threshold"]["SAFE_TO_CHANGE"] is False
    assert by_name["Directional edge margin"]["LIVE_VALUE"] == 5
    assert by_name["Directional edge margin"]["SAFE_TO_CHANGE"] is False
    assert len(audit["LIVE_EFFECTIVE_CONFIG"]) >= 8
    assert any(r["SETTING"] == "Max open trades (ITEConfig default)" for r in audit["LEGACY_CONFIG"])
    assert any(r["SETTING"] == "News protection" for r in audit["RESEARCH_ONLY_CONFIG"])
    assert "UNWIRED_CONFIG" in audit
    assert isinstance(audit["UNWIRED_CONFIG"], list)
    news_row = next(r for r in audit["settings"] if r["SETTING"] == "News protection")
    if news_row["STATUS"] == "UNWIRED":
        assert any(r["SETTING"] == "News protection" for r in audit["UNWIRED_CONFIG"])


def test_cause_strength_never_proven_from_tiny_n() -> None:
    assert cause_strength(sample_size=0) == INSUFFICIENT_SAMPLE
    assert cause_strength(sample_size=19) == INSUFFICIENT_SAMPLE
    assert cause_strength(sample_size=20) == POSSIBLE
    assert cause_strength(sample_size=50) == LIKELY
    assert cause_strength(sample_size=100) == PROVEN
    assert cause_strength(sample_size=200, contradicted=True) == REJECTED
    stats = build_loss_forensics(closed_trades=[])
    assert len(stats["loss_dimensions"]) == len(LOSS_DIMENSIONS)
    assert all(v["classification"] == INSUFFICIENT_SAMPLE for v in stats["loss_dimensions"].values())


def test_compact_snapshot_retains_cycle_and_snapshot_ids() -> None:
    row = compact_signal_row(
        _cycle(cycle_id="cyc-1", snapshot_id="snap-1", pa=70, consensus=65)
    )
    assert row["cycle_id"] == "cyc-1"
    assert row["snapshot_id"] == "snap-1"
    assert row["decision_snapshot"]["cycle_id"] == "cyc-1"
    assert row["decision_snapshot"]["snapshot_id"] == "snap-1"
    assert row["immutable"] is True


def test_conflict_paint_cannot_convert_take_to_wait() -> None:
    from app.domain.institutional_trading.operations.probability_selector import (
        _smc_presence_score,
    )

    paint_states = {"CHASING", "STALE", "CONFLICT"}
    assert "TAKE" not in paint_states
    assert _smc_presence_score(20) == 0
    assert _smc_presence_score(78) == 78
    src = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "domain"
        / "institutional_trading"
        / "ai_scalping"
        / "scoring.py"
    ).read_text(encoding="utf-8")
    i_sniper = src.find("evaluate_sniper_entry(")
    i_paint = src.find('stale_or_chase = setup_state in {"CHASING", "STALE", "CONFLICT"}')
    i_opp = src.find("evaluate_from_score_dict(")
    i_reject = src.find("if not sniper.passed:")
    assert 0 <= i_sniper < i_paint < i_opp < i_reject
    painted = classify_conflict_paint(
        _cycle(
            setup_state="CONFLICT",
            first_authoritative_blocker="WAIT_NO_DIRECTIONAL_EDGE",
            sniper_entry={
                "pillars": {"displacement_or_momentum": True},
                "entry_state": "RETEST",
            },
            opportunity_audit={
                "displacement": {"score": 20},
                "timing": {"score": 20},
            },
        )
    )
    assert painted["changes_qualifying_take_into_wait"] is False
    assert painted["classification"] == "SECONDARY_OBSERVABILITY_SCORING_PAINT"
    assert painted["direction_gate_already_failed"] is True
    assert painted["leave_scoring_unchanged"] is True
    assert painted["paint_is_first_blocker"] is False
    assert painted["raw_displacement"] == 78
    assert painted["effective_displacement"] == 20
    assert painted["raw_timing"] == 80
    assert painted["effective_timing"] == 20
    assert painted["paint_reason"].startswith("STALE_OR_CHASE_PAINT")
    take = classify_conflict_paint(_cycle(setup_state="TAKE", first_authoritative_blocker=""))
    assert take["applies_on_this_scan"] is False
    assert take["paint_reason"] == "NONE"


def test_exit_path_distinguishes_gave_back_mfe() -> None:
    immediate = classify_exit_path({"net_pnl": -2.0, "MAE": -3.0, "MFE": 0.0})
    gave = classify_exit_path({"net_pnl": -1.0, "MAE": -0.5, "MFE": 4.0})
    unknown = classify_exit_path({"net_pnl": -1.0})
    assert immediate["exit_class"] == "IMMEDIATE_ADVERSE"
    assert gave["exit_class"] == "GAVE_BACK_MFE"
    assert gave["auto_changes_exits"] is False
    assert unknown["exit_class"] == UNKNOWN


def test_shadow_candidates_are_twenty_four_and_isolated() -> None:
    assert len(CANDIDATE_SPECS) == 24
    ids = [c["candidate_id"] for c in CANDIDATE_SPECS]
    assert ids == list("ABCDEFGHIJKLMNOPQRSTUVWX")
    names = [c["candidate_name"] for c in CANDIDATE_SPECS]
    assert "continuation" in names
    assert "ob_retest" in names
    assert "mtf_alignment" in names
    assert "continuation_after_liquidity" in names
    assert SHADOW_MAY_SUBMIT_ORDERS is False
    live = observe_shadow_cycle(_cycle())
    assert live["NOT_EXECUTED"] is True
    assert live["COUNTERFACTUAL"] is True
    assert live["would_submit_order"] is False
    assert live["would_current_live_strategy_take"] is False
    assert live["why_live_strategy_rejected"] == "WAIT_NO_DIRECTIONAL_EDGE"
    assert live["counterfactual_edge"] == 4
    assert live["counterfactual_opportunity"] == 64
    assert live["hypothetical_outcome"] == UNKNOWN
    for row in live["candidates"]:
        assert row["would_submit_order"] is False
        assert row["NOT_EXECUTED"] is True
        assert row["hypothetical_outcome"] == UNKNOWN
        assert row["layer"] == "EXPANSION"
        assert row["CORE"] is False


def test_promotion_state_machine_never_returns_live() -> None:
    assert ALLOW_LIVE_PROMOTION is False
    assert "LIVE" in PROMOTION_STATES
    assert promotion_status(sample_size=200, oos_positive=True, lookahead=False) != "LIVE"
    with pytest.raises(ShadowExpansionBlocked):
        apply_human_promotion("LIVE", approved_by="owner")


def test_compact_signal_snapshot_includes_identity_chain() -> None:
    row = compact_signal_row(
        _cycle(
            signal_id="sig-chain",
            decision_hash="hash-chain",
            request_id="req-chain",
            forwarded_to_oms=True,
            mt5_ticket=99,
            order_id=12,
            deal_id=34,
        )
    )
    assert row["signal_id"] == "sig-chain"
    assert row["decision_hash"] == "hash-chain"
    assert row["request_id"] == "req-chain"
    assert row["mt5_ticket"] == 99
    assert row["order_id"] == 12
    assert row["deal_id"] == 34
    assert row["immutable"] is True
    assert row["decision_snapshot"]["opportunity_score"] == 64
    assert row["decision_snapshot"]["directional_edge"] == 4
