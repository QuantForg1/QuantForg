"""Alpha Factory modules — research-only; never fabricate or promote."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

from app.domain.alpha_factory.config import (
    PROMOTION_STAGES,
    REPLAY_TIMEFRAMES,
    STRATEGY_FAMILIES,
    AlphaFactoryConfig,
)
from app.domain.alpha_factory.types import AlphaFactoryInput, ModuleResult


def _dec(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _insufficient(module: str, detail: str) -> ModuleResult:
    return ModuleResult(
        module=module,
        status="insufficient_data",
        score=None,
        recommendation="Insufficient Data",
        reasons=(detail, "Never fabricates research metrics"),
        details={},
    )


def research_workspace(
    inp: AlphaFactoryInput, config: AlphaFactoryConfig
) -> ModuleResult:
    exps = list(inp.experiments or [])
    exps = [e for e in exps if isinstance(e, dict)]
    draft = inp.experiment if isinstance(inp.experiment, dict) else None
    created: dict[str, Any] | None = None
    if draft is not None:
        created = {
            "id": str(draft.get("id") or f"exp_{uuid4().hex[:10]}"),
            "author": str(
                draft.get("author") or inp.author or "unknown"
            ),
            "version": str(draft.get("version") or "0.1.0"),
            "status": str(draft.get("status") or "draft"),
            "created": str(
                draft.get("created")
                or datetime.now(UTC).isoformat()
            ),
            "description": str(draft.get("description") or ""),
            "family": draft.get("family"),
            "cloned_from": draft.get("cloned_from"),
            "outside_production": True,
        }
        exps = [created, *exps]

    if not exps and created is None:
        return ModuleResult(
            module="research_workspace",
            status="empty",
            score=None,
            recommendation="No experiments in workspace",
            reasons=(
                "Supply experiment or experiments list",
                "Workspace is isolated from production",
            ),
            details={"experiments": [], "capacity": config.max_experiments},
        )

    capped = exps[: config.max_experiments]
    return ModuleResult(
        module="research_workspace",
        status="available",
        score=Decimal(len(capped)),
        recommendation=f"{len(capped)} research experiment(s)",
        reasons=(
            "Create / clone / compare / archive — research only",
            "Never modifies the live strategy",
        ),
        details={
            "experiments": capped,
            "created": created,
            "required_fields": [
                "id",
                "author",
                "version",
                "status",
                "created",
                "description",
            ],
            "outside_production": True,
        },
    )


def strategy_laboratory(
    inp: AlphaFactoryInput, config: AlphaFactoryConfig
) -> ModuleResult:
    _ = config
    strategies = list(inp.strategies or [])
    strategies = [s for s in strategies if isinstance(s, dict)]
    one = inp.strategy if isinstance(inp.strategy, dict) else None
    if one:
        family = str(one.get("family") or "Experimental")
        if family not in STRATEGY_FAMILIES:
            family = "Experimental"
        row = {
            **one,
            "family": family,
            "certified": False,
            "affects_production": False,
            "id": str(one.get("id") or f"str_{uuid4().hex[:8]}"),
        }
        strategies = [row, *strategies]

    by_family: dict[str, int] = dict.fromkeys(STRATEGY_FAMILIES, 0)
    for s in strategies:
        fam = str(s.get("family") or "Experimental")
        if fam not in by_family:
            fam = "Experimental"
        by_family[fam] += 1

    if not strategies:
        return ModuleResult(
            module="strategy_laboratory",
            status="empty",
            score=None,
            recommendation="Laboratory empty",
            reasons=(
                f"Supported families: {', '.join(STRATEGY_FAMILIES)}",
                "Strategies never affect production until certified",
            ),
            details={"families": by_family, "strategies": []},
        )

    return ModuleResult(
        module="strategy_laboratory",
        status="available",
        score=Decimal(len(strategies)),
        recommendation=f"{len(strategies)} lab strateg(y/ies)",
        reasons=(
            "Multi-family laboratory — SMC through Experimental",
            "Never affects production until certified (manual)",
        ),
        details={
            "families": by_family,
            "strategies": strategies[:100],
            "certified_count": sum(
                1 for s in strategies if s.get("certified") is True
            ),
            "affects_production": False,
        },
    )


def replay_engine(
    inp: AlphaFactoryInput, config: AlphaFactoryConfig
) -> ModuleResult:
    _ = config
    replay = inp.replay if isinstance(inp.replay, dict) else None
    if not replay:
        return ModuleResult(
            module="replay_engine",
            status="empty",
            score=None,
            recommendation="Await replay payload",
            reasons=(
                "Supply replay results for XAUUSD 1m/5m/15m",
                "Never invents historical bars or trades",
            ),
            details={"supported_timeframes": list(REPLAY_TIMEFRAMES)},
        )

    tf = str(replay.get("timeframe") or "")
    if tf and tf not in REPLAY_TIMEFRAMES:
        return ModuleResult(
            module="replay_engine",
            status="empty",
            score=None,
            recommendation="Unsupported timeframe",
            reasons=(
                f"timeframe={tf} not in {REPLAY_TIMEFRAMES}",
                "Never invents alternate timeframe data",
            ),
            details={"supported_timeframes": list(REPLAY_TIMEFRAMES)},
        )

    trades = replay.get("trades")
    if not isinstance(trades, list):
        trades = []
    metrics = {
        "trade_count": len(trades),
        "expectancy": replay.get("expectancy"),
        "drawdown": replay.get("drawdown") or replay.get("max_drawdown"),
        "profit_factor": replay.get("profit_factor"),
        "equity_curve": replay.get("equity_curve"),
        "journal": replay.get("journal") or trades[:50],
    }
    # Require at least one supplied metric or trades
    has_data = bool(trades) or any(
        metrics[k] is not None
        for k in ("expectancy", "drawdown", "profit_factor", "equity_curve")
    )
    if not has_data:
        return _insufficient(
            "replay_engine",
            "Replay payload lacks trades/metrics — Insufficient Data",
        )

    return ModuleResult(
        module="replay_engine",
        status="available",
        score=_dec(replay.get("expectancy")),
        recommendation=f"Replay {tf or 'n/a'} — {len(trades)} trades",
        reasons=(
            "Historical XAUUSD replay from supplied results only",
            "Outside production — no live orders",
        ),
        details={
            "timeframe": tf or None,
            "metrics": metrics,
            "symbol": "XAUUSD",
            "invented": False,
        },
    )


def paper_trading_pipeline(
    inp: AlphaFactoryInput, config: AlphaFactoryConfig
) -> ModuleResult:
    _ = config
    paper = inp.paper if isinstance(inp.paper, dict) else None
    if not paper:
        return ModuleResult(
            module="paper_trading_pipeline",
            status="empty",
            score=None,
            recommendation="Await paper results",
            reasons=(
                "Paper pipeline runs against live market data — no real orders",
                "Supply paper trades / performance / risk / timing",
            ),
            details={"real_orders": False},
        )

    trades = paper.get("trades") if isinstance(paper.get("trades"), list) else []
    if not trades and not any(
        paper.get(k) is not None
        for k in ("performance", "risk_metrics", "execution_timing")
    ):
        return _insufficient(
            "paper_trading_pipeline",
            "Paper payload empty — Insufficient Data",
        )

    return ModuleResult(
        module="paper_trading_pipeline",
        status="available",
        score=_dec(
            (paper.get("performance") or {}).get("expectancy")
            if isinstance(paper.get("performance"), dict)
            else paper.get("expectancy")
        ),
        recommendation=f"Paper trades n={len(trades)}",
        reasons=(
            "No real orders — paper only",
            "Does not touch Execution Pipeline or Auto Trading",
        ),
        details={
            "paper_trades": trades[:100],
            "performance": paper.get("performance"),
            "risk_metrics": paper.get("risk_metrics"),
            "execution_timing": paper.get("execution_timing"),
            "real_orders": False,
        },
    )


def benchmark_engine(
    inp: AlphaFactoryInput, config: AlphaFactoryConfig
) -> ModuleResult:
    rows = list(inp.benchmarks or [])
    rows = [r for r in rows if isinstance(r, dict)]
    if len(rows) < 2:
        return ModuleResult(
            module="benchmark_engine",
            status="insufficient_data",
            score=None,
            recommendation="Insufficient Data",
            reasons=(
                "Need ≥2 strategies (A/B/C…) with supplied metrics",
                f"min_trades_for_benchmark={config.min_trades_for_benchmark}",
            ),
            details={"candidates": rows},
        )

    table = []
    for r in rows[:20]:
        tc = r.get("trade_count")
        try:
            tc_i = int(tc) if tc is not None else None
        except (TypeError, ValueError):
            tc_i = None
        if tc_i is not None and tc_i < config.min_trades_for_benchmark:
            table.append(
                {
                    "name": r.get("name") or r.get("id"),
                    "status": "Insufficient Data",
                    "trade_count": tc_i,
                }
            )
            continue
        table.append(
            {
                "name": r.get("name") or r.get("id"),
                "win_rate": r.get("win_rate"),
                "profit_factor": r.get("profit_factor"),
                "drawdown": r.get("drawdown"),
                "expectancy": r.get("expectancy"),
                "trade_count": tc_i,
                "status": "available",
            }
        )

    return ModuleResult(
        module="benchmark_engine",
        status="available",
        score=Decimal(len(table)),
        recommendation=f"Benchmark {len(table)} strategies",
        reasons=(
            "Comparison uses supplied metrics only",
            "Never invents missing win rate / PF / drawdown",
        ),
        details={"comparison": table},
    )


def promotion_workflow(
    inp: AlphaFactoryInput, config: AlphaFactoryConfig
) -> ModuleResult:
    _ = config
    promo = inp.promotion if isinstance(inp.promotion, dict) else {}
    stage = str(promo.get("stage") or "Development")
    if stage not in PROMOTION_STAGES:
        stage = "Development"
    approvals = promo.get("approvals") if isinstance(
        promo.get("approvals"), dict
    ) else {}
    try:
        idx = PROMOTION_STAGES.index(stage)
    except ValueError:
        idx = 0
    next_stage = (
        PROMOTION_STAGES[idx + 1] if idx + 1 < len(PROMOTION_STAGES) else None
    )

    # Never auto-advance to Production
    auto = False
    blocked = stage == "Production" and promo.get("auto_promote") is True

    return ModuleResult(
        module="promotion_workflow",
        status="available",
        score=Decimal(idx),
        recommendation=f"Stage: {stage}",
        reasons=(
            "Development → Replay → Paper → Research → Risk → Operator "
            "→ Candidate → Production",
            "No automatic promotion",
            "Production requires human approvals at each gate",
        ),
        details={
            "stages": list(PROMOTION_STAGES),
            "current_stage": stage,
            "next_stage": next_stage,
            "approvals": {
                "research": approvals.get("research"),
                "risk": approvals.get("risk"),
                "operator": approvals.get("operator"),
            },
            "automatic_promotion": auto,
            "auto_promote_blocked": blocked or True,
            "never_auto_promotes": True,
            "strategy_id": promo.get("strategy_id"),
        },
    )


def experiment_history(
    inp: AlphaFactoryInput, config: AlphaFactoryConfig
) -> ModuleResult:
    events = []
    # Existing experiments as immutable history seeds
    for e in inp.experiments or []:
        if isinstance(e, dict):
            events.append(
                {
                    "event_id": f"eh_{uuid4().hex[:8]}",
                    "experiment_id": e.get("id"),
                    "changes": e.get("changes"),
                    "metrics": e.get("metrics"),
                    "results": e.get("results"),
                    "comments": e.get("comments"),
                    "append_only": True,
                }
            )
    he = inp.history_event if isinstance(inp.history_event, dict) else None
    if he:
        events.insert(
            0,
            {
                "event_id": f"eh_{uuid4().hex[:8]}",
                "experiment_id": he.get("experiment_id"),
                "changes": he.get("changes"),
                "metrics": he.get("metrics"),
                "results": he.get("results"),
                "comments": he.get("comments"),
                "append_only": True,
                "never_overwrite": True,
            },
        )

    if not events:
        return ModuleResult(
            module="experiment_history",
            status="empty",
            score=None,
            recommendation="No history events",
            reasons=("Store every experiment — never overwrite",),
            details={"events": [], "max_history": config.max_history},
        )

    capped = events[: config.max_history]
    return ModuleResult(
        module="experiment_history",
        status="available",
        score=Decimal(len(capped)),
        recommendation=f"{len(capped)} history event(s)",
        reasons=(
            "Append-only experiment history",
            "Never overwrites prior results",
        ),
        details={"events": capped, "never_overwrite": True},
    )


def research_dashboard(
    modules: dict[str, ModuleResult],
) -> ModuleResult:
    ws = modules.get("research_workspace")
    lab = modules.get("strategy_laboratory")
    replay = modules.get("replay_engine")
    paper = modules.get("paper_trading_pipeline")
    promo = modules.get("promotion_workflow")

    active = []
    if ws and isinstance((ws.details or {}).get("experiments"), list):
        active = [
            e
            for e in ws.details["experiments"]
            if str(e.get("status") or "").lower()
            not in {"archived", "rejected"}
        ]
    certified = 0
    if lab:
        certified = int((lab.details or {}).get("certified_count") or 0)

    return ModuleResult(
        module="research_dashboard",
        status="available",
        score=Decimal(len(active)),
        recommendation="Research dashboard snapshot",
        reasons=(
            f"Active experiments={len(active)}",
            f"Certified strategies={certified}",
            "Outside production",
        ),
        details={
            "active_experiments": active[:50],
            "certified_strategies": certified,
            "paper_performance": (
                (paper.details or {}).get("performance") if paper else None
            ),
            "replay_performance": (
                (replay.details or {}).get("metrics") if replay else None
            ),
            "approval_status": (
                (promo.details or {}).get("approvals") if promo else None
            ),
            "promotion_stage": (
                (promo.details or {}).get("current_stage") if promo else None
            ),
        },
    )


def alpha_score(
    inp: AlphaFactoryInput, config: AlphaFactoryConfig
) -> ModuleResult:
    src = inp.score_inputs if isinstance(inp.score_inputs, dict) else {}
    # Also accept from replay/paper metrics
    dims = (
        "consistency",
        "risk_discipline",
        "edge_stability",
        "capital_preservation",
        "market_adaptability",
        "execution_quality",
    )
    values: dict[str, Decimal] = {}
    for d in dims:
        v = _dec(src.get(d))
        if v is not None:
            values[d] = v

    trade_n = None
    if isinstance(inp.replay, dict) and isinstance(
        inp.replay.get("trades"), list
    ):
        trade_n = len(inp.replay["trades"])
    elif isinstance(inp.paper, dict) and isinstance(
        inp.paper.get("trades"), list
    ):
        trade_n = len(inp.paper["trades"])
    if trade_n is not None and trade_n < config.min_trades_for_score:
        return _insufficient(
            "alpha_score",
            f"Need ≥{config.min_trades_for_score} trades; have {trade_n}",
        )
    if len(values) < 3:
        return _insufficient(
            "alpha_score",
            "Need ≥3 supplied score dimensions — Insufficient Data",
        )

    overall = (
        sum(values.values()) / Decimal(len(values))
    ).quantize(Decimal("0.01"))
    return ModuleResult(
        module="alpha_score",
        status="available",
        score=overall,
        recommendation=f"Alpha score {overall}",
        reasons=(
            f"Dimensions used: {', '.join(values)}",
            "Observational — not a profitability guarantee",
            "Does not promote strategies",
        ),
        details={
            "dimensions": {k: str(v) for k, v in values.items()},
            "trade_count": trade_n,
            "insufficient_dimensions": [
                d for d in dims if d not in values
            ],
        },
    )


def promotion_report(
    inp: AlphaFactoryInput, modules: dict[str, ModuleResult]
) -> ModuleResult:
    promo = inp.promotion if isinstance(inp.promotion, dict) else {}
    stage = (promo.get("stage") if promo else None) or (
        (modules.get("promotion_workflow").details or {}).get("current_stage")
        if modules.get("promotion_workflow")
        else "Development"
    )
    strengths: list[str] = []
    weaknesses: list[str] = []
    recommendations: list[str] = [
        "Human review required before any production move",
        "Never promote automatically",
        "Do not modify live strategy / Risk / Safety / "
        "Decision / Execution / Auto Trading",
    ]

    alpha = modules.get("alpha_score")
    if alpha and alpha.status == "available":
        strengths.append(f"Alpha score available: {alpha.recommendation}")
    else:
        weaknesses.append("Alpha score Insufficient Data")

    replay = modules.get("replay_engine")
    if replay and replay.status == "available":
        strengths.append(replay.recommendation)
    paper = modules.get("paper_trading_pipeline")
    if paper and paper.status == "available":
        strengths.append(paper.recommendation)
    else:
        weaknesses.append("Paper trading evidence incomplete")

    regimes = promo.get("observed_regimes") if promo else None
    sessions = promo.get("observed_sessions") if promo else None
    risk_profile = promo.get("risk_profile") if promo else None
    limitations = promo.get("known_limitations") if promo else None

    return ModuleResult(
        module="promotion_report",
        status="available",
        score=alpha.score if alpha and alpha.score is not None else None,
        recommendation="Promotion report (human gate)",
        reasons=(
            f"Current stage={stage}",
            "Report does not advance promotion automatically",
        ),
        details={
            "stage": stage,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "observed_regimes": regimes,
            "observed_sessions": sessions,
            "risk_profile": risk_profile,
            "known_limitations": limitations
            or ["Research isolation — not certified for live"],
            "human_recommendations": recommendations,
            "never_auto_promotes": True,
            "certified_for_production": False,
        },
    )
