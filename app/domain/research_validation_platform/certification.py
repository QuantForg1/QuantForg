"""Certification Pipeline + Release Governance."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from app.domain.research_validation_platform.config import ResearchValidationConfig
from app.domain.research_validation_platform.util import dec, reproducible_hash

CERT_STAGES: tuple[str, ...] = (
    "registry",
    "replay",
    "walk_forward",
    "paper",
    "comparison",
    "operator_review",
)


def run_certification_pipeline(
    payload: dict[str, Any], config: ResearchValidationConfig
) -> dict[str, Any]:
    """Certification mandatory before production — never auto-enables live."""
    strategy_key = str(payload.get("strategy_key") or "unknown")
    version = str(payload.get("version") or "unversioned")
    stages_in = payload.get("stage_results")
    reasons: list[str] = []
    stage_rows: list[dict[str, Any]] = []

    if not isinstance(stages_in, dict) or not stages_in:
        return {
            "status": "unavailable",
            "certification_id": None,
            "strategy_key": strategy_key,
            "version": version,
            "certified": False,
            "production_eligible": False,
            "score": None,
            "stages": [],
            "reasons": [
                "No stage_results supplied — certification cannot invent passes",
                "Certification mandatory before production",
            ],
            "input_hash": None,
            "reproducible": False,
            "affects_live_execution": False,
            "require_certification_for_production": True,
        }

    passed_count = 0
    for stage in CERT_STAGES:
        raw = stages_in.get(stage)
        if not isinstance(raw, dict):
            stage_rows.append(
                {
                    "stage": stage,
                    "passed": False,
                    "status": "missing",
                    "detail": "Stage result not supplied",
                }
            )
            reasons.append(f"{stage}: missing — fail closed")
            continue
        ok = raw.get("passed") is True
        score = dec(raw.get("score"))
        stage_rows.append(
            {
                "stage": stage,
                "passed": ok,
                "status": "available",
                "score": str(score) if score is not None else None,
                "detail": str(raw.get("detail") or ("pass" if ok else "fail")),
            }
        )
        if ok:
            passed_count += 1
        else:
            reasons.append(f"{stage}: failed")

    score = (
        Decimal(passed_count) / Decimal(len(CERT_STAGES)) * Decimal("100")
    ).quantize(Decimal("0.01"))
    certified = (
        passed_count == len(CERT_STAGES)
        and score >= config.min_certification_score
    )
    if certified:
        reasons.append("All certification stages passed")
    else:
        reasons.append(
            f"Certification incomplete ({passed_count}/{len(CERT_STAGES)})"
        )
    reasons.append("Production blocked until certified — live pipeline unchanged")
    reasons.append("Never order_send from certification")

    cert_id = f"cert_{uuid4().hex[:12]}"
    inputs = {
        "strategy_key": strategy_key,
        "version": version,
        "stages": stage_rows,
    }
    return {
        "status": "available",
        "certification_id": cert_id,
        "strategy_key": strategy_key,
        "version": version,
        "certified": certified,
        "production_eligible": certified,
        "score": str(score),
        "stages": stage_rows,
        "reasons": reasons,
        "input_hash": reproducible_hash(inputs),
        "reproducible": True,
        "affects_live_execution": False,
        "never_order_send": True,
        "require_certification_for_production": True,
        "created_at": datetime.now(UTC).isoformat(),
    }


def evaluate_release_governance(
    payload: dict[str, Any], config: ResearchValidationConfig
) -> dict[str, Any]:
    """Release gate — certification + operator approval; never live send."""
    strategy_key = str(payload.get("strategy_key") or "unknown")
    version = str(payload.get("version") or "unversioned")
    certified = payload.get("certified") is True
    operator_approved = payload.get("operator_approved") is True
    reasons: list[str] = []

    if not certified:
        reasons.append("Not certified — release blocked (mandatory certification)")
    else:
        reasons.append("Certification present")

    if config.require_operator_release_approval and not operator_approved:
        reasons.append("Operator release approval required — pending")
    elif operator_approved:
        reasons.append("Operator approved release")

    allowed = certified and (
        operator_approved or not config.require_operator_release_approval
    )
    # Even if "allowed", platform never enables live execution itself.
    reasons.append("Release governance does not modify live execution pipeline")
    reasons.append("Promotion is advisory — operator executes via existing path")

    return {
        "status": "available",
        "strategy_key": strategy_key,
        "version": version,
        "release_allowed": allowed,
        "certified": certified,
        "operator_approved": operator_approved,
        "production_go_live": False,
        "affects_live_execution": False,
        "never_order_send": True,
        "require_certification_for_production": True,
        "reasons": reasons,
        "input_hash": reproducible_hash(
            {
                "strategy_key": strategy_key,
                "version": version,
                "certified": certified,
                "operator_approved": operator_approved,
            }
        ),
        "reproducible": True,
    }
