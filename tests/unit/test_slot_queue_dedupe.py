"""Capacity queue must not enqueue duplicate broker/slot requests."""

from __future__ import annotations

from pathlib import Path

from services.mt5_worker_agent import slot_queue


def test_enqueue_dedupes_same_broker_slot(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("QF_MT5_SLOT_ROOT", str(tmp_path))
    slot_queue._QUEUE.clear()
    first = slot_queue.enqueue(
        broker_slug="xm", environment="demo", slot_preference="demo-a"
    )
    second = slot_queue.enqueue(
        broker_slug="xm", environment="demo", slot_preference="demo-a"
    )
    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert second["position"] == 1
    assert slot_queue.snapshot()["depth"] == 1
