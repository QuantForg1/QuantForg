"""Compact opportunity-funnel telemetry — observability only.

Records score/edge/session histograms so production can measure where
WAIT/TAKE/EXECUTED actually occur. Never mutates strategy, Risk, Safety,
Optimizer, OMS, or MT5. Never changes Opportunity 70 or edge 5.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

ADVISORY_ONLY = True
OPP_THRESHOLD = 70
EDGE_MARGIN = 5
_MAX_HOURS = 31 * 24
_PERSIST_EVERY = 10
_PERSIST_SECONDS = 60.0

_OPP_BUCKETS = ("<50", "50-59", "60-69", "70-74", "75-79", "80-89", "90+")
_EDGE_BUCKETS = ("0-2", "3-4", "5-7", "8-10", ">10")
_SCORE_BUCKETS = ("0-19", "20-39", "40-59", "60-79", "80-100")
FUNNEL_STAGES = (
    "MARKET_DATA",
    "DIRECTION",
    "OPPORTUNITY",
    "SNIPER",
    "RISK",
    "SAFETY",
    "OPTIMIZER",
    "OMS",
    "BROKER",
    "MT5",
)
COMPONENT_KEYS = (
    "structure",
    "liquidity",
    "zone",
    "momentum",
    "timing",
    "displacement",
    "consensus",
    "volatility",
    "regime_fit",
    "price_action",
    "rr_quality",
    "mtf_alignment",
    "execution_quality",
)

_LOCK = threading.Lock()
_STATE: dict[str, Any] = {"hours": {}, "updated_at": None, "scans": 0}
_DIRTY = 0
_LAST_FLUSH_MONO = 0.0
_PATH: Path | None = None


def classify_blocker_source(code: str | None) -> str:
    """Map a human/canonical blocker to a funnel stage. Observation only."""
    raw = str(code or "").upper()
    if not raw.strip():
        return "NONE"
    if "NO_DIRECTIONAL_EDGE" in raw or "DIRECTION_NONE" in raw:
        return "DIRECTION"
    if (
        "OPPORTUNITY" in raw
        or "SETUP_NOT_READY" in raw
        or "SCORE_BELOW_THRESHOLD" in raw
    ):
        return "OPPORTUNITY"
    if any(
        token in raw
        for token in (
            "SNIPER",
            "WAIT_CHASE",
            "WAIT_STALE",
            "WAIT_INSUFFICIENT_RR",
            "WAIT_NO_SNIPER",
            "WAIT_ABNORMAL_SPREAD",
            "WAIT_CONFLICT",
            "WAIT_NO_INVALIDATION",
        )
    ):
        return "SNIPER"
    if any(
        token in raw
        for token in ("RISK", "MIN_LOT", "DAILY_LOSS", "MARGIN", "DRAWDOWN")
    ):
        return "RISK"
    if "SAFETY" in raw:
        return "SAFETY"
    if "OPTIMIZER" in raw:
        return "OPTIMIZER"
    if "OMS" in raw:
        return "OMS"
    if "BROKER" in raw or "GATEWAY" in raw:
        return "BROKER"
    if "MT5" in raw:
        return "MT5"
    if "HEALTH" in raw or "REJECT_BURST" in raw or "ENTRY_BURST" in raw:
        return "EXECUTION_HEALTH"
    if any(
        token in raw
        for token in ("NO_SNAPSHOT", "STALE_DATA", "MARKET_DATA", "NO_MARKET")
    ):
        return "MARKET_DATA"
    return "STRATEGY"


def session_bucket(raw: str | None, *, recorded_at: str | None = None) -> str:
    token = str(raw or "").strip().lower()
    if token in {"sydney", "tokyo", "london", "new york", "new_york", "ny"}:
        if token in {"new york", "new_york", "ny"}:
            return "new_york"
        return token
    if "overlap" in token or token in {"london/ny", "london_ny"}:
        return "london_ny_overlap"
    iso = recorded_at
    if not iso:
        return "unknown"
    try:
        hour = datetime.fromisoformat(str(iso).replace("Z", "+00:00")).hour
    except ValueError:
        return "unknown"
    if hour >= 21:
        return "sydney"
    if hour < 7:
        return "tokyo"
    if hour < 12:
        return "london"
    if hour < 16:
        return "london_ny_overlap"
    return "new_york"


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def opp_bucket(score: int | None) -> str | None:
    if score is None:
        return None
    if score < 50:
        return "<50"
    if score < 60:
        return "50-59"
    if score < 70:
        return "60-69"
    if score < 75:
        return "70-74"
    if score < 80:
        return "75-79"
    if score < 90:
        return "80-89"
    return "90+"


def edge_bucket(edge: int | None) -> str | None:
    if edge is None:
        return None
    if edge <= 2:
        return "0-2"
    if edge <= 4:
        return "3-4"
    if edge <= 7:
        return "5-7"
    if edge <= 10:
        return "8-10"
    return ">10"


def score_bucket(score: int | None) -> str | None:
    if score is None:
        return None
    if score < 20:
        return "0-19"
    if score < 40:
        return "20-39"
    if score < 60:
        return "40-59"
    if score < 80:
        return "60-79"
    return "80-100"


def _component_scores(cycle: dict[str, Any]) -> dict[str, int]:
    breakdown = cycle.get("score_breakdown") if isinstance(cycle.get("score_breakdown"), dict) else {}
    audit = cycle.get("opportunity_audit") if isinstance(cycle.get("opportunity_audit"), dict) else {}
    out: dict[str, int] = {}
    for key in COMPONENT_KEYS:
        raw = breakdown.get(key)
        nested = audit.get(key)
        if raw is None and isinstance(nested, dict):
            raw = nested.get("score")
        elif raw is None:
            raw = nested
        n = _as_int(raw)
        if n is not None:
            out[key] = n
    return out


def _empty_counts(keys: tuple[str, ...]) -> dict[str, int]:
    return {k: 0 for k in keys}


def _empty_hour() -> dict[str, Any]:
    return {
        "n": 0,
        "opportunity": _empty_counts(_OPP_BUCKETS),
        "edge": _empty_counts(_EDGE_BUCKETS),
        "buy": _empty_counts(_SCORE_BUCKETS),
        "sell": _empty_counts(_SCORE_BUCKETS),
        "ltf_buy": _empty_counts(_SCORE_BUCKETS),
        "ltf_sell": _empty_counts(_SCORE_BUCKETS),
        "sessions": {},
        "funnel": {
            "edge_ge_3": 0,
            "edge_ge_5": 0,
            "edge_ge_7": 0,
            "edge_ge_10": 0,
            "opp_ge_60": 0,
            "opp_ge_65": 0,
            "opp_ge_70": 0,
            "opp_ge_75": 0,
            "opp_ge_80": 0,
            "opp_ge_85": 0,
            "opp_ge_90": 0,
            "opportunity_ge_70": 0,
            "both_qualify": 0,
            "sniper_take": 0,
            "risk_reached": 0,
            "safety_reached": 0,
            "oms_forward": 0,
            "mt5_ticket": 0,
            "wait": 0,
            "buy_leading": 0,
            "sell_leading": 0,
            "balanced": 0,
            "buy_qualifying": 0,
            "sell_qualifying": 0,
        },
        "blockers": {},
        "blocker_codes": {},
        "setup_state": {},
        "regimes": {},
        "families": {},
        "stages": {s: 0 for s in FUNNEL_STAGES},
        "components": {k: _empty_counts(_SCORE_BUCKETS) for k in COMPONENT_KEYS},
    }


def _inc(bucket: dict[str, int], key: str | None) -> None:
    if not key:
        return
    bucket[key] = int(bucket.get(key) or 0) + 1


def _hour_key(iso: str | None) -> str:
    if not iso:
        return datetime.now(UTC).strftime("%Y-%m-%dT%H")
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return dt.astimezone(UTC).strftime("%Y-%m-%dT%H")
    except ValueError:
        return datetime.now(UTC).strftime("%Y-%m-%dT%H")


def histogram_path() -> Path:
    global _PATH
    if _PATH is not None:
        return _PATH
    try:
        from core.config.settings import get_settings

        base = Path(getattr(get_settings(), "data_dir", None) or "data")
    except Exception:
        base = Path("data")
    _PATH = base / "opportunity_funnel_histograms.json"
    return _PATH


def reset_funnel_telemetry_for_tests(path: Path | None = None) -> None:
    """Test helper — isolate histogram persistence."""
    global _STATE, _DIRTY, _LAST_FLUSH_MONO, _PATH
    with _LOCK:
        _STATE = {"hours": {}, "updated_at": None, "scans": 0}
        _DIRTY = 0
        _LAST_FLUSH_MONO = 0.0
        _PATH = path


def _prune_hours(hours: dict[str, Any]) -> dict[str, Any]:
    if len(hours) <= _MAX_HOURS:
        return hours
    keys = sorted(hours.keys())
    keep = keys[-_MAX_HOURS:]
    return {k: hours[k] for k in keep}


def observe_funnel_cycle(cycle: dict[str, Any] | None) -> dict[str, Any]:
    """Increment compact histograms from one diagnostic cycle. Never decides."""
    row = dict(cycle or {})
    recorded = str(row.get("recorded_at") or "")
    hour = _hour_key(recorded)
    session = session_bucket(
        str(row.get("market_session") or row.get("session") or ""),
        recorded_at=recorded,
    )
    opp = _as_int(row.get("opportunity_score"))
    edge = _as_int(row.get("directional_edge"))
    buy = _as_int(row.get("buy_score") or row.get("bullish_score"))
    sell = _as_int(row.get("sell_score") or row.get("bearish_score"))
    ltf_buy = _as_int(row.get("ltf_buy_score"))
    ltf_sell = _as_int(row.get("ltf_sell_score"))
    action = str(row.get("decision_action") or "").upper()
    setup = str(row.get("setup_state") or "").upper() or None
    blocker = str(
        row.get("first_authoritative_blocker")
        or ((row.get("rejection") or {}).get("primary") if isinstance(row.get("rejection"), dict) else "")
        or ""
    )
    source = str(row.get("blocker_source") or classify_blocker_source(blocker))
    forwarded = bool(row.get("forwarded_to_oms"))
    ticket = row.get("mt5_ticket") or (
        (row.get("execution_handoff") or {}).get("mt5_ticket")
        if isinstance(row.get("execution_handoff"), dict)
        else None
    )
    risk_reached = str(row.get("risk") or "").upper() not in {"", "NOT_REACHED", "NONE"}
    safety_reached = str(row.get("safety") or "").upper() not in {
        "",
        "NOT_REACHED",
        "NONE",
    }

    with _LOCK:
        hours = _STATE.setdefault("hours", {})
        bucket = hours.setdefault(hour, _empty_hour())
        bucket["n"] = int(bucket.get("n") or 0) + 1
        _inc(bucket["opportunity"], opp_bucket(opp))
        _inc(bucket["edge"], edge_bucket(edge))
        _inc(bucket["buy"], score_bucket(buy))
        _inc(bucket["sell"], score_bucket(sell))
        _inc(bucket["ltf_buy"], score_bucket(ltf_buy))
        _inc(bucket["ltf_sell"], score_bucket(ltf_sell))
        sessions = bucket.setdefault("sessions", {})
        sessions[session] = int(sessions.get(session) or 0) + 1
        funnel = bucket.setdefault("funnel", _empty_hour()["funnel"])
        if edge is not None and edge >= EDGE_MARGIN:
            funnel["edge_ge_5"] = int(funnel.get("edge_ge_5") or 0) + 1
        if opp is not None:
            for thresh in (60, 65, 70, 75, 80, 85, 90):
                if opp >= thresh:
                    key = f"opp_ge_{thresh}"
                    funnel[key] = int(funnel.get(key) or 0) + 1
            if opp >= OPP_THRESHOLD:
                funnel["opportunity_ge_70"] = int(funnel.get("opportunity_ge_70") or 0) + 1
        if edge is not None:
            for thresh in (3, 5, 7, 10):
                if edge >= thresh:
                    key = f"edge_ge_{thresh}"
                    funnel[key] = int(funnel.get(key) or 0) + 1
        if (
            edge is not None
            and opp is not None
            and edge >= EDGE_MARGIN
            and opp >= OPP_THRESHOLD
        ):
            funnel["both_qualify"] = int(funnel.get("both_qualify") or 0) + 1
            if buy is not None and sell is not None:
                if buy > sell:
                    funnel["buy_qualifying"] = int(funnel.get("buy_qualifying") or 0) + 1
                elif sell > buy:
                    funnel["sell_qualifying"] = int(funnel.get("sell_qualifying") or 0) + 1
        if setup == "TAKE" or action in {"BUY", "SELL"}:
            funnel["sniper_take"] = int(funnel.get("sniper_take") or 0) + 1
        if risk_reached:
            funnel["risk_reached"] = int(funnel.get("risk_reached") or 0) + 1
        if safety_reached:
            funnel["safety_reached"] = int(funnel.get("safety_reached") or 0) + 1
        if forwarded:
            funnel["oms_forward"] = int(funnel.get("oms_forward") or 0) + 1
        if ticket:
            funnel["mt5_ticket"] = int(funnel.get("mt5_ticket") or 0) + 1
        if action in {"WAIT", "NO_TRADE", "WATCH", ""}:
            funnel["wait"] = int(funnel.get("wait") or 0) + 1
        if buy is not None and sell is not None:
            if buy > sell:
                funnel["buy_leading"] = int(funnel.get("buy_leading") or 0) + 1
            elif sell > buy:
                funnel["sell_leading"] = int(funnel.get("sell_leading") or 0) + 1
            else:
                funnel["balanced"] = int(funnel.get("balanced") or 0) + 1
        if blocker:
            blockers = bucket.setdefault("blockers", {})
            blockers[source] = int(blockers.get(source) or 0) + 1
            codes = bucket.setdefault("blocker_codes", {})
            token = blocker[:80]
            codes[token] = int(codes.get(token) or 0) + 1
        regime = str(row.get("market_regime") or "").strip()
        if regime:
            regimes = bucket.setdefault("regimes", {})
            regimes[regime] = int(regimes.get(regime) or 0) + 1
        if setup:
            states = bucket.setdefault("setup_state", {})
            states[setup] = int(states.get(setup) or 0) + 1
        families = bucket.setdefault("families", {})
        for key in ("buy_families", "sell_families"):
            raw = row.get(key) or []
            if isinstance(raw, (list, tuple)):
                for fam in raw:
                    token = str(fam).strip().lower()
                    if token:
                        families[token] = int(families.get(token) or 0) + 1
        stages = bucket.setdefault("stages", {s: 0 for s in FUNNEL_STAGES})
        stage_key = source if source in FUNNEL_STAGES else None
        if stage_key:
            stages[stage_key] = int(stages.get(stage_key) or 0) + 1
        components = bucket.setdefault(
            "components", {k: _empty_counts(_SCORE_BUCKETS) for k in COMPONENT_KEYS}
        )
        for name, value in _component_scores(row).items():
            _inc(components.setdefault(name, _empty_counts(_SCORE_BUCKETS)), score_bucket(value))
        hours = _prune_hours(hours)
        _STATE["hours"] = hours
        _STATE["updated_at"] = datetime.now(UTC).isoformat()
        _STATE["scans"] = int(_STATE.get("scans") or 0) + 1
        global _DIRTY
        _DIRTY += 1
        snapshot = {
            "advisory_only": True,
            "mutates_engines": False,
            "opportunity_threshold": OPP_THRESHOLD,
            "edge_margin": EDGE_MARGIN,
            **_STATE,
        }
        now_mono = time.monotonic()
        should_flush = _DIRTY >= _PERSIST_EVERY or (
            _LAST_FLUSH_MONO > 0 and (now_mono - _LAST_FLUSH_MONO) >= _PERSIST_SECONDS
        )
    if should_flush:
        _flush_unlocked(snapshot)
    return snapshot


def _flush_unlocked(snapshot: dict[str, Any] | None = None) -> None:
    global _DIRTY, _LAST_FLUSH_MONO

    payload = snapshot
    if payload is None:
        with _LOCK:
            payload = {
                "advisory_only": True,
                "mutates_engines": False,
                "opportunity_threshold": OPP_THRESHOLD,
                "edge_margin": EDGE_MARGIN,
                **_STATE,
            }
    path = histogram_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, default=str), encoding="utf-8")
        tmp.replace(path)
        with _LOCK:
            _DIRTY = 0
            _LAST_FLUSH_MONO = time.monotonic()
    except Exception:
        logger.exception("opportunity_funnel_histogram_persist_failed")


def _merge_hour(dst: dict[str, Any], hour: dict[str, Any]) -> None:
    dst["n"] += int(hour.get("n") or 0)
    for name in ("opportunity", "edge", "buy", "sell", "ltf_buy", "ltf_sell"):
        src = hour.get(name) if isinstance(hour.get(name), dict) else {}
        bucket = dst[name]
        for k, v in src.items():
            bucket[k] = int(bucket.get(k) or 0) + int(v or 0)
    for k, v in (hour.get("funnel") or {}).items():
        dst["funnel"][k] = int(dst["funnel"].get(k) or 0) + int(v or 0)
    for k, v in (hour.get("sessions") or {}).items():
        dst["sessions"][k] = int(dst["sessions"].get(k) or 0) + int(v or 0)
    for k, v in (hour.get("blockers") or {}).items():
        dst["blockers"][k] = int(dst["blockers"].get(k) or 0) + int(v or 0)
    for k, v in (hour.get("blocker_codes") or {}).items():
        dst.setdefault("blocker_codes", {})
        dst["blocker_codes"][k] = int(dst["blocker_codes"].get(k) or 0) + int(v or 0)
    for k, v in (hour.get("regimes") or {}).items():
        dst.setdefault("regimes", {})
        dst["regimes"][k] = int(dst["regimes"].get(k) or 0) + int(v or 0)
    for k, v in (hour.get("setup_state") or {}).items():
        dst["setup_state"][k] = int(dst["setup_state"].get(k) or 0) + int(v or 0)
    for k, v in (hour.get("families") or {}).items():
        dst.setdefault("families", {})
        dst["families"][k] = int(dst["families"].get(k) or 0) + int(v or 0)
    for k, v in (hour.get("stages") or {}).items():
        dst.setdefault("stages", {s: 0 for s in FUNNEL_STAGES})
        dst["stages"][k] = int(dst["stages"].get(k) or 0) + int(v or 0)
    src_comp = hour.get("components") if isinstance(hour.get("components"), dict) else {}
    dst.setdefault("components", {k: _empty_counts(_SCORE_BUCKETS) for k in COMPONENT_KEYS})
    for name, buckets in src_comp.items():
        if not isinstance(buckets, dict):
            continue
        target = dst["components"].setdefault(name, _empty_counts(_SCORE_BUCKETS))
        for k, v in buckets.items():
            target[k] = int(target.get(k) or 0) + int(v or 0)


def _rates(funnel: dict[str, Any], n: int) -> dict[str, float]:
    denom = max(int(n or 0), 1)
    return {
        "edge_ge_3": round(100.0 * int(funnel.get("edge_ge_3") or 0) / denom, 2),
        "edge_ge_5": round(100.0 * int(funnel.get("edge_ge_5") or 0) / denom, 2),
        "edge_ge_7": round(100.0 * int(funnel.get("edge_ge_7") or 0) / denom, 2),
        "edge_ge_10": round(100.0 * int(funnel.get("edge_ge_10") or 0) / denom, 2),
        "opp_ge_60": round(100.0 * int(funnel.get("opp_ge_60") or 0) / denom, 2),
        "opp_ge_65": round(100.0 * int(funnel.get("opp_ge_65") or 0) / denom, 2),
        "opp_ge_70": round(100.0 * int(funnel.get("opp_ge_70") or 0) / denom, 2),
        "opp_ge_75": round(100.0 * int(funnel.get("opp_ge_75") or 0) / denom, 2),
        "opp_ge_80": round(100.0 * int(funnel.get("opp_ge_80") or 0) / denom, 2),
        "opp_ge_85": round(100.0 * int(funnel.get("opp_ge_85") or 0) / denom, 2),
        "opp_ge_90": round(100.0 * int(funnel.get("opp_ge_90") or 0) / denom, 2),
        "opportunity_ge_70": round(
            100.0 * int(funnel.get("opportunity_ge_70") or funnel.get("opp_ge_70") or 0) / denom, 2
        ),
        "both_qualify": round(100.0 * int(funnel.get("both_qualify") or 0) / denom, 2),
        "sniper_take": round(100.0 * int(funnel.get("sniper_take") or 0) / denom, 2),
        "oms_forward": round(100.0 * int(funnel.get("oms_forward") or 0) / denom, 2),
        "mt5_ticket": round(100.0 * int(funnel.get("mt5_ticket") or 0) / denom, 2),
        "wait": round(100.0 * int(funnel.get("wait") or 0) / denom, 2),
    }


def funnel_snapshot() -> dict[str, Any]:
    with _LOCK:
        hours = dict(_STATE.get("hours") or {})
        scans = int(_STATE.get("scans") or 0)
        updated = _STATE.get("updated_at")
    totals = _empty_hour()
    for hour in hours.values():
        _merge_hour(totals, hour if isinstance(hour, dict) else {})
    now = datetime.now(UTC)

    windows: dict[str, Any] = {}
    for label, span in (
        ("1h", 1),
        ("6h", 6),
        ("12h", 12),
        ("24h", 24),
        ("3d", 72),
        ("7d", 168),
        ("14d", 336),
        ("30d", 720),
    ):
        bucket = _empty_hour()
        cutoff_start = (
            now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=span - 1)
        ).strftime("%Y-%m-%dT%H")
        cutoff_end = now.strftime("%Y-%m-%dT%H")
        for key, hour in hours.items():
            if cutoff_start <= str(key) <= cutoff_end:
                _merge_hour(bucket, hour if isinstance(hour, dict) else {})
        windows[label] = {
            "n": bucket["n"],
            "opportunity": bucket["opportunity"],
            "edge": bucket["edge"],
            "sessions": bucket["sessions"],
            "regimes": bucket.get("regimes") or {},
            "setup_state": bucket.get("setup_state") or {},
            "families": bucket.get("families") or {},
            "funnel": bucket["funnel"],
            "blockers": bucket["blockers"],
            "stages": bucket.get("stages") or {},
            "stage_rates_pct": {
                s: round(100.0 * int((bucket.get("stages") or {}).get(s) or 0) / max(int(bucket["n"] or 0), 1), 2)
                for s in FUNNEL_STAGES
            },
            "components": bucket.get("components") or {},
            "rates_pct": _rates(bucket["funnel"], bucket["n"]),
            "incomplete": bucket["n"] == 0,
        }
    return {
        "advisory_only": True,
        "mutates_engines": False,
        "never_changes_thresholds": True,
        "opportunity_threshold": OPP_THRESHOLD,
        "edge_margin": EDGE_MARGIN,
        "scans": scans,
        "updated_at": updated,
        "hours_retained": len(hours),
        "totals": totals,
        "rates_pct": _rates(totals["funnel"], totals["n"]),
        "stage_rates_pct": {
            s: round(100.0 * int((totals.get("stages") or {}).get(s) or 0) / max(int(totals["n"] or 0), 1), 2)
            for s in FUNNEL_STAGES
        },
        "components": totals.get("components") or {},
        "windows": windows,
        "note": (
            "Histograms are observability only. Incomplete windows mean the "
            "store has not yet retained that span — not zero opportunity. "
            "TAKE is not EXECUTED. EXECUTED requires a real MT5 ticket."
        ),
    }
