"""Built-in production runbooks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

RUNBOOKS: dict[str, dict[str, Any]] = {
    "startup": {
        "title": "Platform startup",
        "steps": [
            "Confirm EXECUTION_ENABLED intentional (false until Demo certified)",
            "Start API (Railway) and confirm GET /api/v1/health/live",
            "Start Windows MT5 Gateway; confirm GET /health status=ok",
            "Attach or login MT5; confirm login_status connected",
            "Verify Cloudflare tunnel / gateway URL reachable from API",
            "Open Monitoring + Broker desks — identical gateway state",
            "Review /ite/ops/control-center mode (expect SHADOW until promoted)",
            "Acknowledge overnight alerts before enabling Auto Trading",
        ],
    },
    "shutdown": {
        "title": "Platform shutdown",
        "steps": [
            "Pause Auto Trading (run_state=paused or off)",
            "Arm kill switch if live risk is open",
            "Confirm no in-flight OMS requests",
            "Stop accepting new submissions (EXECUTION_ENABLED=false if lasting)",
            "Stop API process after drain",
            "Stop MT5 Gateway service last (after API callers idle)",
        ],
    },
    "restart": {
        "title": "Controlled restart",
        "steps": [
            "Arm kill switch",
            "Run shutdown checklist",
            "Restart Gateway, then API",
            "Confirm peak equity file/DB loaded",
            "Run startup checklist",
            "Disarm kill switch only after green health",
        ],
    },
    "start_of_trading_day": {
        "title": "Start of trading day",
        "steps": [
            "Verify gateway health and Cloudflare tunnel",
            "Confirm MT5 connected + AutoTrading enabled",
            "Review overnight alerts; acknowledge or escalate",
            "Confirm kill switch is DISARMED (if trading)",
            "Confirm execution mode (SHADOW → CANARY → Demo cert → LIVE)",
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
    "broker_failure": {
        "title": "Broker / Weltrade failure",
        "steps": [
            "Arm kill switch immediately",
            "Set Auto Trading OFF / STOPPED",
            "Confirm no ambiguous PREPARED attempts without reconciliation",
            "Capture gateway /health + last retcodes",
            "Wait for broker status; do not invent fills",
            "Reconnect MT5 only after broker confirms sessions",
            "Disarm kill switch after Monitoring + Broker agree CONNECTED",
        ],
    },
    "recovery": {
        "title": "Recovery after incident",
        "steps": [
            "Keep kill switch armed until root cause known",
            "Run /ite/reliability/recovery/gateway then /mt5 if needed",
            "Safe-read only — never auto-retry order_send",
            "Reconcile open positions vs MT5 terminal",
            "Verify peak equity + daily PnL gates",
            "Promote SHADOW → CANARY only after green soak sample",
        ],
    },
    "disaster_recovery": {
        "title": "Disaster recovery",
        "steps": [
            "Declare incident; arm kill switch",
            "Restore Postgres from latest verified backup (BACKUP_RECOVERY.md)",
            "Restore .quantforg_state / live_account_risk peak equity",
            "Restore research DurableResearchStore archive if process-local lost",
            "Redeploy matching app image tag",
            "EXECUTION_ENABLED=false until smoke + Demo cert",
            "Run startup + recovery checklists",
        ],
    },
    "incident_response": {
        "title": "Incident response",
        "steps": [
            "Acknowledge critical alerts in /ite/ops/alerts",
            "Open /incidents and /monitoring for shared state",
            "Capture request_ids / decision hashes / retcodes",
            "Prefer No Trade — halt Auto Trading",
            "Escalate OWNER/ADMIN; document timeline",
            "Close incident only after verify + audit entry",
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
            "Confirm launch locks PASS (gateway, broker, MT5, EXECUTION_ENABLED, "
            "kill/safety/risk clear, OWNER confirmation)",
            "Operator confirmation required",
            "Transition CANARY → LIVE via official Ops state machine",
            "Optional: Demo certification tooling for operator confidence "
            "(not a LIVE gate)",
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
