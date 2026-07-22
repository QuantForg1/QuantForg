"""IEE analytical modules — advisory only; never fabricate metrics."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation
from statistics import pstdev
from typing import Any

from app.domain.institutional_edge_engine.config import IeeConfig
from app.domain.institutional_edge_engine.types import IeeInput, ModuleResult

REGIME_KEYS = (
    "trend",
    "range",
    "high_volatility",
    "low_volatility",
    "london",
    "new_york",
    "asia",
    "news",
)


def _dec(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _trades(inp: IeeInput) -> list[dict[str, Any]]:
    rows = inp.completed_trades
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)]


def _insufficient(module: str, need: int, have: int) -> ModuleResult:
    return ModuleResult(
        module=module,
        status="insufficient_data",
        score=None,
        recommendation="Insufficient Data",
        reasons=(
            f"Need ≥{need} completed trades; have {have}",
            "Never fabricates edge metrics",
        ),
        details={"required": need, "available": have},
    )


def _win(t: dict[str, Any]) -> bool | None:
    if isinstance(t.get("win"), bool):
        return t["win"]
    pnl = _dec(t.get("pnl") or t.get("net_pnl"))
    if pnl is None:
        return None
    return pnl > 0


def _rr(t: dict[str, Any]) -> Decimal | None:
    return _dec(t.get("rr") or t.get("reward_risk") or t.get("r_multiple"))


def score_edge(inp: IeeInput, config: IeeConfig) -> ModuleResult:
    trades = _trades(inp)
    if len(trades) < config.min_trades_for_edge:
        return _insufficient(
            "edge_scoring", config.min_trades_for_edge, len(trades)
        )

    wins = 0
    losses = 0
    pnl_sum = Decimal("0")
    win_pnls: list[Decimal] = []
    loss_pnls: list[Decimal] = []
    rrs: list[Decimal] = []
    equity = Decimal("0")
    peak = Decimal("0")
    max_dd = Decimal("0")
    streak_w = streak_l = 0
    max_cw = max_cl = 0

    for t in trades:
        w = _win(t)
        pnl = _dec(t.get("pnl") or t.get("net_pnl")) or Decimal("0")
        pnl_sum += pnl
        equity += pnl
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd
        rr = _rr(t)
        if rr is not None:
            rrs.append(rr)
        if w is True:
            wins += 1
            win_pnls.append(pnl)
            streak_w += 1
            streak_l = 0
            max_cw = max(max_cw, streak_w)
        elif w is False:
            losses += 1
            loss_pnls.append(abs(pnl))
            streak_l += 1
            streak_w = 0
            max_cl = max(max_cl, streak_l)

    n = wins + losses
    if n == 0:
        return ModuleResult(
            module="edge_scoring",
            status="empty",
            score=None,
            recommendation="Insufficient Data",
            reasons=("Trades lack win/pnl fields",),
        )

    win_rate = (Decimal(wins) / Decimal(n) * Decimal(100)).quantize(
        Decimal("0.01")
    )
    avg_rr = (
        (sum(rrs) / Decimal(len(rrs))).quantize(Decimal("0.01"))
        if rrs
        else None
    )
    gross_win = sum(win_pnls) if win_pnls else Decimal("0")
    gross_loss = sum(loss_pnls) if loss_pnls else Decimal("0")
    profit_factor = (
        (gross_win / gross_loss).quantize(Decimal("0.01"))
        if gross_loss > 0
        else None
    )
    expectancy = (pnl_sum / Decimal(n)).quantize(Decimal("0.01"))
    recovery = (
        (pnl_sum / max_dd).quantize(Decimal("0.01"))
        if max_dd > 0
        else None
    )

    # Composite edge score 0-100 from supplied stats only
    score = Decimal("50")
    if win_rate >= 50:
        score += Decimal("10")
    if avg_rr is not None and avg_rr >= 1:
        score += Decimal("10")
    if profit_factor is not None and profit_factor >= 1:
        score += Decimal("10")
    if expectancy > 0:
        score += Decimal("10")
    if max_dd == 0 or (pnl_sum > 0 and max_dd < abs(pnl_sum)):
        score += Decimal("5")
    score = min(max(score, Decimal("0")), Decimal("100")).quantize(
        Decimal("0.01")
    )

    return ModuleResult(
        module="edge_scoring",
        status="available",
        score=score,
        recommendation=f"Edge score {score}",
        reasons=(
            f"n={n} expectancy={expectancy} win_rate={win_rate}%",
            f"avg_rr={avg_rr} profit_factor={profit_factor}",
            f"max_dd={max_dd} recovery={recovery}",
            f"max consecutive W/L={max_cw}/{max_cl}",
            "Observational — not a profitability guarantee",
        ),
        details={
            "expectancy": str(expectancy),
            "win_rate_pct": str(win_rate),
            "average_rr": str(avg_rr) if avg_rr is not None else None,
            "profit_factor": (
                str(profit_factor) if profit_factor is not None else None
            ),
            "maximum_drawdown": str(max_dd),
            "recovery_factor": (
                str(recovery) if recovery is not None else None
            ),
            "consecutive_wins_max": max_cw,
            "consecutive_losses_max": max_cl,
            "sample_size": n,
        },
    )


def evaluate_strategy_stability(
    inp: IeeInput, config: IeeConfig
) -> ModuleResult:
    trades = _trades(inp)
    windows = [w for w in config.rolling_windows if w > 0]
    if not trades:
        return ModuleResult(
            module="strategy_stability",
            status="empty",
            score=None,
            recommendation="Insufficient Data",
            reasons=("No completed trades supplied",),
        )

    alerts: list[str] = []
    window_stats: dict[str, Any] = {}
    for w in windows:
        if len(trades) < w:
            window_stats[str(w)] = {
                "status": "insufficient_data",
                "available": len(trades),
                "required": w,
            }
            continue
        slice_t = trades[-w:]
        pnls = [
            float(_dec(t.get("pnl") or t.get("net_pnl")) or 0) for t in slice_t
        ]
        wins = sum(1 for t in slice_t if _win(t) is True)
        wr = wins / w * 100
        variance = pstdev(pnls) if len(pnls) > 1 else 0.0
        window_stats[str(w)] = {
            "status": "available",
            "win_rate_pct": round(wr, 2),
            "pnl_stdev": round(variance, 4),
            "n": w,
        }
        if Decimal(str(variance)) >= config.stability_variance_warn:
            alerts.append(f"Rolling {w}: abnormal variance {variance:.2f}")
        if wr < 40:
            alerts.append(f"Rolling {w}: degradation win_rate={wr:.1f}%")

    if not any(
        isinstance(v, dict) and v.get("status") == "available"
        for v in window_stats.values()
    ):
        return _insufficient(
            "strategy_stability",
            min(windows) if windows else config.min_trades_for_edge,
            len(trades),
        )

    score = Decimal("70")
    if alerts:
        score -= Decimal(min(40, 10 * len(alerts)))
    score = min(max(score, Decimal("0")), Decimal("100")).quantize(
        Decimal("0.01")
    )
    return ModuleResult(
        module="strategy_stability",
        status="available",
        score=score,
        recommendation=(
            "Stability alerts" if alerts else "Rolling windows stable"
        ),
        reasons=(
            *(alerts or ("No degradation/instability alerts from supplied rolls",)),
            "Advisory alerts only — never disables trading",
        ),
        details={
            "windows": window_stats,
            "alerts": alerts,
            "never_disables_trading": True,
        },
    )


def evaluate_regime_performance(
    inp: IeeInput, config: IeeConfig
) -> ModuleResult:
    trades = _trades(inp)
    if len(trades) < config.min_trades_for_regime:
        return _insufficient(
            "regime_performance",
            config.min_trades_for_regime,
            len(trades),
        )

    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in trades:
        tags = []
        for key in ("regime", "volatility", "session", "news"):
            val = t.get(key)
            if val is None:
                continue
            s = str(val).lower().replace(" ", "_")
            if key == "volatility":
                if "high" in s:
                    tags.append("high_volatility")
                elif "low" in s:
                    tags.append("low_volatility")
            elif key == "session":
                if "london" in s:
                    tags.append("london")
                elif "new_york" in s or "ny" in s:
                    tags.append("new_york")
                elif "asia" in s or "asian" in s:
                    tags.append("asia")
            elif key == "news" and (
                val is True or s in {"true", "1", "news", "yes"}
            ):
                tags.append("news")
            elif key == "regime":
                if "trend" in s:
                    tags.append("trend")
                elif "range" in s or "mean" in s:
                    tags.append("range")
        for tag in tags:
            if tag in REGIME_KEYS:
                buckets[tag].append(t)

    if not buckets:
        return ModuleResult(
            module="regime_performance",
            status="empty",
            score=None,
            recommendation="Insufficient Data",
            reasons=(
                "Trades lack regime/session/volatility/news tags",
                "Never invents regime labels",
            ),
        )

    ranked = []
    for key, rows in buckets.items():
        n = len(rows)
        wins = sum(1 for r in rows if _win(r) is True)
        wr = (Decimal(wins) / Decimal(n) * 100).quantize(Decimal("0.01"))
        ranked.append({"regime": key, "n": n, "win_rate_pct": str(wr)})
    ranked.sort(key=lambda r: Decimal(r["win_rate_pct"]), reverse=True)
    best = ranked[0]
    return ModuleResult(
        module="regime_performance",
        status="available",
        score=Decimal(best["win_rate_pct"]),
        recommendation=(
            f"Historically strongest: {best['regime']} "
            f"({best['win_rate_pct']}%, n={best['n']})"
        ),
        reasons=(
            f"{len(ranked)} regime/session buckets with supplied tags",
            "Display only — does not change market selection rules",
        ),
        details={"buckets": ranked, "best": best},
    )


def evaluate_entry_quality(inp: IeeInput, config: IeeConfig) -> ModuleResult:
    trades = _trades(inp)
    if len(trades) < config.min_trades_for_entry_exit:
        return _insufficient(
            "entry_quality",
            config.min_trades_for_entry_exit,
            len(trades),
        )

    late = early = missed = 0
    maes: list[Decimal] = []
    mafes: list[Decimal] = []
    for t in trades:
        timing = str(t.get("entry_timing") or "").lower()
        if "late" in timing:
            late += 1
        elif "early" in timing:
            early += 1
        if t.get("missed_opportunity") is True:
            missed += 1
        mae = _dec(t.get("mae") or t.get("average_adverse_excursion"))
        mfe = _dec(t.get("mfe") or t.get("average_favorable_excursion"))
        if mae is not None:
            maes.append(mae)
        if mfe is not None:
            mafes.append(mfe)

    if not maes and not mafes and late + early + missed == 0:
        return ModuleResult(
            module="entry_quality",
            status="empty",
            score=None,
            recommendation="Insufficient Data",
            reasons=(
                "No entry_timing / MAE / MFE fields on completed trades",
            ),
        )

    avg_mae = (
        (sum(maes) / Decimal(len(maes))).quantize(Decimal("0.01"))
        if maes
        else None
    )
    avg_mfe = (
        (sum(mafes) / Decimal(len(mafes))).quantize(Decimal("0.01"))
        if mafes
        else None
    )
    score = Decimal("70")
    score -= Decimal(min(30, late * 2 + early + missed))
    score = min(max(score, Decimal("0")), Decimal("100")).quantize(
        Decimal("0.01")
    )
    return ModuleResult(
        module="entry_quality",
        status="available",
        score=score,
        recommendation=f"Entry quality {score}",
        reasons=(
            f"late={late} early={early} missed={missed}",
            f"avg_mae={avg_mae} avg_mfe={avg_mfe}",
            "From supplied trade fields only",
        ),
        details={
            "late_entries": late,
            "early_entries": early,
            "missed_opportunities": missed,
            "average_adverse_excursion": (
                str(avg_mae) if avg_mae is not None else None
            ),
            "average_favorable_excursion": (
                str(avg_mfe) if avg_mfe is not None else None
            ),
            "sample_size": len(trades),
        },
    )


def evaluate_exit_quality(inp: IeeInput, config: IeeConfig) -> ModuleResult:
    trades = _trades(inp)
    if len(trades) < config.min_trades_for_entry_exit:
        return _insufficient(
            "exit_quality",
            config.min_trades_for_entry_exit,
            len(trades),
        )

    holds: list[Decimal] = []
    premature = late = 0
    efficiencies: list[Decimal] = []
    for t in trades:
        hold = _dec(t.get("holding_time_sec") or t.get("hold_sec"))
        if hold is not None:
            holds.append(hold)
        timing = str(t.get("exit_timing") or "").lower()
        if "premature" in timing or "early" in timing:
            premature += 1
        elif "late" in timing:
            late += 1
        eff = _dec(t.get("exit_efficiency"))
        if eff is not None:
            efficiencies.append(eff)

    if not holds and not efficiencies and premature + late == 0:
        return ModuleResult(
            module="exit_quality",
            status="empty",
            score=None,
            recommendation="Insufficient Data",
            reasons=("No exit timing / hold / efficiency fields supplied",),
        )

    avg_hold = (
        (sum(holds) / Decimal(len(holds))).quantize(Decimal("0.01"))
        if holds
        else None
    )
    avg_eff = (
        (sum(efficiencies) / Decimal(len(efficiencies))).quantize(
            Decimal("0.01")
        )
        if efficiencies
        else None
    )
    score = Decimal("70")
    score -= Decimal(min(30, premature * 2 + late * 2))
    if avg_eff is not None:
        score = (score + avg_eff) / Decimal("2")
    score = min(max(score, Decimal("0")), Decimal("100")).quantize(
        Decimal("0.01")
    )
    return ModuleResult(
        module="exit_quality",
        status="available",
        score=score,
        recommendation=f"Exit quality {score}",
        reasons=(
            f"avg_holding_sec={avg_hold} exit_efficiency={avg_eff}",
            f"premature={premature} late={late}",
        ),
        details={
            "average_holding_time_sec": (
                str(avg_hold) if avg_hold is not None else None
            ),
            "exit_efficiency": str(avg_eff) if avg_eff is not None else None,
            "premature_exits": premature,
            "late_exits": late,
            "sample_size": len(trades),
        },
    )


def evaluate_risk_discipline(
    inp: IeeInput, config: IeeConfig
) -> ModuleResult:
    _ = config
    facts = (
        inp.discipline_facts if isinstance(inp.discipline_facts, dict) else {}
    )
    trades = _trades(inp)
    if not facts and not trades:
        return ModuleResult(
            module="risk_discipline",
            status="empty",
            score=None,
            recommendation="Insufficient Data",
            reasons=("No discipline_facts or trades supplied",),
        )

    reasons: list[str] = []
    score = Decimal("70")
    keys = (
        ("rule_compliance_pct", Decimal("0.2")),
        ("risk_consistency_pct", Decimal("0.15")),
        ("position_sizing_consistency_pct", Decimal("0.15")),
        ("drawdown_control_pct", Decimal("0.15")),
        ("capital_preservation_pct", Decimal("0.15")),
    )
    present = 0
    for key, weight in keys:
        val = _dec(facts.get(key))
        if val is None:
            continue
        present += 1
        reasons.append(f"{key}={val}")
        # blend toward supplied pct
        score = score * (Decimal("1") - weight) + val * weight

    # sizing consistency from trades if risk_pct present
    risks = [_dec(t.get("risk_pct")) for t in trades]
    risks_f = [float(r) for r in risks if r is not None]
    if len(risks_f) >= 5:
        present += 1
        var = pstdev(risks_f)
        reasons.append(f"position risk_pct stdev={var:.4f} (from trades)")
        if var > 0.5:
            score -= Decimal("10")

    if present == 0:
        return ModuleResult(
            module="risk_discipline",
            status="empty",
            score=None,
            recommendation="Insufficient Data",
            reasons=("Discipline fields not present on input",),
        )

    score = min(max(score, Decimal("0")), Decimal("100")).quantize(
        Decimal("0.01")
    )
    reasons.append("Never auto-modifies risk policies")
    return ModuleResult(
        module="risk_discipline",
        status="available",
        score=score,
        recommendation=f"Risk discipline {score}",
        reasons=tuple(reasons),
        details={"facts": facts or None, "auto_modifies_risk_policies": False},
    )


def detect_edge_decay(
    inp: IeeInput, config: IeeConfig, edge: ModuleResult
) -> ModuleResult:
    trades = _trades(inp)
    if edge.status != "available" or edge.score is None:
        return ModuleResult(
            module="edge_decay",
            status="insufficient_data",
            score=None,
            recommendation="Insufficient Data",
            reasons=(
                "Edge score unavailable — decay not evaluated",
                "Never disables trading automatically",
            ),
            details={"edge_warning": False, "never_disables_trading": True},
        )

    score = edge.score
    prior = inp.prior_edge_score
    warning = score < config.edge_warning_threshold
    critical = score < config.edge_critical_threshold
    reasons = [f"Current edge score={score}"]
    if prior is not None:
        reasons.append(f"Prior edge score={prior}")
        if score + Decimal("5") < prior:
            reasons.append("Observed decline vs prior supplied score")
            warning = True
    # recent half vs older half when enough trades
    if len(trades) >= config.min_trades_for_edge * 2:
        mid = len(trades) // 2
        older = trades[:mid]
        recent = trades[mid:]
        o_wins = sum(1 for t in older if _win(t) is True)
        r_wins = sum(1 for t in recent if _win(t) is True)
        o_n = max(1, sum(1 for t in older if _win(t) is not None))
        r_n = max(1, sum(1 for t in recent if _win(t) is not None))
        o_wr = Decimal(o_wins) / Decimal(o_n) * 100
        r_wr = Decimal(r_wins) / Decimal(r_n) * 100
        reasons.append(
            f"Older half WR={o_wr.quantize(Decimal('0.01'))}% "
            f"vs recent={r_wr.quantize(Decimal('0.01'))}%"
        )
        if r_wr + Decimal("10") < o_wr:
            warning = True
            reasons.append("Recent half weaker than older half (supplied)")

    if critical:
        label = "EDGE WARNING (critical threshold)"
    elif warning:
        label = "EDGE WARNING"
    else:
        label = "Edge within configured thresholds"

    return ModuleResult(
        module="edge_decay",
        status="available",
        score=score,
        recommendation=label,
        reasons=(
            *reasons,
            f"Warn < {config.edge_warning_threshold}; "
            f"critical < {config.edge_critical_threshold}",
            "Advisory only — never disables trading automatically",
        ),
        details={
            "edge_warning": warning or critical,
            "critical": critical,
            "never_disables_trading": True,
            "sample_size": len(trades),
        },
    )


def explainable_edge_report(
    modules: dict[str, ModuleResult],
) -> ModuleResult:
    bullets: list[str] = []
    edge = modules.get("edge_scoring")
    stab = modules.get("strategy_stability")
    regime = modules.get("regime_performance")
    decay = modules.get("edge_decay")

    if edge and edge.status == "available":
        bullets.append(f"Edge: {edge.recommendation}")
        d = edge.details
        if d.get("expectancy"):
            bullets.append(f"Expectancy observed={d['expectancy']}")
    elif edge:
        bullets.append("Edge: Insufficient Data")

    if stab and stab.status == "available":
        alerts = (stab.details or {}).get("alerts") or []
        if alerts:
            bullets.append(f"Stability: {len(alerts)} advisory alert(s)")
            bullets.extend(str(a) for a in alerts[:3])
        else:
            bullets.append("Stability: no degradation alerts from rolls")

    if regime and regime.status == "available":
        best = (regime.details or {}).get("best") or {}
        if best:
            bullets.append(
                f"Best supplied regime/session: {best.get('regime')} "
                f"(n={best.get('n')})"
            )

    if decay and decay.status == "available":
        bullets.append(f"Decay: {decay.recommendation}")
        if (decay.details or {}).get("edge_warning"):
            bullets.append("EDGE WARNING raised — human review recommended")

    if not bullets:
        bullets.append("No observations available to explain")

    bullets.append("No speculation — conclusions limited to supplied trades")
    return ModuleResult(
        module="explainable_edge_report",
        status="available",
        score=None,
        recommendation="Explainable edge report",
        reasons=tuple(bullets[:24]),
        details={"points": bullets, "speculation": False},
    )


def institutional_scorecard(
    modules: dict[str, ModuleResult],
) -> ModuleResult:
    mapping = {
        "Trading Discipline": "risk_discipline",
        "Execution Quality": "entry_quality",
        "Risk Discipline": "risk_discipline",
        "Market Selection": "regime_performance",
        "Entry Quality": "entry_quality",
        "Exit Quality": "exit_quality",
        "Capital Preservation": "risk_discipline",
        "Edge Stability": "strategy_stability",
    }
    panels: dict[str, Any] = {}
    scores: list[Decimal] = []
    for label, key in mapping.items():
        mod = modules.get(key)
        if mod is None or mod.status != "available" or mod.score is None:
            panels[label] = {"status": "Insufficient Data", "score": None}
        else:
            panels[label] = {
                "status": "available",
                "score": str(mod.score),
            }
            scores.append(mod.score)

    edge = modules.get("edge_scoring")
    if edge and edge.status == "available" and edge.score is not None:
        scores.append(edge.score)

    if not scores:
        return ModuleResult(
            module="institutional_scorecard",
            status="insufficient_data",
            score=None,
            recommendation="Insufficient Data",
            reasons=("Not enough module scores for an institutional grade",),
            details={"panels": panels, "overall_grade": None},
        )

    overall = (sum(scores) / Decimal(len(scores))).quantize(Decimal("0.01"))
    if overall >= 80:
        grade = "A"
    elif overall >= 65:
        grade = "B"
    elif overall >= 50:
        grade = "C"
    else:
        grade = "D"

    return ModuleResult(
        module="institutional_scorecard",
        status="available",
        score=overall,
        recommendation=f"Overall Institutional Grade {grade}",
        reasons=(
            f"Composite {overall} across {len(scores)} scored panels",
            "Grade is observational — not a profitability claim",
        ),
        details={
            "panels": panels,
            "overall_grade": grade,
            "overall_score": str(overall),
        },
    )


def monthly_research_package(
    inp: IeeInput,
    config: IeeConfig,
    modules: dict[str, ModuleResult],
) -> ModuleResult:
    trades = _trades(inp)
    if len(trades) < config.min_trades_for_edge:
        return _insufficient(
            "monthly_research_package",
            config.min_trades_for_edge,
            len(trades),
        )

    strengths: list[str] = []
    weaknesses: list[str] = []
    recommendations: list[str] = []

    edge = modules.get("edge_scoring")
    if edge and edge.status == "available":
        strengths.append(f"Edge scoring available: {edge.recommendation}")
        d = edge.details
        if _dec(d.get("win_rate_pct")) is not None and _dec(
            d.get("win_rate_pct")
        ) < Decimal("45"):
            weaknesses.append(f"Win rate {d.get('win_rate_pct')}% observed")
    else:
        weaknesses.append("Edge scoring insufficient")

    regime = modules.get("regime_performance")
    if regime and regime.status == "available":
        strengths.append(regime.recommendation)
    stab = modules.get("strategy_stability")
    if stab and (stab.details or {}).get("alerts"):
        weaknesses.append("Rolling stability alerts present")
        recommendations.append(
            "Human review of recent rolling windows recommended"
        )

    decay = modules.get("edge_decay")
    if decay and (decay.details or {}).get("edge_warning"):
        weaknesses.append("EDGE WARNING active")
        recommendations.append(
            "Review edge decay with operators — do not auto-disable trading"
        )

    recommendations.append(
        "Do not modify strategy rules automatically from this package"
    )
    recommendations.append(
        "Validate conclusions against raw completed-trade exports"
    )

    return ModuleResult(
        module="monthly_research_package",
        status="available",
        score=edge.score if edge and edge.score is not None else None,
        recommendation="Monthly research package (human review)",
        reasons=(
            f"Month label={inp.research_month or 'unspecified'}",
            f"Completed trades n={len(trades)}",
            "Advisory package only",
        ),
        details={
            "month": inp.research_month,
            "performance_summary": edge.to_dict() if edge else None,
            "observed_strengths": strengths,
            "observed_weaknesses": weaknesses,
            "market_regime_analysis": (
                regime.to_dict() if regime else None
            ),
            "session_analysis": (
                regime.details if regime and regime.status == "available" else None
            ),
            "recommendations_for_human_review": recommendations,
            "auto_modifies_strategy_rules": False,
        },
    )
