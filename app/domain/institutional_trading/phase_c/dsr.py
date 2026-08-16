"""Deflated Sharpe Ratio — research validation only.

Addresses selection bias and non-normality (Bailey / López de Prado).
Never promotes a strategy from raw Sharpe alone. Never gates LIVE in Phase C.
"""

from __future__ import annotations

import math
from typing import Any, Sequence


def _sharpe(returns: Sequence[float]) -> float | None:
    n = len(returns)
    if n < 2:
        return None
    mu = sum(returns) / n
    var = sum((x - mu) ** 2 for x in returns) / (n - 1)
    if var <= 0:
        return None
    return mu / math.sqrt(var)


def _moments(returns: Sequence[float]) -> tuple[float, float, float]:
    n = len(returns)
    mu = sum(returns) / n
    m2 = sum((x - mu) ** 2 for x in returns) / n
    m3 = sum((x - mu) ** 3 for x in returns) / n
    m4 = sum((x - mu) ** 4 for x in returns) / n
    sigma = math.sqrt(m2) if m2 > 0 else 0.0
    skew = (m3 / (sigma**3)) if sigma > 0 else 0.0
    kurt = (m4 / (sigma**4)) if sigma > 0 else 3.0
    return skew, kurt, sigma


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def probabilistic_sharpe_ratio(
    *,
    observed_sharpe: float,
    n: int,
    skew: float = 0.0,
    kurtosis: float = 3.0,
    benchmark_sharpe: float = 0.0,
) -> float | None:
    """PSR: P(true Sharpe > benchmark) under non-normal adjustment."""
    if n < 2:
        return None
    sr = observed_sharpe
    sr0 = benchmark_sharpe
    # López de Prado PSR variance of Sharpe estimator
    num = (sr - sr0) * math.sqrt(n - 1)
    den_sq = 1.0 - skew * sr + ((kurtosis - 1.0) / 4.0) * (sr**2)
    if den_sq <= 0:
        return None
    z = num / math.sqrt(den_sq)
    return _norm_cdf(z)


def expected_max_sharpe(*, n_trials: int, n_obs: int) -> float:
    """Expected maximum Sharpe under N(0,1) multiple-testing approximation."""
    if n_trials < 1 or n_obs < 2:
        return 0.0
    # Euler-Mascheroni approximation for E[max of n_trials normals]
    e = 0.5772156649
    if n_trials == 1:
        return 0.0
    z = (1.0 - e) * math.pow(math.log(n_trials), -1) + e * math.pow(
        math.log(n_trials), -1
    )
    # Scale loosely with track length
    return z * math.sqrt(max(1.0, math.log(max(2, n_trials))))


def deflated_sharpe_ratio(
    returns: Sequence[float],
    *,
    n_trials: int,
    benchmark_sharpe: float | None = None,
) -> dict[str, Any]:
    n = len(returns)
    if n < 5:
        return {
            "RAW_SHARPE": None,
            "PROBABILISTIC_SHARPE": None,
            "DEFLATED_SHARPE": None,
            "TRIAL_COUNT": int(n_trials),
            "TRACK_RECORD_LENGTH": n,
            "CONFIDENCE_STATE": "INSUFFICIENT_TRACK_RECORD",
            "live_gate": False,
        }
    raw = _sharpe(returns)
    if raw is None:
        return {
            "RAW_SHARPE": None,
            "PROBABILISTIC_SHARPE": None,
            "DEFLATED_SHARPE": None,
            "TRIAL_COUNT": int(n_trials),
            "TRACK_RECORD_LENGTH": n,
            "CONFIDENCE_STATE": "INSUFFICIENT_TRACK_RECORD",
            "live_gate": False,
        }
    skew, kurt, _ = _moments(returns)
    sr0 = (
        float(benchmark_sharpe)
        if benchmark_sharpe is not None
        else expected_max_sharpe(n_trials=max(1, int(n_trials)), n_obs=n)
    )
    psr = probabilistic_sharpe_ratio(
        observed_sharpe=raw,
        n=n,
        skew=skew,
        kurtosis=kurt,
        benchmark_sharpe=sr0,
    )
    # DSR reported as the PSR against the expected-max Sharpe under trials
    dsr = psr
    if n < 20:
        state = "INSUFFICIENT_TRACK_RECORD"
    elif dsr is None:
        state = "WEAK_EVIDENCE"
    elif dsr >= 0.95:
        state = "STRONG_EVIDENCE"
    elif dsr >= 0.75:
        state = "MODERATE_EVIDENCE"
    else:
        state = "WEAK_EVIDENCE"

    return {
        "RAW_SHARPE": round(raw, 6),
        "PROBABILISTIC_SHARPE": None if psr is None else round(psr, 6),
        "DEFLATED_SHARPE": None if dsr is None else round(dsr, 6),
        "TRIAL_COUNT": int(n_trials),
        "TRACK_RECORD_LENGTH": n,
        "skewness": round(skew, 6),
        "kurtosis": round(kurt, 6),
        "benchmark_sharpe": round(sr0, 6),
        "CONFIDENCE_STATE": state,
        "live_gate": False,
        "auto_promote": False,
    }
