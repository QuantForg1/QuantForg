"""Integration — AQC never modifies production."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.application.services import ai_quant_copilot as svc
from app.domain.ai_quant_copilot.models import ISOLATION_FLAGS
from app.domain.ai_quant_copilot.platform import AiQuantCopilot
from app.domain.ai_quant_copilot.store import AqcStore
from app.main import _ROUTER_SPECS

pytestmark = pytest.mark.integration


def test_router_registered() -> None:
    assert "ai_quant_copilot" in {n for n, _ in _ROUTER_SPECS}


def test_isolation_flags() -> None:
    assert ISOLATION_FLAGS["mutates_production"] is False
    assert ISOLATION_FLAGS["executes_trades"] is False
    assert ISOLATION_FLAGS["approves_promotions"] is False
    assert ISOLATION_FLAGS["writes_production_tables"] is False
    assert ISOLATION_FLAGS["triggers_automation"] is False
    assert ISOLATION_FLAGS["modifies_scheduler"] is False
    assert ISOLATION_FLAGS["modifies_research"] is False


def test_service_dashboard_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    aqc = AiQuantCopilot(store=AqcStore(path=tmp_path / "aqc.json"))
    monkeypatch.setattr("app.domain.ai_quant_copilot._AQC", aqc)
    monkeypatch.setattr(svc, "get_aqc", lambda: aqc)

    def _fast_ctx():
        return {
            "sources": {
                "icc": {},
                "idw": {},
                "aqs": {"recommendations": [], "reports": []},
                "irl": {},
                "diagnostics": {},
                "execution_explain": {},
                "portfolio": {},
                "regime": {},
                "opportunity": {},
                "sic": {},
                "audit": [],
            },
            "availability": {"icc": True},
            "source_count": 1,
            "read_only": True,
            "never_mutates_sources": True,
        }

    monkeypatch.setattr(
        "app.domain.ai_quant_copilot.platform.gather_ops_context", _fast_ctx
    )
    payload = svc.build_aqc_dashboard()
    assert payload["never_modifies_production"] is True
    assert payload["influences_trading"] is False
    assert payload["mutates_engines"] is False
    assert payload["never_executes_trades"] is True
