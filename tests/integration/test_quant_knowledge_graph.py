"""Integration — QKG never modifies production."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.application.services import quant_knowledge_graph as svc
from app.domain.quant_knowledge_graph import qkg_query_for_ai
from app.domain.quant_knowledge_graph.models import ISOLATION_FLAGS
from app.domain.quant_knowledge_graph.platform import QuantKnowledgeGraph
from app.domain.quant_knowledge_graph.store import QkgStore
from app.main import _ROUTER_SPECS

pytestmark = pytest.mark.integration


def test_router_registered() -> None:
    assert "quant_knowledge_graph" in {n for n, _ in _ROUTER_SPECS}


def test_isolation_flags() -> None:
    assert ISOLATION_FLAGS["mutates_production"] is False
    assert ISOLATION_FLAGS["modifies_research"] is False
    assert ISOLATION_FLAGS["modifies_risk"] is False
    assert ISOLATION_FLAGS["modifies_strategy"] is False
    assert ISOLATION_FLAGS["modifies_gateway"] is False
    assert ISOLATION_FLAGS["modifies_oms"] is False
    assert ISOLATION_FLAGS["modifies_scheduler"] is False
    assert ISOLATION_FLAGS["modifies_thresholds"] is False


def test_service_and_ai_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    qkg = QuantKnowledgeGraph(store=QkgStore(path=tmp_path / "qkg.json"))
    monkeypatch.setattr("app.domain.quant_knowledge_graph._QKG", qkg)
    monkeypatch.setattr(svc, "get_qkg", lambda: qkg)
    monkeypatch.setattr(
        "app.domain.quant_knowledge_graph.platform.gather_knowledge_sources",
        lambda: {
            "sources": {
                "idw": {"signals": [], "trades": [], "regimes": []},
                "irl": {"experiments": [], "jobs": []},
                "aqs": {"recommendations": [], "reports": []},
                "portfolio": {},
                "regime": {"current": {"current_regime": "RANGING"}},
                "diagnostics": {},
                "icc": {},
                "sic": {},
                "audit": [],
            },
            "availability": {"regime": True},
            "source_count": 1,
            "read_only": True,
        },
    )
    payload = svc.build_qkg_dashboard()
    assert payload["never_modifies_production"] is True
    assert payload["mutates_engines"] is False
    ans = qkg_query_for_ai("find Market Regimes")
    assert ans["never_modifies_production"] is True
    assert "capability" in ans
