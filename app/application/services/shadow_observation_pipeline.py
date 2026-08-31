"""Persistent SHADOW observation pipeline — research only.

Records every live scan, evaluates A–X candidates independently, and
advances a virtual-trade lifecycle with prices available at each timestamp.

This is not a trade. WOULD_SUBMIT_ORDER is always false. Virtual rows are
labeled SHADOW_VIRTUAL_TRADE and never written into the live forensic
execution ledger. CORE and SHADOW_EXPANSION stay separate. Live Opportunity
70 / edge 5 / Risk / Safety / OMS / MT5 are never called or changed.
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.application.services.shadow_expansion_engine import (
    CANDIDATE_SPECS,
    EDGE_MARGIN,
    OPP_THRESHOLD,
    ShadowExpansionBlocked,
    candidate_present,
    detect_lookahead_fields,
    features_as_of,
    walk_forward_split,
)
from app.application.services.strategy_forensic_ledger import (
    _as_float,
    _as_int,
    _as_str,
    _score_from,
)
from app.application.services.strategy_loss_forensics import (
    CANONICAL_REGIMES,
    CANONICAL_SESSIONS,
    INSUFFICIENT_SAMPLE,
    UNKNOWN,
    _metrics,
    format_win_rate,
    sample_status,
)

ADVISORY_ONLY = True
SHADOW_VIRTUAL_TRADE = "SHADOW_VIRTUAL_TRADE"
STRATEGY_MATCHED_LIVE_TRADE = "STRATEGY_MATCHED_LIVE_TRADE"
ALLOW_LIVE_PROMOTION = False
WOULD_SUBMIT_ORDER = False
LIFECYCLE = (
    "OBSERVED",
    "ELIGIBLE",
    "TRIGGERED",
    "VIRTUAL_ENTRY",
    "VIRTUAL_MANAGEMENT",
    "VIRTUAL_EXIT",
    "OUTCOME",
)
BELOW_CORE_THRESHOLD = "SHADOW CANDIDATE OPERATES BELOW CORE THRESHOLD"
_MAX_SCANS = 80_000
_MAX_VIRTUAL = 20_000
_PERSIST_EVERY = 10

_LOCK = threading.Lock()
_SCANS: list[dict[str, Any]] = []
_VIRTUAL: list[dict[str, Any]] = []
_DIRTY = 0
_ROOT: Path | None = None
_LOADED = False


class ShadowPipelineBlocked(RuntimeError):
    """Raised if shadow observation is used as an execution path."""


def submit_order(*_args: Any, **_kwargs: Any) -> None:
    raise ShadowPipelineBlocked("SHADOW_OBSERVATION_CANNOT_SEND_ORDERS")


def call_oms(*_args: Any, **_kwargs: Any) -> None:
    raise ShadowPipelineBlocked("SHADOW_OBSERVATION_CANNOT_CALL_OMS")


def call_mt5(*_args: Any, **_kwargs: Any) -> None:
    raise ShadowPipelineBlocked("SHADOW_OBSERVATION_CANNOT_CALL_MT5")


def write_live_execution_ledger(*_args: Any, **_kwargs: Any) -> None:
    raise ShadowPipelineBlocked("SHADOW_VIRTUAL_TRADE_CANNOT_ENTER_LIVE_LEDGER")


def promote_to_live(*_args: Any, **_kwargs: Any) -> None:
    raise ShadowExpansionBlocked("SHADOW_CANNOT_GO_LIVE_FROM_THIS_MODULE")


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _data_root() -> Path:
    global _ROOT
    if _ROOT is not None:
        return _ROOT
    try:
        from core.config.settings import get_settings

        base = Path(getattr(get_settings(), "data_dir", None) or "data")
    except Exception:
        base = Path("data")
    _ROOT = base / "shadow_observations"
    return _ROOT


def reset_shadow_pipeline_for_tests(root: Path | None = None) -> None:
    """Isolate shadow files for unit tests. Never used in production."""
    global _SCANS, _VIRTUAL, _DIRTY, _ROOT, _LOADED
    with _LOCK:
        _SCANS = []
        _VIRTUAL = []
        _DIRTY = 0
        _ROOT = root
        _LOADED = True
        if root is not None:
            root.mkdir(parents=True, exist_ok=True)


def _ensure_loaded() -> None:
    global _SCANS, _VIRTUAL, _LOADED
    if _LOADED:
        return
    root = _data_root()
    scans: list[dict[str, Any]] = []
    virtual: list[dict[str, Any]] = []
    try:
        scans_path = root / "scans.json"
        if scans_path.exists():
            raw = json.loads(scans_path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                scans = [r for r in raw if isinstance(r, dict)]
    except Exception:
        scans = []
    try:
        virt_path = root / "virtual_trades.json"
        if virt_path.exists():
            raw = json.loads(virt_path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                virtual = [r for r in raw if isinstance(r, dict)]
    except Exception:
        virtual = []
    _SCANS = scans[-_MAX_SCANS:]
    _VIRTUAL = virtual[-_MAX_VIRTUAL:]
    _LOADED = True


def _flush_locked() -> None:
    global _DIRTY
    root = _data_root()
    try:
        root.mkdir(parents=True, exist_ok=True)
        (root / "scans.json").write_text(
            json.dumps(_SCANS[-_MAX_SCANS:], separators=(",", ":")),
            encoding="utf-8",
        )
        (root / "virtual_trades.json").write_text(
            json.dumps(_VIRTUAL[-_MAX_VIRTUAL:], separators=(",", ":")),
            encoding="utf-8",
        )
        _DIRTY = 0
    except Exception:
        pass


def _touch_locked() -> None:
    global _DIRTY
    _DIRTY += 1
    if _DIRTY >= _PERSIST_EVERY:
        _flush_locked()


def compact_shadow_scan(cycle: dict[str, Any] | None) -> dict[str, Any]:
    """Project a live scan into a compact SHADOW observation. T-or-before only."""
    row = features_as_of(cycle)
    leaked = detect_lookahead_fields(cycle)
    ltf_buy = _as_int(row.get("ltf_buy_score") or row.get("ltf_buy"))
    ltf_sell = _as_int(row.get("ltf_sell_score") or row.get("ltf_sell"))
    edge = _as_int(row.get("directional_edge"))
    opp = _as_int(row.get("opportunity_score"))
    families = [str(x) for x in (row.get("buy_families") or [])] + [
        str(x) for x in (row.get("sell_families") or [])
    ]
    core_clears = bool(
        edge is not None
        and opp is not None
        and edge >= EDGE_MARGIN
        and opp >= OPP_THRESHOLD
    )
    return {
        "record_kind": "SHADOW_SCAN",
        "dataset": "SHADOW",
        "advisory_only": True,
        "would_submit_order": False,
        "ALLOW_LIVE_PROMOTION": False,
        "timestamp": _as_str(row.get("recorded_at") or row.get("scan_as_of")) or _now_iso(),
        "symbol": _as_str(row.get("symbol")) or "XAUUSD_i",
        "buy_score": _as_int(row.get("buy_score") or row.get("bullish_score")),
        "sell_score": _as_int(row.get("sell_score") or row.get("bearish_score")),
        "ltf_buy": ltf_buy,
        "ltf_sell": ltf_sell,
        "edge": edge,
        "opportunity": opp,
        "first_blocker": _as_str(row.get("first_authoritative_blocker")),
        "blocker_source": _as_str(row.get("blocker_source")),
        "setup_state": _as_str(row.get("setup_state")),
        "families": families,
        "structure": _score_from(row, "structure_score", "structure"),
        "liquidity": _score_from(row, "liquidity_score", "liquidity"),
        "zones": _score_from(row, "zone_score", "zone"),
        "ob": _as_str(row.get("ob_state") or row.get("order_block_state")),
        "fvg": _as_str(row.get("fvg_state")),
        "bos": _as_str(row.get("bos_state")),
        "choch": _as_str(row.get("choch_state")),
        "displacement": _score_from(row, "displacement_score", "displacement"),
        "momentum": _score_from(row, "momentum_score", "momentum"),
        "timing": _score_from(row, "timing_score", "timing", "timing_retest"),
        "volatility": _score_from(row, "volatility_score", "volatility"),
        "mtf": _score_from(row, "mtf_score", "mtf", "ltf_mtf_alignment"),
        "pa": _score_from(row, "price_action_score", "price_action", "pa"),
        "consensus": _score_from(row, "consensus_score", "consensus"),
        "rr": _as_float(row.get("rr") or row.get("expected_rr")),
        "session": _as_str(row.get("market_session")),
        "regime": _as_str(row.get("market_regime")),
        "spread": _as_float(row.get("spread")),
        "data_freshness": _as_float(row.get("data_age") or row.get("data_age_seconds")),
        "bid": _as_float(row.get("bid") or row.get("entry") or row.get("entry_price")),
        "ask": _as_float(row.get("ask")),
        "high": _as_float(row.get("high") or row.get("bar_high")),
        "low": _as_float(row.get("low") or row.get("bar_low")),
        "mid": _as_float(row.get("mid")),
        "sl": _as_float(row.get("sl") or row.get("stop") or row.get("stop_loss")),
        "tp": _as_float(row.get("tp") or row.get("target") or row.get("take_profit")),
        "cycle_id": _as_str(row.get("cycle_id")),
        "snapshot_id": _as_str(row.get("snapshot_id")),
        "signal_id": _as_str(row.get("signal_id")),
        "core_clears_thresholds": core_clears,
        "lookahead_fields": leaked,
        "not_a_ticket": True,
        "not_strategy_matched": True,
    }


def _lean(scan: dict[str, Any]) -> str | None:
    buy = scan.get("ltf_buy")
    sell = scan.get("ltf_sell")
    try:
        b = int(buy) if buy is not None else None
        s = int(sell) if sell is not None else None
    except (TypeError, ValueError):
        return None
    if b is None or s is None:
        return None
    if b > s:
        return "BUY"
    if s > b:
        return "SELL"
    return None


def _entry_price(scan: dict[str, Any], direction: str) -> float | None:
    if direction == "BUY":
        return _as_float(scan.get("ask") or scan.get("mid") or scan.get("bid"))
    return _as_float(scan.get("bid") or scan.get("mid") or scan.get("ask"))


def _qualify(spec: dict[str, Any], scan: dict[str, Any], cycle: dict[str, Any]) -> dict[str, Any]:
    present = candidate_present(spec, cycle)
    direction = _lean(scan)
    entry = _entry_price(scan, direction) if direction else None
    sl = _as_float(scan.get("sl"))
    tp = _as_float(scan.get("tp"))
    lifecycle = "OBSERVED"
    if present:
        lifecycle = "ELIGIBLE"
        if direction:
            lifecycle = "TRIGGERED"
            if entry is not None and sl is not None and tp is not None:
                lifecycle = "VIRTUAL_ENTRY"
    core_clears = bool(scan.get("core_clears_thresholds"))
    below = bool(present and not core_clears)
    return {
        "candidate_id": spec["candidate_id"],
        "candidate_name": spec["candidate_name"],
        "layer": "SHADOW_EXPANSION",
        "CORE": False,
        "SHADOW_EXPANSION": True,
        "WOULD_QUALIFY_AS_SHADOW": present,
        "would_submit_order": False,
        "ALLOW_LIVE_PROMOTION": False,
        "lifecycle": lifecycle,
        "present": present,
        "direction": direction,
        "virtual_entry": entry if lifecycle == "VIRTUAL_ENTRY" else None,
        "virtual_sl": sl if lifecycle == "VIRTUAL_ENTRY" else None,
        "virtual_tp": tp if lifecycle == "VIRTUAL_ENTRY" else None,
        "below_core_threshold": below,
        "below_core_label": BELOW_CORE_THRESHOLD if below else None,
        "core_clears_thresholds": core_clears,
        "SHADOW_VIRTUAL_TRADE": lifecycle == "VIRTUAL_ENTRY",
        "STRATEGY_MATCHED_LIVE_TRADE": False,
    }


def _new_virtual_trade(scan: dict[str, Any], qual: dict[str, Any]) -> dict[str, Any]:
    entry = qual["virtual_entry"]
    sl = qual["virtual_sl"]
    tp = qual["virtual_tp"]
    direction = qual["direction"]
    risk = abs(float(entry) - float(sl)) if entry is not None and sl is not None else None
    return {
        "record_kind": SHADOW_VIRTUAL_TRADE,
        "dataset": SHADOW_VIRTUAL_TRADE,
        "not_strategy_matched": True,
        "STRATEGY_MATCHED_LIVE_TRADE": False,
        "would_submit_order": False,
        "ALLOW_LIVE_PROMOTION": False,
        "mt5_ticket": None,
        "order_id": None,
        "deal_id": None,
        "shadow_event_id": (
            f"sh:{qual['candidate_id']}:{scan.get('timestamp')}:{scan.get('symbol')}"
        ),
        "candidate_id": qual["candidate_id"],
        "candidate_name": qual["candidate_name"],
        "lifecycle": "VIRTUAL_ENTRY",
        "timestamp": scan.get("timestamp"),
        "entry_time": scan.get("timestamp"),
        "symbol": scan.get("symbol"),
        "virtual_direction": direction,
        "virtual_entry": entry,
        "virtual_sl": sl,
        "virtual_tp": tp,
        "virtual_R": UNKNOWN,
        "virtual_pnl": UNKNOWN,
        "hold_time": UNKNOWN,
        "exit_reason": None,
        "exit_time": None,
        "exit_price": None,
        "MAE": 0.0,
        "MFE": 0.0,
        "risk": risk,
        "session": scan.get("session"),
        "regime": scan.get("regime"),
        "opportunity": scan.get("opportunity"),
        "edge": scan.get("edge"),
        "below_core_threshold": qual["below_core_threshold"],
        "lookahead_rejected": False,
        "open": True,
    }


def _excursions(trade: dict[str, Any], high: float | None, low: float | None) -> None:
    entry = _as_float(trade.get("virtual_entry"))
    risk = _as_float(trade.get("risk"))
    if entry is None or risk is None or risk <= 0:
        return
    direction = str(trade.get("virtual_direction") or "").upper()
    mae = float(trade.get("MAE") or 0.0)
    mfe = float(trade.get("MFE") or 0.0)
    if direction == "BUY":
        if low is not None:
            mae = min(mae, (low - entry) / risk)
        if high is not None:
            mfe = max(mfe, (high - entry) / risk)
    elif direction == "SELL":
        if high is not None:
            mae = min(mae, (entry - high) / risk)
        if low is not None:
            mfe = max(mfe, (entry - low) / risk)
    trade["MAE"] = round(mae, 6)
    trade["MFE"] = round(mfe, 6)


def _exit_hit(
    *,
    direction: str,
    sl: float | None,
    tp: float | None,
    high: float | None,
    low: float | None,
) -> str | None:
    if high is None and low is None:
        return None
    hi = high if high is not None else low
    lo = low if low is not None else high
    if hi is None or lo is None:
        return None
    if direction == "BUY":
        sl_hit = sl is not None and lo <= sl
        tp_hit = tp is not None and hi >= tp
    else:
        sl_hit = sl is not None and hi >= sl
        tp_hit = tp is not None and lo <= tp
    if sl_hit and tp_hit:
        return "SL"
    if sl_hit:
        return "SL"
    if tp_hit:
        return "TP"
    return None


def _close_virtual(trade: dict[str, Any], *, reason: str, bar_ts: str, price: float) -> None:
    entry = float(trade["virtual_entry"])
    risk = float(trade["risk"] or 0.0) or None
    direction = str(trade.get("virtual_direction") or "").upper()
    r_mult = UNKNOWN
    if risk and risk > 0:
        if direction == "BUY":
            r_mult = round((price - entry) / risk, 6)
        else:
            r_mult = round((entry - price) / risk, 6)
    entry_ts = _parse_ts(trade.get("entry_time"))
    exit_ts = _parse_ts(bar_ts)
    hold = UNKNOWN
    if entry_ts and exit_ts:
        hold = round((exit_ts - entry_ts).total_seconds(), 3)
    trade["lifecycle"] = "OUTCOME"
    trade["open"] = False
    trade["exit_reason"] = reason
    trade["exit_time"] = bar_ts
    trade["exit_price"] = price
    trade["virtual_R"] = r_mult
    trade["virtual_pnl"] = r_mult
    trade["R_multiple"] = r_mult
    trade["hold_time"] = hold
    trade["would_submit_order"] = False
    trade["mt5_ticket"] = None


def apply_future_bar(bar: dict[str, Any] | None) -> dict[str, Any]:
    """Advance open virtual trades using a print STRICTLY after entry time."""
    row = dict(bar or {})
    leaked = detect_lookahead_fields(row)
    if leaked:
        return {
            "applied": 0,
            "lookahead": True,
            "lookahead_fields": leaked,
            "status": "LOOKAHEAD_REJECTED",
            "would_submit_order": False,
        }
    bar_ts = _as_str(row.get("timestamp") or row.get("recorded_at")) or _now_iso()
    bar_dt = _parse_ts(bar_ts)
    high = _as_float(row.get("high") or row.get("ask") or row.get("bid"))
    low = _as_float(row.get("low") or row.get("bid") or row.get("ask"))
    applied = 0
    rejected = 0
    with _LOCK:
        _ensure_loaded()
        for trade in _VIRTUAL:
            if not trade.get("open"):
                continue
            entry_dt = _parse_ts(trade.get("entry_time"))
            if bar_dt is None or entry_dt is None or bar_dt <= entry_dt:
                # Same-timestamp or earlier prints are not future market.
                # Do not poison the open trade; just refuse this bar.
                rejected += 1
                continue
            trade["lifecycle"] = "VIRTUAL_MANAGEMENT"
            _excursions(trade, high, low)
            direction = str(trade.get("virtual_direction") or "").upper()
            hit = _exit_hit(
                direction=direction,
                sl=_as_float(trade.get("virtual_sl")),
                tp=_as_float(trade.get("virtual_tp")),
                high=high,
                low=low,
            )
            if not hit:
                continue
            if hit == "SL":
                price = float(trade["virtual_sl"])
            else:
                price = float(trade["virtual_tp"])
            trade["lifecycle"] = "VIRTUAL_EXIT"
            _close_virtual(trade, reason=hit, bar_ts=bar_ts, price=price)
            applied += 1
        if applied or rejected:
            _touch_locked()
    return {
        "applied": applied,
        "lookahead_rejected": rejected,
        "lookahead": rejected > 0 and applied == 0,
        "status": "OK" if rejected == 0 else "LOOKAHEAD_REJECTED",
        "would_submit_order": False,
        "ALLOW_LIVE_PROMOTION": False,
    }


def chronological_replay(
    scans: list[dict[str, Any]],
    bars: list[dict[str, Any]],
) -> dict[str, Any]:
    """Deterministic time-ordered replay. Refuses same-bar or earlier prints.

    Tests must isolate storage with reset_shadow_pipeline_for_tests first.
    This function never wipes production shadow files on its own.
    """
    ordered_scans = sorted(
        scans, key=lambda s: str(s.get("recorded_at") or s.get("timestamp") or "")
    )
    ordered_bars = sorted(
        bars, key=lambda b: str(b.get("timestamp") or b.get("recorded_at") or "")
    )
    for scan in ordered_scans:
        observe_live_scan(scan, advance_open=False)
    results = [apply_future_bar(bar) for bar in ordered_bars]
    lookahead = any(int(r.get("lookahead_rejected") or 0) > 0 for r in results)
    return {
        "scans": len(ordered_scans),
        "bars": len(ordered_bars),
        "results": results,
        "snapshot": shadow_dataset_snapshot(),
        "would_submit_order": False,
        "lookahead_free": not lookahead,
    }


def observe_live_scan(cycle: dict[str, Any] | None, *, advance_open: bool = True) -> dict[str, Any]:
    """Persist one live scan as SHADOW observations. Never a fill, never OMS/MT5."""
    raw = dict(cycle or {})
    scan = compact_shadow_scan(raw)
    qualifications = [_qualify(spec, scan, raw) for spec in CANDIDATE_SPECS]
    scan["qualifications"] = {
        q["candidate_id"]: {
            "present": q["present"],
            "lifecycle": q["lifecycle"],
            "below_core_threshold": q["below_core_threshold"],
            "WOULD_QUALIFY_AS_SHADOW": q["WOULD_QUALIFY_AS_SHADOW"],
        }
        for q in qualifications
    }
    opened = 0
    with _LOCK:
        _ensure_loaded()
        _SCANS.append(scan)
        if len(_SCANS) > _MAX_SCANS:
            del _SCANS[: len(_SCANS) - _MAX_SCANS]
        for qual in qualifications:
            if qual["lifecycle"] != "VIRTUAL_ENTRY":
                continue
            event_id = f"sh:{qual['candidate_id']}:{scan.get('timestamp')}:{scan.get('symbol')}"
            exists = any(v.get("shadow_event_id") == event_id for v in _VIRTUAL)
            if exists:
                continue
            _VIRTUAL.append(_new_virtual_trade(scan, qual))
            opened += 1
            if len(_VIRTUAL) > _MAX_VIRTUAL:
                del _VIRTUAL[: len(_VIRTUAL) - _MAX_VIRTUAL]
        _touch_locked()
    if advance_open and scan.get("timestamp"):
        apply_future_bar(
            {
                "timestamp": scan.get("timestamp"),
                "high": scan.get("high") or scan.get("ask") or scan.get("bid"),
                "low": scan.get("low") or scan.get("bid") or scan.get("ask"),
                "bid": scan.get("bid"),
                "ask": scan.get("ask"),
            }
        )
    present = [q for q in qualifications if q["WOULD_QUALIFY_AS_SHADOW"]]
    return {
        "advisory_only": True,
        "SHADOW_ONLY": True,
        "would_submit_order": False,
        "ALLOW_LIVE_PROMOTION": False,
        "WOULD_SUBMIT_ORDER": False,
        "scan": scan,
        "candidates": qualifications,
        "present_families": [q["candidate_name"] for q in present],
        "virtual_entries_opened": opened,
        "not_a_ticket": True,
        "not_strategy_matched": True,
        "lookahead_fields": scan.get("lookahead_fields") or [],
    }


def _distribution(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        label = str(row.get(key) or "UNKNOWN")
        out[label] = int(out.get(label) or 0) + 1
    return out


def _candidate_performance(
    spec: dict[str, Any],
    scans: list[dict[str, Any]],
    virtual: list[dict[str, Any]],
) -> dict[str, Any]:
    name = str(spec["candidate_name"])
    cid = str(spec["candidate_id"])
    observations = len(scans)
    eligible = 0
    triggered = 0
    below = 0
    core_overlap = 0
    for scan in scans:
        flags = (scan.get("qualifications") or {}).get(cid) or {}
        present = bool(flags.get("WOULD_QUALIFY_AS_SHADOW") or flags.get("present"))
        lifecycle = str(flags.get("lifecycle") or "")
        if present:
            eligible += 1
        if lifecycle in {"TRIGGERED", "VIRTUAL_ENTRY", "VIRTUAL_MANAGEMENT", "VIRTUAL_EXIT", "OUTCOME"}:
            triggered += 1
        if flags.get("below_core_threshold"):
            below += 1
        if present and scan.get("core_clears_thresholds"):
            core_overlap += 1
    trades = [
        t
        for t in virtual
        if t.get("candidate_id") == cid or t.get("candidate_name") == name
    ]
    completed = [t for t in trades if not t.get("open") and t.get("lifecycle") == "OUTCOME"]
    metrics = _metrics(
        [
            {
                **t,
                "direction": t.get("virtual_direction"),
                "R_multiple": t.get("virtual_R"),
                "session": t.get("session"),
                "market_session": t.get("session"),
                "market_regime": t.get("regime"),
            }
            for t in completed
        ]
    )
    n = len(completed)
    status = sample_status(n)
    wins = sum(1 for t in completed if _as_float(t.get("virtual_R")) is not None and float(t["virtual_R"]) > 0)
    return {
        "candidate_id": cid,
        "candidate_name": name,
        "layer": "SHADOW_EXPANSION",
        "CORE": False,
        "SHADOW_EXPANSION": True,
        "WOULD_QUALIFY_AS_SHADOW": eligible > 0,
        "would_submit_order": False,
        "ALLOW_LIVE_PROMOTION": False,
        "observations": observations,
        "eligible": eligible,
        "triggered": triggered,
        "completed": n,
        "wins": wins,
        "losses": n - wins,
        "win_rate": metrics.get("WIN_RATE"),
        "win_rate_display": format_win_rate(metrics.get("WIN_RATE"), n, status=status),
        "average_R": metrics.get("AVERAGE_R"),
        "expectancy": metrics.get("EXPECTANCY"),
        "profit_factor": metrics.get("PROFIT_FACTOR"),
        "max_drawdown": metrics.get("MAX_DRAWDOWN"),
        "consecutive_losses": metrics.get("MAX_CONSECUTIVE_LOSSES"),
        "MAE": metrics.get("MAE"),
        "MFE": metrics.get("MFE"),
        "average_hold_time": metrics.get("AVERAGE_HOLD_TIME"),
        "session_distribution": _distribution(completed, "session"),
        "regime_distribution": _distribution(completed, "regime"),
        "opportunity_distribution": _distribution(completed, "opportunity"),
        "edge_distribution": _distribution(completed, "edge"),
        "sample_size": n,
        "sample_status": status,
        "below_core_threshold_n": below,
        "overlap_with_core": core_overlap,
        "unique_vs_core": max(eligible - core_overlap, 0),
        "below_core_label": BELOW_CORE_THRESHOLD if below > 0 else None,
        "classification": INSUFFICIENT_SAMPLE if n < 20 else metrics.get("status"),
    }


def shadow_dataset_snapshot() -> dict[str, Any]:
    with _LOCK:
        _ensure_loaded()
        scans = list(_SCANS)
        virtual = list(_VIRTUAL)
    completed = [t for t in virtual if not t.get("open") and t.get("lifecycle") == "OUTCOME"]
    open_virtual = [t for t in virtual if t.get("open")]
    candidates = [_candidate_performance(spec, scans, virtual) for spec in CANDIDATE_SPECS]
    core_n = sum(1 for s in scans if s.get("core_clears_thresholds"))
    expansion_n = 0
    overlap_n = 0
    for scan in scans:
        flags = scan.get("qualifications") if isinstance(scan.get("qualifications"), dict) else {}
        any_shadow = any(
            bool((row or {}).get("WOULD_QUALIFY_AS_SHADOW") or (row or {}).get("present"))
            for row in flags.values()
        )
        if any_shadow:
            expansion_n += 1
            if scan.get("core_clears_thresholds"):
                overlap_n += 1
    unique_n = max(expansion_n - overlap_n, 0)
    split = walk_forward_split(
        [
            {
                **t,
                "exit_time": t.get("exit_time"),
                "entry_time": t.get("entry_time"),
                "R_multiple": t.get("virtual_R"),
                "direction": t.get("virtual_direction"),
            }
            for t in completed
        ]
    )
    train_m = _metrics(split.get("train") or [])
    val_m = _metrics(split.get("validation") or [])
    oos_m = _metrics(split.get("out_of_sample") or [])
    sessions = {
        name: _metrics([t for t in completed if str(t.get("session") or "").lower() == name])
        for name in CANONICAL_SESSIONS
    }
    regimes = {
        name: _metrics(
            [t for t in completed if str(t.get("regime") or "").upper() == name]
        )
        for name in CANONICAL_REGIMES
    }
    n_completed = len(completed)
    return {
        "advisory_only": True,
        "dataset": "SHADOW",
        "SHADOW_VIRTUAL_TRADE": SHADOW_VIRTUAL_TRADE,
        "STRATEGY_MATCHED_LIVE_TRADE": STRATEGY_MATCHED_LIVE_TRADE,
        "never_mixes_live_and_shadow": True,
        "would_submit_order": False,
        "ALLOW_LIVE_PROMOTION": False,
        "observations": len(scans),
        "virtual_open": len(open_virtual),
        "virtual_completed": n_completed,
        "sample_status": sample_status(n_completed),
        "candidates": candidates,
        "core_vs_expansion": {
            "CORE": {
                "layer": "CORE",
                "threshold_clearing_scans": core_n,
                "opportunity": OPP_THRESHOLD,
                "edge": EDGE_MARGIN,
                "n": core_n,
                "sample_status": sample_status(core_n),
            },
            "SHADOW_EXPANSION": {
                "layer": "SHADOW_EXPANSION",
                "eligible_scans": expansion_n,
                "n": expansion_n,
                "sample_status": sample_status(expansion_n),
            },
            "overlap": overlap_n,
            "unique_expansion": unique_n,
            "additional_opportunities": unique_n,
            "never_merged": True,
            "more_signals_is_not_success": True,
        },
        "session_analysis": sessions,
        "regime_analysis": regimes,
        "walk_forward": {
            "status": split.get("status"),
            "lookahead": split.get("lookahead"),
            "train": train_m,
            "validation": val_m,
            "out_of_sample": oos_m,
            "n": n_completed,
        },
        "oos": {
            "status": split.get("status") if n_completed < 20 else oos_m.get("status"),
            "expectancy": oos_m.get("EXPECTANCY"),
            "n": len(split.get("out_of_sample") or []),
        },
        "verdict": _shadow_verdict(n_completed, candidates),
        "disclaimer": "Historical data does not guarantee future profitability.",
    }


def _shadow_verdict(n: int, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    if n <= 0:
        return {
            "code": "NO_SAFE_EXPANSION_PROVEN",
            "text": "NO SAFE EXPANSION PROVEN — CONTINUE COLLECTING DATA",
            "n": n,
        }
    promising = [
        c
        for c in candidates
        if c.get("completed", 0) >= 20
        and c.get("expectancy") not in {None, UNKNOWN}
        and _as_float(c.get("expectancy")) is not None
        and float(c["expectancy"]) > 0
    ]
    if n < 10:
        return {
            "code": "SHADOW_CANDIDATE_DETECTED",
            "text": "SHADOW CANDIDATE DETECTED — INSUFFICIENT SAMPLE",
            "n": n,
        }
    if promising and n < 50:
        return {
            "code": "PROMISING_NEED_OOS",
            "text": "SHADOW CANDIDATE HAS PROMISING EXPECTANCY — NEED OOS VALIDATION",
            "n": n,
        }
    if promising and n >= 50:
        return {
            "code": "PROMOTION_CANDIDATE",
            "text": "PROMOTION CANDIDATE — HUMAN REVIEW REQUIRED",
            "n": n,
        }
    return {
        "code": "NO_SAFE_EXPANSION_PROVEN",
        "text": "NO SAFE EXPANSION PROVEN — CONTINUE COLLECTING DATA",
        "n": n,
    }
