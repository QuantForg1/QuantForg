"""IVP modules — read-only evidence; never invents metrics or places trades."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from math import sqrt
from statistics import pstdev
from typing import Any
from uuid import uuid4

from app.domain.institutional_validation_program.config import IvpConfig
from app.domain.institutional_validation_program.types import (
    IvpInput,
    ModuleResult,
)

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

INSUFFICIENT = "INSUFFICIENT EVIDENCE"


def _dec(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _trades(inp: IvpInput) -> list[dict[str, Any]]:
    rows = inp.completed_trades
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)]


def _insufficient(module: str, need: int, have: int) -> ModuleResult:
    return ModuleResult(
        module=module,
        status="insufficient_evidence",
        score=None,
        recommendation=INSUFFICIENT,
        reasons=(
            f"Need ≥{need} completed trades; have {have}",
            "Never fabricates validation metrics",
            "Read-only evidence only",
        ),
        details={"required": need, "available": have, "verdict": INSUFFICIENT},
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


def _hold_minutes(t: dict[str, Any]) -> Decimal | None:
    return _dec(
        t.get("hold_minutes")
        or t.get("avg_hold_minutes")
        or t.get("duration_minutes")
    )


def _compute_stats(trades: list[dict[str, Any]]) -> dict[str, Any] | None:
    wins = 0
    losses = 0
    pnl_sum = Decimal("0")
    win_pnls: list[Decimal] = []
    loss_pnls: list[Decimal] = []
    rrs: list[Decimal] = []
    holds: list[Decimal] = []
    equity = Decimal("0")
    peak = Decimal("0")
    max_dd = Decimal("0")

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
        hm = _hold_minutes(t)
        if hm is not None:
            holds.append(hm)
        if w is True:
            wins += 1
            win_pnls.append(pnl)
        elif w is False:
            losses += 1
            loss_pnls.append(abs(pnl))

    n = wins + losses
    if n == 0:
        return None

    win_rate = (Decimal(wins) / Decimal(n) * Decimal(100)).quantize(
        Decimal("0.01")
    )
    expectancy = (pnl_sum / Decimal(n)).quantize(Decimal("0.01"))
    gross_win = sum(win_pnls) if win_pnls else Decimal("0")
    gross_loss = sum(loss_pnls) if loss_pnls else Decimal("0")
    profit_factor = (
        (gross_win / gross_loss).quantize(Decimal("0.01"))
        if gross_loss > 0
        else None
    )
    recovery = (
        (pnl_sum / max_dd).quantize(Decimal("0.01"))
        if max_dd > 0
        else None
    )
    avg_r = (
        (sum(rrs) / Decimal(len(rrs))).quantize(Decimal("0.01"))
        if rrs
        else None
    )
    avg_hold = (
        (sum(holds) / Decimal(len(holds))).quantize(Decimal("0.01"))
        if holds
        else None
    )
    return {
        "trade_count": n,
        "win_rate": str(win_rate),
        "expectancy": str(expectancy),
        "profit_factor": str(profit_factor) if profit_factor is not None else None,
        "recovery_factor": str(recovery) if recovery is not None else None,
        "maximum_drawdown": str(max_dd.quantize(Decimal("0.01"))),
        "average_r": str(avg_r) if avg_r is not None else None,
        "average_hold_time_minutes": (
            str(avg_hold) if avg_hold is not None else None
        ),
        "net_pnl": str(pnl_sum.quantize(Decimal("0.01"))),
        "wins": wins,
        "losses": losses,
        "_expectancy_num": expectancy,
        "_win_rate_frac": Decimal(wins) / Decimal(n),
        "_pnls": [
            float(_dec(t.get("pnl") or t.get("net_pnl")) or 0) for t in trades
        ],
    }


def statistical_validation(
    inp: IvpInput, config: IvpConfig
) -> ModuleResult:
    trades = _trades(inp)
    if len(trades) < config.min_trades_for_evidence:
        return _insufficient(
            "statistical_validation",
            config.min_trades_for_evidence,
            len(trades),
        )
    stats = _compute_stats(trades)
    if stats is None:
        return ModuleResult(
            module="statistical_validation",
            status="insufficient_evidence",
            score=None,
            recommendation=INSUFFICIENT,
            reasons=("Trades lack win/pnl fields",),
            details={"verdict": INSUFFICIENT},
        )
    public = {k: v for k, v in stats.items() if not k.startswith("_")}
    return ModuleResult(
        module="statistical_validation",
        status="available",
        score=Decimal(str(stats["trade_count"])),
        recommendation="Statistical metrics computed from supplied trades",
        reasons=(
            "Trade count, win rate, expectancy, PF, recovery, max DD, avg R, hold",
            "Read-only — never places trades",
        ),
        details={
            **public,
            "strategy_id": inp.strategy_id,
            "configuration_id": inp.configuration_id,
        },
    )


def confidence_analysis(inp: IvpInput, config: IvpConfig) -> ModuleResult:
    trades = _trades(inp)
    if len(trades) < config.min_trades_for_evidence:
        return _insufficient(
            "confidence_analysis",
            config.min_trades_for_evidence,
            len(trades),
        )
    stats = _compute_stats(trades)
    if stats is None:
        return ModuleResult(
            module="confidence_analysis",
            status="insufficient_evidence",
            score=None,
            recommendation=INSUFFICIENT,
            reasons=("Cannot estimate intervals without win/pnl",),
            details={"verdict": INSUFFICIENT},
        )

    n = int(stats["trade_count"])
    z = float(config.confidence_z)
    # Win-rate CI via normal approx; widen note when n is modest
    p = float(stats["_win_rate_frac"])
    se_p = sqrt(max(p * (1 - p) / n, 0.0))
    wr_lo = max(0.0, (p - z * se_p) * 100)
    wr_hi = min(100.0, (p + z * se_p) * 100)

    pnls = stats["_pnls"]
    mean_pnl = sum(pnls) / n if n else 0.0
    sd = pstdev(pnls) if n > 1 else 0.0
    se_m = sd / sqrt(n) if n else 0.0
    exp_lo = mean_pnl - z * se_m
    exp_hi = mean_pnl + z * se_m

    # Precision policy: fewer decimals when sample is thinner
    decimals = 0 if n < 50 else (1 if n < 100 else 2)
    fmt = f"{{:.{decimals}f}}"

    return ModuleResult(
        module="confidence_analysis",
        status="available",
        score=Decimal(str(n)),
        recommendation="Intervals estimated from sample; not guarantees",
        reasons=(
            f"Approx {int(float(config.confidence_z) * 50 + 50)}% normal CI",
            "Never reports precision beyond sample support",
            "Not a profitability promise",
        ),
        details={
            "sample_size": n,
            "z": str(config.confidence_z),
            "win_rate_ci_pct": {
                "low": fmt.format(wr_lo),
                "high": fmt.format(wr_hi),
            },
            "expectancy_ci": {
                "low": fmt.format(exp_lo),
                "high": fmt.format(exp_hi),
            },
            "precision_decimals": decimals,
            "note": "CI width reflects sample uncertainty only",
        },
    )


def regime_validation(inp: IvpInput, config: IvpConfig) -> ModuleResult:
    trades = _trades(inp)
    if not trades:
        return ModuleResult(
            module="regime_validation",
            status="empty",
            score=None,
            recommendation=INSUFFICIENT,
            reasons=("No completed trades supplied",),
            details={"regimes": {}, "verdict": INSUFFICIENT},
        )

    by_regime: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in trades:
        key = str(t.get("regime") or t.get("session") or "").strip().lower()
        key = key.replace(" ", "_").replace("-", "_")
        aliases = {
            "ny": "new_york",
            "newyork": "new_york",
            "high_vol": "high_volatility",
            "low_vol": "low_volatility",
            "hv": "high_volatility",
            "lv": "low_volatility",
        }
        key = aliases.get(key, key)
        if key in REGIME_KEYS:
            by_regime[key].append(t)

    regimes: dict[str, Any] = {}
    strongest: str | None = None
    strongest_n = 0
    for rk in REGIME_KEYS:
        subset = by_regime.get(rk, [])
        if len(subset) < config.min_trades_for_regime:
            regimes[rk] = {
                "status": "insufficient_evidence",
                "verdict": INSUFFICIENT,
                "trade_count": len(subset),
                "required": config.min_trades_for_regime,
            }
            continue
        st = _compute_stats(subset)
        if st is None:
            regimes[rk] = {
                "status": "insufficient_evidence",
                "verdict": INSUFFICIENT,
                "trade_count": len(subset),
            }
            continue
        public = {k: v for k, v in st.items() if not k.startswith("_")}
        regimes[rk] = {"status": "available", **public}
        if int(st["trade_count"]) > strongest_n:
            strongest_n = int(st["trade_count"])
            strongest = rk

    available = sum(1 for v in regimes.values() if v.get("status") == "available")
    return ModuleResult(
        module="regime_validation",
        status="available" if available else "insufficient_evidence",
        score=Decimal(str(available)) if available else None,
        recommendation=(
            f"Strongest sample: {strongest}"
            if strongest
            else INSUFFICIENT
        ),
        reasons=(
            "Evaluated Trend/Range/HV/LV/London/NY/Asia/News separately",
            "Evidence strength ranked by sample size only — not auto-selected",
        ),
        details={
            "regimes": regimes,
            "strongest_evidence_regime": strongest,
            "strongest_sample_size": strongest_n or None,
            "never_auto_selects_winner": True,
        },
    )


def configuration_comparison(
    inp: IvpInput, config: IvpConfig
) -> ModuleResult:
    configs = list(inp.configurations or [])
    configs = [c for c in configs if isinstance(c, dict)]
    if not configs:
        return ModuleResult(
            module="configuration_comparison",
            status="empty",
            score=None,
            recommendation="No configurations to compare",
            reasons=(
                "Supply configurations[] with trades or metrics",
                "Never automatically selects a winner",
            ),
            details={"rankings": [], "auto_selected_winner": None},
        )

    rankings: list[dict[str, Any]] = []
    for c in configs[:50]:
        cid = str(c.get("id") or c.get("configuration_id") or "unknown")
        trades = c.get("trades") if isinstance(c.get("trades"), list) else []
        trades = [t for t in trades if isinstance(t, dict)]
        if len(trades) >= config.min_trades_for_comparison:
            st = _compute_stats(trades)
            if st is None:
                rankings.append(
                    {
                        "id": cid,
                        "status": "insufficient_evidence",
                        "verdict": INSUFFICIENT,
                        "trade_count": len(trades),
                    }
                )
                continue
            public = {k: v for k, v in st.items() if not k.startswith("_")}
            exp = float(st["_expectancy_num"])
            rankings.append(
                {
                    "id": cid,
                    "status": "available",
                    **public,
                    "_sort_expectancy": exp,
                }
            )
        else:
            # Allow pre-computed metrics if trade list thin
            tc = int(c.get("trade_count") or 0)
            if tc < config.min_trades_for_comparison and not trades:
                rankings.append(
                    {
                        "id": cid,
                        "status": "insufficient_evidence",
                        "verdict": INSUFFICIENT,
                        "trade_count": tc or len(trades),
                        "required": config.min_trades_for_comparison,
                    }
                )
                continue
            exp = _dec(c.get("expectancy"))
            rankings.append(
                {
                    "id": cid,
                    "status": (
                        "available"
                        if exp is not None
                        else "insufficient_evidence"
                    ),
                    "trade_count": tc or len(trades),
                    "expectancy": str(exp) if exp is not None else None,
                    "win_rate": (
                        str(_dec(c.get("win_rate")))
                        if _dec(c.get("win_rate")) is not None
                        else None
                    ),
                    "profit_factor": (
                        str(_dec(c.get("profit_factor")))
                        if _dec(c.get("profit_factor")) is not None
                        else None
                    ),
                    "_sort_expectancy": (
                        float(exp) if exp is not None else None
                    ),
                    "verdict": None if exp is not None else INSUFFICIENT,
                }
            )

    ranked = sorted(
        [r for r in rankings if r.get("_sort_expectancy") is not None],
        key=lambda r: float(r["_sort_expectancy"]),
        reverse=True,
    )
    for i, r in enumerate(ranked, start=1):
        r["evidence_rank"] = i
        r.pop("_sort_expectancy", None)
    for r in rankings:
        r.pop("_sort_expectancy", None)
        if "evidence_rank" not in r:
            r["evidence_rank"] = None

    return ModuleResult(
        module="configuration_comparison",
        status="available" if ranked else "insufficient_evidence",
        score=Decimal(str(len(ranked))) if ranked else None,
        recommendation="Evidence-based ranking only — no automatic winner",
        reasons=(
            "Ranked by supplied expectancy when sample adequate",
            "Never automatically selects a production winner",
        ),
        details={
            "rankings": rankings,
            "ordered_by_expectancy": [r["id"] for r in ranked],
            "auto_selected_winner": None,
            "never_auto_selects_winner": True,
        },
    )


def stability_analysis(inp: IvpInput, config: IvpConfig) -> ModuleResult:
    trades = _trades(inp)
    windows = list(config.rolling_windows)
    if not trades:
        return ModuleResult(
            module="stability_analysis",
            status="empty",
            score=None,
            recommendation=INSUFFICIENT,
            reasons=("No trades for rolling windows",),
            details={"windows": {}, "verdict": INSUFFICIENT},
        )

    window_results: dict[str, Any] = {}
    expectancies: list[float] = []
    for w in windows:
        if len(trades) < w:
            window_results[str(w)] = {
                "status": "insufficient_evidence",
                "verdict": INSUFFICIENT,
                "required": w,
                "available": len(trades),
            }
            continue
        subset = trades[-w:]
        st = _compute_stats(subset)
        if st is None:
            window_results[str(w)] = {
                "status": "insufficient_evidence",
                "verdict": INSUFFICIENT,
            }
            continue
        public = {k: v for k, v in st.items() if not k.startswith("_")}
        window_results[str(w)] = {"status": "available", **public}
        expectancies.append(float(st["_expectancy_num"]))

    degradation = False
    instability = False
    if len(expectancies) >= 2:
        # Degradation: later (larger) window expectancy materially below smaller
        if expectancies[-1] < expectancies[0] * 0.5 and expectancies[0] > 0:
            degradation = True
        if pstdev(expectancies) > abs(sum(expectancies) / len(expectancies)) * 0.75:
            instability = True

    status = (
        "available"
        if any(v.get("status") == "available" for v in window_results.values())
        else "insufficient_evidence"
    )
    return ModuleResult(
        module="stability_analysis",
        status=status,
        score=Decimal(str(len(expectancies))) if expectancies else None,
        recommendation=(
            "Degradation or instability signals detected"
            if degradation or instability
            else (
                "Rolling windows evaluated"
                if status == "available"
                else INSUFFICIENT
            )
        ),
        reasons=(
            f"Windows: {', '.join(str(w) for w in windows)}",
            "Detects degradation/instability — does not change configs",
        ),
        details={
            "windows": window_results,
            "degradation_signal": degradation,
            "instability_signal": instability,
            "read_only": True,
        },
    )


def risk_validation(inp: IvpInput, config: IvpConfig) -> ModuleResult:
    _ = config
    trades = _trades(inp)
    facts = inp.risk_facts if isinstance(inp.risk_facts, dict) else {}
    stats = _compute_stats(trades) if trades else None

    capital = facts.get("capital_preservation")
    dd_behavior = facts.get("drawdown_behavior") or (
        {"maximum_drawdown": stats["maximum_drawdown"]}
        if stats
        else None
    )
    sizing = facts.get("position_sizing_consistency")
    compliance = facts.get("risk_rule_compliance")

    if not trades and not facts:
        return ModuleResult(
            module="risk_validation",
            status="empty",
            score=None,
            recommendation=INSUFFICIENT,
            reasons=("Supply completed_trades and/or risk_facts",),
            details={"verdict": INSUFFICIENT},
        )

    measured: dict[str, Any] = {
        "capital_preservation": capital,
        "drawdown_behavior": dd_behavior,
        "position_sizing_consistency": sizing,
        "risk_rule_compliance": compliance,
    }
    if stats:
        measured["from_trades"] = {
            "maximum_drawdown": stats["maximum_drawdown"],
            "recovery_factor": stats["recovery_factor"],
            "net_pnl": stats["net_pnl"],
        }

    known = sum(1 for v in (capital, dd_behavior, sizing, compliance) if v)
    return ModuleResult(
        module="risk_validation",
        status="available" if known or stats else "insufficient_evidence",
        score=Decimal(str(known)) if known or stats else None,
        recommendation="Risk evidence assembled from supplied facts only",
        reasons=(
            "Capital preservation, DD behavior, sizing consistency, rule compliance",
            "Never modifies Risk Engine",
        ),
        details={
            **measured,
            "modifies_risk_engine": False,
            "never_bypasses_risk": True,
        },
    )


def replay_vs_paper(inp: IvpInput, config: IvpConfig) -> ModuleResult:
    _ = config
    replay = inp.replay_results if isinstance(inp.replay_results, dict) else None
    paper = inp.paper_results if isinstance(inp.paper_results, dict) else None
    if not replay and not paper:
        return ModuleResult(
            module="replay_vs_paper",
            status="empty",
            score=None,
            recommendation=INSUFFICIENT,
            reasons=("Supply replay_results and/or paper_results",),
            details={"verdict": INSUFFICIENT},
        )

    differences: list[str] = []
    assumptions = [
        "Replay assumes fill at bar close / model price — no live slippage path",
        "Paper may include gateway latency and partial fills if supplied",
        "Neither path places live MT5 orders from IVP",
    ]

    def _metric(src: dict[str, Any] | None, key: str) -> Decimal | None:
        if not src:
            return None
        return _dec(src.get(key))

    for key in ("expectancy", "win_rate", "profit_factor", "drawdown", "trade_count"):
        rv = _metric(replay, key)
        pv = _metric(paper, key)
        if rv is not None and pv is not None:
            delta = (pv - rv).quantize(Decimal("0.01"))
            differences.append(f"{key}: paper - replay = {delta}")
        elif rv is not None or pv is not None:
            differences.append(f"{key}: only one side supplied")

    return ModuleResult(
        module="replay_vs_paper",
        status="available",
        score=Decimal(str(len(differences))),
        recommendation="Replay vs paper compared — assumptions differ",
        reasons=tuple(assumptions[:3]),
        details={
            "replay": replay or {},
            "paper": paper or {},
            "observed_differences": differences,
            "execution_assumption_notes": assumptions,
            "never_places_trades": True,
        },
    )


def evidence_dashboard(modules: dict[str, ModuleResult]) -> ModuleResult:
    statuses = {k: v.status for k, v in modules.items()}
    available = sum(1 for s in statuses.values() if s == "available")
    insufficient = sum(
        1
        for s in statuses.values()
        if s in ("insufficient_evidence", "empty")
    )
    total = max(len(statuses), 1)
    strength = (Decimal(available) / Decimal(total) * Decimal(100)).quantize(
        Decimal("0.01")
    )

    sample = None
    conf = None
    if "statistical_validation" in modules:
        d = modules["statistical_validation"].details or {}
        sample = d.get("trade_count")
    if "confidence_analysis" in modules:
        conf = (modules["confidence_analysis"].details or {}).get(
            "win_rate_ci_pct"
        )

    strengths: list[str] = []
    weaknesses: list[str] = []
    unknowns: list[str] = []

    skip = (
        "evidence_dashboard",
        "human_decision_package",
        "validation_history",
    )
    for name, mod in modules.items():
        if name in skip:
            continue
        if mod.status == "available":
            strengths.append(f"{name}: evidence available")
        elif mod.status in ("insufficient_evidence", "empty"):
            weaknesses.append(f"{name}: {INSUFFICIENT}")
            unknowns.append(f"{name}: needs more sample or inputs")

    stab = modules.get("stability_analysis")
    if stab and (stab.details or {}).get("degradation_signal"):
        weaknesses.append("stability_analysis: degradation signal")
    if stab and (stab.details or {}).get("instability_signal"):
        weaknesses.append("stability_analysis: instability signal")

    return ModuleResult(
        module="evidence_dashboard",
        status="available",
        score=strength,
        recommendation=f"Evidence strength {strength}% of evaluated modules",
        reasons=(
            "Dashboard aggregates read-only module outcomes",
            "Never auto-promotes or deploys",
        ),
        details={
            "evidence_strength_pct": str(strength),
            "sample_size": sample,
            "confidence": conf,
            "known_strengths": strengths,
            "known_weaknesses": weaknesses,
            "unknown_areas": unknowns,
            "module_statuses": statuses,
            "available_modules": available,
            "insufficient_modules": insufficient,
        },
    )


def human_decision_package(
    inp: IvpInput, modules: dict[str, ModuleResult]
) -> ModuleResult:
    dash = modules.get("evidence_dashboard")
    stats = modules.get("statistical_validation")
    conf = modules.get("confidence_analysis")
    strength = (
        (dash.details or {}).get("evidence_strength_pct") if dash else None
    )
    sample = (
        (stats.details or {}).get("trade_count") if stats else None
    )

    deployment_ok = False
    if (
        stats
        and stats.status == "available"
        and sample
        and int(sample) >= 30
        and dash
        and Decimal(str(strength or 0)) >= Decimal("60")
    ):
        # Only allow a soft "evidence supports consideration" — never auto-deploy
        stab = modules.get("stability_analysis")
        deg = bool(stab and (stab.details or {}).get("degradation_signal"))
        deployment_ok = not deg

    exec_summary = (
        f"IVP read-only evaluation for strategy={inp.strategy_id or 'n/a'} "
        f"config={inp.configuration_id or 'n/a'}. "
        f"Evidence strength={strength or 'n/a'}%; sample={sample or 'n/a'}."
    )
    limitations = [
        "Caller-supplied trades only — never invents market outcomes",
        "Confidence intervals are approximate and sample-limited",
        "Regime labels must be provided on trades to validate regimes",
    ]
    open_q = [
        "Is the sample representative of current XAUUSD regimes?",
        "Do replay assumptions match paper/live execution frictions?",
    ]
    next_tests = [
        "Increase completed trade sample to ≥100 for tighter CIs",
        "Label trades with regime/session for full regime grid",
        "Run matched replay vs paper with identical parameter sets",
    ]
    if not deployment_ok:
        next_tests.insert(
            0,
            "Do not change production configuration until evidence strengthens",
        )

    return ModuleResult(
        module="human_decision_package",
        status="available",
        score=Decimal(str(strength)) if strength is not None else None,
        recommendation=(
            "Evidence may support human consideration of config changes"
            if deployment_ok
            else "No deployment recommendation — evidence insufficient or unstable"
        ),
        reasons=(
            "Human Decision Package only — IVP never deploys",
            "No automatic production selection",
        ),
        details={
            "executive_summary": exec_summary,
            "observed_performance": (
                dict(stats.details or {})
                if stats and stats.status == "available"
                else {"verdict": INSUFFICIENT}
            ),
            "limitations": limitations,
            "evidence_quality": {
                "strength_pct": strength,
                "sample_size": sample,
                "confidence": (
                    (conf.details or {}) if conf else None
                ),
            },
            "open_questions": open_q,
            "recommended_next_tests": next_tests,
            "deployment_recommendation": (
                "CONSIDER — human review only"
                if deployment_ok
                else "NONE — insufficient or unstable evidence"
            ),
            "auto_deploy": False,
            "never_auto_promotes": True,
        },
    )


def validation_history(
    inp: IvpInput,
    *,
    prior: list[dict[str, Any]],
    audit_id: str,
    snapshot: dict[str, Any],
) -> ModuleResult:
    """Append-only — never overwrites prior validation results."""
    event = inp.history_event if isinstance(inp.history_event, dict) else {}
    entry = {
        "id": str(event.get("id") or f"ivp_{uuid4().hex[:10]}"),
        "audit_id": audit_id,
        "recorded_at": datetime.now(UTC).isoformat(),
        "strategy_id": inp.strategy_id,
        "configuration_id": inp.configuration_id,
        "snapshot": {
            "evidence_strength_pct": snapshot.get("evidence_strength_pct"),
            "sample_size": snapshot.get("sample_size"),
            "deployment_recommendation": snapshot.get(
                "deployment_recommendation"
            ),
        },
        "comments": str(event.get("comments") or ""),
        "append_only": True,
        "overwrites_prior": False,
    }
    # Caller orchestrator appends; this module only describes the policy
    return ModuleResult(
        module="validation_history",
        status="available",
        score=Decimal(str(len(prior) + 1)),
        recommendation="Append-only history entry prepared",
        reasons=(
            "Never overwrites previous validation results",
            "Read-only evidence archive",
        ),
        details={
            "entry": entry,
            "prior_count": len(prior),
            "append_only": True,
            "overwrites_prior": False,
        },
    )
