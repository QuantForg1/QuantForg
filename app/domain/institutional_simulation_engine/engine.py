"""ISE simulation core — deterministic digital twin (never touches production)."""

from __future__ import annotations

import hashlib
import statistics
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.domain.institutional_simulation_engine.models import (
    PIPELINE_STAGES,
    SCENARIO_KEYS,
    STRESS_KEYS,
    SimulationMode,
)


def _as_dict(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _as_list(v: Any) -> list[Any]:
    return v if isinstance(v, list) else []


def _f(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or v == "":
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _seed(*parts: Any) -> int:
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return int(h[:12], 16)


def _rng(seed: int) -> float:
    """Deterministic [0,1) from integer seed (LCG step)."""
    x = (seed * 1103515245 + 12345) & 0x7FFFFFFF
    return x / 0x7FFFFFFF


def _baseline_metrics(ctx: dict[str, Any]) -> dict[str, float]:
    portfolio = _as_dict(ctx.get("sources", {}).get("portfolio"))
    sections = _as_dict(portfolio.get("sections"))
    perf = _as_dict(sections.get("performance") or portfolio.get("performance"))
    risk = _as_dict(sections.get("risk") or portfolio.get("risk"))
    behavior = _as_dict(sections.get("behavior") or portfolio.get("behavior"))

    irl = _as_dict(ctx.get("sources", {}).get("irl"))
    bench = _as_dict(_as_dict(irl.get("benchmark")).get("production_baseline"))
    board = _as_list(_as_dict(irl.get("leaderboard")).get("rows"))
    best = board[0] if board and isinstance(board[0], dict) else {}

    win_rate = _f(perf.get("win_rate_pct") or perf.get("win_rate") or bench.get("win_rate"), 52.0)
    if win_rate <= 1.0:
        win_rate *= 100.0
    pf = _f(perf.get("profit_factor") or best.get("profit_factor") or bench.get("profit_factor"), 1.6)
    expectancy = _f(perf.get("expectancy") or best.get("expectancy"), 2.5)
    dd = _f(risk.get("max_drawdown_pct") or best.get("maximum_drawdown_pct"), 10.0)
    rr = _f(perf.get("average_rr") or perf.get("avg_rr") or best.get("average_rr"), 1.3)
    trades = int(_f(perf.get("trade_count") or portfolio.get("trade_count") or bench.get("total_trades"), 80))
    holding = _f(behavior.get("average_holding_time_sec"), 1800.0)
    exposure = _f(perf.get("exposure_pct") or risk.get("avg_exposure_pct"), 35.0)

    return {
        "win_rate": win_rate,
        "profit_factor": pf,
        "expectancy": expectancy,
        "drawdown": dd,
        "average_rr": rr,
        "trade_count": float(max(trades, 20)),
        "exposure": exposure,
        "holding_time": holding,
    }


# Scenario multipliers: (wr, pf, exp, dd, rr, trades, exposure, holding)
_SCENARIO_FX: dict[str, tuple[float, float, float, float, float, float, float, float]] = {
    "higher_spread": (0.96, 0.92, 0.90, 1.08, 0.95, 0.95, 1.0, 1.05),
    "lower_spread": (1.03, 1.06, 1.05, 0.95, 1.03, 1.02, 1.0, 0.98),
    "broker_delay": (0.94, 0.90, 0.88, 1.12, 0.92, 0.90, 1.0, 1.15),
    "higher_volatility": (0.97, 1.08, 1.10, 1.25, 1.12, 1.10, 1.15, 0.90),
    "lower_volatility": (1.02, 0.95, 0.92, 0.85, 0.90, 0.88, 0.90, 1.10),
    "london_disabled": (0.95, 0.93, 0.92, 1.05, 0.97, 0.75, 0.85, 1.0),
    "ny_disabled": (0.96, 0.94, 0.93, 1.04, 0.98, 0.80, 0.88, 1.0),
    "atr_scaling": (0.99, 1.02, 1.01, 1.06, 1.05, 1.0, 1.08, 1.0),
    "risk_scaling": (0.98, 1.04, 1.03, 1.18, 1.08, 1.05, 1.25, 1.0),
    "execution_delay": (0.93, 0.88, 0.86, 1.15, 0.90, 0.92, 1.0, 1.20),
    "liquidity_reduction": (0.92, 0.85, 0.82, 1.22, 0.88, 0.70, 0.80, 1.25),
    "session_changes": (0.97, 0.96, 0.95, 1.07, 0.97, 0.90, 0.95, 1.05),
}

_STRESS_FX: dict[str, tuple[float, float, float, float, float, float, float, float]] = {
    "extreme_spread": (0.85, 0.70, 0.65, 1.45, 0.80, 0.60, 0.85, 1.40),
    "execution_delay": (0.88, 0.75, 0.70, 1.35, 0.82, 0.75, 0.90, 1.50),
    "volatility_spike": (0.90, 1.15, 1.20, 1.80, 1.30, 1.40, 1.40, 0.70),
    "low_liquidity": (0.86, 0.72, 0.68, 1.50, 0.78, 0.55, 0.70, 1.60),
    "gap": (0.80, 0.65, 0.55, 2.00, 0.70, 0.50, 0.90, 0.50),
    "rapid_trend": (1.05, 1.25, 1.30, 1.40, 1.35, 1.20, 1.30, 0.60),
    "rapid_reversal": (0.82, 0.68, 0.60, 1.70, 0.75, 1.10, 1.20, 0.55),
}


def _apply_fx(
    base: dict[str, float], fx: tuple[float, float, float, float, float, float, float, float]
) -> dict[str, float]:
    keys = (
        "win_rate",
        "profit_factor",
        "expectancy",
        "drawdown",
        "average_rr",
        "trade_count",
        "exposure",
        "holding_time",
    )
    out = {}
    for k, m in zip(keys, fx, strict=True):
        out[k] = round(base[k] * m, 4)
    out["win_rate"] = round(min(95.0, max(5.0, out["win_rate"])), 2)
    out["profit_factor"] = round(max(0.1, out["profit_factor"]), 3)
    out["drawdown"] = round(min(80.0, max(0.5, out["drawdown"])), 2)
    out["trade_count"] = round(max(1.0, out["trade_count"]), 0)
    return out


def _pipeline_trace(scenario: str | None, seed: int) -> list[dict[str, Any]]:
    """Reproduce full pipeline stages without calling production engines."""
    stages = []
    t0 = seed % 10_000
    for i, name in enumerate(PIPELINE_STAGES):
        r = _rng(seed + i * 97)
        status = "PASS"
        if scenario in {"london_disabled", "ny_disabled"} and name == "Signal" and r < 0.15:
            status = "SKIP"
        if scenario in {"broker_delay", "execution_delay", "extreme_spread"} and name in {
            "OMS",
            "Gateway",
            "Execution",
        }:
            status = "DEGRADED" if r < 0.35 else "PASS"
        if scenario in {"liquidity_reduction", "low_liquidity", "gap"} and name == "Execution":
            status = "STRESSED" if r < 0.5 else "PASS"
        stages.append(
            {
                "stage": name,
                "order": i + 1,
                "status": status,
                "timestamp_offset_ms": t0 + i * (12 + int(r * 40)),
                "isolated": True,
            }
        )
    return stages


def simulate_scenario(
    ctx: dict[str, Any],
    *,
    scenario: str,
    mode: str = SimulationMode.SCENARIO_BUILDER.value,
) -> dict[str, Any]:
    base = _baseline_metrics(ctx)
    key = scenario if scenario in _SCENARIO_FX else "session_changes"
    metrics = _apply_fx(base, _SCENARIO_FX[key])
    seed = _seed("scenario", key, metrics["trade_count"])
    return {
        "simulation_id": str(uuid4()),
        "title": f"Scenario · {key}",
        "mode": mode,
        "scenario": key,
        "metrics": metrics,
        "baseline": base,
        "pipeline": _pipeline_trace(key, seed),
        "never_modifies_production": True,
        "digital_twin": True,
        "observed_at": datetime.now(UTC).isoformat(),
    }


def simulate_stress(ctx: dict[str, Any], *, stress: str) -> dict[str, Any]:
    base = _baseline_metrics(ctx)
    key = stress if stress in _STRESS_FX else "volatility_spike"
    metrics = _apply_fx(base, _STRESS_FX[key])
    seed = _seed("stress", key)
    return {
        "simulation_id": str(uuid4()),
        "title": f"Stress · {key}",
        "mode": SimulationMode.STRESS_TEST.value,
        "scenario": key,
        "metrics": metrics,
        "baseline": base,
        "pipeline": _pipeline_trace(key, seed),
        "never_modifies_production": True,
        "digital_twin": True,
        "observed_at": datetime.now(UTC).isoformat(),
    }


def simulate_replay(ctx: dict[str, Any]) -> dict[str, Any]:
    base = _baseline_metrics(ctx)
    # Replay ≈ baseline with tiny deterministic noise
    seed = _seed("replay", base["profit_factor"], base["trade_count"])
    noise = 0.98 + _rng(seed) * 0.04
    metrics = {
        k: round(v * (noise if k != "trade_count" else 1.0), 4) for k, v in base.items()
    }
    metrics["trade_count"] = base["trade_count"]
    return {
        "simulation_id": str(uuid4()),
        "title": "Historical Replay",
        "mode": SimulationMode.HISTORICAL_REPLAY.value,
        "scenario": "baseline_replay",
        "metrics": metrics,
        "baseline": base,
        "pipeline": _pipeline_trace(None, seed),
        "never_modifies_production": True,
        "digital_twin": True,
        "observed_at": datetime.now(UTC).isoformat(),
    }


def simulate_monte_carlo(
    ctx: dict[str, Any], *, paths: int = 100, scenario: str | None = None
) -> dict[str, Any]:
    paths = int(paths)
    if paths not in {100, 500, 1000, 5000}:
        # clamp to nearest allowed
        paths = min({100, 500, 1000, 5000}, key=lambda p: abs(p - paths))

    base = _baseline_metrics(ctx)
    if scenario and scenario in _SCENARIO_FX:
        center = _apply_fx(base, _SCENARIO_FX[scenario])
    else:
        center = dict(base)

    finals: list[float] = []
    ruin = 0
    path_summaries: list[dict[str, Any]] = []
    seed0 = _seed("mc", paths, scenario or "none", center["profit_factor"])

    for i in range(paths):
        r1 = _rng(seed0 + i * 3)
        r2 = _rng(seed0 + i * 3 + 1)
        r3 = _rng(seed0 + i * 3 + 2)
        # equity path proxy ending multiple of starting 1.0
        shock = (r1 - 0.5) * 0.35 + (r2 - 0.5) * 0.15
        pf_factor = max(0.2, center["profit_factor"] * (0.85 + r3 * 0.35) + shock)
        end = max(0.01, 1.0 + (pf_factor - 1.0) * 0.4 + shock * 0.5)
        # ruin if end equity < 0.5 of start under elevated DD
        dd = center["drawdown"] * (0.8 + r1 * 0.6)
        if end < 0.5 or dd >= 45:
            ruin += 1
            end = min(end, 0.45)
        finals.append(end)
        if i < 20:
            path_summaries.append(
                {
                    "path": i + 1,
                    "ending_equity_multiple": round(end, 4),
                    "drawdown_proxy": round(dd, 2),
                }
            )

    finals_sorted = sorted(finals)
    n = len(finals_sorted)

    def _pct(p: float) -> float:
        idx = min(n - 1, max(0, int((p / 100.0) * (n - 1))))
        return round(finals_sorted[idx], 4)

    metrics = dict(center)
    metrics["profit_factor"] = round(statistics.median(
        [max(0.1, center["profit_factor"] * f) for f in finals_sorted[n // 4 : 3 * n // 4]]
    ), 3)

    return {
        "simulation_id": str(uuid4()),
        "title": f"Monte Carlo · {paths} paths",
        "mode": SimulationMode.MONTE_CARLO.value,
        "scenario": scenario or "baseline",
        "paths": paths,
        "metrics": metrics,
        "baseline": base,
        "monte_carlo": {
            "paths": paths,
            "probability_of_ruin": round((ruin / paths) * 100.0, 2),
            "confidence_interval": {
                "p05": _pct(5),
                "p95": _pct(95),
            },
            "worst_case": round(min(finals), 4),
            "median_case": round(statistics.median(finals), 4),
            "best_case": round(max(finals), 4),
            "sample_paths": path_summaries,
        },
        "pipeline": _pipeline_trace(scenario, seed0),
        "never_modifies_production": True,
        "digital_twin": True,
        "observed_at": datetime.now(UTC).isoformat(),
    }


def simulate_walk_forward(ctx: dict[str, Any]) -> dict[str, Any]:
    base = _baseline_metrics(ctx)
    seed = _seed("wf", base["trade_count"], base["profit_factor"])
    # Split: train 60% / validate 20% / test 20% of trade_count
    n = int(base["trade_count"])
    train_n = max(5, int(n * 0.6))
    val_n = max(3, int(n * 0.2))
    test_n = max(3, n - train_n - val_n)

    def _split_metrics(label: str, mult: float, count: int) -> dict[str, Any]:
        m = {k: round(v * mult, 4) for k, v in base.items()}
        m["trade_count"] = float(count)
        m["win_rate"] = round(min(95.0, max(5.0, m["win_rate"])), 2)
        return {"split": label, "metrics": m, "trade_count": count}

    train = _split_metrics("train", 1.02 + _rng(seed) * 0.03, train_n)
    validate = _split_metrics("validate", 0.97 + _rng(seed + 1) * 0.04, val_n)
    test = _split_metrics("test", 0.94 + _rng(seed + 2) * 0.05, test_n)

    # Generalization: how close test PF/WR stay to train
    t_pf = train["metrics"]["profit_factor"]
    te_pf = test["metrics"]["profit_factor"]
    t_wr = train["metrics"]["win_rate"]
    te_wr = test["metrics"]["win_rate"]
    pf_ratio = min(t_pf, te_pf) / max(t_pf, te_pf) if max(t_pf, te_pf) else 0
    wr_ratio = min(t_wr, te_wr) / max(t_wr, te_wr) if max(t_wr, te_wr) else 0
    generalization = round(max(0.0, min(100.0, (pf_ratio * 0.6 + wr_ratio * 0.4) * 100.0)), 1)

    return {
        "simulation_id": str(uuid4()),
        "title": "Historical Walk Forward",
        "mode": SimulationMode.WALK_FORWARD.value,
        "scenario": "walk_forward",
        "metrics": test["metrics"],
        "baseline": base,
        "walk_forward": {
            "train": train,
            "validate": validate,
            "test": test,
            "generalization_score": generalization,
        },
        "pipeline": _pipeline_trace(None, seed),
        "never_modifies_production": True,
        "digital_twin": True,
        "observed_at": datetime.now(UTC).isoformat(),
    }


def compare_scenarios(results: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for r in results:
        m = _as_dict(r.get("metrics"))
        rows.append(
            {
                "simulation_id": r.get("simulation_id"),
                "title": r.get("title"),
                "scenario": r.get("scenario"),
                "mode": r.get("mode"),
                "profit_factor": m.get("profit_factor"),
                "win_rate": m.get("win_rate"),
                "drawdown": m.get("drawdown"),
                "expectancy": m.get("expectancy"),
                "trade_count": m.get("trade_count"),
            }
        )
    rows.sort(key=lambda x: _f(x.get("profit_factor")), reverse=True)
    return {
        "comparisons": rows,
        "best_by_pf": rows[0] if rows else None,
        "never_modifies_production": True,
    }


def build_reports(simulations: list[dict[str, Any]]) -> dict[str, Any]:
    by_mode: dict[str, list] = {}
    for s in simulations:
        by_mode.setdefault(str(s.get("mode")), []).append(s)

    def _pack(title: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "title": title,
            "count": len(rows),
            "simulations": [
                {
                    "simulation_id": r.get("simulation_id"),
                    "scenario": r.get("scenario"),
                    "metrics": r.get("metrics"),
                    "monte_carlo": r.get("monte_carlo"),
                    "walk_forward": r.get("walk_forward"),
                }
                for r in rows[:20]
            ],
            "advisory_only": True,
            "never_modifies_production": True,
        }

    return {
        "simulation_report": _pack("Simulation Report", simulations[:30]),
        "scenario_comparison": {
            **compare_scenarios(
                [s for s in simulations if "Scenario" in str(s.get("mode")) or s.get("mode") == SimulationMode.SCENARIO_BUILDER.value]
                or simulations[:10]
            ),
            "title": "Scenario Comparison",
        },
        "stress_report": _pack(
            "Stress Report",
            [s for s in simulations if s.get("mode") == SimulationMode.STRESS_TEST.value],
        ),
        "walk_forward_report": _pack(
            "Walk Forward Report",
            [s for s in simulations if s.get("mode") == SimulationMode.WALK_FORWARD.value],
        ),
        "monte_carlo_report": _pack(
            "Monte Carlo Report",
            [s for s in simulations if s.get("mode") == SimulationMode.MONTE_CARLO.value],
        ),
        "generated_at": datetime.now(UTC).isoformat(),
    }


def aqs_analysis_pack(simulation: dict[str, Any]) -> dict[str, Any]:
    """Structured pack for AI Quant Scientist — advisory only."""
    m = _as_dict(simulation.get("metrics"))
    findings = []
    pf = _f(m.get("profit_factor"))
    dd = _f(m.get("drawdown"))
    if pf < 1.2:
        findings.append("Simulated PF below institutional research preference (<1.2).")
    if dd >= 20:
        findings.append("Simulated drawdown elevated — stress/scenario caution.")
    if simulation.get("monte_carlo"):
        por = _f(_as_dict(simulation.get("monte_carlo")).get("probability_of_ruin"))
        findings.append(f"Monte Carlo probability of ruin ≈ {por}%.")
    if simulation.get("walk_forward"):
        g = _f(_as_dict(simulation.get("walk_forward")).get("generalization_score"))
        findings.append(f"Walk-forward generalization score ≈ {g}.")
    return {
        "simulation_id": simulation.get("simulation_id"),
        "mode": simulation.get("mode"),
        "scenario": simulation.get("scenario"),
        "metrics": m,
        "pipeline_stages": simulation.get("pipeline"),
        "findings": findings or ["Simulation within baseline envelope."],
        "recommendations": [
            "Humans decide — ISE never modifies production or thresholds.",
            "Compare against CVF drift alerts before any research promotion workflow.",
        ],
        "for_aqs": True,
        "never_modifies_production": True,
    }


def catalog() -> dict[str, Any]:
    return {
        "modes": [m.value for m in SimulationMode],
        "scenarios": list(SCENARIO_KEYS),
        "stress_tests": list(STRESS_KEYS),
        "monte_carlo_paths": [100, 500, 1000, 5000],
        "pipeline_stages": list(PIPELINE_STAGES),
        "never_modifies_production": True,
    }
