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
    from app.domain.institutional_trading.ai_scalping.strategies import (
        attribution_store as mod,
    )

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


def test_ite_comment_does_not_invent_ite_primary_strategy_id() -> None:
    meta = merge_position_metadata(
        snapshot={"symbol": "XAUUSD"},
        comment="ite:v1:S:deadbeefcafe",
        live_meta={},
    )
    assert meta.get("attribution_engine") == "ite"
    assert meta.get("strategy_id") in {None, ""}


def test_bind_fill_rejects_fabricated_ite_primary(tmp_path: Path) -> None:
    store = StrategyAttributionStore(path=tmp_path / "attr_reject.json")
    store.bind_fill(
        strategy_id="ite_primary",
        engine="ite",
        ticket=444,
        position_id=444,
    )
    assert store.resolve(ticket=444) is None
    store.bind_fill(
        strategy_id="smc_scalping",
        engine="soe",
        ticket=444,
        position_id=444,
        contributors=["momentum_scalping", "trend_continuation"],
    )
    hit = store.resolve(ticket=444)
    assert hit is not None
    assert hit.strategy_id == "smc_scalping"
    assert "momentum_scalping" in hit.contributors
    assert hit.attribution_confidence == "bound_five_pack"


def test_live_fill_strategy_survives_sl_comment_overwrite() -> None:
    meta = merge_position_metadata(
        snapshot={"symbol": "XAUUSD", "ticket": 333, "position_id": 333},
        comment="[sl 3920.000]",
        live_meta={
            "ticket": 333,
            "position_id": 333,
            "strategy_id": "momentum_scalping",
            "strategy_name": "Momentum Scalping",
            "attribution_engine": "soe",
            "comment_hash": "deadbeef",
        },
        ticket=333,
        position_id=333,
    )
    assert meta.get("strategy_id") == "momentum_scalping"
    assert meta.get("attribution_engine") == "soe"
