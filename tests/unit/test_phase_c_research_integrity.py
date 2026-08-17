"""Phase C research integrity & model governance — research/shadow only."""

from __future__ import annotations

import pytest

from app.domain.institutional_trading.phase_a.plane import reset_phase_a_plane_for_tests
from app.domain.institutional_trading.phase_b.plane import reset_phase_b_plane_for_tests
from app.domain.institutional_trading.phase_c.calibration_monitor import (
    CalibrationMonitor,
)
from app.domain.institutional_trading.phase_c.champion_challenger_shadow import (
    ChallengerExecutionForbidden,
    ChampionChallengerShadowStore,
    forbid_challenger_execution,
)
from app.domain.institutional_trading.phase_c.change_control import (
    ModelChangeControlStore,
)
from app.domain.institutional_trading.phase_c.drift import classify_drift
from app.domain.institutional_trading.phase_c.dsr import deflated_sharpe_ratio
from app.domain.institutional_trading.phase_c.fair_comparison import (
    compare_champion_challenger,
)
from app.domain.institutional_trading.phase_c.leakage import check_time_splits
from app.domain.institutional_trading.phase_c.monte_carlo_cert import (
    run_monte_carlo_certification,
)
from app.domain.institutional_trading.phase_c.parameter_sensitivity import (
    classify_from_scores,
)
from app.domain.institutional_trading.phase_c.parity_report import build_parity_report
from app.domain.institutional_trading.phase_c.pbo import estimate_pbo
from app.domain.institutional_trading.phase_c.plane import (
    get_phase_c_plane,
    reset_phase_c_plane_for_tests,
)
from app.domain.institutional_trading.phase_c.promotion_gate import (
    PromotionState,
    PromotionStateMachine,
)
from app.domain.institutional_trading.phase_c.provenance import (
    ProvenanceStore,
    hash_dataset_payload,
)


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_phase_a_plane_for_tests()
    reset_phase_b_plane_for_tests()
    reset_phase_c_plane_for_tests()
    yield
    reset_phase_c_plane_for_tests()


def test_provenance_unverified_without_fields() -> None:
    store = ProvenanceStore()
    rec = store.register(strategy_id="s1")
    assert rec.status == "UNVERIFIED_RESEARCH_RESULT"
    assert rec.verified is False


def test_provenance_verified_and_hash_reproducible() -> None:
    h1 = hash_dataset_payload({"bars": [1, 2, 3], "symbol": "EURUSD"})
    h2 = hash_dataset_payload({"symbol": "EURUSD", "bars": [1, 2, 3]})
    assert h1 == h2
    store = ProvenanceStore()
    rec = store.register(
        strategy_id="mom",
        model_id="m1",
        code_commit="abc",
        dataset_id="ds1",
        dataset_hash=h1,
        data_start="2020-01-01",
        data_end="2024-01-01",
        timeframe="M15",
        symbols=["EURUSD"],
        validation_method="walk_forward",
        number_of_trials=40,
        random_seed=7,
    )
    assert rec.status == "VERIFIED_RESEARCH_RESULT"


def test_leakage_blocks_lookahead_and_overlap() -> None:
    bad = check_time_splits(
        train_end="2024-06-01",
        oos_start="2024-01-01",
        train_indices=[0, 1, 2, 5],
        oos_indices=[5, 6, 7],
    )
    assert bad["ok"] is False
    codes = {f["code"] for f in bad["findings"]}
    assert "TRAIN_AFTER_OOS" in codes or "OVERLAPPING_TRAIN_OOS" in codes

    good = check_time_splits(
        train_indices=[0, 1, 2],
        validation_indices=[3, 4],
        oos_indices=[10, 11, 12],
        embargo_bars=2,
    )
    assert good["ok"] is True
    assert good["oos_certified"] is True


def test_pbo_insufficient_and_reproducible() -> None:
    thin = estimate_pbo([[0.1, 0.2]])
    assert thin["state"] == "INSUFFICIENT_DATA"
    assert thin["live_block"] is False if "live_block" in thin else True

    # 8 configs × 6 splits
    matrix = [
        [0.1 + 0.01 * i + 0.02 * j for j in range(6)] for i in range(8)
    ]
    a = estimate_pbo(matrix, min_trials=8)
    b = estimate_pbo(matrix, min_trials=8)
    assert a["PBO"] == b["PBO"]
    assert a["selection_method"] == "CSCV"
    assert a["live_block"] is False
    assert a["state"] in {
        "LOW_PBO_RISK",
        "MODERATE_PBO_RISK",
        "HIGH_PBO_RISK",
        "INSUFFICIENT_DATA",
    }


def test_dsr_does_not_auto_promote() -> None:
    # Positive drift returns
    rets = [0.01, 0.02, -0.005, 0.015, 0.01] * 10
    out = deflated_sharpe_ratio(rets, n_trials=50)
    assert out["auto_promote"] is False
    assert out["live_gate"] is False
    assert out["RAW_SHARPE"] is not None
    assert out["CONFIDENCE_STATE"] in {
        "STRONG_EVIDENCE",
        "MODERATE_EVIDENCE",
        "WEAK_EVIDENCE",
        "INSUFFICIENT_TRACK_RECORD",
    }
    tiny = deflated_sharpe_ratio([0.1, -0.1], n_trials=100)
    assert tiny["CONFIDENCE_STATE"] == "INSUFFICIENT_TRACK_RECORD"


def test_monte_carlo_records_assumptions() -> None:
    out = run_monte_carlo_certification(
        [0.5, -0.3, 0.8, -0.2, 0.4, 0.1, -0.1],
        iterations=50,
        seed=1,
    )
    assert out["state"] == "COMPUTED"
    assert out["assumptions"]["seed"] == 1
    assert out["live_action"] == "NONE"
    assert out["distributions"] is not None


def test_parameter_sensitivity_fragile() -> None:
    out = classify_from_scores(1.0, [0.2, 0.15, 0.9])
    assert out["state"] == "FRAGILE"
    thin = classify_from_scores(1.0, [1.0])
    assert thin["state"] == "INSUFFICIENT_DATA"


def test_challenger_cannot_call_oms_gateway_mt5() -> None:
    with pytest.raises(ChallengerExecutionForbidden):
        forbid_challenger_execution("OMS")
    with pytest.raises(ChallengerExecutionForbidden):
        forbid_challenger_execution("Gateway")
    with pytest.raises(ChallengerExecutionForbidden):
        forbid_challenger_execution("MT5")
    store = ChampionChallengerShadowStore()
    with pytest.raises(ChallengerExecutionForbidden):
        store.record_shadow(symbol="EURUSD", challenger_executed=True)
    opp = store.record_shadow(
        symbol="EURUSD",
        direction="BUY",
        champion_action="BUY",
        challenger_action="NONE",
        champion_score=80,
        challenger_score=55,
    )
    assert opp.challenger_executed is False
    assert store.snapshot()["challenger_execution_authority"] is False


def test_fair_comparison_insufficient_sample() -> None:
    out = compare_champion_challenger(
        champion_r=[1.0, 0.5, -0.2],
        challenger_r=[1.2, 0.4],
        min_sample=20,
    )
    assert out["verdict"] == "INSUFFICIENT_SAMPLE"
    assert out["auto_promote"] is False


def test_drift_insufficient_and_no_auto_disable() -> None:
    out = classify_drift(baseline=[1.0] * 5, live=[0.5] * 5, min_sample=20)
    assert out["state"] == "INSUFFICIENT_SAMPLE"
    assert out["auto_disable"] is False
    base = [1.0] * 30
    live = [0.4] * 30
    alert = classify_drift(baseline=base, live=live, min_sample=20)
    assert alert["response"] in {"OBSERVE", "WARN", "ALERT"}
    assert alert["auto_retrain"] is False


def test_calibration_buckets() -> None:
    mon = CalibrationMonitor(min_sample=5)
    for _ in range(5):
        mon.record(confidence=85, realized_r=0.2, win=True)
    for _ in range(5):
        mon.record(confidence=85, realized_r=-0.5, win=False)
    snap = mon.snapshot()
    assert snap["auto_recalibrate_live"] is False
    assert any(b["state"] != "INSUFFICIENT_SAMPLE" for b in snap["buckets"])


def test_parity_states() -> None:
    out = build_parity_report(
        research={"trade_count": 5, "expectancy": 1.0},
        live={"trade_count": 5, "expectancy": 0.9},
        min_sample=20,
    )
    assert out["state"] == "INSUFFICIENT_SAMPLE"


def test_promotion_requires_explicit_approval() -> None:
    sm = PromotionStateMachine()
    cand = sm.register(strategy_id="s", research_run_id="r1")
    sm.transition(cand.candidate_id, PromotionState.VALIDATION_PASSED)
    sm.transition(cand.candidate_id, PromotionState.SHADOW)
    sm.transition(cand.candidate_id, PromotionState.SHADOW_PASSED)
    sm.transition(cand.candidate_id, PromotionState.PROMOTION_REVIEW)
    with pytest.raises(PermissionError):
        sm.transition(
            cand.candidate_id,
            PromotionState.APPROVED_FOR_LIVE,
            actor="system",
        )
    sm.transition(
        cand.candidate_id,
        PromotionState.APPROVED_FOR_LIVE,
        actor="product_owner",
        note="evidence reviewed",
    )
    assert sm.candidates[cand.candidate_id].state is PromotionState.APPROVED_FOR_LIVE
    assert sm.snapshot()["auto_approve_for_live"] is False


def test_change_control_does_not_silently_approve() -> None:
    store = ModelChangeControlStore()
    rec = store.propose(
        old_commit="a",
        new_commit="b",
        old_model="m1",
        new_model="m2",
        reason="test",
        research_run_id="r",
        approval_status="APPROVED_FOR_LIVE",
    )
    assert rec.approval_status == "PROPOSED"


def test_plane_snapshot_no_live_authority() -> None:
    pc = get_phase_c_plane()
    snap = pc.snapshot()
    assert snap["live_decision_authority"] is False
    assert snap["challenger_execution_authority"] is False
    assert snap["policy_changes"] is False


def test_research_failure_does_not_alter_phase_a() -> None:
    from app.domain.institutional_trading.phase_a import get_phase_a_plane

    pa = get_phase_a_plane()
    before = pa.halt.mode.value
    pc = get_phase_c_plane()
    # Incomplete / corrupted research stays unverified
    pc.provenance.register(strategy_id="x")
    pc.run_pbo([[1.0]])
    assert pa.halt.mode.value == before


def test_provenance_aliases_and_model_id_required() -> None:
    store = ProvenanceStore()
    missing_model = store.register(
        strategy_id="s",
        code_commit="abc",
        dataset_id="ds",
        dataset_hash="h",
        data_start="2020",
        data_end="2024",
        timeframe="M15",
        symbols=["EURUSD"],
        validation_method="walk_forward",
        number_of_trials=10,
    )
    assert missing_model.status == "UNVERIFIED_RESEARCH_RESULT"
    rec = store.register(
        strategy_id="s",
        model_id="m1",
        code_commit="abc",
        dataset_id="ds",
        dataset_hash="h",
        data_start="2020",
        data_end="2024",
        timeframe="M15",
        symbols=["EURUSD"],
        validation_method="walk_forward",
        number_of_trials=10,
    )
    d = rec.to_dict()
    assert d["trial_count"] == 10
    assert d["created_at"] == d["research_timestamp"]
    assert d["timeframes"] == ["M15"]
    assert store.snapshot()["latest"]["research_run_id"] == rec.research_run_id


def test_regime_specific_drift_keeps_cells_distinct() -> None:
    from app.domain.institutional_trading.phase_c.drift import regime_specific_drift

    trending = regime_specific_drift(
        strategy="trend_continuation",
        symbol="EURUSD_I",
        session="LONDON",
        regime="TRENDING",
        direction="BUY",
        baseline_r=[1.0] * 25,
        live_r=[0.9] * 25,
        min_sample=20,
    )
    ranging = regime_specific_drift(
        strategy="trend_continuation",
        symbol="EURUSD_I",
        session="LONDON",
        regime="RANGING",
        direction="BUY",
        baseline_r=[1.0] * 25,
        live_r=[0.2] * 25,
        min_sample=20,
    )
    assert trending["cell"]["regime"] == "TRENDING"
    assert ranging["cell"]["regime"] == "RANGING"
    assert ranging["state"] in {"WARN", "ALERT", "STABLE"}
    assert ranging["auto_disable"] is False


def test_corrupted_research_never_auto_approved() -> None:
    sm = PromotionStateMachine()
    cand = sm.register(strategy_id="bad", research_run_id="")
    # Missing / corrupted evidence — stay in RESEARCH or fail validation
    sm.transition(
        cand.candidate_id,
        PromotionState.VALIDATION_FAILED,
        note="missing dataset hash",
    )
    assert sm.candidates[cand.candidate_id].state is PromotionState.VALIDATION_FAILED
    assert sm.snapshot()["auto_approve_for_live"] is False
    # Shadow crash isolation: plane still reports no live authority
    pc = get_phase_c_plane()
    snap = pc.snapshot()
    assert snap["challenger_execution_authority"] is False
    assert snap["live_decision_authority"] is False


def test_challenger_hypothetical_metrics_insufficient() -> None:
    store = ChampionChallengerShadowStore()
    store.record_shadow(symbol="XAUUSD", hypothetical_R=0.5)
    snap = store.snapshot()
    assert snap["hypothetical"]["state"] == "INSUFFICIENT_SAMPLE"
    assert snap["challenger_execution_authority"] is False
