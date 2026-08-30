"""Fair research-scan scheduling.

Priority never bypasses safety. This module only orders symbols for
research refresh. It never calls OMS / MT5 / order_send.
"""

from __future__ import annotations

from typing import Any

from app.domain.market_universe.constants import (
    ALLOW_LIVE_PROMOTION,
    RESEARCH_RETRY_BACKOFF_S,
)
from app.domain.market_universe.identity import canonical_desk
from app.domain.trading.gold_only import is_gold_symbol

DEFAULT_RESEARCH_BATCH = 48
MAX_RESEARCH_BATCH = 96

_CLASS_ROTATION = (
    "FOREX",
    "METALS",
    "CRYPTO",
    "INDICES",
    "ENERGY",
    "STOCKS",
    "COMMODITIES",
    "OTHER",
)
_WEEKEND_CLASS_ROTATION = (
    "CRYPTO",
    "METALS",
    "FOREX",
    "INDICES",
    "ENERGY",
    "STOCKS",
    "COMMODITIES",
    "OTHER",
)


def _class_rotation() -> tuple[str, ...]:
    """Prefer 24/7 crypto first on weekends; otherwise standard rotation."""
    from datetime import UTC, datetime

    if datetime.now(UTC).weekday() >= 5:
        return _WEEKEND_CLASS_ROTATION
    return _CLASS_ROTATION


def research_scan_order(
    instruments: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    last_opportunity: dict[str, int] | None = None,
    last_analyzed: dict[str, str] | None = None,
    max_batch: int = DEFAULT_RESEARCH_BATCH,
    exclude_stale: bool = True,
) -> dict[str, Any]:
    """Return a rate-limited research queue.

    Gold reference is observed first for backward-compatible monitoring,
    then round-robin across asset classes. Closed/no-data symbols are
    excluded from scoring (they remain in the registry as explicit states).
    Prefer never-analyzed desks, then oldest analyzed (stale-first).
    """
    from datetime import UTC, datetime

    cap = min(max(1, int(max_batch or DEFAULT_RESEARCH_BATCH)), MAX_RESEARCH_BATCH)
    opp = last_opportunity or {}
    analyzed_at = last_analyzed or {}
    now = datetime.now(UTC)
    rotation = _class_rotation()
    buckets: dict[str, list[dict[str, Any]]] = {k: [] for k in rotation}
    skipped: list[dict[str, str]] = []
    gold: list[dict[str, Any]] = []

    def _analysis_age_s(desk: str) -> float | None:
        raw = analyzed_at.get(desk)
        if not raw:
            return None
        try:
            ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            return max(0.0, (now - ts).total_seconds())
        except Exception:
            return None

    for item in instruments:
        desk = canonical_desk(
            str(item.get("canonical_symbol") or item.get("broker_symbol") or "")
        )
        if not desk:
            continue
        state = str(
            (item.get("data_quality") or {}).get("state")
            or item.get("data_availability")
            or ""
        )
        cls = str(item.get("asset_class") or "OTHER").upper()
        if cls not in buckets:
            cls = "OTHER"
        # Closed traditional markets stay in registry but are not scored.
        # Open CRYPTO / OTHER (often LIVE on weekends) remain eligible.
        if exclude_stale and state in {
            "STALE",
            "NO_DATA",
            "DISABLED",
            "UNSUPPORTED",
            "MARKET_CLOSED",
        }:
            skipped.append({"symbol": desk, "reason": state})
            continue
        age_s = _analysis_age_s(desk)
        payload = {
            "canonical_symbol": desk,
            "broker_symbol": item.get("broker_symbol") or desk,
            "asset_class": cls,
            "data_state": state,
            "last_opportunity": opp.get(desk, None),
            "last_analyzed_at": analyzed_at.get(desk),
            "analysis_age_s": age_s,
            "history_sufficient": bool(
                (item.get("timeframe_quality") or {}).get("sufficient")
            )
            if isinstance(item.get("timeframe_quality"), dict)
            else None,
            "data_age": (item.get("data_quality") or {}).get("quote_age_s")
            if isinstance(item.get("data_quality"), dict)
            else None,
        }
        if is_gold_symbol(desk):
            gold.append(payload)
        else:
            buckets[cls].append(payload)

    for key in buckets:
        buckets[key].sort(
            key=lambda r: (
                1 if r.get("data_state") == "LIVE" else 0,
                1 if r.get("history_sufficient") is True else 0,
                # Prefer never-analyzed desks so coverage fills across cycles.
                1 if r.get("last_opportunity") is None else 0,
                # Among scored desks, stale-first (oldest analysis first).
                float(r.get("analysis_age_s") or 0.0),
                1 if r.get("data_age") not in (None, "") else 0,
                -(
                    float(r.get("data_age") or 0)
                    if r.get("data_age") not in (None, "")
                    else 0
                ),
                -(
                    float(r.get("last_opportunity"))
                    if r.get("last_opportunity") is not None
                    else 0
                ),
            ),
            reverse=True,
        )

    eligible_n = len(gold) + sum(len(bucket) for bucket in buckets.values())

    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _take(row: dict[str, Any]) -> None:
        desk = str(row["canonical_symbol"])
        if desk in seen or len(ordered) >= cap:
            return
        seen.add(desk)
        ordered.append(row)

    for row in gold:
        _take(row)
    pointers = dict.fromkeys(rotation, 0)
    progress = True
    while progress and len(ordered) < cap:
        progress = False
        for key in rotation:
            i = pointers[key]
            bucket = buckets[key]
            if i >= len(bucket):
                continue
            _take(bucket[i])
            pointers[key] = i + 1
            progress = True
            if len(ordered) >= cap:
                break

    return {
        "advisory_only": True,
        "authorizes_trade": False,
        "ALLOW_LIVE_PROMOTION": ALLOW_LIVE_PROMOTION,
        "priority_never_bypasses_safety": True,
        "batch_size": len(ordered),
        "max_batch": cap,
        "eligible_n": eligible_n,
        "skipped_n": len(skipped),
        "queue": ordered,
        "skipped": skipped,
        "class_rotation": list(rotation),
        "note": (
            "Research queue only. Live ITE scan universe remains gold-only "
            "in production. Missing data is deferred, never scored as 0. "
            "Weekend rotation prefers CRYPTO when available. "
            "Unscored then stale-analyzed desks are preferred for coverage fill."
        ),
        "priority_order": (
            "LIVE_DATA",
            "sufficient_history",
            "never_analyzed",
            "stale_analyzed",
            "lower_data_age",
            "lower_known_opportunity",
        ),
        "retry_backoff_s": RESEARCH_RETRY_BACKOFF_S,
        "uncontrolled_polling": False,
    }
