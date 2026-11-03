"""Ticket-keyed strategy attribution survives SL/TP comment overwrite."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.domain.institutional_trading.ai_scalping.strategies.attribution_store import (
    StrategyAttributionStore,
)
from app.domain.institutional_trading.management.class_policy import (
    merge_position_metadata,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def test_bind_resolve_and_partial_close(tmp_path: Path) -> None:
    store = StrategyAttributionStore(path=tmp_path / "attr.json")
    store.bind_fill(
        strategy_id="momentum_scalping",
        engine="soe",
        strategy_name="Momentum Scalping",
        symbol="XAUUSD",
        ticket=111,
        position_id=111,
        volume=0.02,
    )
    hit = store.resolve(ticket=111)
    assert hit is not None
    assert hit.strategy_id == "momentum_scalping"
    assert hit.engine == "soe"

    # Partial close keeps binding.
    store.note_partial_close(ticket=111, position_id=111, closed_volume=0.01)
    assert store.resolve(ticket=111) is not None

    # Flat clears binding.
    store.note_partial_close(
        ticket=111, position_id=111, closed_volume=0.01, fully_closed=True
    )
    assert store.resolve(ticket=111) is None


def test_merge_metadata_prefers_ticket_store_over_sl_comment(tmp_path: Path) -> None:
    store = StrategyAttributionStore(path=tmp_path / "attr2.json")
    store.bind_fill(
        strategy_id="trend_continuation",
        engine="soe",
        ticket=222,
        position_id=222,
    )
    # Monkeypatch global store used by merge — bind via direct resolve path
    # by injecting ticket into snapshot that merge looks up through store.
    import app.domain.institutional_trading.ai_scalping.strategies.attribution_store as mod

    previous = mod._STORE
    mod._STORE = store
    try:
        meta = merge_position_metadata(
            snapshot={"symbol": "XAUUSD", "comment": "[sl 3920.000]"},
            comment="[sl 3920.000]",
            live_meta={},
            ticket=222,
            position_id=222,
        )
        assert meta.get("strategy_id") == "trend_continuation"
        assert meta.get("attribution_engine") == "soe"
    finally:
        mod._STORE = previous


def test_m1_comment_engine_tag_without_inventing_five_pack_id() -> None:
    meta = merge_position_metadata(
        snapshot={"symbol": "XAUUSD"},
        comment="m1:mom-buy-3922.053",
        live_meta={},
    )
    assert meta.get("attribution_engine") == "m1"
    assert meta.get("strategy_id") == "m1_micro"
