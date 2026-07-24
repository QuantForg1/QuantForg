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
    selected, skipped = select_full_mode_symbol(
        adapter, ["XAUUSD", "EURUSD", "GBPUSD"]
    )
    assert skipped == ["XAUUSD"]
    assert selected == "EURUSD"


@pytest.mark.unit
def test_resolve_prefers_ranked_full_mode() -> None:
    adapter = _Adapter({"XAUUSD": "closeonly", "EURUSD": "full"})
    selected, skipped = resolve_executable_symbol(
        adapter,
        preferred="XAUUSD",
        alpha_ranking=[{"symbol": "EURUSD", "opportunity_score": 90}],
    )
    assert "XAUUSD" in skipped
    assert selected == "EURUSD"


@pytest.mark.unit
def test_read_trade_mode_closeonly() -> None:
    adapter = _Adapter({"XAUUSD": "closeonly"})
    assert read_trade_mode(adapter, "XAUUSD") == "closeonly"


@pytest.mark.unit
def test_candidates_include_universe() -> None:
    rows = build_opportunity_candidates(
        preferred="XAUUSD",
        plane=SimpleNamespace(allowed_symbols=("NAS100",)),
    )
    assert rows[0] == "XAUUSD"
    assert "NAS100" in rows
    assert "EURUSD" in rows
