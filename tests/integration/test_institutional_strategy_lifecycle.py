"""Integration — ISLM preserves production governance rules."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.application.services import institutional_strategy_lifecycle as svc
from app.domain.institutional_strategy_lifecycle.models import ISOLATION_FLAGS
from app.domain.institutional_strategy_lifecycle.platform import (
    InstitutionalStrategyLifecycleManager,
)
from app.domain.institutional_strategy_lifecycle.store import IslmStore
from app.main import _ROUTER_SPECS

pytestmark = pytest.mark.integration


def test_router_registered() -> None:
    assert "institutional_strategy_lifecycle" in {n for n, _ in _ROUTER_SPECS}


def test_isolation_flags() -> None:
    assert ISOLATION_FLAGS["executes_trades"] is False
    assert ISOLATION_FLAGS["modifies_production"] is False
    assert ISOLATION_FLAGS["changes_strategy_parameters"] is False
    assert ISOLATION_FLAGS["approves_promotions_automatically"] is False
    assert ISOLATION_FLAGS["retires_strategies_automatically"] is False
    assert ISOLATION_FLAGS["human_approval_required_for_transitions"] is True
    assert ISOLATION_FLAGS["lifecycle_governance_read_only"] is True


def test_service_dashboard_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    islm = InstitutionalStrategyLifecycleManager(
        store=IslmStore(path=tmp_path / "islm.json")
    )
    monkeypatch.setattr(
        "app.domain.institutional_strategy_lifecycle._ISLM", islm
    )
    monkeypatch.setattr(svc, "get_islm", lambda: islm)
    monkeypatch.setattr(
        "app.domain.institutional_strategy_lifecycle.platform.gather_lifecycle_sources",
        lambda: {
            "sources": {
                "portfolio": {"trade_count": 1, "sections": {}},
                "irl": {"experiments": []},
                "aqs": {"recommendations": []},
                "ise": {"simulations": []},
                "cvf": {},
                "irap": {},
                "eqs": {},
                "res": {},
                "irdp": [],
                "qkg": {},
                "sic": {},
            },
            "availability": {"portfolio": True},
            "source_count": 1,
            "read_only": True,
        },
    )
    payload = svc.build_islm_dashboard()
    assert payload["never_executes_trades"] is True
    assert payload["never_modifies_production"] is True
    assert payload["never_changes_strategy_parameters"] is True
    assert payload["never_approves_promotions_automatically"] is True
    assert payload["never_retires_strategies_automatically"] is True
    assert payload["human_approval_required_for_transitions"] is True
    assert payload["mutates_engines"] is False
    assert payload["registry"]
