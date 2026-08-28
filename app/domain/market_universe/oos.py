"""Chronological OOS / walk-forward helpers for shadow candidates.

Never shuffles time series. Labels are research confidence, not trading
permission. No automatic promotion.
"""

from __future__ import annotations

from typing import Any

from app.domain.market_universe.constants import (
    ALLOW_LIVE_PROMOTION,
    INSUFFICIENT_SAMPLE,
    UNKNOWN,
)
from app.domain.market_universe.honesty import sample_status
from app.domain.market_universe.lookahead import detect_lookahead_fields


def _ts(row: dict[str, Any]) -> str:
    return str(
        row.get("timestamp")
        or row.get("features_as_of")
        or row.get("recorded_at")
        or row.get("entry_time")
        or ""
    )


def chronological_split(
    rows: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
    *,
    train_frac: float = 0.6,
    val_frac: float = 0.2,
) -> dict[str, Any]:
    ordered = sorted((r for r in (rows or ()) if isinstance(r, dict)), key=_ts)
    n = len(ordered)
    if n < 20:
        return {
            "n": n,
            "status": INSUFFICIENT_SAMPLE,
            "train": [],
            "validation": [],
            "oos": [],
            "shuffled": False,
            "ALLOW_LIVE_PROMOTION": False,
        }
    n_train = max(1, int(n * train_frac))
    n_val = max(1, int(n * val_frac))
    if n_train + n_val >= n:
        n_val = max(1, n - n_train - 1)
    train = ordered[:n_train]
    val = ordered[n_train : n_train + n_val]
    oos = ordered[n_train + n_val :]
    return {
        "n": n,
        "status": sample_status(n),
        "train": train,
        "validation": val,
        "oos": oos,
        "n_train": len(train),
        "n_validation": len(val),
        "n_oos": len(oos),
        "shuffled": False,
        "ALLOW_LIVE_PROMOTION": ALLOW_LIVE_PROMOTION,
        "automatic_promotion": False,
    }


def walk_forward_windows(
    rows: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
    *,
    window: int = 40,
    step: int = 20,
) -> dict[str, Any]:
    ordered = sorted((r for r in (rows or ()) if isinstance(r, dict)), key=_ts)
    n = len(ordered)
    if n < 20:
        return {
            "n": n,
            "status": INSUFFICIENT_SAMPLE,
            "windows": [],
            "shuffled": False,
            "ALLOW_LIVE_PROMOTION": False,
        }
    folds: list[dict[str, Any]] = []
    start = 0
    while start + window <= n:
        chunk = ordered[start : start + window]
        split = chronological_split(chunk)
        folds.append(
            {
                "start_index": start,
                "n": len(chunk),
                "n_train": split.get("n_train"),
                "n_oos": split.get("n_oos"),
                "status": split.get("status"),
            }
        )
        start += max(1, step)
        if len(folds) >= 12:
            break
    return {
        "n": n,
        "status": sample_status(n),
        "windows": folds,
        "shuffled": False,
        "automatic_promotion": False,
        "ALLOW_LIVE_PROMOTION": False,
        "research_confidence_only": True,
    }


def candidate_research_record(row: dict[str, Any]) -> dict[str, Any]:
    leaked = detect_lookahead_fields(row)
    features = {k: v for k, v in dict(row).items() if k not in leaked}
    return {
        "candidate_id": row.get("candidate_id") or UNKNOWN,
        "symbol": row.get("symbol") or UNKNOWN,
        "asset_class": row.get("asset_class") or UNKNOWN,
        "timestamp": _ts(row) or UNKNOWN,
        "features_as_of": features.get("features_as_of") or _ts(row) or UNKNOWN,
        "direction": row.get("direction") or UNKNOWN,
        "entry": row.get("entry") or row.get("hypothetical_entry") or UNKNOWN,
        "SL": row.get("sl") or row.get("hypothetical_SL") or UNKNOWN,
        "TP": row.get("tp") or row.get("hypothetical_TP") or UNKNOWN,
        "RR": row.get("rr") or row.get("hypothetical_R") or UNKNOWN,
        "setup": row.get("setup") or row.get("candidate_name") or UNKNOWN,
        "session": row.get("session") or UNKNOWN,
        "regime": row.get("regime") or UNKNOWN,
        "spread": row.get("spread") or UNKNOWN,
        "volatility": row.get("volatility") or UNKNOWN,
        "opportunity": row.get("opportunity")
        or row.get("opportunity_score")
        or UNKNOWN,
        "edge": row.get("edge") or row.get("directional_edge") or UNKNOWN,
        "hypothetical_outcome": UNKNOWN
        if leaked
        else (row.get("hypothetical_outcome") or UNKNOWN),
        "MAE": row.get("MAE") or UNKNOWN,
        "MFE": row.get("MFE") or UNKNOWN,
        "hold_time": row.get("hold_time") or UNKNOWN,
        "lookahead_fields": leaked,
        "lookahead_blocked": bool(leaked),
        "SHADOW_ONLY": True,
        "ALLOW_LIVE_PROMOTION": False,
        "would_submit_order": False,
    }


def assert_no_lookahead(row: dict[str, Any]) -> None:
    leaked = detect_lookahead_fields(row)
    if leaked:
        raise ValueError(f"LOOKAHEAD_FORBIDDEN: {leaked}")
