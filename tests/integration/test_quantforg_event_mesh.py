"""Integration — QEM is read-only and never modifies production."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.application.services import quantforg_event_mesh as svc
from app.domain.quantforg_event_mesh.models import EVENT_SOURCES, ISOLATION_FLAGS
from app.domain.quantforg_event_mesh.platform import QuantForgEventMesh
from app.domain.quantforg_event_mesh.store import QemStore
from app.main import _ROUTER_SPECS

pytestmark = pytest.mark.integration


def test_router_registered() -> None:
    assert "quantforg_event_mesh" in {n for n, _ in _ROUTER_SPECS}


def test_isolation_flags() -> None:
    assert ISOLATION_FLAGS["executes_trades"] is False
    assert ISOLATION_FLAGS["modifies_production"] is False
    assert ISOLATION_FLAGS["modifies_strategies"] is False
    assert ISOLATION_FLAGS["modifies_risk"] is False
    assert ISOLATION_FLAGS["approves_releases"] is False
    assert ISOLATION_FLAGS["event_distribution_read_only"] is True
    assert ISOLATION_FLAGS["events_immutable"] is True


def test_service_dashboard_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    qem = QuantForgEventMesh(store=QemStore(path=tmp_path / "qem.json"))
    monkeypatch.setattr("app.domain.quantforg_event_mesh._QEM", qem)
    monkeypatch.setattr(svc, "get_qem", lambda: qem)
    monkeypatch.setattr(
        "app.domain.quantforg_event_mesh.platform.gather_event_sources",
        lambda: {
            "sources": {s: {} for s in EVENT_SOURCES},
            "availability": {s: False for s in EVENT_SOURCES},
            "source_count": 0,
            "read_only": True,
        },
    )
    payload = svc.build_qem_dashboard()
    assert payload["never_executes_trades"] is True
    assert payload["never_modifies_production"] is True
    assert payload["never_modifies_strategies"] is True
    assert payload["never_modifies_risk"] is True
    assert payload["never_approves_releases"] is True
    assert payload["events_immutable"] is True
    assert payload["event_distribution_read_only"] is True
    assert payload["mutates_engines"] is False
    assert payload["ordering_consistency"]["ok"] is True
    assert payload["replay_consistency"]["ok"] is True

    stream = svc.qem_stream(limit=20)
    assert stream["never_modifies_production"] is True
    assert stream["immutable"] is True

    replay = svc.qem_replay(limit=20)
    assert replay["never_modifies_production"] is True
    assert replay["replay_consistency"]["ok"] is True
