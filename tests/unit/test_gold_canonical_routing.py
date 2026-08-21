"""Gold-only routing must stay on XAUUSD_i. Never fallback to unsuffixed XAUUSD."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.application.services.closeonly_symbol_router import (
    build_opportunity_candidates,
    resolve_executable_symbol,
    select_full_mode_symbol,
)
from app.application.services.signal_center_service import _row_from_score
from app.domain.institutional_trading.management.class_policy import (
    HOLD_ABSOLUTE_MAX_HOLD_MINUTES,
    HOLD_BREAK_EVEN_AT_R,
    SCALP_ABSOLUTE_MAX_HOLD_MINUTES,
    SCALP_BREAK_EVEN_AT_R,
    resolve_class_management,
)
from app.domain.institutional_trading.operations.fast_decision_path import (
    classify_candidate_outcome,
)
from app.domain.trading.gold_only import (
    CANONICAL_GOLD_BROKER_DISPLAY,
    canonical_gold_execution_symbol,
    is_bare_gold_symbol,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


@pytest.fixture
def gold_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.domain.trading.gold_only.gold_only_enabled",
        lambda: True,
    )


class _RaisingBareGoldAdapter:
    """503s unsuffixed XAUUSD the way live Weltrade does."""

    def symbol_info(self, symbol: str) -> SimpleNamespace:
        code = (symbol or "").strip().upper()
        if code in {"XAUUSD", "GOLD", "XAUUSDM"}:
            raise RuntimeError(f"503 symbol unavailable for {code}")
        return SimpleNamespace(trade_mode="full")


def test_preferred_xauusd_i_stays_xauusd_i(gold_only: None) -> None:
    rows = build_opportunity_candidates(preferred="XAUUSD_i")
    assert rows == ["XAUUSD_i"]
    assert "XAUUSD" not in rows or rows == ["XAUUSD_i"]
    assert all(not is_bare_gold_symbol(s) for s in rows)


def test_mixed_xauusd_and_suffix_collapses_to_canonical(gold_only: None) -> None:
    rows = build_opportunity_candidates(
        preferred="XAUUSD",
        alpha_ranking=[{"symbol": "XAUUSD_i"}, {"symbol": "XAUUSD"}],
        plane=SimpleNamespace(allowed_symbols=("XAUUSD", "EURUSD")),
    )
    assert rows == [CANONICAL_GOLD_BROKER_DISPLAY]
    assert "XAUUSD" not in rows


def test_xauusd_503_does_not_win_when_xauusd_i_is_authoritative(
    gold_only: None,
) -> None:
    selected, _skipped = resolve_executable_symbol(
        _RaisingBareGoldAdapter(),
        preferred="XAUUSD_i",
        alpha_ranking=[{"symbol": "XAUUSD"}],
        plane=SimpleNamespace(allowed_symbols=("XAUUSD", "XAUUSD_i")),
        direction="BUY",
    )
    assert selected == "XAUUSD_i"
    assert selected != "XAUUSD"
    assert "XAUUSD" not in {selected}


def test_resolver_never_returns_unsuffixed_xauusd(gold_only: None) -> None:
    selected, _skipped = select_full_mode_symbol(
        _RaisingBareGoldAdapter(),
        ["XAUUSD", "XAUUSD_i", "EURUSD"],
        direction="BUY",
    )
    assert selected == "XAUUSD_i"
    assert selected != "XAUUSD"


def test_canonical_helper_never_returns_bare() -> None:
    assert canonical_gold_execution_symbol("XAUUSD_i") == "XAUUSD_i"
    assert canonical_gold_execution_symbol("XAUUSD_I") == "XAUUSD_i"
    assert canonical_gold_execution_symbol("XAUUSD") == "XAUUSD_i"
    assert not is_bare_gold_symbol(canonical_gold_execution_symbol(None))


def test_buy_survives_symbol_routing_block() -> None:
    out = classify_candidate_outcome(
        abort_reason="GATEWAY_MARKET_DATA_UNAVAILABLE: GET /quotes/XAUUSD 503",
        failed_reasons=("trade_mode_lookup_failed",),
        cycle_outcome="blocked",
        decision_action="BUY",
    )
    assert out["fault_code"] == "SYMBOL_ROUTING_BLOCK"
    assert out["fault_code"] != "DIRECTION_NONE"


def test_buy_survives_risk_block_in_signal_center() -> None:
    row = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "BUY",
            "trade_quality": 78,
            "ai_confidence": 67,
            "reject": True,
            "reject_reason": "RISK_BLOCK: daily loss or size rejected",
        }
    )
    assert row["direction"] == "BUY"
    assert row["block_code"] == "RISK_BLOCK"
    assert "NONE" not in str(row["direction"])


def test_scalp_and_hold_management_profiles() -> None:
    scalp = resolve_class_management("SCALP")
    hold = resolve_class_management("HOLD")
    unknown = resolve_class_management("")
    assert scalp.break_even_at_r == SCALP_BREAK_EVEN_AT_R
    assert scalp.absolute_max_hold_minutes == SCALP_ABSOLUTE_MAX_HOLD_MINUTES
    assert hold.break_even_at_r == HOLD_BREAK_EVEN_AT_R
    assert hold.absolute_max_hold_minutes == HOLD_ABSOLUTE_MAX_HOLD_MINUTES
    assert unknown.profile_name == "unknown_safe_fallback"
    assert unknown.trade_class != "SCALP"
    assert unknown.trade_class != "HOLD"
