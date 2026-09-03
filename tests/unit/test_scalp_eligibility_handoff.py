"""TAKE → eligibility handoff: named predicates, SCALPING_V1, no swing 80.

Does not send orders. Does not lower Opportunity 70 or convert WAIT→TAKE.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.application.services.signal_center_service import (
    _overlay_last_ite_cycle,
    _row_from_score,
)
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    scalping_ite_config,
)
from app.domain.institutional_trading.ai_scalping.multi_symbol import (
    rank_scalping_opportunities,
)
from app.domain.institutional_trading.config import ITEConfig
from app.domain.institutional_trading.decision_models import (
    ConfluenceResult,
    TradeDirection,
)
from app.domain.institutional_trading.eligibility import PositionEligibilityEngine
from app.domain.institutional_trading.operations.execution_chain_log import (
    build_execution_handoff,
)
from app.domain.institutional_trading.operations.fast_decision_path import (
    build_current_scan_decision,
    scan_ineligible_abort_reason,
)
from app.domain.institutional_trading.operations.scalp_eligibility import (
    explain_scalp_handoff,
    sniper_is_take,
)
from app.domain.trading.gold_only import (
    same_gold_identity,
    symbol_in_scan_universe,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

_GOLD = "XAUUSD_I"


def _gold_cycle(**kwargs: object) -> dict:
    payload: dict = {"symbol": _GOLD}
    payload.update(kwargs)
    return payload


def _take_score(**overrides: object) -> dict:
    row: dict = {
        "symbol": _GOLD,
        "direction": "SELL",
        "signal_action": "SELL",
        "reject": False,
        "reject_reason": None,
        "opportunity_score": 75,
        "opportunity_threshold": 70,
        "opportunity_eligible": True,
        "trade_quality": 66,
        "ai_confidence": 65,
        "expected_rr": "1.20",
        "setup_state": "TAKE",
        "signal_id": "sig-live-66",
        "setup_family": "bos_continuation",
        "indicators": {"stop_distance": "1.8"},
        "sniper_entry": {
            "passed": True,
            "action": "SELL",
            "setup_state": "TAKE",
            "signal_id": "sig-live-66",
            "confluence_class": "HIGH_CONFLUENCE",
            "atr_timeframe": "M5",
        },
        "opportunity_audit": {"confluence": "HIGH_CONFLUENCE"},
    }
    row.update(overrides)
    return row


def test_1_opportunity_pass_sniper_take_reaches_eligibility() -> None:
    trace = explain_scalp_handoff(_take_score(), universe=(_GOLD,), in_portfolio_eligible=True)
    assert sniper_is_take(_take_score()) is True
    assert trace.should_hand_off is True
    assert trace.eligibility_status == "PASS"
    assert trace.candidate_direction == "SELL"
    assert trace.first_failed_code is None


def test_2_valid_scalp_not_blocked_by_swing_config() -> None:
    swing = ITEConfig()
    assert swing.is_scalping() is False
    assert swing.min_trade_quality_score == 80
    scalp = scalping_ite_config(swing)
    assert scalp.is_scalping() is True
    trace = explain_scalp_handoff(
        _take_score(),
        universe=(_GOLD,),
        ite_trading_mode=scalp.trading_mode,
        in_portfolio_eligible=False,
    )
    assert trace.should_hand_off is True
    names = {p["name"] for p in trace.passed_predicates}
    assert "no_swing_quality_80" in names
    assert "no_swing_confluence_80" in names


def test_3_quality_80_confluence_80_not_reapplied() -> None:
    trace = explain_scalp_handoff(_take_score(trade_quality=66, ai_confidence=65))
    assert trace.should_hand_off is True
    failed_names = {p["name"] for p in trace.failed_predicates}
    assert "no_swing_quality_80" not in failed_names
    assert "no_swing_confluence_80" not in failed_names


def test_fx_take_hands_off_when_gold_only_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Production AUDUSD sniper TAKE was labeled SYMBOL_UNIVERSE_MISMATCH."""
    monkeypatch.setattr(
        "app.domain.trading.gold_only.gold_only_enabled",
        lambda: False,
    )
    row = _take_score(symbol="AUDUSD", direction="SELL", signal_action="SELL")
    trace = explain_scalp_handoff(
        row,
        universe=("EURUSD", "AUDUSD", "XAUUSD"),
        in_portfolio_eligible=True,
    )
    assert trace.should_hand_off is True
    assert trace.first_failed_code is None
    assert trace.eligibility_reason == "SCALP_ELIGIBLE"


def test_fx_take_blocked_when_gold_only_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.domain.trading.gold_only.gold_only_enabled",
        lambda: True,
    )
    row = _take_score(symbol="AUDUSD", direction="SELL", signal_action="SELL")
    trace = explain_scalp_handoff(
        row,
        universe=("EURUSD", "AUDUSD", "XAUUSD"),
        in_portfolio_eligible=True,
    )
    assert trace.should_hand_off is False
    assert trace.first_failed_code == "SYMBOL_UNIVERSE_MISMATCH"


def test_4_xauusd_i_symbol_accepted() -> None:
    assert same_gold_identity("XAUUSD_i", "XAUUSD_I") is True
    assert symbol_in_scan_universe("XAUUSD_I", ("XAUUSD",)) is True
    ranked = rank_scalping_opportunities(
        [_take_score(symbol="XAUUSD_I")],
        config=replace(DEFAULT_AI_SCALPING_CONFIG, universe=("XAUUSD",)),
    )
    assert ranked["best"] is not None
    assert str(ranked["best"]["symbol"]).upper() == "XAUUSD_I"


def test_5_signal_id_preserved() -> None:
    trace = explain_scalp_handoff(_take_score())
    assert trace.candidate_signal_id == "sig-live-66"


def test_6_direction_preserved() -> None:
    trace = explain_scalp_handoff(_take_score(direction="BUY", signal_action="BUY"))
    assert trace.candidate_direction == "BUY"
    assert trace.should_hand_off is True


def test_7_timeframe_preserved() -> None:
    trace = explain_scalp_handoff(_take_score())
    sniper = next(p for p in trace.passed_predicates if p["name"] == "sniper_take")
    assert sniper["timeframe"] == "M5"


def test_8_fresh_take_remains_eligible() -> None:
    trace = explain_scalp_handoff(_take_score())
    assert trace.should_hand_off is True
    assert trace.optimizer_status == "NOT_REACHED"


def test_9_stale_take_is_rejected() -> None:
    row = _take_score(
        reject=True,
        reject_reason="WAIT_STALE_FVG",
        opportunity_eligible=False,
        sniper_entry={
            "passed": False,
            "action": "WAIT",
            "setup_state": "STALE",
            "primary_reason": "WAIT_STALE_FVG",
        },
        signal_action="WAIT",
        setup_state="STALE",
    )
    trace = explain_scalp_handoff(row)
    assert trace.should_hand_off is False
    assert "STALE" in str(trace.first_failed_code or "").upper() or "WAIT_STALE" in str(
        trace.first_failed_code or ""
    )


def test_10_invalid_rr_is_rejected() -> None:
    row = _take_score(
        reject=True,
        reject_reason="Expected RR 0.4 below minimum 1.20",
        opportunity_eligible=False,
        sniper_entry={"passed": False, "setup_state": "WAIT", "primary_reason": "RR_TOO_LOW"},
        signal_action="WAIT",
    )
    trace = explain_scalp_handoff(row)
    assert trace.should_hand_off is False
    assert trace.first_failed_code == "RR_REJECTED"


def test_11_invalid_stop_is_rejected() -> None:
    row = _take_score(
        reject=True,
        reject_reason="WAIT_NO_INVALIDATION — stop invalid",
        opportunity_eligible=False,
        sniper_entry={"passed": False, "setup_state": "WAIT", "primary_reason": "INVALIDATION_INVALID"},
        signal_action="WAIT",
    )
    trace = explain_scalp_handoff(row)
    assert trace.should_hand_off is False
    assert trace.first_failed_code == "INVALID_STOP"


def test_12_min_lot_rejection_is_explicit() -> None:
    row = _take_score(reject=True, reject_reason="MIN_LOT_CONSTRAINT", opportunity_eligible=False)
    trace = explain_scalp_handoff(row)
    assert trace.should_hand_off is False
    assert trace.first_failed_code == "MIN_LOT_REJECTED"


def test_13_capacity_rejection_is_explicit() -> None:
    trace = explain_scalp_handoff(
        _take_score(),
        blocked_by_portfolio=True,
        portfolio_block_reason="Max open positions reached (2>=2)",
    )
    assert trace.should_hand_off is False
    assert trace.first_failed_code == "CAPACITY_REJECTED"


def test_14_duplicate_rejection_is_explicit() -> None:
    row = _take_score(
        reject=True,
        reject_reason="duplicate signal guard — same setup already open",
        opportunity_eligible=False,
    )
    trace = explain_scalp_handoff(row)
    assert trace.should_hand_off is False
    assert trace.first_failed_code == "DUPLICATE_REJECTED"


def test_15_optimizer_rejection_is_explicit() -> None:
    from app.domain.institutional_trading.ai_scalping.execution_optimizer import (
        HARD_BLOCK_REASONS,
    )

    assert "NO_ELIGIBLE_SETUP" in HARD_BLOCK_REASONS
    over = _overlay_last_ite_cycle(
        _row_from_score(_take_score()),
        _gold_cycle(
            forwarded_to_oms=False,
            abort_reason="OPTIMIZER_BLOCK",
            mt5_ticket=None,
            execution_blocked={
                "stage": "OPTIMIZER",
                "reason_code": "OPTIMIZER_BLOCK",
                "human_reason": "spread widening",
            },
        ),
    )
    assert over["pipeline"]["optimizer"] == "WAIT"
    assert over["pipeline"]["oms"] == "NOT_REACHED"
    assert over["first_blocker"] == "OPTIMIZER_BLOCK"


def test_16_risk_rejection_does_not_reach_safety_oms() -> None:
    over = _overlay_last_ite_cycle(
        _row_from_score(_take_score()),
        _gold_cycle(
            forwarded_to_oms=False,
            abort_reason="RISK_REJECTED",
            mt5_ticket=None,
            execution_blocked={
                "stage": "RISK",
                "reason_code": "RISK_REJECTED",
                "human_reason": "margin",
            },
        ),
    )
    assert over["pipeline"]["risk"] == "BLOCK"
    assert over["pipeline"]["safety"] == "NOT_REACHED"
    assert over["pipeline"]["oms"] == "NOT_REACHED"


def test_17_safety_rejection_does_not_reach_oms() -> None:
    over = _overlay_last_ite_cycle(
        _row_from_score(_take_score()),
        _gold_cycle(
            forwarded_to_oms=False,
            abort_reason="SAFETY_BLOCKED",
            mt5_ticket=None,
            execution_blocked={
                "stage": "SAFETY",
                "reason_code": "SAFETY_BLOCKED",
                "human_reason": "kill switch",
            },
        ),
    )
    assert over["pipeline"]["safety"] == "BLOCK"
    assert over["pipeline"]["oms"] == "NOT_REACHED"


def test_18_oms_rejection_is_not_mt5_execution() -> None:
    over = _overlay_last_ite_cycle(
        _row_from_score(_take_score()),
        _gold_cycle(
            forwarded_to_oms=True,
            abort_reason="OMS_REJECT",
            mt5_ticket=None,
            execution_blocked={
                "stage": "OMS",
                "reason_code": "OMS_REJECT",
            },
        ),
    )
    assert over["pipeline"]["oms"] == "BLOCK"
    assert over["pipeline"]["mt5"] == "NOT_REACHED"
    assert over["pipeline"].get("execution_lifecycle") != "FILLED"


def test_19_real_ticket_required_for_executed() -> None:
    handoff = build_execution_handoff(
        take=True,
        forwarded_to_oms=True,
        mt5_ticket=None,
        abort_reason="NO_ELIGIBLE_SETUP",
    )
    assert handoff["execution_confirmed"] is False
    over = _overlay_last_ite_cycle(
        _row_from_score(_take_score()),
        _gold_cycle(
            forwarded_to_oms=True,
            mt5_ticket="123456",
            abort_reason=None,
        ),
    )
    assert over["pipeline"]["mt5"] == "PENDING"
    assert over["pipeline"]["forwarded_to_oms"] is True


def test_20_wait_never_becomes_oms_block() -> None:
    wait = _row_from_score(
        {
            "symbol": _GOLD,
            "direction": "SELL",
            "signal_action": "WAIT",
            "reject": True,
            "reject_reason": "WAIT_NO_SNIPER_TRIGGER",
            "opportunity_score": 44,
            "sniper_entry": {"passed": False, "setup_state": "WAIT"},
        }
    )
    over = _overlay_last_ite_cycle(
        wait,
        {
            "forwarded_to_oms": False,
            "abort_reason": "NO_EXECUTABLE_SYMBOL",
            "mt5_ticket": None,
        },
    )
    assert over["pipeline"]["final_decision"] == "WAIT"
    assert over["pipeline"]["oms"] == "NOT_REACHED"
    assert over["pipeline"]["oms"] != "BLOCK"


def test_missing_from_portfolio_ranked_still_hands_off_valid_scalp() -> None:
    """Live bug: Opportunity 75 + sniper TAKE, ranked miss → generic NO_ELIGIBLE_SETUP."""
    trace = explain_scalp_handoff(
        _take_score(),
        universe=("XAUUSD",),
        in_portfolio_eligible=False,
        portfolio_row=None,
    )
    assert trace.should_hand_off is True
    assert trace.eligibility_reason == "SCALP_ELIGIBLE"


def test_extra_cooldown_is_named_not_generic() -> None:
    trace = explain_scalp_handoff(
        _take_score(),
        portfolio_row={
            "symbol": _GOLD,
            "reject": True,
            "reject_reason": "Symbol cooldown active (32s)",
        },
        in_portfolio_eligible=False,
    )
    assert trace.should_hand_off is False
    assert trace.first_failed_code == "SYMBOL_COOLDOWN_ACTIVE"
    assert trace.eligibility_reason != "NO_ELIGIBLE_SETUP"


def test_scan_abort_reason_uses_named_trace() -> None:
    reason = scan_ineligible_abort_reason(
        {
            "no_eligible_setup": True,
            "first_blocking_gate": "NO_ELIGIBLE_SETUP",
            "eligibility_trace": {
                "first_failed_code": "SYMBOL_COOLDOWN_ACTIVE",
                "eligibility_reason": "SYMBOL_COOLDOWN_ACTIVE",
            },
            "opportunity_ranked": [
                {"symbol": _GOLD, "opportunity_score": 75, "opportunity_threshold": 70}
            ],
        }
    )
    assert reason == "SYMBOL_COOLDOWN_ACTIVE"


def test_current_scan_exposes_failed_predicates() -> None:
    decision = build_current_scan_decision(
        {
            "as_of": "2026-08-27T18:00:00Z",
            "best_symbol": None,
            "eligible_symbols": [],
            "first_blocking_gate": "NO_ELIGIBLE_SETUP",
            "eligibility_trace": {
                "first_failed_code": "SYMBOL_COOLDOWN_ACTIVE",
                "eligibility_status": "FAIL",
                "eligibility_reason": "SYMBOL_COOLDOWN_ACTIVE",
                "failed_predicates": [
                    {
                        "name": "portfolio_extra_reject",
                        "actual": "Symbol cooldown active (32s)",
                        "required": "no extra portfolio reject after score PASS",
                    }
                ],
                "passed_predicates": [{"name": "opportunity_pass"}],
                "optimizer_status": "NOT_REACHED",
            },
            "opportunity_ranked": [_take_score()],
        }
    )
    assert decision["first_blocking_gate"] == "SYMBOL_COOLDOWN_ACTIVE"
    assert decision["eligibility_status"] == "FAIL"
    assert decision["failed_predicates"]
    assert decision["optimizer_status"] in {"NOT_REACHED", "NOT_RUN"}


def test_no_eligible_setup_overlay_does_not_infer_risk_ready() -> None:
    over = _overlay_last_ite_cycle(
        _row_from_score(_take_score()),
        _gold_cycle(
            forwarded_to_oms=False,
            abort_reason="NO_ELIGIBLE_SETUP",
            cycle_outcome="waiting_next_cycle",
            mt5_ticket=None,
        ),
    )
    assert over["pipeline"]["oms"] == "NOT_REACHED"
    assert over["pipeline"]["risk"] == "NOT_REACHED"
    assert over["pipeline"]["safety"] == "NOT_REACHED"
    assert over["pipeline"]["optimizer"] == "NOT_REACHED"


def test_scalping_eligibility_engine_does_not_use_quality_80() -> None:
    from tests.unit.test_institutional_trading_phase_c import _account, _snapshot
    from app.domain.market_structure.enums import TrendDirection

    snap = _snapshot(direction=TrendDirection.DOWN, quality=66)
    conf = ConfluenceResult(
        confidence=65,
        direction=TradeDirection.SELL,
        reasons=("scalp",),
        rejected_rules=(),
        input_hash="elig",
        band="tradable",
        passed=True,
        factors={},
    )
    elig = PositionEligibilityEngine(config=scalping_ite_config()).evaluate(
        snapshot=snap,
        confluence=conf,
        account=_account(),
        risk_allowed=True,
    )
    assert elig.eligible is True
    swing = PositionEligibilityEngine(config=ITEConfig()).evaluate(
        snapshot=snap,
        confluence=conf,
        account=_account(),
        risk_allowed=True,
    )
    assert swing.eligible is False


def test_live_like_take_not_scanner_extra_rejected_on_fresh_health_latch() -> None:
    """Live 26d2c94 payload: Opportunity 76 + sniper TAKE, no execution_health_ok key."""
    from app.domain.institutional_trading.ai_scalping.portfolio_scanner import (
        _row_from_score as scan_row_from_score,
        scan_multi_asset_portfolio,
    )
    from app.domain.institutional_trading.ai_scalping.symbol_state import (
        SymbolStateBook,
    )
    from app.domain.institutional_trading.operations.execution_chain_log import (
        bridge_abort_stage,
        build_execution_handoff,
    )

    book = SymbolStateBook()
    live = _take_score(
        opportunity_score=76,
        ai_confidence=58,
        trade_quality=69,
        spread="0.224",
        spread_score=80,
        score_breakdown={
            "structure": 85,
            "momentum": 78,
            "consensus": 62,
            "regime_fit": 70,
            "price_action": 80,
            "liquidity": 80,
            "volatility": 74,
            "execution_quality": 100,
            "mtf_alignment": 78,
            "rr_quality": 48,
        },
    )
    assert "execution_health_ok" not in live
    row = scan_row_from_score(
        live, book=book, config=DEFAULT_AI_SCALPING_CONFIG
    )
    assert row.execution_health_ok is True
    assert "execution health" not in str(row.reject_reason or "").lower()
    assert row.reject is False

    result = scan_multi_asset_portfolio(
        [live],
        open_positions=0,
        config=replace(DEFAULT_AI_SCALPING_CONFIG, universe=(_GOLD, "XAUUSD")),
        state_book=book,
    )
    assert result.blocked_by_portfolio is False
    assert result.best is not None
    assert str(result.best.get("symbol") or "").upper() == _GOLD
    assert result.best.get("reject") is not True

    none_key = dict(live)
    none_key["execution_health_ok"] = None
    none_row = scan_row_from_score(
        none_key, book=SymbolStateBook(), config=DEFAULT_AI_SCALPING_CONFIG
    )
    assert none_row.execution_health_ok is True
    assert "execution health" not in str(none_row.reject_reason or "").lower()

    poisoned = SymbolStateBook()
    for _ in range(5):
        poisoned.note_reject(_GOLD)
    assert poisoned.get(_GOLD).execution_health_ok is False
    latch_row = scan_row_from_score(
        live, book=poisoned, config=DEFAULT_AI_SCALPING_CONFIG
    )
    assert latch_row.execution_health_ok is False
    assert "execution health" not in str(latch_row.reject_reason or "").lower()
    assert latch_row.reject is False

    trace = explain_scalp_handoff(
        live,
        portfolio_row=latch_row.to_dict(),
        universe=(_GOLD,),
        in_portfolio_eligible=True,
    )
    assert trace.should_hand_off is True
    assert trace.first_failed_code != "EXECUTION_HEALTH_DEGRADED"
    assert trace.optimizer_status == "NOT_REACHED"

    handoff = build_execution_handoff(
        take=True,
        abort_reason="health_degraded",
        forwarded_to_oms=False,
        mt5_ticket=None,
    )
    assert bridge_abort_stage("health_degraded") == "EXECUTION_HEALTH"
    assert handoff["blocking_stage"] == "EXECUTION_HEALTH"
    assert handoff["risk_passed"] is True
    assert handoff["safety_passed"] is True
    assert handoff["optimizer_entered"] is False
    assert handoff["oms_entered"] is False
    assert handoff["oms_forwarded"] is False
    assert handoff["execution_confirmed"] is False
    assert handoff["mt5_ticket"] is None


def test_execution_health_overlay_is_not_oms_and_not_ticket() -> None:
    over = _overlay_last_ite_cycle(
        _row_from_score(_take_score()),
        _gold_cycle(
            forwarded_to_oms=False,
            abort_reason="EXECUTION_HEALTH_DEGRADED",
            execution_blocked={
                "reason_code": "EXECUTION_HEALTH_DEGRADED",
                "human_reason": "New entries paused: critical:gateway",
                "stage": "EXECUTION_HEALTH",
            },
            mt5_ticket=None,
        ),
    )
    pipe = over["pipeline"]
    assert pipe["first_blocker"] == "EXECUTION_HEALTH_DEGRADED"
    assert pipe["blocker_category"] == "EXECUTION_HEALTH"
    assert pipe["risk"] == "READY"
    assert pipe["safety"] == "READY"
    assert pipe["optimizer"] == "NOT_REACHED"
    assert pipe["oms"] == "NOT_REACHED"
    assert pipe["broker"] == "NOT_REACHED"
    assert pipe["mt5"] == "NOT_REACHED"
    assert pipe["forwarded_to_oms"] is False
    assert pipe["ticket"] is None
    assert over.get("execution_state") != "EXECUTED"
    assert over.get("execution_state") != "ORDER_SENT"
