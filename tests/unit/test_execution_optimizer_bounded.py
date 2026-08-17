"""Phase E — bounded execution optimizer: hard block vs soft wait."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.domain.institutional_trading.ai_scalping import execution_optimizer as eo
from app.domain.institutional_trading.ai_scalping.execution_optimizer import (
    clear_optimizer_defers,
    evaluate_execution_moment,
    should_defer_submit,
)
from app.domain.institutional_trading.ai_scalping.smart_order_routing import (
    estimate_smart_routing,
)


def _buy(symbol: str = "EURUSD") -> SimpleNamespace:
    return SimpleNamespace(
        action=SimpleNamespace(value="BUY"),
        symbol=symbol,
        input_hash="phase-e-opt",
    )


def _acceptable_account() -> SimpleNamespace:
    return SimpleNamespace(atr=1.2, mid_price=2300.0)


def _calm_snapshot() -> SimpleNamespace:
    return SimpleNamespace(entry_closes=(2300.0, 2300.05, 2300.04))


def _force_better_tick_required(monkeypatch: pytest.MonkeyPatch) -> None:
    """Quality < defer_below and worsening spread → WAIT_BOUNDED until bound."""
    monkeypatch.setattr(
        eo,
        "_spread_trend",
        lambda _sym: {"samples": 8, "trend": "worsening", "score": 20},
    )
    monkeypatch.setattr(
        eo,
        "_tick_momentum",
        lambda _snap: {"samples": 3, "momentum": "spike", "score": 20},
    )
    monkeypatch.setattr(
        eo,
        "_micro_volatility",
        lambda _s, _a: {"atr_pct": 0.05, "band": "compression", "score": 20},
    )
    monkeypatch.setattr(
        eo, "_latency_score", lambda: {"avg_latency_ms": 3000, "score": 20}
    )
    monkeypatch.setattr(
        eo,
        "_broker_response_score",
        lambda: {"fill_rate": None, "reject_rate": None, "score": 20},
    )
    monkeypatch.setattr(
        eo, "_slippage_history_score", lambda: {"avg_slippage": None, "score": 20}
    )
    monkeypatch.setattr(eo, "_optimizer_bounds", lambda: (2, 60_000, 45, 40))


@pytest.fixture(autouse=True)
def _reset_optimizer() -> None:
    clear_optimizer_defers()
    yield
    clear_optimizer_defers()


def _force_current_tick_acceptable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        eo,
        "_spread_trend",
        lambda _sym: {"samples": 8, "trend": "stable", "score": 70},
    )
    monkeypatch.setattr(
        eo,
        "_tick_momentum",
        lambda _snap: {"samples": 3, "momentum": "calm", "score": 75},
    )
    monkeypatch.setattr(
        eo,
        "_micro_volatility",
        lambda _s, _a: {"atr_pct": 0.2, "band": "normal", "score": 75},
    )
    monkeypatch.setattr(
        eo, "_latency_score", lambda: {"avg_latency_ms": 120, "score": 85}
    )
    monkeypatch.setattr(
        eo,
        "_broker_response_score",
        lambda: {"fill_rate": 90, "reject_rate": 2, "score": 85},
    )
    monkeypatch.setattr(
        eo, "_slippage_history_score", lambda: {"avg_slippage": 0.02, "score": 85}
    )


@pytest.mark.unit
def test_current_tick_acceptable_executes_now(monkeypatch: pytest.MonkeyPatch) -> None:
    _force_current_tick_acceptable(monkeypatch)
    out = evaluate_execution_moment(
        symbol="EURUSD",
        decision=_buy(),
        snapshot=_calm_snapshot(),
        account=_acceptable_account(),
        decision_key="tick-ok",
    )
    assert out["final_state"] == "EXECUTE_NOW"
    assert out["reason"] == "all_hard_gates_pass_current_tick_acceptable"
    assert out["current_tick_acceptable"] is True
    assert should_defer_submit(out) is False
    assert out["defer_count"] == 0
    assert out["remaining_wait_ms"] == 0
    assert out["forced_trades"] is False


@pytest.mark.unit
def test_marginal_improvement_expected_wait_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _force_better_tick_required(monkeypatch)
    out = evaluate_execution_moment(
        symbol="XAUUSD",
        decision=_buy("XAUUSD"),
        snapshot=_calm_snapshot(),
        account=_acceptable_account(),
        decision_key="wait-1",
    )
    assert out["final_state"] == "WAIT_BOUNDED"
    assert out["reason"] in {
        "spread_improvement_expected",
        "wait_for_better_tick_within_limits",
    }
    assert should_defer_submit(out) is True
    assert out["defer_count"] >= 1
    assert out["remaining_wait_ms"] > 0
    assert out["max_defer_attempts"] == 2
    assert out["max_defer_duration_ms"] == 60_000


@pytest.mark.unit
def test_wait_duration_reached_executes_if_hard_gates_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _force_better_tick_required(monkeypatch)
    monkeypatch.setattr(eo, "_optimizer_bounds", lambda: (2, 2500, 45, 40))
    key = "dur-1"
    started = (datetime.now(UTC) - timedelta(seconds=5)).isoformat().replace(
        "+00:00", "Z"
    )
    with eo._LOCK:
        eo._DEFER_COUNTS[key] = {"count": 1, "first_at": started}
    out = evaluate_execution_moment(
        symbol="EURUSD",
        decision=_buy(),
        snapshot=_calm_snapshot(),
        account=_acceptable_account(),
        decision_key=key,
    )
    assert out["final_state"] == "EXECUTE_NOW"
    assert out["reason"] == "max_defer_duration_reached_submit"
    assert should_defer_submit(out) is False


@pytest.mark.unit
def test_wait_attempt_limit_reached_executes_if_hard_gates_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _force_better_tick_required(monkeypatch)
    last = None
    for _ in range(5):
        last = evaluate_execution_moment(
            symbol="EURUSD",
            decision=_buy(),
            snapshot=_calm_snapshot(),
            account=_acceptable_account(),
            decision_key="attempts-1",
        )
    assert last is not None
    assert last["final_state"] == "EXECUTE_NOW"
    assert last["reason"] == "max_defers_reached_submit_anyway"
    assert last["defer_count"] <= last["max_defer_attempts"]
    assert should_defer_submit(last) is False


@pytest.mark.unit
@pytest.mark.parametrize(
    "reason",
    [
        "STALE_MARKET_DATA",
        "UNACCEPTABLE_SPREAD",
        "RISK_BLOCK",
        "RECONCILIATION_REQUIRED",
        "KILL_SWITCH",
        "MIN_LOT_CONSTRAINT",
        "PORTFOLIO_RISK_LIMIT",
        "NO_ELIGIBLE_SETUP",
    ],
)
def test_hard_gate_during_or_before_wait_blocks(reason: str) -> None:
    out = evaluate_execution_moment(
        symbol="EURUSD",
        decision=_buy(),
        snapshot=_calm_snapshot(),
        account=_acceptable_account(),
        decision_key=f"block-{reason}",
        hard_block_reason=reason,
    )
    assert out["final_state"] == "BLOCK"
    assert out["reason"] == reason
    assert should_defer_submit(out) is False
    assert out["remaining_wait_ms"] == 0


@pytest.mark.unit
def test_hard_gates_fail_flag_blocks() -> None:
    out = evaluate_execution_moment(
        symbol="EURUSD",
        decision=_buy(),
        snapshot=_calm_snapshot(),
        account=_acceptable_account(),
        decision_key="gates-fail",
        hard_gates_pass=False,
    )
    assert out["final_state"] == "BLOCK"
    assert out["reason"] == "HARD_GATE_FAILED"
    assert should_defer_submit(out) is False


@pytest.mark.unit
def test_optimizer_never_remains_waiting_forever(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _force_better_tick_required(monkeypatch)
    monkeypatch.setattr(eo, "_optimizer_bounds", lambda: (2, 500, 45, 40))
    states = []
    for i in range(8):
        if i == 2:
            started = (datetime.now(UTC) - timedelta(seconds=2)).isoformat().replace(
                "+00:00", "Z"
            )
            with eo._LOCK:
                row = eo._DEFER_COUNTS.get("forever") or {}
                row["first_at"] = started
                eo._DEFER_COUNTS["forever"] = row
        out = evaluate_execution_moment(
            symbol="EURUSD",
            decision=_buy(),
            snapshot=_calm_snapshot(),
            account=_acceptable_account(),
            decision_key="forever",
        )
        states.append(out["final_state"])
    assert "WAIT_BOUNDED" in states
    assert states[-1] == "EXECUTE_NOW"
    assert "WAITING" not in states


@pytest.mark.unit
def test_sor_does_not_duplicate_wait_when_optimizer_executes() -> None:
    sor = estimate_smart_routing(
        symbol="EURUSD",
        side="BUY",
        spread=0.12,
        optimizer={
            "execution_quality_score": 40,
            "recommendation": "PROCEED",
            "final_state": "EXECUTE_NOW",
        },
    )
    assert sor["recommendation"] == "SUBMIT"
    assert sor["ai_decision_unchanged"] is True
    assert sor["forced_trades"] is False


@pytest.mark.unit
def test_config_exposes_optimizer_bounds() -> None:
    from app.domain.institutional_trading.ai_scalping.config import (
        DEFAULT_AI_SCALPING_CONFIG,
    )

    cfg = DEFAULT_AI_SCALPING_CONFIG
    assert 1 <= cfg.optimizer_max_defer_attempts <= 5
    assert 500 <= cfg.optimizer_max_defer_duration_ms <= 8_000
    payload = cfg.to_dict()["execution_optimizer"]
    assert payload["max_defer_attempts"] == cfg.optimizer_max_defer_attempts
    assert payload["defer_below_quality"] <= payload["proceed_quality"]
