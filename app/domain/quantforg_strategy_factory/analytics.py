"""QSF analytics — pipeline board, work items, dossiers, integrity checks."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha1
from typing import Any

from app.domain.quantforg_strategy_factory.models import (
    DOSSIER_KINDS,
    PIPELINE_ORDER,
    PIPELINE_STAGES,
    PipelineStage,
    WORK_ITEM_STATUSES,
)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _stable_id(*parts: Any) -> str:
    raw = "|".join(str(p) for p in parts)
    return "qsf-" + sha1(raw.encode("utf-8")).hexdigest()[:16]


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def map_lifecycle_to_stage(lifecycle: str) -> str:
    lc = lifecycle.lower()
    if "draft" in lc or "idea" in lc:
        return PipelineStage.IDEA.value
    if "hypothes" in lc:
        return PipelineStage.HYPOTHESIS.value
    if "research" in lc:
        return PipelineStage.RESEARCH.value
    if "experiment" in lc:
        return PipelineStage.EXPERIMENT.value
    if "replay" in lc:
        return PipelineStage.REPLAY.value
    if "simulat" in lc:
        return PipelineStage.SIMULATION.value
    if "validat" in lc:
        return PipelineStage.CONTINUOUS_VALIDATION.value
    if "risk" in lc:
        return PipelineStage.RISK_REVIEW.value
    if "certif" in lc:
        return PipelineStage.CERTIFICATION.value
    if "decision" in lc or "review" in lc:
        return PipelineStage.DECISION_INTELLIGENCE.value
    if "paper" in lc or "ready" in lc or "live" in lc or "product" in lc:
        return PipelineStage.PAPER_TRADING_READY.value
    return PipelineStage.RESEARCH.value


def next_stage(current: str) -> str | None:
    try:
        idx = PIPELINE_ORDER.index(current)
    except ValueError:
        return PIPELINE_ORDER[0]
    if idx >= len(PIPELINE_ORDER) - 1:
        return None
    return PIPELINE_ORDER[idx + 1]


def can_transition(from_stage: str, to_stage: str) -> bool:
    if from_stage not in PIPELINE_ORDER or to_stage not in PIPELINE_ORDER:
        return False
    # Allow forward one step, or reject staying; human may also reject (stay)
    fi = PIPELINE_ORDER.index(from_stage)
    ti = PIPELINE_ORDER.index(to_stage)
    return ti == fi + 1 or ti == fi


def derive_stage_for_strategy(strategy: dict[str, Any], ctx: dict[str, Any]) -> str:
    """Derive pipeline stage from lifecycle + available evidence signals."""
    base = map_lifecycle_to_stage(
        str(strategy.get("lifecycle_state") or strategy.get("lifecycle") or "Research")
    )
    sources = _as_dict(ctx.get("sources"))
    sid = str(strategy.get("strategy_id") or "")

    cvf_conf = _num(
        _as_dict(_as_dict(sources.get("cvf")).get("confidence") or sources.get("cvf")).get(
            "confidence"
        ),
        0.0,
    )
    qcs_score = _num(
        _as_dict(_as_dict(sources.get("qcs")).get("scores") or {}).get(
            "overall_institutional_readiness_score"
        ),
        0.0,
    )
    sims = _as_list(_as_dict(sources.get("ise")).get("simulations"))
    replays = _as_list(_as_dict(sources.get("replay")).get("simulations"))
    irap_alerts = _as_list(_as_dict(sources.get("irap")).get("alerts"))
    exps = _as_list(_as_dict(sources.get("iep")).get("registry"))
    linked_exp = any(
        sid and sid in str(_as_dict(e).get("strategy_id") or "") for e in exps
    )

    # Progressive evidence bumps (never skips human gate — advisory placement only)
    stage = base
    if linked_exp and PIPELINE_ORDER.index(stage) < PIPELINE_ORDER.index(
        PipelineStage.EXPERIMENT.value
    ):
        stage = PipelineStage.EXPERIMENT.value
    if replays and PIPELINE_ORDER.index(stage) < PIPELINE_ORDER.index(
        PipelineStage.REPLAY.value
    ):
        stage = PipelineStage.REPLAY.value
    if sims and PIPELINE_ORDER.index(stage) < PIPELINE_ORDER.index(
        PipelineStage.SIMULATION.value
    ):
        stage = PipelineStage.SIMULATION.value
    if cvf_conf >= 50 and PIPELINE_ORDER.index(stage) < PIPELINE_ORDER.index(
        PipelineStage.CONTINUOUS_VALIDATION.value
    ):
        stage = PipelineStage.CONTINUOUS_VALIDATION.value
    if (irap_alerts or cvf_conf >= 60) and PIPELINE_ORDER.index(stage) < PIPELINE_ORDER.index(
        PipelineStage.RISK_REVIEW.value
    ):
        stage = PipelineStage.RISK_REVIEW.value
    if qcs_score >= 50 and PIPELINE_ORDER.index(stage) < PIPELINE_ORDER.index(
        PipelineStage.CERTIFICATION.value
    ):
        stage = PipelineStage.CERTIFICATION.value
    if _as_dict(sources.get("qdie")) and PIPELINE_ORDER.index(stage) < PIPELINE_ORDER.index(
        PipelineStage.DECISION_INTELLIGENCE.value
    ):
        stage = PipelineStage.DECISION_INTELLIGENCE.value
    return stage


def build_work_items(
    ctx: dict[str, Any],
    *,
    stage_overrides: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    sources = _as_dict(ctx.get("sources"))
    overrides = stage_overrides or {}
    strategies = _as_list(_as_dict(sources.get("islm")).get("registry"))
    items: list[dict[str, Any]] = []
    target = (datetime.now(UTC) + timedelta(days=14)).date().isoformat()

    if not strategies:
        # Placeholder work item so factory remains operable with empty registry
        items.append(
            {
                "work_item_id": _stable_id("placeholder", "idea"),
                "strategy_id": None,
                "title": "Seed first strategy idea",
                "owner": "research",
                "status": "queued",
                "pipeline_stage": PipelineStage.IDEA.value,
                "evidence": [{"source": "qsf", "id": "empty-registry"}],
                "dependencies": ["irl", "islm"],
                "required_approvals": ["human_operator"],
                "target_completion": target,
                "never_deploys": True,
                "requires_human_approval": True,
            }
        )
        return items

    for s in strategies:
        sd = _as_dict(s)
        sid = str(sd.get("strategy_id") or "")
        if not sid:
            continue
        derived = derive_stage_for_strategy(sd, ctx)
        stage = overrides.get(sid) or derived
        nxt = next_stage(stage)
        evidence = [
            {"source": "islm", "id": sid, "note": sd.get("lifecycle_state")},
        ]
        if _as_dict(sources.get("cvf")):
            evidence.append({"source": "cvf", "id": "cvf-snapshot"})
        if _as_dict(sources.get("qcs")):
            evidence.append({"source": "qcs", "id": "qcs-snapshot"})
        status = "awaiting_approval" if nxt else "done"
        items.append(
            {
                "work_item_id": _stable_id(sid, stage),
                "strategy_id": sid,
                "title": f"Advance {sd.get('name') or sid} toward {nxt or 'complete'}",
                "owner": str(sd.get("owner") or "strategy_owner"),
                "status": status,
                "pipeline_stage": stage,
                "next_stage": nxt,
                "evidence": evidence,
                "dependencies": ["islm", "cvf", "qcs", "qdie"],
                "required_approvals": ["human_operator"],
                "target_completion": target,
                "never_deploys": True,
                "never_executes_trades": True,
                "requires_human_approval": True,
                "name": sd.get("name") or sid,
            }
        )
    return items


def build_pipeline_board(work_items: list[dict[str, Any]]) -> dict[str, Any]:
    columns: dict[str, list[dict[str, Any]]] = {s: [] for s in PIPELINE_STAGES}
    for item in work_items:
        stage = str(item.get("pipeline_stage") or PipelineStage.IDEA.value)
        if stage not in columns:
            stage = PipelineStage.IDEA.value
        columns[stage].append(
            {
                "work_item_id": item.get("work_item_id"),
                "strategy_id": item.get("strategy_id"),
                "title": item.get("title"),
                "owner": item.get("owner"),
                "status": item.get("status"),
                "name": item.get("name"),
            }
        )
    return {
        "stages": list(PIPELINE_STAGES),
        "columns": columns,
        "counts": {s: len(columns[s]) for s in PIPELINE_STAGES},
        "read_only": True,
        "advancement_requires_human_approval": True,
    }


def build_dossiers(
    ctx: dict[str, Any], work_items: list[dict[str, Any]]
) -> dict[str, Any]:
    sources = _as_dict(ctx.get("sources"))
    strategies = _as_list(_as_dict(sources.get("islm")).get("registry"))
    dossiers: dict[str, Any] = {k: [] for k in DOSSIER_KINDS}

    for s in strategies:
        sd = _as_dict(s)
        sid = str(sd.get("strategy_id") or "")
        if not sid:
            continue
        item = next((w for w in work_items if w.get("strategy_id") == sid), None)
        stage = str((item or {}).get("pipeline_stage") or PipelineStage.IDEA.value)
        base = {
            "strategy_id": sid,
            "name": sd.get("name") or sid,
            "pipeline_stage": stage,
            "lifecycle_state": sd.get("lifecycle_state"),
            "evidence_ids": [e.get("id") for e in _as_list((item or {}).get("evidence"))],
            "human_approval_required": True,
            "never_deploys": True,
            "read_only": True,
        }
        dossiers["strategy_dossier"].append(
            {**base, "kind": "strategy_dossier", "sections": ["identity", "lifecycle", "owner"]}
        )
        dossiers["research_dossier"].append(
            {
                **base,
                "kind": "research_dossier",
                "iep_count": len(_as_list(_as_dict(sources.get("iep")).get("registry"))),
                "irl_count": len(_as_list(_as_dict(sources.get("irl")).get("experiments"))),
            }
        )
        dossiers["validation_dossier"].append(
            {
                **base,
                "kind": "validation_dossier",
                "cvf": _as_dict(sources.get("cvf")).get("confidence")
                or _as_dict(sources.get("cvf")),
                "simulations": len(_as_list(_as_dict(sources.get("ise")).get("simulations"))),
                "replays": len(_as_list(_as_dict(sources.get("replay")).get("simulations"))),
            }
        )
        dossiers["certification_dossier"].append(
            {
                **base,
                "kind": "certification_dossier",
                "qcs": {
                    "level": _as_dict(sources.get("qcs")).get("level"),
                    "scores": _as_dict(sources.get("qcs")).get("scores"),
                },
                "risk_alerts": len(_as_list(_as_dict(sources.get("irap")).get("alerts"))),
            }
        )
        ready = stage == PipelineStage.PAPER_TRADING_READY.value
        dossiers["paper_trading_dossier"].append(
            {
                **base,
                "kind": "paper_trading_dossier",
                "paper_trading_ready": ready,
                "qdie": bool(sources.get("qdie")),
                "blocked_reason": None
                if ready
                else "Awaiting human-approved pipeline completion",
                "never_goes_live_automatically": True,
            }
        )

    return {
        "dossiers": dossiers,
        "kinds": list(DOSSIER_KINDS),
        "read_only": True,
        "never_deploys_strategies": True,
    }


def build_approval_queue(
    work_items: list[dict[str, Any]],
    approvals: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []
    for item in work_items:
        if item.get("status") in {"awaiting_approval", "in_progress", "queued"}:
            nxt = item.get("next_stage")
            if not nxt:
                continue
            queue.append(
                {
                    "queue_id": _stable_id("queue", item.get("work_item_id")),
                    "work_item_id": item.get("work_item_id"),
                    "strategy_id": item.get("strategy_id"),
                    "from_stage": item.get("pipeline_stage"),
                    "to_stage": nxt,
                    "owner": item.get("owner"),
                    "title": item.get("title"),
                    "required_approvals": item.get("required_approvals"),
                    "status": "pending_human_approval",
                    "requires_human_approval": True,
                    "never_auto_advances": True,
                }
            )
    # Attach recent approval history summary
    hist = approvals or []
    for row in queue:
        sid = row.get("strategy_id")
        row["prior_approvals"] = [
            a
            for a in hist
            if isinstance(a, dict) and a.get("strategy_id") == sid
        ][:5]
    return queue


def build_reports(
    *,
    board: dict[str, Any],
    work_items: list[dict[str, Any]],
    dossiers: dict[str, Any],
    queue: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "factory_status_report": {
            "title": "QSF Factory Status",
            "stage_counts": board.get("counts"),
            "work_item_count": len(work_items),
            "approval_queue_depth": len(queue),
            "human_approval_required": True,
            "read_only": True,
        },
        "pipeline_progress_report": {
            "stages": board.get("stages"),
            "counts": board.get("counts"),
            "advancement_requires_human_approval": True,
        },
        "dossier_index": {
            "kinds": dossiers.get("kinds"),
            "counts": {
                k: len(_as_list(_as_dict(dossiers.get("dossiers")).get(k)))
                for k in DOSSIER_KINDS
            },
        },
        "approval_queue_report": {
            "pending": len(queue),
            "items": queue[:20],
            "never_auto_approves": True,
        },
    }


def workflow_consistency_check(
    work_items: list[dict[str, Any]], queue: list[dict[str, Any]]
) -> dict[str, Any]:
    issues: list[str] = []
    ids = [str(w.get("work_item_id") or "") for w in work_items]
    if len(ids) != len(set(ids)):
        issues.append("duplicate_work_item_ids")
    for w in work_items:
        stage = w.get("pipeline_stage")
        if stage not in PIPELINE_STAGES:
            issues.append(f"invalid_stage:{stage}")
        status = w.get("status")
        if status not in WORK_ITEM_STATUSES:
            issues.append(f"invalid_status:{status}")
        if w.get("requires_human_approval") is not True:
            issues.append("missing_human_approval_flag")
        if w.get("never_deploys") is not True and w.get("never_executes_trades") is not True:
            # at least one safety flag
            if "never_deploys" not in w:
                issues.append("missing_never_deploys")
        nxt = w.get("next_stage")
        if nxt and not can_transition(str(stage), str(nxt)):
            issues.append(f"invalid_next:{w.get('work_item_id')}")
    for q in queue:
        if q.get("requires_human_approval") is not True:
            issues.append("queue_missing_human_flag")
        if q.get("never_auto_advances") is not True:
            issues.append("queue_may_auto_advance")
        if not can_transition(str(q.get("from_stage")), str(q.get("to_stage"))):
            # next stage is always +1 which is valid
            if next_stage(str(q.get("from_stage"))) != q.get("to_stage"):
                issues.append(f"queue_bad_transition:{q.get('queue_id')}")
    return {"ok": len(issues) == 0, "issues": issues, "read_only": True}


def evidence_integrity_check(
    work_items: list[dict[str, Any]], dossiers: dict[str, Any]
) -> dict[str, Any]:
    issues: list[str] = []
    dossier_map = _as_dict(dossiers.get("dossiers"))
    for w in work_items:
        if not _as_list(w.get("evidence")):
            issues.append(f"no_evidence:{w.get('work_item_id')}")
        sid = w.get("strategy_id")
        if not sid:
            continue
        for kind in DOSSIER_KINDS:
            rows = _as_list(dossier_map.get(kind))
            if not any(_as_dict(r).get("strategy_id") == sid for r in rows):
                issues.append(f"missing_dossier:{kind}:{sid}")
    return {"ok": len(issues) == 0, "issues": issues, "read_only": True}
