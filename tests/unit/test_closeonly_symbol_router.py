"""Close-only symbol router — skip and rotate to full-mode opportunities."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.application.services.closeonly_symbol_router import (
    build_opportunity_candidates,
    read_trade_mode,
    resolve_executable_symbol,
    select_full_mode_symbol,
)


class _Info:
    def __init__(self, trade_mode: str) -> None:
        self.trade_mode = trade_mode


class _Adapter:
    def __init__(self, modes: dict[str, str]) -> None:
        self.modes = modes

    def symbol_info(self, symbol: str) -> _Info:
        return _Info(self.modes.get(symbol.upper(), "full"))


@pytest.mark.unit
def test_skips_closeonly_and_picks_next_full() -> None:
    adapter = _Adapter({"XAUUSD": "closeonly", "EURUSD": "full", "GBPUSD": "full"})
    selected, skipped = select_full_mode_symbol(adapter, ["XAUUSD", "EURUSD", "GBPUSD"])
    assert skipped == ["XAUUSD"]
    assert selected == "EURUSD"


@pytest.mark.unit
def test_resolve_prefers_ranked_full_mode() -> None:
    """Without a preferred desk, alpha ranking may supply the next full-mode symbol."""
    adapter = _Adapter({"XAUUSD": "closeonly", "EURUSD": "full"})
    selected, skipped = resolve_executable_symbol(
        adapter,
        preferred=None,
        alpha_ranking=[
            {"symbol": "XAUUSD", "opportunity_score": 95},
            {"symbol": "EURUSD", "opportunity_score": 90},
        ],
    )
    assert "XAUUSD" in skipped
    assert selected == "EURUSD"


@pytest.mark.unit
@pytest.mark.trading_core
def test_preferred_does_not_fall_through_broker_catalogue() -> None:
    """Live defect: preferred NDXUSD skipped → EURCAD catalogue steal."""
    rows = build_opportunity_candidates(
        preferred="NDXUSD",
        plane=SimpleNamespace(allowed_symbols=("EURCAD", "EURCHF", "NAS100")),
        alpha_ranking=[{"symbol": "EURUSD", "opportunity_score": 90}],
    )
    assert rows[0] == "NDXUSD"
    assert "EURCAD" not in rows
    assert "EURCHF" not in rows
    assert "EURUSD" not in rows
    assert "NAS100" not in rows


@pytest.mark.unit
def test_read_trade_mode_closeonly() -> None:
    adapter = _Adapter({"XAUUSD": "closeonly"})
    assert read_trade_mode(adapter, "XAUUSD") == "closeonly"


@pytest.mark.unit
def test_candidates_without_preferred_include_universe() -> None:
    rows = build_opportunity_candidates(
        preferred=None,
        plane=SimpleNamespace(allowed_symbols=("NAS100",)),
    )
    assert "NAS100" in rows
    assert "EURUSD" in rows


@pytest.mark.unit
@pytest.mark.trading_core
def test_preferred_closeonly_does_not_steal_fx_from_catalogue() -> None:
    adapter = _Adapter(
        {"NDXUSD": "closeonly", "NDXUSD_I": "closeonly", "EURCAD": "full"}
    )
    selected, skipped = resolve_executable_symbol(
        adapter,
        preferred="NDXUSD",
        plane=SimpleNamespace(allowed_symbols=("EURCAD", "EURCHF")),
        alpha_ranking=[{"symbol": "EURUSD"}],
    )
    assert "NDXUSD" in skipped
    assert selected is None
    assert "EURCAD" not in skipped
