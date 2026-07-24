"""Integration — CVF never modifies production."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.application.services import continuous_validation_framework as svc
from app.domain.continuous_validation_framework.models import ISOLATION_FLAGS
from app.domain.continuous_validation_framework.platform import (
    ContinuousValidationFramework,
)
from app.domain.continuous_validation_framework.store import CvfStore
from app.main import _ROUTER_SPECS

pytestmark = pytest.mark.integration


def test_router_registered() -> None:
    assert "continuous_validation_framework" in {n for n, _ in _ROUTER_SPECS}


def test_isolation_flags() -> None:
    assert ISOLATION_FLAGS["mutates_production"] is False
    assert ISOLATION_FLAGS["executes_trades"] is False
    assert ISOLATION_FLAGS["modifies_strategy"] is False
    assert ISOLATION_FLAGS["modifies_thresholds"] is False
    assert ISOLATION_FLAGS["modifies_risk"] is False
    assert ISOLATION_FLAGS["modifies_safety"] is False
    assert ISOLATION_FLAGS["modifies_oms"] is False
    assert ISOLATION_FLAGS["modifies_gateway"] is False
    assert ISOLATION_FLAGS["modifies_scheduler"] is False
    assert ISOLATION_FLAGS["approves_promotions"] is False
    assert ISOLATION_FLAGS["triggers_automation"] is False


def test_service_dashboard_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cvf = ContinuousValidationFramework(store=CvfStore(path=tmp_path / "cvf.json"))
    monkeypatch.setattr("app.domain.continuous_validation_framework._CVF", cvf)
    monkeypatch.setattr(svc, "get_cvf", lambda: cvf)
    monkeypatch.setattr(
        "app.domain.continuous_validation_framework.platform.gather_validation_sources",
        lambda: {
            "sources": {
                "idw": {},
                "irl": {},
                "portfolio": {},
                "regime": {},
                "sic": {},
                "aqs": {"recommendations": [], "reports": []},
                "aqc": {"conversations": []},
                "eqs": {},
                "res": {},
                "qkg": {},
            },
            "availability": {"portfolio": True},
            "source_count": 1,
            "read_only": True,
        },
    )
    payload = svc.build_cvf_dashboard()
    assert payload["never_modifies_production"] is True
    assert payload["never_executes_trades"] is True
    assert payload["never_approves_promotions"] is True
    assert payload["influences_trading"] is False
    assert payload["mutates_engines"] is False
    assert payload["humans_remain_responsible"] is True
