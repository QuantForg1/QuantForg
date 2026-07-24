"""ISE platform orchestrator — digital twin laboratory."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from app.domain.institutional_simulation_engine.engine import (
    aqs_analysis_pack,
    build_reports,
    catalog,
    compare_scenarios,
    simulate_monte_carlo,
    simulate_replay,
    simulate_scenario,
    simulate_stress,
    simulate_walk_forward,
)
from app.domain.institutional_simulation_engine.gather import gather_simulation_context
from app.domain.institutional_simulation_engine.models import ISOLATION_FLAGS, SimulationMode
from app.domain.institutional_simulation_engine.store import IseStore


class InstitutionalSimulationEngine:
    def __init__(self, store: IseStore | None = None) -> None:
        self.store = store or IseStore()
        self.isolation = dict(ISOLATION_FLAGS)

    def run_suite(self, *, persist: bool = True) -> dict[str, Any]:
        t0 = time.perf_counter()
        ctx = gather_simulation_context()
        results: list[dict[str, Any]] = []

        results.append(simulate_replay(ctx))
        results.append(simulate_walk_forward(ctx))
        results.append(simulate_monte_carlo(ctx, paths=100))
        for sc in ("higher_spread", "broker_delay", "higher_volatility"):
            results.append(simulate_scenario(ctx, scenario=sc))
        for st in ("extreme_spread", "volatility_spike", "gap"):
            results.append(simulate_stress(ctx, stress=st))

        if persist:
            for row in results:
                self.store.upsert_simulation(row)
            reports = build_reports(self.store.list_simulations(limit=40))
            for key, body in reports.items():
                if key == "generated_at" or not isinstance(body, dict):
                    continue
                self.store.save_report(
                    {
                        "report_id": f"ise-{key}-{datetime.now(UTC).date()}",
                        "kind": key,
                        **body,
                    }
                )
        else:
            reports = build_reports(results)

        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        return {
            "schema_version": "1.0.0",
            "mode": "institutional_simulation_engine",
            "isolation": self.isolation,
            "observed_at": datetime.now(UTC).isoformat(),
            "elapsed_ms": elapsed_ms,
            "context": {
                "availability": ctx.get("availability"),
                "source_count": ctx.get("source_count"),
            },
            "catalog": catalog(),
            "simulations": self.store.list_simulations(limit=40) if persist else results,
            "comparison": compare_scenarios(results),
            "reports": reports,
            "knowledge_nodes": self.store.knowledge_nodes(limit=40),
            "read_only": True,
            "never_modifies_production": True,
            "digital_twin": True,
        }

    def dashboard(self) -> dict[str, Any]:
        pack = self.run_suite(persist=True)
        pack["sections"] = {
            "simulation_dashboard": {
                "count": len(pack.get("simulations") or []),
                "catalog": pack.get("catalog"),
            },
            "scenario_builder": {"scenarios": (pack.get("catalog") or {}).get("scenarios")},
            "scenario_explorer": pack.get("simulations"),
            "stress_testing": [
                s
                for s in pack.get("simulations") or []
                if s.get("mode") == SimulationMode.STRESS_TEST.value
            ],
            "monte_carlo": [
                s
                for s in pack.get("simulations") or []
                if s.get("mode") == SimulationMode.MONTE_CARLO.value
            ],
            "walk_forward": [
                s
                for s in pack.get("simulations") or []
                if s.get("mode") == SimulationMode.WALK_FORWARD.value
            ],
            "reports": self.store.list_reports(limit=20),
            "knowledge_nodes": pack.get("knowledge_nodes"),
        }
        return pack

    def simulate(
        self,
        *,
        mode: str,
        scenario: str | None = None,
        paths: int = 100,
        persist: bool = True,
    ) -> dict[str, Any]:
        ctx = gather_simulation_context()
        mode_l = (mode or "").lower()
        if "monte" in mode_l:
            row = simulate_monte_carlo(ctx, paths=paths, scenario=scenario)
        elif "walk" in mode_l:
            row = simulate_walk_forward(ctx)
        elif "stress" in mode_l:
            row = simulate_stress(ctx, stress=scenario or "volatility_spike")
        elif "replay" in mode_l:
            row = simulate_replay(ctx)
        else:
            row = simulate_scenario(
                ctx, scenario=scenario or "higher_spread", mode=SimulationMode.SCENARIO_BUILDER.value
            )
        if persist:
            row = self.store.upsert_simulation(row)
        row["aqs_analysis"] = aqs_analysis_pack(row)
        row["knowledge_node"] = {
            "id": f"simulation:{row.get('simulation_id')}",
            "type": "Research Experiments",
            "source_subsystem": "institutional_simulation_engine",
        }
        row["isolation"] = self.isolation
        return row

    def analyze_for_aqs(self, simulation_id: str) -> dict[str, Any] | None:
        row = self.store.get_simulation(simulation_id)
        if not row:
            return None
        return aqs_analysis_pack(row)
