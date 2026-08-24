"""Risk-blocked cycles must not replay a prior OMS / MT5 ticket.

Observability only — does not submit, change Risk, or send orders.
"""

from __future__ import annotations

from threading import Lock
from types import SimpleNamespace

import pytest

from app.application.services.institutional_ite_runtime import (
    InstitutionalIteRuntime,
    ShadowCycleResult,
)
from app.domain.institutional_trading.operations.execution_chain_log import (
    CHAIN_PASS,
    NOT_ATTEMPTED,
    classify_post_ai_execution_chain,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

PRIOR_TICKET = 562442610


def _decision(*, eligible: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        action=SimpleNamespace(value="BUY"),
        eligibility=SimpleNamespace(
            eligible=eligible,
            rejection_reasons=("MIN_LOT_CONSTRAINT",) if not eligible else (),
        ),
        risk_reasons=("MIN_LOT_CONSTRAINT",) if not eligible else (),
    )


def _stale_bridge() -> SimpleNamespace:
    return SimpleNamespace(
        aborted=False,
        abort_reason=None,
        forwarded_to_oms=True,
        oms_result=SimpleNamespace(
            message="done",
            retcode=10009,
            order_ticket=PRIOR_TICKET,
            deal_ticket=PRIOR_TICKET,
        ),
        journal_entry=SimpleNamespace(comment="filled"),
    )


def test_risk_block_does_not_claim_oms_or_ticket() -> None:
    out = classify_post_ai_execution_chain(
        forwarded_to_oms=False,
        may_submit_oms=False,
        blocking_stage="RISK",
        ticket=PRIOR_TICKET,
        retcode=10009,
    )
    assert out["oms_submit"] == NOT_ATTEMPTED
    assert out["submitting_order"] is False
    assert out["mt5_gateway"] == NOT_ATTEMPTED
    assert out["mt5_accepted"] is False
    assert out["ticket"] is None
    assert out["retcode"] is None
    assert out["forwarded_to_oms"] is False


def test_stale_ticket_dropped_when_this_cycle_not_forwarded() -> None:
    out = classify_post_ai_execution_chain(
        forwarded_to_oms=True,
        ticket=PRIOR_TICKET,
        retcode=10009,
        this_cycle_forwarded=False,
    )
    assert out["ticket"] is None
    assert out["oms_submit"] == NOT_ATTEMPTED
    assert out["mt5_accepted"] is False


def test_successful_fill_still_reports_oms_gateway_mt5() -> None:
    out = classify_post_ai_execution_chain(
        forwarded_to_oms=True,
        may_submit_oms=True,
        blocking_stage=None,
        ticket=PRIOR_TICKET,
        retcode=10009,
        this_cycle_forwarded=True,
    )
    assert out["oms_submit"] == CHAIN_PASS
    assert out["submitting_order"] is True
    assert out["mt5_gateway"] == CHAIN_PASS
    assert out["mt5_accepted"] is True
    assert out["ticket"] == PRIOR_TICKET
    assert out["retcode"] == 10009
    assert out["forwarded_to_oms"] is True


def test_unsubmitted_cycle_clears_stale_bridge() -> None:
    runtime = SimpleNamespace(
        _lock=Lock(),
        _last_bridge_result=_stale_bridge(),
        _last_cycle=None,
        _last_decision=None,
        _cycles=1,
    )
    result = ShadowCycleResult(
        ok=True,
        trace_id="blocked",
        mode="LIVE",
        decision_action="BUY",
        forwarded_to_oms=False,
        cycle_outcome="execution_contract",
        abort_reason="MIN_LOT_CONSTRAINT",
    )
    with runtime._lock:
        runtime._last_cycle = result
        runtime._last_decision = _decision()
        runtime._cycles += 1
        runtime._last_bridge_result = None
    assert runtime._last_bridge_result is None
    assert runtime._last_cycle.forwarded_to_oms is False
    assert runtime._last_cycle.abort_reason == "MIN_LOT_CONSTRAINT"


def test_blocked_cycle_log_does_not_print_stale_ticket(
    capsys: pytest.CaptureFixture[str],
) -> None:
    InstitutionalIteRuntime._log_post_ai_execution_chain(
        SimpleNamespace(),
        decision=_decision(eligible=False),
        bridge_result=_stale_bridge(),
        execution_enabled=True,
        force_shadow=False,
        this_cycle_forwarded=False,
        may_submit_oms=False,
        blocking_stage="RISK",
    )
    text = capsys.readouterr().out
    assert str(PRIOR_TICKET) not in text
    assert "NOT_ATTEMPTED" in text
    assert "Submitting Order" not in text
    assert "MT5 Accepted" not in text
    assert "OMS Submit" in text
    assert "filled" not in text


def test_successful_cycle_log_still_prints_ticket(
    capsys: pytest.CaptureFixture[str],
) -> None:
    InstitutionalIteRuntime._log_post_ai_execution_chain(
        SimpleNamespace(),
        decision=_decision(eligible=True),
        bridge_result=_stale_bridge(),
        execution_enabled=True,
        force_shadow=False,
        this_cycle_forwarded=True,
        may_submit_oms=True,
    )
    text = capsys.readouterr().out
    assert str(PRIOR_TICKET) in text
    assert "Submitting Order" in text
    assert "MT5 Accepted" in text
    assert "NOT_ATTEMPTED" not in text
