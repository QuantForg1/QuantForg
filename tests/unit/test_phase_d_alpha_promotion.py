"""Phase D — evidence-gated alpha promotion (governance only)."""

from __future__ import annotations

import pytest

from app.domain.institutional_trading.phase_a.plane import reset_phase_a_plane_for_tests
from app.domain.institutional_trading.phase_b.plane import reset_phase_b_plane_for_tests
from app.domain.institutional_trading.phase_c.plane import reset_phase_c_plane_for_tests
from app.domain.institutional_trading.phase_d.canary import CanaryState
from app.domain.institutional_trading.phase_d.isolation import (
    CandidateExecutionForbidden,
    forbid_candidate_execution,
)
from app.domain.institutional_trading.phase_d.plane import (
    get_phase_d_plane,
    reset_phase_d_plane_for_tests,
)


def _full_evidence() -> dict:
    return {
        "research_evidence": {
            "walk_forward_status": "PASSED",
            "oos_status": "CERTIFIED",
            "pbo": "LOW_PBO_RISK",
            "dsr": "MODERATE_EVIDENCE",
            "monte_carlo_status": "ROBUST",
            "parameter_sensitivity": "ROBUST",
            "live_parity_status": "ALIGNED",
            "shadow_status": "SHADOW_PASSED",
            "sample_size": 40,
        },
        "risk_evidence": {
            "risk_impact": "ACCEPTABLE",
            "drawdown_impact": "ACCEPTABLE",
            "correlation_impact": "ACCEPTABLE",
            "execution_impact": "ACCEPTABLE",
        },
        "change_isolation": {"kinds": ["parameter"], "includes_unrelated_refactor": False},
    }


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_phase_a_plane_for_tests()
    reset_phase_b_plane_for_tests()
    reset_phase_c_plane_for_tests()
    reset_phase_d_plane_for_tests()
    yield
    reset_phase_d_plane_for_tests()


def test_candidate_missing_evidence_not_promotable() -> None:
    pd = get_phase_d_plane()
    row = pd.register_candidate(strategy_id="s1")
    assert row["status"] == "NOT_PROMOTABLE"
    assert row["execution_authority"] is False


def test_candidate_schema_and_gates() -> None:
    pd = get_phase_d_plane()
    row = pd.register_candidate(
        strategy_id="mom",
        model_id="m1",
        version="v2",
        code_commit="abc",
        research_run_id="r1",
        dataset_hash="h1",
        symbols=["XAUUSD"],
        timeframes=["M15"],
        regimes=["TRENDING"],
        **_full_evidence(),
    )
    assert row["status"] == "PROMOTABLE"
    ev = pd.evaluate_candidate(
        row["candidate_id"],
        total_trades=40,
        oos_trades=25,
        shadow_trades=25,
        live_matched=25,
        regime_coverage=2,
        symbol_coverage=1,
        session_coverage=1,
    )
    assert ev["result"] == "GATES_PASSED"
    assert ev["auto_promoted"] is False


def test_insufficient_sample_blocks() -> None:
    pd = get_phase_d_plane()
    row = pd.register_candidate(
        strategy_id="mom",
        model_id="m1",
        version="v2",
        code_commit="abc",
        research_run_id="r1",
        dataset_hash="h1",
        symbols=["XAUUSD"],
        timeframes=["M15"],
        **_full_evidence(),
    )
    ev = pd.evaluate_candidate(row["candidate_id"], total_trades=2, oos_trades=1)
    assert ev["result"] == "PROMOTION_BLOCKED"
    assert ev["why_blocked"] == "INSUFFICIENT_SAMPLE"


def test_candidate_cannot_call_oms_gateway_mt5() -> None:
    with pytest.raises(CandidateExecutionForbidden):
        forbid_candidate_execution("OMS")
    with pytest.raises(CandidateExecutionForbidden):
        forbid_candidate_execution("Gateway")
    with pytest.raises(CandidateExecutionForbidden):
        forbid_candidate_execution("MT5")
    snap = get_phase_d_plane().snapshot()
    assert snap["candidate_execution_authority"] is False
    assert snap["auto_promote_to_live"] is False


def test_duplicate_promotion_request_rejected() -> None:
    pd = get_phase_d_plane()
    row = pd.register_candidate(
        strategy_id="mom",
        model_id="m1",
        version="v2",
        code_commit="abc",
        research_run_id="r1",
        dataset_hash="h1",
        symbols=["XAUUSD"],
        timeframes=["M15"],
        **_full_evidence(),
    )
    cid = row["candidate_id"]
    first = pd.request_promotion(candidate_id=cid, request_id="req-1")
    assert first["result"] == "PROMOTION_REVIEW"
    second = pd.request_promotion(candidate_id=cid, request_id="req-1")
    assert second["result"] == "DUPLICATE_PROMOTION_REQUEST"


def test_canary_block_and_rollback() -> None:
    pd = get_phase_d_plane()
    risk = pd.canary_risk(
        equity=100.0,
        projected_risk_per_trade=1.0,
        min_lot=0.01,
        margin_required=200.0,
        projected_drawdown_pct=5.0,
        max_daily_loss_pct=3.0,
        max_drawdown_pct=10.0,
        within_portfolio_caps=True,
        within_correlation_limits=True,
        execution_safe=True,
    )
    assert risk["result"] == "CANARY_BLOCKED"

    row = pd.register_candidate(
        strategy_id="mom",
        model_id="m1",
        version="v2",
        code_commit="abc",
        research_run_id="r1",
        dataset_hash="h1",
        symbols=["XAUUSD"],
        timeframes=["M15"],
        **_full_evidence(),
    )
    pd.request_promotion(candidate_id=row["candidate_id"], request_id="req-2")
    pd.canary.transition(row["candidate_id"], CanaryState.CANARY_APPROVED)
    pd.canary.transition(row["candidate_id"], CanaryState.CANARY)
    rb = pd.evaluate_rollback(
        candidate_id=row["candidate_id"],
        drawdown_breach=True,
        open_positions=1,
    )
    assert rb["action"] == "ROLLBACK"
    assert rb["new_risk_allowed"] is False
    assert rb["phase_a_disabled"] is False
    assert pd.canary.records[row["candidate_id"]].state is CanaryState.SHADOW_ONLY


def test_explicit_approval_required() -> None:
    pd = get_phase_d_plane()
    with pytest.raises(PermissionError):
        pd.approvals.approve(
            candidate_id="c1",
            old_champion="prod",
            new_candidate="v2",
            research_run_id="r",
            evidence_summary={"ok": True},
            risk_review="ACCEPTABLE",
            execution_review="ACCEPTABLE",
            canary_result="PASS",
            approval_actor="system",
            promotion_reason="test",
        )
    ok = pd.approve_live(
        candidate_id="c1",
        old_champion="prod",
        new_candidate="v2",
        research_run_id="r",
        evidence_summary={"ok": True},
        risk_review="ACCEPTABLE",
        execution_review="ACCEPTABLE",
        canary_result="PASS",
        approval_actor="product_owner",
        promotion_reason="evidence reviewed",
    )
    assert ok["approval"]["state"] == "APPROVED_FOR_LIVE"
    assert ok["execution_authority"] is False
    assert ok["auto_promoted"] is False


def test_champion_candidate_comparison_and_live_ab() -> None:
    pd = get_phase_d_plane()
    thin = pd.compare(champion_r=[1.0], candidate_r=[1.2], min_sample=20)
    assert thin["state"] == "INSUFFICIENT_SAMPLE"
    champ = [1.0] * 25
    cand = [1.2] * 25
    cmp = pd.compare(champion_r=champ, candidate_r=cand, min_sample=20)
    assert cmp["auto_promote"] is False
    ab = pd.live_ab(champion_r=champ, candidate_r=cand, min_sample=20)
    assert ab["live_state"] in {"BETTER", "ALIGNED", "WORSE", "INSUFFICIENT_SAMPLE"}
    assert ab["declared_superior"] is False


def test_phase_d_failure_does_not_alter_phase_a() -> None:
    from app.domain.institutional_trading.phase_a import get_phase_a_plane

    pa = get_phase_a_plane()
    before = pa.halt.mode.value
    pd = get_phase_d_plane()
    pd.register_candidate(strategy_id="x")
    pd.evaluate_candidate("missing")
    assert pa.halt.mode.value == before
    assert get_phase_d_plane().snapshot()["live_decision_authority"] is False


def test_execution_and_small_account_gates() -> None:
    pd = get_phase_d_plane()
    eq = pd.execution_gate(
        spread_ok=True,
        quote_fresh=True,
        gateway_rtt_ms=100.0,
        mt5_rtt_ms=80.0,
        slippage_ok=True,
        fill_quality_ok=True,
        order_ack_ok=True,
        reconciliation_ok=True,
    )
    assert eq["promotable"] is True
    sa = pd.small_account(
        equity=100.0,
        min_lot=0.01,
        risk_per_trade=1.0,
        margin_required=20.0,
        projected_drawdown_pct=5.0,
        portfolio_concentration_ok=True,
        execution_cost_ok=True,
    )
    assert sa["eligible"] is True
    sa_bad = pd.small_account(
        equity=100.0,
        min_lot=0.01,
        risk_per_trade=50.0,
        margin_required=20.0,
        projected_drawdown_pct=5.0,
        portfolio_concentration_ok=True,
        execution_cost_ok=True,
    )
    assert sa_bad["eligible"] is False
    assert sa_bad["risk_increased_to_test"] is False
