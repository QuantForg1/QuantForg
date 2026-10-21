"""Daily-loss stop and Live Trading Control state are GLOBAL safety blockers."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.domain.institutional_trading.auto_trading import (
    GLOBAL_SAFETY_CONDITION_KEYS,
    safety_blocks_decision,
    safety_failure_scope,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _result(*failed: str) -> SimpleNamespace:
    conditions = [SimpleNamespace(key=k, passed=False) for k in failed]
    conditions.append(SimpleNamespace(key="ops_mode", passed=True))
    return SimpleNamespace(allowed=not failed, conditions=conditions)


@pytest.mark.parametrize("key", ["daily_loss", "live_trading_state"])
def test_daily_loss_and_live_state_abort_the_whole_universe(key: str) -> None:
    assert key in GLOBAL_SAFETY_CONDITION_KEYS
    result = _result(key)
    assert safety_failure_scope(result) == "global"
    assert safety_blocks_decision(result) is True


@pytest.mark.parametrize(
    "key", ["max_open_positions", "risk_engine", "margin_available"]
)
def test_capacity_misses_still_scan_continue(key: str) -> None:
    assert safety_failure_scope(_result(key)) == "scan_continue"


def test_result_without_conditions_fails_closed_as_global() -> None:
    assert safety_failure_scope(SimpleNamespace(allowed=False)) == "global"


def test_allowed_result_is_allowed() -> None:
    assert safety_failure_scope(_result()) == "allowed"
