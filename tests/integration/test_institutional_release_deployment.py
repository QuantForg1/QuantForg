"""Integration — IRDP preserves production safety guarantees."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.application.services import institutional_release_deployment as svc
from app.domain.institutional_release_deployment.models import ISOLATION_FLAGS
from app.domain.institutional_release_deployment.platform import (
    InstitutionalReleaseDeploymentPlatform,
)
from app.domain.institutional_release_deployment.store import IrdpStore
from app.main import _ROUTER_SPECS

pytestmark = pytest.mark.integration


def test_router_registered() -> None:
    assert "institutional_release_deployment" in {n for n, _ in _ROUTER_SPECS}


def test_isolation_flags() -> None:
    assert ISOLATION_FLAGS["executes_trades"] is False
    assert ISOLATION_FLAGS["modifies_strategies_automatically"] is False
    assert ISOLATION_FLAGS["modifies_risk_automatically"] is False
    assert ISOLATION_FLAGS["modifies_safety_automatically"] is False
    assert ISOLATION_FLAGS["approves_releases_automatically"] is False
    assert ISOLATION_FLAGS["rollbacks_automatically"] is False
    assert ISOLATION_FLAGS["human_approval_required"] is True
    assert ISOLATION_FLAGS["preserves_production_safety_guarantees"] is True


def test_service_dashboard_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    irdp = InstitutionalReleaseDeploymentPlatform(
        store=IrdpStore(path=tmp_path / "irdp.json")
    )
    monkeypatch.setattr("app.domain.institutional_release_deployment._IRDP", irdp)
    monkeypatch.setattr(svc, "get_irdp", lambda: irdp)
    monkeypatch.setattr(
        "app.domain.institutional_release_deployment.platform.gather_release_evidence",
        lambda: {
            "sources": {
                "cvf": {},
                "eqs": {},
                "res": {},
                "ise": {"simulations": [], "reports": []},
                "qkg": {},
                "audit": [],
                "icc": {},
                "prr": {},
            },
            "availability": {"cvf": True},
            "source_count": 1,
            "read_only": True,
        },
    )
    payload = svc.build_irdp_dashboard()
    assert payload["never_executes_trades"] is True
    assert payload["never_auto_approves"] is True
    assert payload["never_rollbacks_automatically"] is True
    assert payload["preserves_production_safety_guarantees"] is True
    assert payload["mutates_engines"] is False
