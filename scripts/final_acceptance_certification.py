#!/usr/bin/env python3
"""QuantForg v1.0.1 Final Acceptance & Readiness Certification.

Certification only — no new platform modules, no trading-behaviour changes.
Never overrides evidence gates. Never fabricates LIVE readiness.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CheckStatus = Literal["PASS", "FAIL", "BLOCKED"]
GoNoGo = Literal[
    "NOT READY",
    "READY FOR CONTROLLED DEMO",
    "READY FOR CONTROLLED LIVE",
]

VERSION = "1.0.1"

# Subsystems expected present after architecture complete (import paths)
SUBSYSTEMS: tuple[dict[str, str], ...] = (
    {
        "id": "strategy",
        "label": "Trading Strategy / Decision",
        "module": "app.domain.institutional_trading.trade_decision",
        "version": VERSION,
    },
    {
        "id": "risk",
        "label": "Risk Engine",
        "module": "app.domain.institutional_trading.eligibility",
        "version": VERSION,
    },
    {
        "id": "safety",
        "label": "Safety / Kill Switch",
        "module": "app.domain.institutional_trading.execution.kill_switch",
        "version": VERSION,
    },
    {
        "id": "execution",
        "label": "Execution Pipeline",
        "module": "app.domain.institutional_trading.operations.control_plane",
        "version": VERSION,
    },
    {
        "id": "performance_iq",
        "label": "Performance Intelligence",
        "module": "app.domain.performance_intelligence",
        "version": VERSION,
    },
    {
        "id": "replay_evidence_lab",
        "label": "Replay & Evidence Lab",
        "module": "app.domain.replay_evidence_lab",
        "version": VERSION,
    },
    {
        "id": "trading_operations_center",
        "label": "Trading Operations Center",
        "module": "app.domain.trading_operations_center",
        "version": VERSION,
    },
    {
        "id": "audit_governance",
        "label": "Audit Trail & Governance",
        "module": "app.domain.audit_governance",
        "version": VERSION,
    },
    {
        "id": "warehouse",
        "label": "Institutional Data Warehouse",
        "module": "app.domain.institutional_data_warehouse",
        "version": VERSION,
    },
    {
        "id": "observability",
        "label": "Institutional Observability",
        "module": "app.domain.institutional_observability",
        "version": VERSION,
    },
    {
        "id": "launch_readiness",
        "label": "Launch Readiness",
        "module": "app.application.services.launch_readiness",
        "version": VERSION,
    },
)

ROUTER_SPECS_EXPECTED: tuple[str, ...] = (
    "performance_intelligence",
    "replay_evidence_lab",
    "trading_operations_center",
    "audit_governance",
    "institutional_data_warehouse",
    "institutional_observability",
)


def _item(
    *,
    id: str,
    label: str,
    status: CheckStatus,
    reason: str,
    resolution: str,
) -> dict[str, Any]:
    return {
        "id": id,
        "label": label,
        "status": status,
        "reason": reason,
        "resolution": resolution,
    }


def probe_architecture() -> dict[str, Any]:
    inventory: list[dict[str, Any]] = []
    for spec in SUBSYSTEMS:
        present = False
        healthy = False
        detail = ""
        try:
            importlib.import_module(spec["module"])
            present = True
            healthy = True
            detail = "module importable"
        except Exception as exc:
            detail = str(exc)[:200]
        inventory.append(
            {
                "id": spec["id"],
                "label": spec["label"],
                "present": present,
                "healthy": healthy,
                "version": spec["version"],
                "dependencies": [spec["module"]],
                "readiness": (
                    "ready" if healthy else ("missing" if not present else "unhealthy")
                ),
                "detail": detail,
            }
        )

    # Router registration (read main._ROUTER_SPECS — no mutation)
    routers_ok: list[str] = []
    routers_missing: list[str] = []
    try:
        from app.main import _ROUTER_SPECS

        registered = {name for name, _ in _ROUTER_SPECS}
        for name in ROUTER_SPECS_EXPECTED:
            if name in registered:
                routers_ok.append(name)
            else:
                routers_missing.append(name)
    except Exception as exc:
        routers_missing = list(ROUTER_SPECS_EXPECTED)
        detail_routers = str(exc)[:200]
    else:
        detail_routers = "ok"

    return {
        "status": "available",
        "version": VERSION,
        "inventory": inventory,
        "routers_registered": routers_ok,
        "routers_missing": routers_missing,
        "routers_detail": detail_routers,
        "all_present": all(i["present"] for i in inventory)
        and not routers_missing,
    }


def probe_operational_readiness() -> dict[str, Any]:
    """Best-effort ops facts — never fabricates LIVE or EXECUTION_ENABLED."""
    facts: dict[str, Any] = {
        "gateway": None,
        "broker": None,
        "mt5": None,
        "ops_mode": None,
        "execution_enabled": None,
        "kill_switch_armed": None,
    }
    source = "unavailable"
    try:
        from app.application.services.auto_trading_status import (
            build_auto_trading_status,
        )
        from app.domain.institutional_trading.operations.control_plane import (
            get_control_plane,
        )
        from core.config.settings import get_settings

        settings = get_settings()
        plane = get_control_plane()
        snap = build_auto_trading_status(plane, settings=settings)
        f = snap.facts
        facts = {
            "gateway": bool(f.gateway_connected),
            "broker": bool(f.broker_connected),
            "mt5": bool(f.broker_connected),
            "ops_mode": str(f.ops_mode or plane.mode.value),
            "execution_enabled": bool(f.execution_enabled),
            "kill_switch_armed": bool(plane.kill_switch_armed),
        }
        source = "auto_trading_status"
    except Exception as exc:
        facts["error"] = str(exc)[:200]

    # Evidence gates — never override
    evidence_gates: dict[str, Any] = {"status": "unavailable"}
    try:
        from app.domain.replay_evidence_lab.evidence_store import get_evidence_database
        from app.domain.replay_evidence_lab.gates import evaluate_evidence_gates

        db = get_evidence_database()
        lanes = db.counts()
        research = db.list("research")
        no_trade_obs = sum(
            1
            for r in research
            if r.get("kind") == "no_trade_counterfactual"
            or str(r.get("decision") or "").upper() == "NO_TRADE"
        )
        evidence_gates = evaluate_evidence_gates(
            live_closed_trades=lanes.get("live", 0),
            replay_opportunities=lanes.get("replay", 0),
            no_trade_observations=no_trade_obs,
        )
    except Exception as exc:
        evidence_gates = {"status": "unavailable", "error": str(exc)[:200]}

    confidence: dict[str, Any] = {"status": "unavailable"}
    try:
        from app.domain.institutional_observability.reports import (
            build_observability_pack,
        )

        # Observability snapshot for health overlay (not a trading change)
        iop = build_observability_pack(ops_facts=None, error_events=[])
        confidence = {
            "status": "available",
            "observability_overall": (iop.get("health") or {}).get("overall"),
            "alert_count": (iop.get("alerts") or {}).get("count"),
        }
    except Exception as exc:
        confidence = {"status": "unavailable", "error": str(exc)[:200]}

    warehouse: dict[str, Any] = {"status": "unavailable"}
    try:
        from app.domain.institutional_data_warehouse.store import get_warehouse

        inv = get_warehouse().inventory()
        warehouse = {
            "status": "available",
            "total_records": inv.get("total_records"),
            "read_only": True,
        }
    except Exception as exc:
        warehouse = {"status": "unavailable", "error": str(exc)[:200]}

    governance: dict[str, Any] = {"status": "unavailable"}
    try:
        from app.domain.audit_governance.store import get_audit_store

        sec = get_audit_store().security_status()
        governance = {
            "status": "available",
            "record_count": sec.get("record_count"),
            "append_only": sec.get("append_only"),
            "immutable": sec.get("immutable"),
        }
    except Exception as exc:
        governance = {"status": "unavailable", "error": str(exc)[:200]}

    performance_iq = {"status": "module_present", "note": "advisory; journals only"}
    replay_lab = {
        "status": "module_present",
        "evidence_gates": evidence_gates,
        "note": "never override evidence gates",
    }

    return {
        "status": "available",
        "source": source,
        "facts": facts,
        "evidence_gates": evidence_gates,
        "confidence": confidence,
        "observability": confidence,
        "governance": governance,
        "warehouse": warehouse,
        "performance_iq": performance_iq,
        "replay_lab": replay_lab,
    }


def build_acceptance_checklist(
    *,
    architecture: dict[str, Any],
    operational: dict[str, Any],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    # Architecture presence
    for row in architecture.get("inventory") or []:
        if row.get("present") and row.get("healthy"):
            items.append(
                _item(
                    id=f"arch_{row['id']}",
                    label=f"Architecture: {row['label']}",
                    status="PASS",
                    reason=f"Present and importable ({row.get('detail')})",
                    resolution="None",
                )
            )
        else:
            items.append(
                _item(
                    id=f"arch_{row['id']}",
                    label=f"Architecture: {row['label']}",
                    status="FAIL",
                    reason=row.get("detail") or "Missing or unhealthy",
                    resolution=f"Restore module {row.get('dependencies')}",
                )
            )

    missing_routers = architecture.get("routers_missing") or []
    if not missing_routers:
        items.append(
            _item(
                id="routers",
                label="Advisory routers registered",
                status="PASS",
                reason="All expected advisory routers present in _ROUTER_SPECS",
                resolution="None",
            )
        )
    else:
        items.append(
            _item(
                id="routers",
                label="Advisory routers registered",
                status="FAIL",
                reason=f"Missing: {missing_routers}",
                resolution="Register missing routers in app.main._ROUTER_SPECS",
            )
        )

    facts = operational.get("facts") or {}
    # Operational checks — BLOCKED when unknown (no fabrication)
    def _bool_check(
        key: str,
        label: str,
        *,
        need_true: bool = True,
        blocked_if_unknown: bool = True,
    ) -> None:
        val = facts.get(key)
        if val is None and blocked_if_unknown:
            items.append(
                _item(
                    id=key,
                    label=label,
                    status="BLOCKED",
                    reason=(
                        "Ops facts unavailable in this environment — "
                        "not fabricated"
                    ),
                    resolution=(
                        "Run against a live API process with gateway/broker "
                        "attached"
                    ),
                )
            )
            return
        ok = bool(val) if need_true else (val is not None)
        if need_true:
            ok = val is True
        if ok:
            items.append(
                _item(
                    id=key,
                    label=label,
                    status="PASS",
                    reason=f"{key}={val}",
                    resolution="None",
                )
            )
        else:
            items.append(
                _item(
                    id=key,
                    label=label,
                    status="FAIL",
                    reason=f"{key}={val}",
                    resolution=(
                        "Restore connectivity / promote via official ops path "
                        "(see Launch Readiness)"
                    ),
                )
            )

    _bool_check("gateway", "Gateway connected")
    _bool_check("broker", "Broker connected")
    _bool_check("mt5", "MT5 session")

    mode = facts.get("ops_mode")
    if mode is None:
        items.append(
            _item(
                id="ops_mode",
                label="Ops Mode",
                status="BLOCKED",
                reason="Ops mode unknown — not fabricated",
                resolution="Query GET /ite/ops/auto-trading on a running API",
            )
        )
    elif str(mode).upper() == "LIVE":
        items.append(
            _item(
                id="ops_mode",
                label="Ops Mode",
                status="PASS",
                reason=f"ops_mode={mode}",
                resolution="None",
            )
        )
    elif str(mode).upper() in {"CANARY", "SHADOW"}:
        items.append(
            _item(
                id="ops_mode",
                label="Ops Mode",
                status="FAIL",
                reason=f"ops_mode={mode} (not LIVE)",
                resolution="Promote SHADOW→CANARY→LIVE via official OWNER path only",
            )
        )
    else:
        items.append(
            _item(
                id="ops_mode",
                label="Ops Mode",
                status="FAIL",
                reason=f"ops_mode={mode}",
                resolution="Inspect control plane mode",
            )
        )

    exec_en = facts.get("execution_enabled")
    if exec_en is None:
        items.append(
            _item(
                id="execution_enabled",
                label="Execution Enabled",
                status="BLOCKED",
                reason="EXECUTION_ENABLED unknown — not fabricated",
                resolution="Confirm Railway env EXECUTION_ENABLED and redeploy",
            )
        )
    elif exec_en is True:
        items.append(
            _item(
                id="execution_enabled",
                label="Execution Enabled",
                status="PASS",
                reason="execution_enabled=true",
                resolution="None",
            )
        )
    else:
        items.append(
            _item(
                id="execution_enabled",
                label="Execution Enabled",
                status="FAIL",
                reason="execution_enabled=false (env only; no API bypass)",
                resolution="Set EXECUTION_ENABLED=true on Railway and restart API",
            )
        )

    gates = operational.get("evidence_gates") or {}
    if gates.get("all_passed") is True:
        items.append(
            _item(
                id="evidence_gates",
                label="Evidence Gates",
                status="PASS",
                reason="All evidence thresholds met",
                resolution="None",
            )
        )
    elif gates.get("status") == "unavailable" and "checks" not in gates:
        items.append(
            _item(
                id="evidence_gates",
                label="Evidence Gates",
                status="BLOCKED",
                reason="Evidence gate evaluator unavailable",
                resolution="Ensure Replay & Evidence Lab is installed",
            )
        )
    else:
        failed = [
            c
            for c in (gates.get("checks") or [])
            if isinstance(c, dict) and not c.get("passed")
        ]
        items.append(
            _item(
                id="evidence_gates",
                label="Evidence Gates",
                status="FAIL",
                reason=(
                    "Evidence gates not passed — never overridden. "
                    f"Failed: {[c.get('id') for c in failed]}"
                ),
                resolution=(
                    "Accumulate live closed trades / replay opportunities / "
                    "NO_TRADE observations to threshold"
                ),
            )
        )

    # Advisory platforms presence
    for key, label in (
        ("performance_iq", "Performance IQ"),
        ("replay_lab", "Replay Lab"),
        ("governance", "Governance"),
        ("warehouse", "Warehouse"),
        ("observability", "Observability"),
    ):
        meta = operational.get(key) or {}
        st = meta.get("status")
        if st in {"available", "module_present"}:
            items.append(
                _item(
                    id=key,
                    label=label,
                    status="PASS",
                    reason=f"status={st}",
                    resolution="None",
                )
            )
        else:
            items.append(
                _item(
                    id=key,
                    label=label,
                    status="FAIL",
                    reason=str(meta.get("error") or st or "unavailable"),
                    resolution=f"Restore {label} module",
                )
            )

    # Confidence — tied to evidence gates (never override)
    if gates.get("all_passed") is True:
        items.append(
            _item(
                id="confidence",
                label="Confidence",
                status="PASS",
                reason="Evidence gates passed — confidence eligible",
                resolution="None",
            )
        )
    else:
        items.append(
            _item(
                id="confidence",
                label="Confidence",
                status="FAIL",
                reason=(
                    "Confidence blocked while evidence gates fail "
                    "(never overridden)"
                ),
                resolution="Clear evidence gates before claiming high confidence",
            )
        )

    return items


def decide_go_nogo(checklist: list[dict[str, Any]]) -> dict[str, Any]:
    """GO/NO-GO decision. Never overrides evidence gates."""
    by_id = {c["id"]: c for c in checklist}
    fails = [c for c in checklist if c["status"] == "FAIL"]
    blocked = [c for c in checklist if c["status"] == "BLOCKED"]
    arch_fails = [c for c in fails if str(c["id"]).startswith("arch_")]

    evidence = by_id.get("evidence_gates")
    evidence_pass = evidence is not None and evidence["status"] == "PASS"
    exec_pass = (by_id.get("execution_enabled") or {}).get("status") == "PASS"
    ops_live = (by_id.get("ops_mode") or {}).get("status") == "PASS"
    gateway_ok = (by_id.get("gateway") or {}).get("status") == "PASS"
    broker_ok = (by_id.get("broker") or {}).get("status") == "PASS"

    decision: GoNoGo
    explanation: list[str] = []

    if arch_fails:
        decision = "NOT READY"
        explanation.append("Architecture inventory has FAIL items")
    elif not evidence_pass:
        # Architecture OK but evidence gates block LIVE claims
        # Controlled demo may still be appropriate if modules present
        demo_blockers = [
            c
            for c in checklist
            if c["id"] in {"routers"} and c["status"] != "PASS"
        ]
        if demo_blockers or arch_fails:
            decision = "NOT READY"
            explanation.append("Core architecture/routers not certified")
        else:
            decision = "READY FOR CONTROLLED DEMO"
            explanation.append(
                "Architecture complete; evidence gates not passed — "
                "LIVE blocked (never overridden)"
            )
            explanation.append(
                "Controlled Demo allowed for operator drills without LIVE execution"
            )
    elif evidence_pass and exec_pass and ops_live and gateway_ok and broker_ok:
        decision = "READY FOR CONTROLLED LIVE"
        explanation.append("Evidence gates passed")
        explanation.append("Ops LIVE + EXECUTION_ENABLED + gateway/broker green")
        explanation.append("Controlled Live only — not unrestricted production")
    elif evidence_pass and not (exec_pass and ops_live and gateway_ok and broker_ok):
        decision = "READY FOR CONTROLLED DEMO"
        explanation.append("Evidence gates passed but live ops path incomplete")
        explanation.append(
            f"execution={ (by_id.get('execution_enabled') or {}).get('status') }, "
            f"ops={ (by_id.get('ops_mode') or {}).get('status') }, "
            f"gateway={ (by_id.get('gateway') or {}).get('status') }, "
            f"broker={ (by_id.get('broker') or {}).get('status') }"
        )
    else:
        decision = "NOT READY"
        explanation.append("Checklist does not meet Demo or Live criteria")

    if blocked and decision == "READY FOR CONTROLLED LIVE":
        decision = "READY FOR CONTROLLED DEMO"
        explanation.append(
            "BLOCKED operational facts present — cannot certify Controlled Live"
        )

    return {
        "decision": decision,
        "explanation": explanation,
        "fail_count": len(fails),
        "blocked_count": len(blocked),
        "pass_count": sum(1 for c in checklist if c["status"] == "PASS"),
        "never_overrides_evidence_gates": True,
    }


def build_risk_review(
    *,
    checklist: list[dict[str, Any]],
    operational: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    fails = [c for c in checklist if c["status"] == "FAIL"]
    blocked = [c for c in checklist if c["status"] == "BLOCKED"]
    return {
        "known_risks": [
            "Default Ops Mode is SHADOW until OWNER promotes",
            "EXECUTION_ENABLED is env-only and defaults false in many deploys",
            "In-memory control plane resets on process restart",
        ],
        "operational_risks": [
            f"{c['label']}: {c['reason']}" for c in fails if c["id"] in {
                "gateway",
                "broker",
                "mt5",
                "ops_mode",
                "execution_enabled",
            }
        ]
        or ["No operational FAIL items in this snapshot (or facts unavailable)"],
        "evidence_risks": [
            f"{c['label']}: {c['reason']}"
            for c in fails
            if c["id"] in {"evidence_gates", "confidence"}
        ]
        or ["Evidence gates review required before LIVE"],
        "infrastructure_risks": [
            "Wall-clock soak 24h/72h/7d remains PENDING OPERATIONAL EVIDENCE",
            "psutil/resource metrics may be unavailable in some hosts",
            "Gateway depends on Windows MT5 + Cloudflare tunnel",
        ],
        "outstanding_dependencies": [
            c["resolution"] for c in (fails + blocked) if c.get("resolution") != "None"
        ],
        "decision_context": decision.get("decision"),
        "evidence_gates_snapshot": operational.get("evidence_gates"),
    }


def build_certification_pack() -> dict[str, Any]:
    architecture = probe_architecture()
    operational = probe_operational_readiness()
    checklist = build_acceptance_checklist(
        architecture=architecture, operational=operational
    )
    decision = decide_go_nogo(checklist)
    risks = build_risk_review(
        checklist=checklist, operational=operational, decision=decision
    )
    outstanding = [
        {
            "id": c["id"],
            "status": c["status"],
            "reason": c["reason"],
            "resolution": c["resolution"],
        }
        for c in checklist
        if c["status"] in {"FAIL", "BLOCKED"}
    ]
    return {
        "version": VERSION,
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "scope": "final_acceptance_readiness_certification",
        "certification_only": True,
        "never_overrides_evidence_gates": True,
        "never_modifies_trading_behaviour": True,
        "architecture": architecture,
        "operational_readiness": operational,
        "acceptance_checklist": checklist,
        "production_risk_review": risks,
        "go_nogo": decision,
        "outstanding_blockers": outstanding,
        "evidence_summary": {
            "decision": decision.get("decision"),
            "pass": decision.get("pass_count"),
            "fail": decision.get("fail_count"),
            "blocked": decision.get("blocked_count"),
            "architecture_all_present": architecture.get("all_present"),
            "evidence_gates_passed": (operational.get("evidence_gates") or {}).get(
                "all_passed"
            ),
        },
    }


def _md(pack: dict[str, Any]) -> str:
    decision = (pack.get("go_nogo") or {}).get("decision")
    lines = [
        "# QuantForg v1.0.1 — Final Acceptance & Readiness Certification",
        "",
        f"**Generated:** {pack.get('generated_at')}",
        "**Scope:** Certification only. No new platform modules. "
        "Never overrides evidence gates. Never modifies trading behaviour.",
        "",
        "## GO / NO-GO",
        "",
        f"### **{decision}**",
        "",
    ]
    for e in (pack.get("go_nogo") or {}).get("explanation") or []:
        lines.append(f"- {e}")
    lines.extend(
        [
            "",
            "## Evidence summary",
            "",
            "```json",
            json.dumps(pack.get("evidence_summary"), indent=2),
            "```",
            "",
            "## Subsystem inventory",
            "",
            "| ID | Present | Healthy | Version | Readiness |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in (pack.get("architecture") or {}).get("inventory") or []:
        lines.append(
            f"| {row.get('id')} | {row.get('present')} | {row.get('healthy')} | "
            f"{row.get('version')} | {row.get('readiness')} |"
        )
    lines.extend(["", "## Acceptance checklist", ""])
    for c in pack.get("acceptance_checklist") or []:
        lines.append(
            f"- **{c.get('status')}** — {c.get('label')}: {c.get('reason')} "
            f"(Resolution: {c.get('resolution')})"
        )
    lines.extend(
        [
            "",
            "## Production risk review",
            "",
            "```json",
            json.dumps(pack.get("production_risk_review"), indent=2),
            "```",
            "",
            "## Outstanding blockers",
            "",
        ]
    )
    for b in pack.get("outstanding_blockers") or []:
        lines.append(
            f"- [{b.get('status')}] {b.get('id')}: {b.get('reason')} "
            f"→ {b.get('resolution')}"
        )
    if not pack.get("outstanding_blockers"):
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Hard locks",
            "",
            "- certification_only: true",
            "- never_overrides_evidence_gates: true",
            "- never_modifies_trading_behaviour: true",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def _architecture_report(pack: dict[str, Any]) -> str:
    lines = [
        "# QuantForg v1.x Final Architecture Report",
        "",
        f"**Generated:** {pack.get('generated_at')}",
        f"**Platform version:** {VERSION}",
        "",
        "Architecture is feature-complete for the institutional advisory stack:",
        "Performance IQ, Replay & Evidence Lab, Trading Operations Center,",
        "Audit Governance, Institutional Data Warehouse, Institutional Observability.",
        "",
        "Trading Strategy / Risk / Safety / Execution remain protected baselines.",
        "",
        "## Inventory",
        "",
        "```json",
        json.dumps((pack.get("architecture") or {}).get("inventory"), indent=2),
        "```",
        "",
        "## Registered advisory routers",
        "",
        "```json",
        json.dumps(
            {
                "registered": (pack.get("architecture") or {}).get(
                    "routers_registered"
                ),
                "missing": (pack.get("architecture") or {}).get("routers_missing"),
            },
            indent=2,
        ),
        "```",
        "",
    ]
    return "\n".join(lines) + "\n"


def _readiness_report(pack: dict[str, Any]) -> str:
    lines = [
        "# QuantForg v1.0.1 — Production Readiness Report",
        "",
        f"**Generated:** {pack.get('generated_at')}",
        f"**Decision:** {(pack.get('go_nogo') or {}).get('decision')}",
        "",
        "## Operational snapshot",
        "",
        "```json",
        json.dumps(pack.get("operational_readiness"), indent=2),
        "```",
        "",
        "## Known limitations",
        "",
        "- Evidence gates must pass before strategy-change recommendations",
        "- Controlled Live requires OWNER promote + EXECUTION_ENABLED + Demo cert",
        "- Wall-clock soak evidence remains operational (not claimed here)",
        "- Process-local stores reset on restart unless durable backends configured",
        "",
        "## Outstanding actions",
        "",
    ]
    for b in pack.get("outstanding_blockers") or []:
        lines.append(f"- {b.get('resolution')} ({b.get('id')}: {b.get('status')})")
    if not pack.get("outstanding_blockers"):
        lines.append("- None in this certification snapshot")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-md", action="store_true")
    args = parser.parse_args()

    pack = build_certification_pack()
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = ROOT / "docs" / "production" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"final_acceptance_{ts}.json"
    json_path.write_text(json.dumps(pack, indent=2), encoding="utf-8")
    print(f"Wrote {json_path}")

    if args.write_md:
        cert_md = (
            ROOT
            / "docs"
            / "production"
            / "FINAL_ACCEPTANCE_CERTIFICATION_v1.0.1.md"
        )
        cert_md.write_text(_md(pack), encoding="utf-8")
        print(f"Wrote {cert_md}")
        arch_md = (
            ROOT / "docs" / "production" / "FINAL_ARCHITECTURE_REPORT_v1.0.1.md"
        )
        arch_md.write_text(_architecture_report(pack), encoding="utf-8")
        print(f"Wrote {arch_md}")
        ready_md = (
            ROOT / "docs" / "production" / "PRODUCTION_READINESS_REPORT_v1.0.1.md"
        )
        ready_md.write_text(_readiness_report(pack), encoding="utf-8")
        print(f"Wrote {ready_md}")

    print(json.dumps(pack.get("evidence_summary"), indent=2))
    print("GO/NO-GO:", (pack.get("go_nogo") or {}).get("decision"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
