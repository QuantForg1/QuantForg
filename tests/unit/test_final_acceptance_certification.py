"""Unit tests — Final Acceptance certification decision logic (certification only)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "final_acceptance_certification.py"


def _load():
    spec = importlib.util.spec_from_file_location(
        "final_acceptance_certification", SCRIPT
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.unit
class TestFinalAcceptanceCertification:
    def test_architecture_inventory_present(self) -> None:
        mod = _load()
        arch = mod.probe_architecture()
        assert arch["all_present"] is True
        assert not arch["routers_missing"]
        ids = {r["id"] for r in arch["inventory"]}
        assert "performance_iq" in ids
        assert "observability" in ids
        assert "warehouse" in ids

    def test_evidence_gates_never_overridden_for_live(self) -> None:
        mod = _load()
        checklist = [
            {
                "id": "arch_x",
                "label": "Arch",
                "status": "PASS",
                "reason": "ok",
                "resolution": "None",
            },
            {
                "id": "routers",
                "label": "Routers",
                "status": "PASS",
                "reason": "ok",
                "resolution": "None",
            },
            {
                "id": "evidence_gates",
                "label": "Evidence Gates",
                "status": "FAIL",
                "reason": "thresholds unmet",
                "resolution": "grow samples",
            },
            {
                "id": "execution_enabled",
                "label": "Execution",
                "status": "PASS",
                "reason": "true",
                "resolution": "None",
            },
            {
                "id": "ops_mode",
                "label": "Ops",
                "status": "PASS",
                "reason": "LIVE",
                "resolution": "None",
            },
            {
                "id": "gateway",
                "label": "Gateway",
                "status": "PASS",
                "reason": "ok",
                "resolution": "None",
            },
            {
                "id": "broker",
                "label": "Broker",
                "status": "PASS",
                "reason": "ok",
                "resolution": "None",
            },
        ]
        decision = mod.decide_go_nogo(checklist)
        assert decision["decision"] == "READY FOR CONTROLLED DEMO"
        assert decision["never_overrides_evidence_gates"] is True
        assert decision["decision"] != "READY FOR CONTROLLED LIVE"

    def test_controlled_live_requires_all_green(self) -> None:
        mod = _load()
        checklist = [
            {
                "id": "evidence_gates",
                "label": "Evidence Gates",
                "status": "PASS",
                "reason": "ok",
                "resolution": "None",
            },
            {
                "id": "execution_enabled",
                "label": "Execution",
                "status": "PASS",
                "reason": "true",
                "resolution": "None",
            },
            {
                "id": "ops_mode",
                "label": "Ops",
                "status": "PASS",
                "reason": "LIVE",
                "resolution": "None",
            },
            {
                "id": "gateway",
                "label": "Gateway",
                "status": "PASS",
                "reason": "ok",
                "resolution": "None",
            },
            {
                "id": "broker",
                "label": "Broker",
                "status": "PASS",
                "reason": "ok",
                "resolution": "None",
            },
        ]
        decision = mod.decide_go_nogo(checklist)
        assert decision["decision"] == "READY FOR CONTROLLED LIVE"

    def test_full_pack_certification_only(self) -> None:
        mod = _load()
        pack = mod.build_certification_pack()
        assert pack["certification_only"] is True
        assert pack["never_overrides_evidence_gates"] is True
        assert pack["go_nogo"]["decision"] in {
            "NOT READY",
            "READY FOR CONTROLLED DEMO",
            "READY FOR CONTROLLED LIVE",
        }
        assert isinstance(pack["acceptance_checklist"], list)
        assert len(pack["acceptance_checklist"]) > 0
