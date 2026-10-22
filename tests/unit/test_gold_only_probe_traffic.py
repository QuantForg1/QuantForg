"""FT-2: Gold-only mode never asks the broker for non-Gold quotes or candles.

Production 2026-10-22 (a0a68230): the gateway still served /quotes/EURUSD,
/quotes/XPDUSD, /quotes/NAS100, ... because the market-universe probes and the
Alpha Engine universe ran before the Gold-only filter.
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

MIXED = ["XAUUSD", "EURUSD", "XPDUSD", "NAS100", "BTCUSD", "XAUUSD_i"]


@pytest.fixture
def gold_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.domain.trading.gold_only.gold_only_enabled", lambda: True)


@pytest.fixture
def multi_market(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.domain.trading.gold_only.gold_only_enabled", lambda: False)


def test_probe_codes_are_gold_only(gold_only: None) -> None:
    from app.application.services.market_universe_service import _gold_only_probe

    assert _gold_only_probe(list(MIXED)) == ["XAUUSD", "XAUUSD_i"]


def test_probe_codes_unchanged_when_multi_market(multi_market: None) -> None:
    from app.application.services.market_universe_service import _gold_only_probe

    assert _gold_only_probe(list(MIXED)) == MIXED


def test_alpha_universe_is_gold_only(gold_only: None) -> None:
    from app.application.services.institutional_alpha_engine import alpha_scan_universe
    from app.domain.institutional_trading.alpha_engine.config import (
        InstitutionalAlphaConfig,
    )

    assert alpha_scan_universe(InstitutionalAlphaConfig()) == ("XAUUSD",)


def test_alpha_scan_never_queries_non_gold(
    gold_only: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.application.services.institutional_alpha_engine as mod

    queried: list[str] = []

    def facts(sym: str, **_: Any) -> Any:
        queried.append(sym)
        raise RuntimeError("stop after recording")

    monkeypatch.setattr(mod, "_facts_from_runtime_symbol", facts)
    with pytest.raises(RuntimeError):
        mod.run_alpha_scan()
    assert queried == ["XAUUSD"]
