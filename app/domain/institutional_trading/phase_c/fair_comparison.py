"""Fair champion vs challenger comparison on matched samples."""

from __future__ import annotations

from typing import Any, Sequence


def _metrics(rs: Sequence[float]) -> dict[str, Any]:
    n = len(rs)
    if n == 0:
        return {
            "trade_count": 0,
            "win_rate": None,
            "avg_win": None,
            "avg_loss": None,
            "expectancy": None,
            "profit_factor": None,
            "average_R": None,
            "median_R": None,
            "max_drawdown": None,
            "tail_loss": None,
        }
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r < 0]
    avg = sum(rs) / n
    s = sorted(rs)
    mid = n // 2
    median = s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0
    # Drawdown on cumulative R
    eq = 0.0
    peak = 0.0
    max_dd = 0.0
    for r in rs:
        eq += r
        peak = max(peak, eq)
        max_dd = max(max_dd, peak - eq)
    sum_win = sum(wins)
    sum_loss = abs(sum(losses))
    return {
        "trade_count": n,
        "win_rate": round(100.0 * len(wins) / n, 2),
        "avg_win": round(sum_win / len(wins), 6) if wins else None,
        "avg_loss": round(sum(losses) / len(losses), 6) if losses else None,
        "expectancy": round(avg, 6),
        "profit_factor": round(sum_win / sum_loss, 6) if sum_loss > 0 else None,
        "average_R": round(avg, 6),
        "median_R": round(median, 6),
        "max_drawdown": round(max_dd, 6),
        "tail_loss": round(min(rs), 6),
    }


def compare_champion_challenger(
    *,
    champion_r: Sequence[float],
    challenger_r: Sequence[float],
    min_sample: int = 20,
    champion_mae: Sequence[float] | None = None,
    challenger_mae: Sequence[float] | None = None,
    champion_mfe: Sequence[float] | None = None,
    challenger_mfe: Sequence[float] | None = None,
) -> dict[str, Any]:
    ch = _metrics(list(champion_r))
    cg = _metrics(list(challenger_r))
    n = min(ch["trade_count"], cg["trade_count"])
    if n < int(min_sample):
        verdict = "INSUFFICIENT_SAMPLE"
    else:
        # Never declare better on tiny evidence — already gated
        de = (cg["expectancy"] or 0) - (ch["expectancy"] or 0)
        dd = (cg["max_drawdown"] or 0) - (ch["max_drawdown"] or 0)
        if de > 0 and dd <= 0:
            verdict = "CHALLENGER_AHEAD_NEEDS_REVIEW"
        elif de < 0:
            verdict = "CHAMPION_AHEAD"
        else:
            verdict = "MIXED_NEEDS_REVIEW"

    def _avg(xs: Sequence[float] | None) -> float | None:
        if not xs:
            return None
        return round(sum(float(x) for x in xs) / len(xs), 6)

    return {
        "matched_sample_size": n,
        "min_sample": int(min_sample),
        "champion": ch,
        "challenger": cg,
        "difference_in_expectancy": (
            None
            if ch["expectancy"] is None or cg["expectancy"] is None
            else round(cg["expectancy"] - ch["expectancy"], 6)
        ),
        "difference_in_drawdown": (
            None
            if ch["max_drawdown"] is None or cg["max_drawdown"] is None
            else round(cg["max_drawdown"] - ch["max_drawdown"], 6)
        ),
        "MAE": {"champion": _avg(champion_mae), "challenger": _avg(challenger_mae)},
        "MFE": {"champion": _avg(champion_mfe), "challenger": _avg(challenger_mfe)},
        "verdict": verdict,
        "auto_promote": False,
        "challenger_execution_authority": False,
    }
