"""Threshold Performance Analysis — offline Research tool only.

Independent gate-matrix replays on XAUUSD using production strategy code paths
with *copied* ITEConfig overrides. Never mutates DEFAULT_ITE_CONFIG, live
thresholds, strategy, risk, safety, OMS, or MT5.
"""

from __future__ import annotations

import csv
import io
import math
import statistics
from bisect import bisect_right
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from time import perf_counter
from typing import Any

from app.application.services.institutional_decision_pipeline import (
    InstitutionalDecisionPipeline,
)
from app.application.services.institutional_trading_analysis import (
    InstitutionalTradingAnalysisService,
)
from app.application.services.production_replay_validation import (
    ALLOWED_SESSIONS,
    _CANDLE_BUFFER,
    _MIN_HISTORY_PER_TF,
    _REQUIRED_TIMEFRAMES,
    _compute_atr,
    _normalize_bars_by_tf,
    _select_walk_points,
    build_synthetic_bars,
)
from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG, ITEConfig
from app.domain.institutional_trading.decision_models import (
    AccountRiskState,
    DecisionAction,
    TradeDecision,
)
from app.domain.institutional_trading.models import (
    MarketAnalysisSnapshot,
    TradeQualityScore,
)
from app.domain.institutional_trading.session_filter import classify_session_utc
from app.domain.market_data.candle import Candle
from app.domain.market_data.timeframe import Timeframe
from app.domain.trading.gold_only import GOLD_SYMBOL

GATE_LADDER: tuple[int, ...] = (80, 75, 70, 65, 60)
BASELINE_QUALITY = 80
BASELINE_CONFLUENCE = 80
_TRADE_ACTIONS = frozenset({DecisionAction.BUY, DecisionAction.SELL})
_M15_SECONDS = 15 * 60


def override_ite_config(*, quality_gate: int, confluence_gate: int) -> ITEConfig:
    """Copy of production config with research-only gate overrides."""
    return replace(
        DEFAULT_ITE_CONFIG,
        min_trade_quality_score=int(quality_gate),
        min_confluence_score=int(confluence_gate),
        config_version=f"research-tpa-q{quality_gate}-c{confluence_gate}",
    )


def _snapshot_for_gates(
    snapshot: MarketAnalysisSnapshot, *, quality_gate: int
) -> MarketAnalysisSnapshot:
    """Recompute quality.passed for the research gate without re-scoring."""
    tq = snapshot.trade_quality
    passed = tq.total >= quality_gate
    if tq.total < quality_gate:
        band = "reject"
    elif tq.total >= DEFAULT_ITE_CONFIG.high_confidence_score:
        band = "high_confidence"
    else:
        band = "tradable"
    new_tq = TradeQualityScore(
        total=tq.total,
        passed=passed,
        band=band,
        factors=tq.factors,
    )
    return replace(snapshot, trade_quality=new_tq)


def _zone_mid(zone: Any, fallback: float | None) -> float | None:
    if zone is None:
        return fallback
    mid = getattr(zone, "mid", None)
    if mid is not None:
        try:
            return float(mid)
        except (TypeError, ValueError):
            pass
    try:
        return (float(zone.low) + float(zone.high)) / 2.0
    except (TypeError, ValueError, AttributeError):
        return fallback


def simulate_trade_outcome(
    *,
    direction: str,
    entry: float,
    stop: float,
    target: float,
    bars_after: list[Candle],
    spread: float,
    risk_amount: float,
) -> dict[str, Any] | None:
    """Research fill model: next bars, SL/TP first-touch (ambiguous → skip PnL)."""
    side = direction.upper()
    if side not in {"BUY", "SELL"}:
        return None
    risk = abs(entry - stop)
    if risk <= 1e-9:
        return None
    reward = abs(target - entry)
    planned_rr = reward / risk if risk else None
    # Research slippage model: half-spread against the trade (never invents fills).
    slip = max(0.0, spread / 2.0)
    fill = entry + slip if side == "BUY" else entry - slip

    n = 0
    for bar in bars_after:
        n += 1
        high = float(bar.high.value)
        low = float(bar.low.value)
        if side == "BUY":
            hit_sl = low <= stop
            hit_tp = high >= target
        else:
            hit_sl = high >= stop
            hit_tp = low <= target
        if hit_sl and hit_tp:
            return {
                "result": "ambiguous",
                "bars": n,
                "hold_sec": n * _M15_SECONDS,
                "r_multiple": None,
                "net_pnl": None,
                "planned_rr": planned_rr,
                "slippage": slip,
                "spread": spread,
            }
        if hit_sl:
            # Loss ≈ -1R on risked capital (fill slippage already in fill).
            r_mult = -abs(fill - stop) / risk
            return {
                "result": "loss",
                "bars": n,
                "hold_sec": n * _M15_SECONDS,
                "r_multiple": round(r_mult, 4),
                "net_pnl": round(r_mult * risk_amount, 4),
                "planned_rr": planned_rr,
                "slippage": slip,
                "spread": spread,
            }
        if hit_tp:
            r_mult = abs(target - fill) / risk
            return {
                "result": "win",
                "bars": n,
                "hold_sec": n * _M15_SECONDS,
                "r_multiple": round(r_mult, 4),
                "net_pnl": round(r_mult * risk_amount, 4),
                "planned_rr": planned_rr,
                "slippage": slip,
                "spread": spread,
            }
    return {
        "result": "timeout",
        "bars": n,
        "hold_sec": n * _M15_SECONDS,
        "r_multiple": 0.0,
        "net_pnl": 0.0,
        "planned_rr": planned_rr,
        "slippage": slip,
        "spread": spread,
    }


def _equity_curve_metrics(pnls: list[float]) -> tuple[float | None, float | None]:
    """Max drawdown % and Sharpe (per-trade, population) from PnL series."""
    if not pnls:
        return None, None
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for p in pnls:
        equity += p
        peak = max(peak, equity)
        dd = (peak - equity) / peak * 100.0 if peak > 0 else 0.0
        max_dd = max(max_dd, dd)
    sharpe = None
    if len(pnls) >= 2:
        mu = statistics.mean(pnls)
        sd = statistics.pstdev(pnls)
        if sd > 1e-12:
            sharpe = round(mu / sd * math.sqrt(len(pnls)), 4)
    return round(max_dd, 4), sharpe


def compute_cell_metrics(
    *,
    total_signals: int,
    executed_trades: list[dict[str, Any]],
    rejected: int,
) -> dict[str, Any]:
    closed = [
        t
        for t in executed_trades
        if t.get("net_pnl") is not None and t.get("result") in {"win", "loss", "timeout"}
    ]
    n = len(closed)
    wins = [t for t in closed if float(t["net_pnl"]) > 0]
    losses = [t for t in closed if float(t["net_pnl"]) < 0]
    pnls = [float(t["net_pnl"]) for t in closed]
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = abs(sum(p for p in pnls if p < 0))
    net = sum(pnls)
    win_rate = (len(wins) / n) if n else None
    loss_rate = (len(losses) / n) if n else None
    avg_win = (gross_profit / len(wins)) if wins else None
    avg_loss = (gross_loss / len(losses)) if losses else None
    expectancy = None
    if win_rate is not None and avg_win is not None and avg_loss is not None:
        expectancy = win_rate * avg_win - (1.0 - win_rate) * avg_loss
    elif win_rate is not None and avg_win is not None and not losses:
        expectancy = win_rate * avg_win
    pf = None
    if gross_loss > 0:
        pf = gross_profit / gross_loss
    # If only winners and no losses, leave profit_factor null (undefined / infinite).
    rs = [float(t["r_multiple"]) for t in closed if t.get("r_multiple") is not None]
    holds = [float(t["hold_sec"]) for t in closed if t.get("hold_sec") is not None]
    spreads = [float(t["spread"]) for t in executed_trades if t.get("spread") is not None]
    slips = [float(t["slippage"]) for t in executed_trades if t.get("slippage") is not None]
    max_dd, sharpe = _equity_curve_metrics(pnls)
    recovery = None
    if max_dd is not None and max_dd > 0 and abs(net) > 0:
        recovery = round(net / max_dd, 4)

    return {
        "total_signals": total_signals,
        "executed_trades": n,
        "rejected_trades": rejected,
        "win_rate": round(win_rate, 4) if win_rate is not None else None,
        "loss_rate": round(loss_rate, 4) if loss_rate is not None else None,
        "average_rr": round(sum(rs) / len(rs), 4) if rs else None,
        "average_holding_time_sec": round(sum(holds) / len(holds), 1) if holds else None,
        "profit_factor": round(pf, 4) if pf is not None else None,
        "gross_profit": round(gross_profit, 4),
        "gross_loss": round(gross_loss, 4),
        "net_profit": round(net, 4),
        "expectancy": round(expectancy, 6) if expectancy is not None else None,
        "maximum_drawdown_pct": max_dd,
        "recovery_factor": recovery,
        "sharpe_ratio": sharpe,
        "average_spread": round(sum(spreads) / len(spreads), 4) if spreads else None,
        "average_slippage": round(sum(slips) / len(slips), 4) if slips else None,
    }


@dataclass
class _CellAccumulator:
    quality_gate: int
    confluence_gate: int
    total_signals: int = 0
    rejected: int = 0
    trades: list[dict[str, Any]] | None = None

    def __post_init__(self) -> None:
        if self.trades is None:
            self.trades = []


async def run_threshold_performance_analysis(
    *,
    days: int = 90,
    max_evaluations: int = 120,
    bars_by_tf: dict[Timeframe | str, list[Candle]] | None = None,
    equity: Decimal = Decimal("10000"),
    quality_gates: tuple[int, ...] = GATE_LADDER,
    confluence_gates: tuple[int, ...] = GATE_LADDER,
    future_bars: int = 48,
) -> dict[str, Any]:
    """Walk-forward independent gate-matrix replay. Research / offline only."""
    t0 = perf_counter()
    generated_at = datetime.now(UTC)
    normalized = (
        _normalize_bars_by_tf(bars_by_tf)
        if bars_by_tf
        else build_synthetic_bars(days)
    )
    m15 = normalized.get(Timeframe.M15, [])
    close_times_by_tf: dict[Timeframe, list[datetime]] = {
        tf: [c.close_time for c in candles] for tf, candles in normalized.items()
    }

    eligible: list[tuple[int, datetime]] = []
    for i, candle in enumerate(m15):
        as_of = candle.close_time
        if classify_session_utc(as_of) in ALLOWED_SESSIONS:
            eligible.append((i, as_of))
    walk_points = _select_walk_points(eligible, max_evaluations=max_evaluations)

    cells: dict[tuple[int, int], _CellAccumulator] = {
        (q, c): _CellAccumulator(quality_gate=q, confluence_gate=c)
        for q in quality_gates
        for c in confluence_gates
    }

    analysis = InstitutionalTradingAnalysisService(config=DEFAULT_ITE_CONFIG)
    pipelines: dict[tuple[int, int], InstitutionalDecisionPipeline] = {
        (q, c): InstitutionalDecisionPipeline(
            config=override_ite_config(quality_gate=q, confluence_gate=c)
        )
        for q, c in cells
    }

    risk_pct = float(DEFAULT_ITE_CONFIG.risk_per_trade_pct) / 100.0
    risk_amount = float(equity) * risk_pct
    evaluations = 0

    for eval_idx, (m15_idx, as_of) in enumerate(walk_points):
        sliced: dict[Timeframe, list[Candle]] = {}
        sufficient = True
        for tf in _REQUIRED_TIMEFRAMES:
            series = normalized.get(tf, [])
            times = close_times_by_tf.get(tf, [])
            cutoff = bisect_right(times, as_of)
            if cutoff < _MIN_HISTORY_PER_TF:
                sufficient = False
                break
            sliced[tf] = series[max(0, cutoff - _CANDLE_BUFFER) : cutoff]
        if not sufficient:
            continue

        atr = _compute_atr(sliced[Timeframe.M15])
        mid = float(sliced[Timeframe.M15][-1].close.value)
        account = AccountRiskState(
            equity=equity,
            peak_equity=equity,
            daily_pnl=Decimal("0"),
            weekly_pnl=Decimal("0"),
            open_positions=0,
            already_in_trade=False,
            consecutive_losses=0,
            cooldown_active=False,
            cooldown_remaining_minutes=0,
            market_open=True,
            atr=atr,
            mid_price=Decimal(str(mid)),
            free_margin=equity,
        )
        spread = Decimal("0.30")
        snapshot = await analysis.analyze_bars(sliced, as_of=as_of, spread=spread)
        future = m15[m15_idx + 1 : m15_idx + 1 + future_bars]
        evaluations += 1

        for (q, c), acc in cells.items():
            snap = _snapshot_for_gates(snapshot, quality_gate=q)
            decision: TradeDecision = pipelines[(q, c)].run(
                snap,
                account,
                request_id=f"tpa_{q}_{c}_{eval_idx}",
            )
            acc.total_signals += 1
            if decision.action not in _TRADE_ACTIONS:
                acc.rejected += 1
                continue
            entry = _zone_mid(decision.entry_zone, mid)
            stop = _zone_mid(decision.stop_zone, None)
            target = _zone_mid(decision.target_zone, None)
            if entry is None or stop is None or target is None:
                acc.rejected += 1
                continue
            outcome = simulate_trade_outcome(
                direction=decision.direction.value,
                entry=entry,
                stop=stop,
                target=target,
                bars_after=future,
                spread=float(snapshot.spread or spread),
                risk_amount=risk_amount,
            )
            if outcome is None or outcome.get("result") == "ambiguous":
                acc.rejected += 1
                continue
            assert acc.trades is not None
            acc.trades.append(outcome)

    matrix: list[dict[str, Any]] = []
    for (q, c), acc in sorted(cells.items(), key=lambda x: (-x[0][0], -x[0][1])):
        metrics = compute_cell_metrics(
            total_signals=acc.total_signals,
            executed_trades=acc.trades or [],
            rejected=acc.rejected,
        )
        matrix.append(
            {
                "quality_gate": q,
                "confluence_gate": c,
                "is_baseline": q == BASELINE_QUALITY and c == BASELINE_CONFLUENCE,
                **metrics,
            }
        )

    rankings = _build_rankings(matrix)
    heatmap = _build_heatmap(matrix, quality_gates, confluence_gates)
    recommendation = _build_recommendation(matrix)
    elapsed_ms = round((perf_counter() - t0) * 1000.0, 1)

    return {
        "schema_version": "1.0.0",
        "generated_at": generated_at.isoformat(),
        "advisory_only": True,
        "research_only": True,
        "offline_only": True,
        "never_modifies_strategy": True,
        "never_modifies_thresholds": True,
        "never_modifies_live_engine": True,
        "never_modifies_risk_safety_oms_mt5": True,
        "symbol": GOLD_SYMBOL,
        "params": {
            "days": days,
            "max_evaluations": max_evaluations,
            "equity": str(equity),
            "quality_gates": list(quality_gates),
            "confluence_gates": list(confluence_gates),
            "future_bars_m15": future_bars,
        },
        "baseline": {
            "quality_gate": BASELINE_QUALITY,
            "confluence_gate": BASELINE_CONFLUENCE,
        },
        "evaluations": evaluations,
        "eligible_bars_considered": len(eligible),
        "elapsed_ms": elapsed_ms,
        "matrix": matrix,
        "rankings": rankings,
        "heatmap": heatmap,
        "recommendation": recommendation,
    }


def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _build_rankings(matrix: list[dict[str, Any]]) -> dict[str, Any]:
    def top(key: str, *, reverse: bool = True, n: int = 5) -> list[dict[str, Any]]:
        scored = [
            m
            for m in matrix
            if _safe_float(m.get(key)) is not None
        ]
        scored.sort(key=lambda m: float(m[key]), reverse=reverse)
        return [
            {
                "quality_gate": m["quality_gate"],
                "confluence_gate": m["confluence_gate"],
                "value": m[key],
                "net_profit": m.get("net_profit"),
                "is_baseline": m.get("is_baseline"),
            }
            for m in scored[:n]
        ]

    # Risk-adjusted ≈ Sharpe when available, else net / max(dd, eps)
    rar: list[dict[str, Any]] = []
    for m in matrix:
        sharpe = _safe_float(m.get("sharpe_ratio"))
        net = _safe_float(m.get("net_profit")) or 0.0
        dd = _safe_float(m.get("maximum_drawdown_pct")) or 0.0
        score = sharpe if sharpe is not None else (net / dd if dd > 0 else net)
        rar.append({**m, "_rar": score})
    rar.sort(key=lambda m: float(m["_rar"]), reverse=True)

    return {
        "best_net_profit": top("net_profit", reverse=True),
        "best_profit_factor": top("profit_factor", reverse=True),
        "lowest_drawdown": top("maximum_drawdown_pct", reverse=False),
        "best_expectancy": top("expectancy", reverse=True),
        "best_risk_adjusted_return": [
            {
                "quality_gate": m["quality_gate"],
                "confluence_gate": m["confluence_gate"],
                "value": round(float(m["_rar"]), 4),
                "sharpe_ratio": m.get("sharpe_ratio"),
                "net_profit": m.get("net_profit"),
                "is_baseline": m.get("is_baseline"),
            }
            for m in rar[:5]
        ],
    }


def _build_heatmap(
    matrix: list[dict[str, Any]],
    quality_gates: tuple[int, ...],
    confluence_gates: tuple[int, ...],
) -> dict[str, Any]:
    by_key = {(m["quality_gate"], m["confluence_gate"]): m for m in matrix}
    cells: list[dict[str, Any]] = []
    for q in quality_gates:
        for c in confluence_gates:
            m = by_key.get((q, c), {})
            cells.append(
                {
                    "quality_gate": q,
                    "confluence_gate": c,
                    "profit_factor": m.get("profit_factor"),
                    "win_rate": m.get("win_rate"),
                    "expectancy": m.get("expectancy"),
                    "drawdown": m.get("maximum_drawdown_pct"),
                    "net_profit": m.get("net_profit"),
                }
            )
    return {
        "rows_quality_gates": list(quality_gates),
        "columns_confluence_gates": list(confluence_gates),
        "cells": cells,
        "metrics": ["profit_factor", "win_rate", "expectancy", "drawdown"],
    }


def _build_recommendation(matrix: list[dict[str, Any]]) -> dict[str, Any]:
    baseline = next(
        (
            m
            for m in matrix
            if m.get("quality_gate") == BASELINE_QUALITY
            and m.get("confluence_gate") == BASELINE_CONFLUENCE
        ),
        None,
    )
    keep = {
        "action": "keep_production_thresholds_unchanged",
        "quality_gate": BASELINE_QUALITY,
        "confluence_gate": BASELINE_CONFLUENCE,
        "auto_applied": False,
        "never_auto_lowers_thresholds": True,
        "summary": "Keep production thresholds unchanged.",
        "reasons": [],
    }
    if baseline is None:
        keep["reasons"] = ["Baseline cell Q80/C80 missing from matrix."]
        return keep

    base_net = _safe_float(baseline.get("net_profit")) or 0.0
    base_dd = _safe_float(baseline.get("maximum_drawdown_pct"))
    # Acceptable drawdown: not worse than baseline + 10% relative (or +1pp floor).
    dd_cap = None
    if base_dd is not None:
        dd_cap = max(base_dd * 1.10, base_dd + 1.0)

    candidates: list[dict[str, Any]] = []
    for m in matrix:
        if m.get("is_baseline"):
            continue
        net = _safe_float(m.get("net_profit"))
        exp = _safe_float(m.get("expectancy"))
        dd = _safe_float(m.get("maximum_drawdown_pct"))
        if net is None or exp is None:
            continue
        if net <= base_net:
            continue
        if exp <= 0:
            continue
        if dd_cap is not None and dd is not None and dd > dd_cap:
            continue
        if dd_cap is not None and dd is None:
            continue
        candidates.append(m)

    if not candidates:
        keep["reasons"] = [
            "No gate combination improved net profit with positive expectancy "
            "and acceptable drawdown versus baseline Q80/C80.",
            "Do not lower production thresholds.",
        ]
        return keep

    candidates.sort(
        key=lambda m: (
            _safe_float(m.get("sharpe_ratio"))
            or (
                (_safe_float(m.get("net_profit")) or 0.0)
                / max(_safe_float(m.get("maximum_drawdown_pct")) or 1.0, 1e-6)
            ),
            _safe_float(m.get("net_profit")) or 0.0,
        ),
        reverse=True,
    )
    best = candidates[0]
    return {
        "action": "research_candidate_only",
        "auto_applied": False,
        "never_auto_lowers_thresholds": True,
        "keep_production_unless_operator_promotes": True,
        "production_remains": {
            "quality_gate": BASELINE_QUALITY,
            "confluence_gate": BASELINE_CONFLUENCE,
        },
        "candidate": {
            "quality_gate": best["quality_gate"],
            "confluence_gate": best["confluence_gate"],
            "net_profit": best.get("net_profit"),
            "expectancy": best.get("expectancy"),
            "maximum_drawdown_pct": best.get("maximum_drawdown_pct"),
            "profit_factor": best.get("profit_factor"),
            "sharpe_ratio": best.get("sharpe_ratio"),
        },
        "summary": (
            f"Research candidate Q{best['quality_gate']}/C{best['confluence_gate']} "
            "met improve-profit + acceptable-DD + positive-expectancy tests. "
            "Production thresholds remain unchanged until an operator explicitly promotes."
        ),
        "reasons": [
            "Profit improved vs baseline.",
            "Drawdown stayed within acceptable band vs baseline.",
            "Expectancy remained positive.",
            "This is NOT an automatic threshold change.",
        ],
    }


def matrix_to_csv(report: dict[str, Any]) -> str:
    rows = report.get("matrix") or []
    if not rows:
        return ""
    fields = [
        "quality_gate",
        "confluence_gate",
        "is_baseline",
        "total_signals",
        "executed_trades",
        "rejected_trades",
        "win_rate",
        "loss_rate",
        "average_rr",
        "average_holding_time_sec",
        "profit_factor",
        "gross_profit",
        "gross_loss",
        "net_profit",
        "expectancy",
        "maximum_drawdown_pct",
        "recovery_factor",
        "sharpe_ratio",
        "average_spread",
        "average_slippage",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow({k: r.get(k) for k in fields})
    return buf.getvalue()


def report_to_markdown(report: dict[str, Any]) -> str:
    rec = report.get("recommendation") or {}
    lines = [
        "# Threshold Performance Analysis",
        "",
        f"- Generated: `{report.get('generated_at')}`",
        f"- Symbol: `{report.get('symbol')}` · days={report.get('params', {}).get('days')}",
        "- Offline research only — live thresholds / engines unchanged",
        f"- Evaluations: **{report.get('evaluations')}**",
        "",
        "## Recommendation",
        "",
        rec.get("summary", "Keep production thresholds unchanged."),
        "",
        "## Rankings",
        "",
    ]
    ranks = report.get("rankings") or {}
    for title, key in [
        ("Best Net Profit", "best_net_profit"),
        ("Best Profit Factor", "best_profit_factor"),
        ("Lowest Drawdown", "lowest_drawdown"),
        ("Best Expectancy", "best_expectancy"),
        ("Best Risk Adjusted Return", "best_risk_adjusted_return"),
    ]:
        lines.append(f"### {title}")
        lines.append("")
        for row in ranks.get(key) or []:
            lines.append(
                f"- Q{row.get('quality_gate')}/C{row.get('confluence_gate')}: "
                f"**{row.get('value')}**"
            )
        lines.append("")
    lines.append("## Matrix (summary)")
    lines.append("")
    lines.append(
        "| Q | C | Exec | WR | PF | Net | Exp | DD% | Sharpe |"
    )
    lines.append("|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for m in report.get("matrix") or []:
        lines.append(
            f"| {m.get('quality_gate')} | {m.get('confluence_gate')} | "
            f"{m.get('executed_trades')} | {m.get('win_rate')} | "
            f"{m.get('profit_factor')} | {m.get('net_profit')} | "
            f"{m.get('expectancy')} | {m.get('maximum_drawdown_pct')} | "
            f"{m.get('sharpe_ratio')} |"
        )
    lines.append("")
    return "\n".join(lines)


def build_pdf_bytes(report: dict[str, Any]) -> bytes:
    """Minimal multi-line PDF 1.4 — no external deps."""
    md = report_to_markdown(report)
    lines = []
    for raw in md.splitlines():
        # PDF Helvetica can't reliably show markdown markers; strip lightly.
        line = raw.replace("**", "").replace("`", "").replace("#", "").strip()
        if line:
            lines.append(line[:110])
        if len(lines) >= 55:
            break
    if not lines:
        lines = ["Threshold Performance Analysis", "No data"]

    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    y = 780
    content = ["BT", "/F1 9 Tf", "12 TL"]
    for line in lines:
        content.append(f"1 0 0 1 40 {y} Tm ({esc(line)}) Tj")
        y -= 12
        if y < 40:
            break
    content.append("ET")
    stream = "\n".join(content)
    objects = [
        "1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj",
        "2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj",
        "3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj",
        f"4 0 obj<< /Length {len(stream)} >>stream\n{stream}\nendstream endobj",
        "5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj",
    ]
    pdf = "%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf.encode("latin-1", errors="replace")))
        pdf += obj + "\n"
    xref = len(pdf.encode("latin-1", errors="replace"))
    pdf += f"xref\n0 {len(objects) + 1}\n"
    pdf += "0000000000 65535 f \n"
    for i in range(1, len(offsets)):
        pdf += f"{offsets[i]:010d} 00000 n \n"
    pdf += f"trailer<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
    pdf += f"startxref\n{xref}\n%%EOF"
    return pdf.encode("latin-1", errors="replace")
