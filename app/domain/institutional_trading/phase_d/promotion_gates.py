"""Deterministic promotion gates — no subjective override of mandatory checks."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_trading.phase_d.candidate import AlphaCandidate


MANDATORY_GATES = (
    "RESEARCH_VALIDATION",
    "OUT_OF_SAMPLE",
    "ROBUSTNESS",
    "PBO_DSR_EVIDENCE",
    "SHADOW_EVIDENCE",
    "LIVE_PARITY",
    "RISK_REVIEW",
    "EXECUTION_REVIEW",
)


def _pass(value: Any, *, ok_tokens: set[str]) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    token = str(value).strip().upper()
    return token in ok_tokens


def evaluate_promotion_gates(candidate: AlphaCandidate) -> dict[str, Any]:
    if candidate.status != "PROMOTABLE":
        return {
            "result": "PROMOTION_BLOCKED",
            "why_blocked": candidate.why_blocked or "NOT_PROMOTABLE",
            "gates": {g: "FAIL" for g in MANDATORY_GATES},
            "auto_promoted": False,
        }

    re = candidate.research_evidence
    rk = candidate.risk_evidence
    gates: dict[str, str] = {}

    gates["RESEARCH_VALIDATION"] = (
        "PASS"
        if _pass(
            re.get("walk_forward_status"),
            ok_tokens={"PASS", "PASSED", "OK", "VALIDATED"},
        )
        else "FAIL"
    )
    gates["OUT_OF_SAMPLE"] = (
        "PASS"
        if _pass(re.get("oos_status"), ok_tokens={"PASS", "PASSED", "CERTIFIED", "OK"})
        else "FAIL"
    )
    gates["ROBUSTNESS"] = (
        "PASS"
        if _pass(
            re.get("monte_carlo_status"),
            ok_tokens={"PASS", "PASSED", "COMPUTED", "ROBUST"},
        )
        and _pass(
            re.get("parameter_sensitivity"),
            ok_tokens={"ROBUST", "SENSITIVE", "PASS", "PASSED"},
        )
        and str(re.get("parameter_sensitivity")).upper() != "FRAGILE"
        else "FAIL"
    )
    pbo = str(re.get("pbo") or "").upper()
    dsr = str(re.get("dsr") or "").upper()
    gates["PBO_DSR_EVIDENCE"] = (
        "PASS"
        if pbo
        and dsr
        and "INSUFFICIENT" not in pbo
        and "INSUFFICIENT" not in dsr
        and "HIGH_PBO" not in pbo
        else "FAIL"
    )
    gates["SHADOW_EVIDENCE"] = (
        "PASS"
        if _pass(
            re.get("shadow_status"),
            ok_tokens={"PASS", "PASSED", "SHADOW_PASSED", "OK"},
        )
        else "FAIL"
    )
    gates["LIVE_PARITY"] = (
        "PASS"
        if _pass(
            re.get("live_parity_status"),
            ok_tokens={"ALIGNED", "MILD_DEVIATION", "PASS", "PASSED"},
        )
        else "FAIL"
    )
    gates["RISK_REVIEW"] = (
        "PASS"
        if _pass(rk.get("risk_impact"), ok_tokens={"ACCEPTABLE", "PASS", "PASSED", "OK"})
        and _pass(
            rk.get("drawdown_impact"),
            ok_tokens={"ACCEPTABLE", "PASS", "PASSED", "OK"},
        )
        and _pass(
            rk.get("correlation_impact"),
            ok_tokens={"ACCEPTABLE", "PASS", "PASSED", "OK"},
        )
        else "FAIL"
    )
    gates["EXECUTION_REVIEW"] = (
        "PASS"
        if _pass(
            rk.get("execution_impact"),
            ok_tokens={"ACCEPTABLE", "PASS", "PASSED", "OK"},
        )
        else "FAIL"
    )

    failed = [g for g, s in gates.items() if s != "PASS"]
    if failed:
        return {
            "result": "PROMOTION_BLOCKED",
            "why_blocked": "failed gates: " + ",".join(failed),
            "gates": gates,
            "auto_promoted": False,
        }
    return {
        "result": "GATES_PASSED",
        "why_blocked": None,
        "gates": gates,
        "auto_promoted": False,
        "next": "PROMOTION_REVIEW",
    }
