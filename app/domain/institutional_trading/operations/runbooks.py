"""Built-in production runbooks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

RUNBOOKS: dict[str, dict[str, Any]] = {
    "start_of_trading_day": {
        "title": "Start of trading day",
        "steps": [
            "Verify gateway health and Cloudflare tunnel",
            "Confirm MT5 connected + AutoTrading enabled",
            "Review overnight alerts; acknowledge or escalate",
            "Confirm kill switch is DISARMED (if trading)",
            "Confirm execution mode (SHADOW/CANARY/LIVE)",
            "Confirm active strategy + config versions",
            "Review daily loss budget remaining",
        ],
    },
    "gateway_restart": {
        "title": "Gateway restart",
        "steps": [
            "Arm kill switch",
            "Drain OMS queue / confirm no in-flight orders",
            "Restart Windows MT5 gateway service",
            "Verify /health and gateway latency",
            "Disarm kill switch only after green health",
        ],
    },
    "mt5_reconnect": {
        "title": "MT5 reconnect",
        "steps": [
            "Arm kill switch",
            "Re-login MT5 terminal; enable AutoTrading",
            "Verify account sync + symbol XAUUSD tradable",
            "Disarm kill switch after connected=true",
        ],
    },
    "promotion_to_canary": {
        "title": "Promotion to Canary",
        "steps": [
            "Confirm Phase E promotion gate PASS",
            "Promote config version (append-only)",
            "Transition SHADOW → CANARY with confirmation + reason",
            "Cap 1 trade/day; monitor canary alerts",
        ],
    },
    "promotion_to_live": {
        "title": "Promotion to Live",
        "steps": [
            "Confirm canary period stable (no canary failure alerts)",
            "Operator confirmation required",
            "Transition CANARY → LIVE",
            "Monitor order latency + rejection rate",
        ],
    },
    "emergency_shutdown": {
        "title": "Emergency shutdown",
        "steps": [
            "ARM kill switch immediately",
            "Transition LIVE → SHADOW if needed",
            "Flatten open risk via PME/OMS only if safe",
            "Acknowledge critical alerts; page on-call",
            "Do not disarm until root cause cleared",
        ],
    },
    "rollback": {
        "title": "Rollback",
        "steps": [
            "Select rollback_target config version",
            "One-click rollback (strategy + config + mode + risk)",
            "Verify active versions match target",
            "Audit log must show operator + reason",
        ],
    },
}


@dataclass(frozen=True, slots=True)
class RunbookCatalog:
    def list(self) -> list[dict[str, Any]]:
        return [
            {"id": k, "title": v["title"], "steps": list(v["steps"])}
            for k, v in RUNBOOKS.items()
        ]

    def get(self, runbook_id: str) -> dict[str, Any] | None:
        raw = RUNBOOKS.get(runbook_id)
        if not raw:
            return None
        return {"id": runbook_id, "title": raw["title"], "steps": list(raw["steps"])}

    def execute_checklist(self, runbook_id: str) -> dict[str, Any]:
        """Return runbook steps as an executable checklist (deterministic)."""
        rb = self.get(runbook_id)
        if rb is None:
            return {"ok": False, "error": "unknown_runbook"}
        return {
            "ok": True,
            "runbook_id": runbook_id,
            "title": rb["title"],
            "checklist": [
                {"step": i + 1, "text": s, "done": False}
                for i, s in enumerate(rb["steps"])
            ],
        }
