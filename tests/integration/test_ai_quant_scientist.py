"""Integration — AQS never modifies production."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.application.services import ai_quant_scientist as svc
from app.domain.ai_quant_scientist.models import ISOLATION_FLAGS
from app.domain.ai_quant_scientist.platform import AiQuantScientist
from app.domain.ai_quant_scientist.store import AqsStore
from app.main import _ROUTER_SPECS

pytestmark = pytest.mark.integration


def test_router_registered() -> None:
    assert "ai_quant_scientist" in {n for n, _ in _ROUTER_SPECS}


def test_isolation_flags() -> None:
    assert ISOLATION_FLAGS["mutates_production"] is False
    assert ISOLATION_FLAGS["executes_trades"] is False
    assert ISOLATION_FLAGS["approves_promotion"] is False
    assert ISOLATION_FLAGS["writes_production_tables"] is False
    assert ISOLATION_FLAGS["triggers_automation"] is False


def test_service_dashboard_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    aqs = AiQuantScientist(store=AqsStore(path=tmp_path / "aqs.json"))
    monkeypatch.setattr("app.domain.ai_quant_scientist._AQS", aqs)
    monkeypatch.setattr(svc, "get_aqs", lambda: aqs)
    payload = svc.build_aqs_dashboard()
    assert payload["never_modifies_production"] is True
    assert payload["influences_trading"] is False
    assert payload["mutates_engines"] is False
