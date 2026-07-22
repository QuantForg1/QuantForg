"""PRC modules — certify readiness from evidence; never mutate production."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

from app.domain.production_readiness_certification.config import PrcConfig
from app.domain.production_readiness_certification.types import (
    ModuleResult,
    PrcInput,
)

INSUFFICIENT = "INSUFFICIENT EVIDENCE"
VERDICT_PASS = "PASS"  # noqa: S105 — certification verdict, not a password
VERDICT_WATCH = "WATCH"
VERDICT_FAIL = "FAIL"


def _dec(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    s = str(value).strip().lower()
    if s in ("true", "yes", "pass", "ok", "healthy"):
        return True
    if s in ("false", "no", "fail", "unhealthy"):
        return False
    return None


def _verdict_from_score(
    score: Decimal, config: PrcConfig
) -> str:
    if score >= config.pass_threshold:
        return VERDICT_PASS
    if score >= config.watch_threshold:
        return VERDICT_WATCH
    return VERDICT_FAIL


def _score_checks(
    facts: dict[str, Any],
    specs: list[tuple[str, str, Any]],
) -> tuple[Decimal, list[dict[str, Any]], list[str]]:
    """
    specs: (key, kind, threshold)
      kind: higher_better | lower_better | bool_true | present
    """
    results: list[dict[str, Any]] = []
    missing: list[str] = []
    points = Decimal("0")
    max_points = Decimal("0")

    for key, kind, threshold in specs:
        max_points += Decimal("1")
        raw = facts.get(key)
        if raw is None:
            missing.append(key)
            results.append(
                {"metric": key, "value": None, "result": INSUFFICIENT}
            )
            continue

        ok: bool | None = None
        if kind == "present":
            ok = True
        elif kind == "bool_true":
            b = _bool(raw)
            ok = b is True
            if b is None:
                missing.append(key)
                results.append(
                    {"metric": key, "value": raw, "result": INSUFFICIENT}
                )
                continue
        elif kind == "higher_better":
            v = _dec(raw)
            t = _dec(threshold)
            if v is None or t is None:
                missing.append(key)
                results.append(
                    {"metric": key, "value": raw, "result": INSUFFICIENT}
                )
                continue
            ok = v >= t
        elif kind == "lower_better":
            v = _dec(raw)
            t = _dec(threshold)
            if v is None or t is None:
                missing.append(key)
                results.append(
                    {"metric": key, "value": raw, "result": INSUFFICIENT}
                )
                continue
            ok = v <= t
        else:
            ok = False

        if ok:
            points += Decimal("1")
            results.append({"metric": key, "value": raw, "result": VERDICT_PASS})
        else:
            results.append({"metric": key, "value": raw, "result": VERDICT_FAIL})

    if max_points == 0:
        score = Decimal("0")
    else:
        # Missing metrics don't invent passes — score only on available
        available = max_points - Decimal(len(missing))
        if available <= 0:
            score = Decimal("0")
        else:
            # points already only counted passes among available
            scored_passes = sum(
                1 for r in results if r["result"] == VERDICT_PASS
            )
            score = (
                Decimal(scored_passes) / available * Decimal("100")
            ).quantize(Decimal("0.01"))

    return score, results, missing


def _domain_result(
    module: str,
    facts: dict[str, Any] | None,
    specs: list[tuple[str, str, Any]],
    config: PrcConfig,
    label: str,
) -> ModuleResult:
    if not facts:
        return ModuleResult(
            module=module,
            status="insufficient_evidence",
            score=None,
            recommendation=INSUFFICIENT,
            reasons=(
                f"No {label} evidence supplied",
                "Never invents certification metrics",
            ),
            details={"verdict": INSUFFICIENT, "checks": []},
        )

    score, checks, missing = _score_checks(facts, specs)
    if len(missing) == len(specs):
        return ModuleResult(
            module=module,
            status="insufficient_evidence",
            score=None,
            recommendation=INSUFFICIENT,
            reasons=("All required metrics missing",),
            details={
                "verdict": INSUFFICIENT,
                "checks": checks,
                "missing": missing,
            },
        )

    verdict = _verdict_from_score(score, config)
    # Any hard FAIL metric with enough coverage → at best WATCH unless majority fail
    hard_fails = sum(1 for c in checks if c["result"] == VERDICT_FAIL)
    if hard_fails >= max(2, len(specs) // 2):
        verdict = VERDICT_FAIL
    elif hard_fails >= 1 and verdict == VERDICT_PASS:
        verdict = VERDICT_WATCH

    return ModuleResult(
        module=module,
        status="available",
        score=score,
        recommendation=verdict,
        reasons=(
            f"{label} certification from supplied evidence only",
            "Never changes production configuration",
        ),
        details={
            "verdict": verdict,
            "score": str(score),
            "checks": checks,
            "missing": missing,
            "certifies_only": True,
        },
    )


def reliability_certification(
    inp: PrcInput, config: PrcConfig
) -> ModuleResult:
    specs: list[tuple[str, str, Any]] = [
        ("service_uptime_pct", "higher_better", 99.0),
        ("recovery_success_rate_pct", "higher_better", 95.0),
        ("restart_recovery_ok", "bool_true", True),
        ("watchdog_health_ok", "bool_true", True),
        ("mt5_synchronization_ok", "bool_true", True),
        ("incident_rate_per_day", "lower_better", 1.0),
        ("duplicate_protection_ok", "bool_true", True),
    ]
    return _domain_result(
        "reliability_certification",
        inp.reliability if isinstance(inp.reliability, dict) else None,
        specs,
        config,
        "Reliability",
    )


def risk_certification(inp: PrcInput, config: PrcConfig) -> ModuleResult:
    specs: list[tuple[str, str, Any]] = [
        ("risk_policy_compliance_pct", "higher_better", 98.0),
        ("maximum_drawdown_pct", "lower_better", 10.0),
        ("position_sizing_consistency_ok", "bool_true", True),
        ("daily_loss_compliance_ok", "bool_true", True),
        ("exposure_discipline_ok", "bool_true", True),
    ]
    return _domain_result(
        "risk_certification",
        inp.risk if isinstance(inp.risk, dict) else None,
        specs,
        config,
        "Risk",
    )


def execution_certification(
    inp: PrcInput, config: PrcConfig
) -> ModuleResult:
    specs: list[tuple[str, str, Any]] = [
        ("fill_reliability_pct", "higher_better", 97.0),
        ("execution_latency_ms_p95", "lower_better", 250.0),
        ("broker_acknowledgement_ok", "bool_true", True),
        ("slippage_observations_ok", "bool_true", True),
        ("retry_behavior_ok", "bool_true", True),
    ]
    return _domain_result(
        "execution_certification",
        inp.execution if isinstance(inp.execution, dict) else None,
        specs,
        config,
        "Execution",
    )


def decision_certification(
    inp: PrcInput, config: PrcConfig
) -> ModuleResult:
    specs: list[tuple[str, str, Any]] = [
        ("decision_explainability_ok", "bool_true", True),
        ("decision_consistency_pct", "higher_better", 90.0),
        ("confidence_calibration_ok", "bool_true", True),
        ("no_trade_discipline_ok", "bool_true", True),
    ]
    return _domain_result(
        "decision_certification",
        inp.decision if isinstance(inp.decision, dict) else None,
        specs,
        config,
        "Decision",
    )


def data_certification(inp: PrcInput, config: PrcConfig) -> ModuleResult:
    specs: list[tuple[str, str, Any]] = [
        ("market_data_integrity_ok", "bool_true", True),
        ("missing_data_handling_ok", "bool_true", True),
        ("feed_coverage_pct", "higher_better", 95.0),
        ("timestamp_consistency_ok", "bool_true", True),
        ("historical_completeness_pct", "higher_better", 90.0),
    ]
    return _domain_result(
        "data_certification",
        inp.data if isinstance(inp.data, dict) else None,
        specs,
        config,
        "Data",
    )


def research_certification(
    inp: PrcInput, config: PrcConfig
) -> ModuleResult:
    facts = inp.research if isinstance(inp.research, dict) else None
    specs: list[tuple[str, str, Any]] = [
        ("replay_evidence_ok", "bool_true", True),
        ("paper_trading_evidence_ok", "bool_true", True),
        ("ivp_evidence_ok", "bool_true", True),
        ("llp_evidence_ok", "bool_true", True),
        ("alpha_factory_evidence_ok", "bool_true", True),
    ]
    return _domain_result(
        "research_certification",
        facts,
        specs,
        config,
        "Research",
    )


def operational_certification(
    inp: PrcInput, config: PrcConfig
) -> ModuleResult:
    specs: list[tuple[str, str, Any]] = [
        ("health_ok", "bool_true", True),
        ("monitoring_ok", "bool_true", True),
        ("alerts_ok", "bool_true", True),
        ("audit_ok", "bool_true", True),
        ("logging_ok", "bool_true", True),
        ("recovery_ok", "bool_true", True),
        ("operator_workflow_ok", "bool_true", True),
    ]
    return _domain_result(
        "operational_certification",
        inp.operations if isinstance(inp.operations, dict) else None,
        specs,
        config,
        "Operational",
    )


def readiness_dashboard(
    modules: dict[str, ModuleResult], config: PrcConfig
) -> ModuleResult:
    domains = (
        "reliability_certification",
        "risk_certification",
        "execution_certification",
        "decision_certification",
        "data_certification",
        "research_certification",
        "operational_certification",
    )
    scores: list[Decimal] = []
    board: dict[str, Any] = {}
    for name in domains:
        mod = modules.get(name)
        short = name.replace("_certification", "")
        if not mod or mod.status != "available" or mod.score is None:
            board[short] = {
                "verdict": INSUFFICIENT,
                "score": None,
            }
            continue
        board[short] = {
            "verdict": (mod.details or {}).get("verdict") or mod.recommendation,
            "score": str(mod.score),
        }
        scores.append(mod.score)

    if not scores:
        overall = None
        status = INSUFFICIENT
    else:
        overall = (sum(scores) / Decimal(len(scores))).quantize(
            Decimal("0.01")
        )
        status = _verdict_from_score(overall, config)
        # Any FAIL domain blocks PASS
        if (
            any(v.get("verdict") == VERDICT_FAIL for v in board.values())
            and status == VERDICT_PASS
        ):
            status = VERDICT_WATCH
        if sum(
            1 for v in board.values() if v.get("verdict") == VERDICT_FAIL
        ) >= 2:
            status = VERDICT_FAIL
        if (
            any(v.get("verdict") == INSUFFICIENT for v in board.values())
            and status == VERDICT_PASS
        ):
            status = VERDICT_WATCH

    evidence_ok = all(
        board[k].get("verdict") in (VERDICT_PASS, VERDICT_WATCH)
        for k in ("research", "data")
        if k in board
    )

    return ModuleResult(
        module="readiness_dashboard",
        status="available" if overall is not None else "insufficient_evidence",
        score=overall,
        recommendation=status if overall is not None else INSUFFICIENT,
        reasons=(
            "Overall readiness from domain certifications",
            "Never changes production automatically",
        ),
        details={
            "overall_readiness": str(overall) if overall is not None else None,
            "reliability": board.get("reliability"),
            "execution": board.get("execution"),
            "risk": board.get("risk"),
            "research": board.get("research"),
            "evidence": {
                "data": board.get("data"),
                "research": board.get("research"),
                "decision": board.get("decision"),
                "sufficient": evidence_ok,
            },
            "operations": board.get("operational"),
            "domains": board,
            "certification_status": (
                status if overall is not None else INSUFFICIENT
            ),
        },
    )


def human_signoff_package(
    modules: dict[str, ModuleResult],
) -> ModuleResult:
    dash = modules.get("readiness_dashboard")
    d = (dash.details or {}) if dash else {}
    status = d.get("certification_status") or INSUFFICIENT
    overall = d.get("overall_readiness")

    known_risks: list[str] = []
    known_unknowns: list[str] = []
    open_issues: list[str] = []
    restrictions: list[str] = []

    for name, mod in modules.items():
        if name in (
            "readiness_dashboard",
            "human_signoff_package",
            "continuous_certification",
        ):
            continue
        verdict = (mod.details or {}).get("verdict") or mod.recommendation
        if verdict == VERDICT_FAIL:
            known_risks.append(f"{name}: FAIL")
            open_issues.append(f"Remediate {name} before live capital")
        elif verdict == VERDICT_WATCH:
            known_risks.append(f"{name}: WATCH")
            restrictions.append(f"Restrict scope until {name} improves")
        elif verdict == INSUFFICIENT or mod.status != "available":
            known_unknowns.append(f"{name}: {INSUFFICIENT}")
            open_issues.append(f"Supply evidence for {name}")

    if status != VERDICT_PASS:
        restrictions.append(
            "Do not deploy live capital without human approval"
        )
    restrictions.append(
        "PRC never changes configuration automatically"
    )

    decision = {
        VERDICT_PASS: (
            "CERTIFIED — human approval still required before live capital"
        ),
        VERDICT_WATCH: (
            "CONDITIONAL — human approval required; restrictions apply"
        ),
        VERDICT_FAIL: (
            "NOT CERTIFIED — live capital deployment blocked by evidence"
        ),
        INSUFFICIENT: "NOT CERTIFIED — insufficient evidence",
    }.get(str(status), "NOT CERTIFIED")

    return ModuleResult(
        module="human_signoff_package",
        status="available",
        score=dash.score if dash else None,
        recommendation=decision,
        reasons=(
            "Human Sign-off Package — PRC never auto-deploys",
            "Human Approval Required always",
        ),
        details={
            "executive_summary": (
                f"Overall readiness={overall or 'n/a'}; "
                f"certification_status={status}. "
                "PRC is read-only and requires human approval."
            ),
            "evidence_summary": d.get("domains") or {},
            "known_risks": known_risks,
            "known_unknowns": known_unknowns,
            "recommended_restrictions": restrictions,
            "open_issues": open_issues,
            "certification_decision": decision,
            "human_approval_required": True,
            "auto_deploy": False,
            "changes_production": False,
        },
    )


def continuous_certification(
    *,
    prior_status: str | None,
    current_status: str,
    prior: list[dict[str, Any]],
    audit_id: str,
    snapshot: dict[str, Any],
) -> ModuleResult:
    status_changed = (
        prior_status is not None
        and prior_status != current_status
    )
    entry = {
        "id": f"prc_{uuid4().hex[:10]}",
        "audit_id": audit_id,
        "recorded_at": datetime.now(UTC).isoformat(),
        "prior_status": prior_status,
        "current_status": current_status,
        "status_changed": status_changed,
        "notify_operators": status_changed,
        "snapshot": snapshot,
        "changes_production": False,
        "append_only": True,
    }
    return ModuleResult(
        module="continuous_certification",
        status="available",
        score=Decimal(str(len(prior) + 1)),
        recommendation=(
            "Certification status changed — notify operators"
            if status_changed
            else "Certification recalculated — no status change"
        ),
        reasons=(
            "Recalculates as new evidence arrives",
            "Never changes production automatically — notify only",
        ),
        details={
            "entry": entry,
            "prior_count": len(prior),
            "status_changed": status_changed,
            "notify_operators": status_changed,
            "changes_production": False,
            "auto_configure": False,
        },
    )
