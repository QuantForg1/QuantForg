"""Strategy attribution binds pass a datetime for opened_at (timestamptz)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from app.domain.institutional_trading.ai_scalping.strategies import (
    attribution_store as mod,
)


def test_bind_fill_sends_datetime_to_postgres(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = mod.StrategyAttributionStore(path=tmp_path / "attr.json")
    calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(store, "_use_postgres", lambda: True)
    monkeypatch.setattr(store, "_ensure_schema", lambda: None)

    import app.infrastructure.persistence.direct_postgres as dp

    monkeypatch.setattr(dp, "execute", lambda _q, *a: calls.append(a))
    store.bind_fill(
        strategy_id="xau_sniper_v2",
        engine="ite",
        symbol="XAUUSD",
        ticket=709187428,
        volume=0.01,
        broker_login=12439799,
    )
    assert calls, "postgres upsert was not attempted"
    assert all(isinstance(args[-1], datetime) for args in calls)
    assert calls[0][-1].tzinfo is not None
