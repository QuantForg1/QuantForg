"""Stale gateway heartbeat must alert (16 Nov 2026: frozen 8 h, no alert)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

from app.application.services import operator_alerts as oa

NOW = datetime(2026, 11, 16, 19, 0, tzinfo=UTC)


def _adapter(beat: Any) -> SimpleNamespace:
    def gateway_health() -> dict[str, Any]:
        if isinstance(beat, Exception):
            raise beat
        return {"mt5": {"last_heartbeat_at": beat}}

    return SimpleNamespace(client=SimpleNamespace(gateway_health=gateway_health))


def test_age_from_iso_heartbeat() -> None:
    beat = (NOW - timedelta(hours=8)).isoformat()
    assert oa.gateway_heartbeat_age_seconds(_adapter(beat), now_utc=NOW) == 8 * 3600


def test_unreadable_heartbeat_is_none() -> None:
    assert oa.gateway_heartbeat_age_seconds(_adapter(None), now_utc=NOW) is None
    assert oa.gateway_heartbeat_age_seconds(_adapter("x"), now_utc=NOW) is None
    err = _adapter(RuntimeError("down"))
    assert oa.gateway_heartbeat_age_seconds(err, now_utc=NOW) is None
    assert oa.gateway_heartbeat_age_seconds(SimpleNamespace(), now_utc=NOW) is None


class _Alerter:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def alert(self, kind: str, text: str, **_: Any) -> bool:
        self.sent.append((kind, text))
        return True


def _watch(beat_holder: dict[str, str], clock: list[float]) -> tuple[Any, _Alerter]:
    alerter = _Alerter()
    adapter = SimpleNamespace(
        client=SimpleNamespace(
            gateway_health=lambda: {"mt5": {"last_heartbeat_at": beat_holder["b"]}}
        )
    )
    watch = oa.OperatorWatch(
        adapter=adapter,
        alerter=alerter,  # type: ignore[arg-type]
        journal=SimpleNamespace(),  # type: ignore[arg-type]
        clock=lambda: clock[0],
        now_utc=lambda: NOW,
    )
    return watch, alerter


def test_stale_heartbeat_alerts_once_then_recovers() -> None:
    beat = {"b": (NOW - timedelta(hours=8)).isoformat()}
    clock = [0.0]
    watch, alerter = _watch(beat, clock)
    watch._heartbeat_watch(now=0.0, utc=NOW)
    assert alerter.sent == []  # grace period before alerting
    clock[0] = oa.OFFLINE_ALERT_S + 1
    watch._heartbeat_watch(now=clock[0], utc=NOW)
    watch._heartbeat_watch(now=clock[0] + 60, utc=NOW)
    assert [k for k, _ in alerter.sent] == ["GATEWAY HEARTBEAT STALE"]
    assert "480 min" in alerter.sent[0][1]
    beat["b"] = (NOW - timedelta(seconds=5)).isoformat()
    watch._heartbeat_watch(now=clock[0] + 120, utc=NOW)
    assert alerter.sent[-1][0] == "GATEWAY HEARTBEAT RECOVERED"


def test_fresh_heartbeat_never_alerts() -> None:
    beat = {"b": (NOW - timedelta(seconds=10)).isoformat()}
    watch, alerter = _watch(beat, [0.0])
    for t in (0.0, 500.0, 1000.0):
        watch._heartbeat_watch(now=t, utc=NOW)
    assert alerter.sent == []
