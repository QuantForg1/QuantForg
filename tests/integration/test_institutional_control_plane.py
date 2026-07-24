"""Integration — ICP never modifies production."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.application.services import institutional_control_plane as svc
from app.domain.institutional_control_plane.models import ISOLATION_FLAGS, SUBSYSTEMS
from app.domain.institutional_control_plane.platform import InstitutionalControlPlane
from app.domain.institutional_control_plane.store import IcpStore
from app.main import _ROUTER_SPECS

pytestmark = pytest.mark.integration


def test_router_registered() -> None:
    assert "institutional_control_plane" in {n for n, _ in _ROUTER_SPECS}


def test_isolation_flags() -> None:
    assert ISOLATION_FLAGS["executes_trades"] is False
    assert ISOLATION_FLAGS["modifies_production"] is False
    assert ISOLATION_FLAGS["modifies_strategy"] is False
    assert ISOLATION_FLAGS["modifies_risk"] is False
    assert ISOLATION_FLAGS["modifies_releases"] is False
    assert ISOLATION_FLAGS["approves_experiments"] is False
    assert ISOLATION_FLAGS["approves_lifecycle_transitions"] is False
    assert ISOLATION_FLAGS["executive_ops_read_only"] is True


def test_service_dashboard_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    icp = InstitutionalControlPlane(store=IcpStore(path=tmp_path / "icp.json"))
    monkeypatch.setattr("app.domain.institutional_control_plane._ICP", icp)
    monkeypatch.setattr(svc, "get_icp", lambda: icp)
    monkeypatch.setattr(
        "app.domain.institutional_control_plane.platform.gather_control_plane_sources",
        lambda: {
            "sources": {s: {} for s in SUBSYSTEMS},
            "availability": {s: False for s in SUBSYSTEMS},
            "source_count": 0,
            "read_only": True,
        },
    )
    payload = svc.build_icp_dashboard()
    assert payload["never_executes_trades"] is True
    assert payload["never_modifies_production"] is True
    assert payload["never_modifies_strategy"] is True
    assert payload["never_modifies_risk"] is True
    assert payload["never_modifies_releases"] is True
    assert payload["never_approves_experiments"] is True
    assert payload["never_approves_lifecycle_transitions"] is True
    assert payload["mutates_engines"] is False
    assert payload["health"]
    assert payload["dependencies"]["node_count"] == len(SUBSYSTEMS)
