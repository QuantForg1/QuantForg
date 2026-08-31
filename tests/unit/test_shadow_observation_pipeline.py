"""Shadow observation pipeline: collect without executing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.application.services.shadow_expansion_engine import ALLOW_LIVE_PROMOTION as ENGINE_PROMO
from app.application.services.shadow_observation_pipeline import (
    ALLOW_LIVE_PROMOTION,
    SHADOW_VIRTUAL_TRADE,
    STRATEGY_MATCHED_LIVE_TRADE,
    WOULD_SUBMIT_ORDER,
    apply_future_bar,
    call_mt5,
    call_oms,
    chronological_replay,
    observe_live_scan,
    promote_to_live,
    reset_shadow_pipeline_for_tests,
    shadow_dataset_snapshot,
    submit_order,
    write_live_execution_ledger,
    ShadowPipelineBlocked,
)
from app.application.services.strategy_forensic_ledger import (
    list_submissions,
    reset_forensic_ledger_for_tests,
)
from app.application.services.strategy_loss_forensics import (
    EARLY_SIGNAL,
    HIGHER_CONFIDENCE,
    INSUFFICIENT_SAMPLE,
    MEANINGFUL_RESEARCH,
    PRELIMINARY,
    STRONGER_EVIDENCE,
    sample_status,
)
from app.domain.institutional_trading.ai_scalping.profiles.scalping_v1 import SCALPING_V1
from app.domain.institutional_trading.operations.probability_selector import (
    OPPORTUNITY_SCORE_THRESHOLD,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _ts(minutes: int = 0) -> str:
    return (datetime(2026, 8, 28, 12, 0, tzinfo=UTC) + timedelta(minutes=minutes)).isoformat()


def _wait_cycle(**kwargs):
    row = {
        "recorded_at": _ts(0),
        "symbol": "XAUUSD_i",
        "buy_score": 42,
        "sell_score": 34,
        "ltf_buy_score": 28,
        "ltf_sell_score": 24,
        "directional_edge": 4,
        "opportunity_score": 64,
        "setup_state": "CONFLICT",
        "first_authoritative_blocker": "WAIT_NO_DIRECTIONAL_EDGE",
        "blocker_source": "DIRECTION",
        "buy_families": ["structure", "zone"],
        "sell_families": ["structure"],
        "market_session": "london",
        "decision_action": "WAIT",
        "spread": 18.0,
        "data_age_seconds": 0,
    }
    row.update(kwargs)
    return row


def test_shadow_cannot_execute(tmp_path: Path) -> None:
    reset_shadow_pipeline_for_tests(tmp_path)
    with pytest.raises(ShadowPipelineBlocked):
        submit_order()
    with pytest.raises(ShadowPipelineBlocked):
        call_oms()
    with pytest.raises(ShadowPipelineBlocked):
        call_mt5()
    with pytest.raises(ShadowPipelineBlocked):
        write_live_execution_ledger()
    with pytest.raises(Exception):
        promote_to_live()
    assert WOULD_SUBMIT_ORDER is False
    assert ALLOW_LIVE_PROMOTION is False
    assert ENGINE_PROMO is False


def test_live_wait_tape_records_observations_without_fabricating_fills(tmp_path: Path) -> None:
    reset_shadow_pipeline_for_tests(tmp_path)
    out = observe_live_scan(_wait_cycle())
    assert out["would_submit_order"] is False
    assert out["ALLOW_LIVE_PROMOTION"] is False
    assert out["virtual_entries_opened"] == 0
    present = set(out["present_families"])
    assert "continuation" in present
    assert "london_setup" in present
    snap = shadow_dataset_snapshot()
    assert snap["observations"] == 1
    assert snap["virtual_completed"] == 0
    assert snap["would_submit_order"] is False
    assert snap["verdict"]["text"] == "NO SAFE EXPANSION PROVEN — CONTINUE COLLECTING DATA"
    below = [c for c in out["candidates"] if c["WOULD_QUALIFY_AS_SHADOW"]]
    assert below
    assert all(c["below_core_threshold"] for c in below)
    assert all(c["would_submit_order"] is False for c in out["candidates"])


def test_virtual_trade_never_writes_live_ledger(tmp_path: Path) -> None:
    reset_shadow_pipeline_for_tests(tmp_path)
    reset_forensic_ledger_for_tests(tmp_path / "live")
    observe_live_scan(
        _wait_cycle(
            bid=2400.0,
            ask=2400.4,
            sl=2395.0,
            tp=2406.4,
            ltf_buy_score=30,
            ltf_sell_score=20,
        )
    )
    snap = shadow_dataset_snapshot()
    assert snap["virtual_open"] >= 1
    assert all(t.get("mt5_ticket") is None for t in _open_or_closed())
    assert list_submissions() == []


def _open_or_closed():
    from app.application.services import shadow_observation_pipeline as pip

    return list(pip._VIRTUAL)


def test_lookahead_future_bar_before_entry_is_rejected(tmp_path: Path) -> None:
    reset_shadow_pipeline_for_tests(tmp_path)
    observe_live_scan(
        _wait_cycle(
            recorded_at=_ts(10),
            bid=2400.0,
            ask=2400.4,
            sl=2395.0,
            tp=2406.4,
            ltf_buy_score=30,
            ltf_sell_score=20,
        ),
        advance_open=False,
    )
    early = apply_future_bar({"timestamp": _ts(9), "high": 2410.0, "low": 2399.0})
    assert early["status"] == "LOOKAHEAD_REJECTED"
    assert early["applied"] == 0
    assert _open_or_closed()[0]["open"] is True
    later = apply_future_bar({"timestamp": _ts(11), "high": 2410.0, "low": 2399.0})
    assert later["applied"] >= 1
    trade = _open_or_closed()[0]
    assert trade["open"] is False
    assert trade["record_kind"] == SHADOW_VIRTUAL_TRADE
    assert trade["STRATEGY_MATCHED_LIVE_TRADE"] is False
    assert trade["mt5_ticket"] is None
    assert trade["exit_reason"] == "TP"


def test_same_bar_cannot_close_virtual_entry(tmp_path: Path) -> None:
    reset_shadow_pipeline_for_tests(tmp_path)
    observe_live_scan(
        _wait_cycle(
            recorded_at=_ts(0),
            bid=2400.0,
            ask=2400.4,
            sl=2395.0,
            tp=2406.4,
            ltf_buy_score=30,
            ltf_sell_score=20,
            high=2410.0,
            low=2390.0,
        ),
        advance_open=False,
    )
    same = apply_future_bar({"timestamp": _ts(0), "high": 2410.0, "low": 2390.0})
    assert same["applied"] == 0
    assert _open_or_closed()[0]["open"] is True


def test_chronological_replay_orders_shuffled_input(tmp_path: Path) -> None:
    reset_shadow_pipeline_for_tests(tmp_path)
    scans = [
        _wait_cycle(
            recorded_at=_ts(2),
            bid=2400.0,
            ask=2400.4,
            sl=2395.0,
            tp=2406.4,
            ltf_buy_score=30,
            ltf_sell_score=20,
        ),
        _wait_cycle(
            recorded_at=_ts(0),
            bid=2390.0,
            ask=2390.4,
            sl=2385.0,
            tp=2396.4,
            ltf_buy_score=30,
            ltf_sell_score=20,
        ),
    ]
    bars = [
        {"timestamp": _ts(3), "high": 2410.0, "low": 2399.0},
        {"timestamp": _ts(1), "high": 2400.0, "low": 2389.0},
    ]
    out = chronological_replay(scans, bars)
    assert out["would_submit_order"] is False
    assert out["scans"] == 2
    completed = out["snapshot"]["virtual_completed"]
    assert completed >= 1


def test_future_field_at_entry_is_stripped(tmp_path: Path) -> None:
    reset_shadow_pipeline_for_tests(tmp_path)
    out = observe_live_scan(_wait_cycle(future_close=9999, lookahead_pnl=12))
    assert "future_close" not in (out["scan"] or {})
    assert out["lookahead_fields"]


def test_core_and_expansion_never_merge(tmp_path: Path) -> None:
    reset_shadow_pipeline_for_tests(tmp_path)
    observe_live_scan(_wait_cycle())
    observe_live_scan(
        _wait_cycle(
            recorded_at=_ts(1),
            opportunity_score=72,
            directional_edge=6,
            setup_state="TAKE",
        )
    )
    snap = shadow_dataset_snapshot()
    cmp_ = snap["core_vs_expansion"]
    assert cmp_["CORE"]["n"] == 1
    assert cmp_["SHADOW_EXPANSION"]["n"] >= 1
    assert cmp_["never_merged"] is True
    assert cmp_["CORE"]["layer"] == "CORE"
    assert cmp_["SHADOW_EXPANSION"]["layer"] == "SHADOW_EXPANSION"


def test_candidate_isolation(tmp_path: Path) -> None:
    reset_shadow_pipeline_for_tests(tmp_path)
    observe_live_scan(_wait_cycle(buy_families=["structure"], choch_state=None))
    snap = shadow_dataset_snapshot()
    by_id = {c["candidate_id"]: c for c in snap["candidates"]}
    assert by_id["A"]["eligible"] == 1
    assert by_id["D"]["eligible"] == 0
    assert all(c["CORE"] is False for c in snap["candidates"])
    assert all(c["would_submit_order"] is False for c in snap["candidates"])


def test_sample_confidence_bands_are_research_only() -> None:
    assert sample_status(0) == INSUFFICIENT_SAMPLE
    assert sample_status(7) == EARLY_SIGNAL
    assert sample_status(10) == PRELIMINARY
    assert sample_status(20) == MEANINGFUL_RESEARCH
    assert sample_status(50) == STRONGER_EVIDENCE
    assert sample_status(100) == HIGHER_CONFIDENCE


def test_live_thresholds_unchanged_by_shadow_module() -> None:
    assert OPPORTUNITY_SCORE_THRESHOLD == 70
    assert SCALPING_V1.direction_edge_margin == 5
    assert STRATEGY_MATCHED_LIVE_TRADE == "STRATEGY_MATCHED_LIVE_TRADE"


def test_diagnostics_record_observes_shadow_without_oms(tmp_path: Path, monkeypatch) -> None:
    reset_shadow_pipeline_for_tests(tmp_path)
    reset_forensic_ledger_for_tests(tmp_path / "live")
    from app.application.services.strategy_diagnostics import StrategyDiagnosticsStore

    store = StrategyDiagnosticsStore()
    store.record(_wait_cycle())
    snap = shadow_dataset_snapshot()
    assert snap["observations"] == 1
    assert list_submissions() == []
    assert snap["would_submit_order"] is False


def test_sl_preferred_when_same_future_bar_hits_both(tmp_path: Path) -> None:
    reset_shadow_pipeline_for_tests(tmp_path)
    observe_live_scan(
        _wait_cycle(
            recorded_at=_ts(0),
            bid=2400.0,
            ask=2400.4,
            sl=2395.0,
            tp=2406.4,
            ltf_buy_score=30,
            ltf_sell_score=20,
        ),
        advance_open=False,
    )
    apply_future_bar({"timestamp": _ts(1), "high": 2412.0, "low": 2390.0})
    trade = _open_or_closed()[0]
    assert trade["exit_reason"] == "SL"
    assert trade["virtual_R"] is not None
    assert float(trade["virtual_R"]) < 0
