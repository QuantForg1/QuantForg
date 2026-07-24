"""Integration — QCS never modifies production."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.application.services import quantforg_certification_suite as svc
from app.domain.quantforg_certification_suite.models import (
    DATA_SOURCES,
    ISOLATION_FLAGS,
)
from app.domain.quantforg_certification_suite.platform import (
    QuantForgCertificationSuite,
)
from app.domain.quantforg_certification_suite.store import QcsStore
from app.main import _ROUTER_SPECS

pytestmark = pytest.mark.integration


def test_router_registered() -> None:
    assert "quantforg_certification_suite" in {n for n, _ in _ROUTER_SPECS}


def test_isolation_flags() -> None:
    assert ISOLATION_FLAGS["executes_trades"] is False
    assert ISOLATION_FLAGS["modifies_production"] is False
    assert ISOLATION_FLAGS["modifies_strategies"] is False
    assert ISOLATION_FLAGS["modifies_risk"] is False
    assert ISOLATION_FLAGS["modifies_safety"] is False
    assert ISOLATION_FLAGS["approves_releases_automatically"] is False
    assert ISOLATION_FLAGS["human_approval_required_for_certification"] is True
    assert ISOLATION_FLAGS["certification_read_only"] is True


def test_service_dashboard_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    qcs = QuantForgCertificationSuite(store=QcsStore(path=tmp_path / "qcs.json"))
    monkeypatch.setattr("app.domain.quantforg_certification_suite._QCS", qcs)
    monkeypatch.setattr(svc, "get_qcs", lambda: qcs)
    monkeypatch.setattr(
        "app.domain.quantforg_certification_suite.platform.gather_certification_sources",
        lambda: {
            "sources": {s: {} for s in DATA_SOURCES},
            "availability": {s: False for s in DATA_SOURCES},
            "source_count": 0,
            "read_only": True,
        },
    )
    payload = svc.build_qcs_dashboard()
    assert payload["never_executes_trades"] is True
    assert payload["never_modifies_production"] is True
    assert payload["never_modifies_strategies"] is True
    assert payload["never_modifies_risk"] is True
    assert payload["never_modifies_safety"] is True
    assert payload["never_approves_releases_automatically"] is True
    assert payload["human_approval_required_for_certification"] is True
    assert payload["mutates_engines"] is False
    assert payload["scores"]
    assert payload["level"]["pending_human_certification"] is True
