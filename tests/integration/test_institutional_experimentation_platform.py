"""Integration — IEP never modifies production."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.application.services import institutional_experimentation_platform as svc
from app.domain.institutional_experimentation_platform.models import ISOLATION_FLAGS
from app.domain.institutional_experimentation_platform.platform import (
    InstitutionalExperimentationPlatform,
)
from app.domain.institutional_experimentation_platform.store import IepStore
from app.main import _ROUTER_SPECS

pytestmark = pytest.mark.integration


def test_router_registered() -> None:
    assert "institutional_experimentation_platform" in {n for n, _ in _ROUTER_SPECS}


def test_isolation_flags() -> None:
    assert ISOLATION_FLAGS["executes_trades"] is False
    assert ISOLATION_FLAGS["modifies_production"] is False
    assert ISOLATION_FLAGS["modifies_strategies"] is False
    assert ISOLATION_FLAGS["approves_experiments_automatically"] is False
    assert ISOLATION_FLAGS["promotes_experiments_automatically"] is False
    assert ISOLATION_FLAGS["experiment_governance_read_only"] is True
    assert ISOLATION_FLAGS["human_decision_required"] is True


def test_service_dashboard_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    iep = InstitutionalExperimentationPlatform(
        store=IepStore(path=tmp_path / "iep.json")
    )
    monkeypatch.setattr(
        "app.domain.institutional_experimentation_platform._IEP", iep
    )
    monkeypatch.setattr(svc, "get_iep", lambda: iep)
    monkeypatch.setattr(
        "app.domain.institutional_experimentation_platform.platform.gather_experiment_sources",
        lambda: {
            "sources": {
                "irl": {"experiments": [], "leaderboard": {}, "jobs": []},
                "ise": {"simulations": []},
                "cvf": {},
                "irap": {},
                "aqs": {"recommendations": []},
                "qkg": {},
                "portfolio": {"trade_count": 10, "sections": {}},
                "sic": {},
                "islm": {"registry": []},
            },
            "availability": {"portfolio": True},
            "source_count": 1,
            "read_only": True,
        },
    )
    payload = svc.build_iep_dashboard()
    assert payload["never_executes_trades"] is True
    assert payload["never_modifies_production"] is True
    assert payload["never_modifies_strategies"] is True
    assert payload["never_approves_experiments_automatically"] is True
    assert payload["never_promotes_experiments_automatically"] is True
    assert payload["mutates_engines"] is False
    assert payload["registry"]
