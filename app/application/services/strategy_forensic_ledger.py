"""Deterministic strategy forensic ledger — observability only.

Persists compact signal / submission / close rows so future eligible
executions can be joined without guessing. Never mutates Strategy, Risk,
Safety, Optimizer, OMS, or MT5. Never manufactures fills or tickets.

Join rule: a broker deal is STRATEGY_MATCHED only when a stored submission
carries the same MT5 ticket AND at least one of signal_id / decision_hash /
request_id matches the stored signal. Time-window joins are forbidden.
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

ADVISORY_ONLY = True
UNMATCHED = "UNMATCHED_BROKER_ACTIVITY"
STRATEGY_MATCHED = "STRATEGY_MATCHED"
JOIN_FIELDS = ("signal_id", "decision_hash", "request_id")
IMMUTABLE_SUBMISSION_FIELDS = (
    "signal_id",
    "decision_hash",
    "request_id",
    "ticket",
    "setup_features",
    "decision_snapshot",
)
IMMUTABLE_CLOSE_FIELDS = (
    "signal_id",
    "decision_hash",
    "request_id",
    "ticket",
    "decision_snapshot",
    "entry",
    "sl",
    "tp",
    "direction",
)

_MAX_SIGNALS = 80_000
_MAX_SUBMISSIONS = 20_000
_MAX_CLOSES = 20_000
_PERSIST_EVERY = 10

_LOCK = threading.Lock()
_SIGNALS: list[dict[str, Any]] = []
_SUBMISSIONS: list[dict[str, Any]] = []
_CLOSES: list[dict[str, Any]] = []
_DIRTY = 0
_ROOT: Path | None = None
_LOADED = False


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _ticket(value: Any) -> int | None:
    n = _as_int(value)
    if n is None or n <= 0:
        return None
    return n


def _data_root() -> Path:
    global _ROOT
    if _ROOT is not None:
        return _ROOT
    try:
        from core.config.settings import get_settings

        base = Path(getattr(get_settings(), "data_dir", None) or "data")
    except Exception:
        base = Path("data")
    _ROOT = base / "strategy_forensics"
    return _ROOT


def reset_forensic_ledger_for_tests(root: Path | None = None) -> None:
    """Isolate ledger files for unit tests."""
    global _SIGNALS, _SUBMISSIONS, _CLOSES, _DIRTY, _ROOT, _LOADED
    with _LOCK:
        _SIGNALS = []
        _SUBMISSIONS = []
        _CLOSES = []
        _DIRTY = 0
        _ROOT = root
        _LOADED = True
        if root is not None:
            root.mkdir(parents=True, exist_ok=True)


def _merge_immutable(
    kept: dict[str, Any],
    incoming: dict[str, Any],
    frozen: tuple[str, ...],
) -> dict[str, Any]:
    """Fill missing observational fields only. Never rewrite identity snapshots."""
    merged = dict(kept)
    for key, value in incoming.items():
        if key in frozen and merged.get(key) not in (None, "", [], {}):
            continue
        if merged.get(key) in (None, "", [], {}) and value not in (None, "", [], {}):
            merged[key] = value
    return merged


def _score_from(cycle: dict[str, Any], *names: str) -> int | None:
    breakdown = cycle.get("score_breakdown")
    audit = cycle.get("opportunity_audit")
    for name in names:
        if name in cycle and cycle.get(name) not in (None, ""):
            n = _as_int(cycle.get(name))
            if n is not None:
                return n
        if isinstance(breakdown, dict) and breakdown.get(name) not in (None, ""):
            n = _as_int(breakdown.get(name))
            if n is not None:
                return n
        if isinstance(audit, dict):
            raw = audit.get(name)
            if isinstance(raw, dict):
                n = _as_int(raw.get("score") or raw.get("value") or raw.get("x"))
            else:
                n = _as_int(raw)
            if n is not None:
                return n
    return None


def compact_signal_row(cycle: dict[str, Any] | None) -> dict[str, Any]:
    """Project a diagnostics cycle into the forensic signal contract."""
    row = dict(cycle or {})
    signal_id = _as_str(row.get("signal_id") or row.get("candidate_signal_id"))
    scan_as_of = _as_str(row.get("scan_as_of") or row.get("as_of") or row.get("tick_time"))
    symbol = _as_str(row.get("symbol")) or "XAUUSD_i"
    observation_id = signal_id or (
        f"obs:{scan_as_of or row.get('recorded_at') or _now_iso()}:{symbol}"
    )
    handoff = row.get("execution_handoff") if isinstance(row.get("execution_handoff"), dict) else {}
    ticket = _ticket(
        row.get("mt5_ticket")
        or row.get("ticket")
        or handoff.get("mt5_ticket")
    )
    canonical = _as_str(row.get("canonical_symbol"))
    broker_symbol = _as_str(row.get("broker_symbol")) or symbol
    asset_class = _as_str(row.get("asset_class"))
    try:
        from app.domain.market_universe.classification import classify_instrument
        from app.domain.market_universe.identity import canonical_desk

        canonical = canonical or canonical_desk(symbol)
        asset_class = asset_class or classify_instrument(symbol).asset_class
    except Exception:
        if not canonical:
            text = (symbol or "").strip().upper()
            canonical = text[:-2] if text.endswith("_I") and len(text) > 3 else text
        asset_class = asset_class or None
    return {
        "record_kind": "signal",
        "advisory_only": True,
        "mutates_engines": False,
        "observation_id": observation_id,
        "signal_id": signal_id,
        "decision_hash": _as_str(row.get("decision_hash")),
        "request_id": _as_str(row.get("request_id") or row.get("trace_id")),
        "cycle_id": _as_str(row.get("cycle_id")),
        "snapshot_id": _as_str(row.get("snapshot_id")),
        "timestamp_utc": _as_str(row.get("recorded_at")) or _now_iso(),
        "symbol": symbol,
        "canonical_symbol": canonical,
        "broker_symbol": broker_symbol,
        "asset_class": asset_class,
        "direction": _as_str(row.get("candidate") or row.get("decision_action")),
        "timeframe": _as_str(row.get("timeframe") or row.get("atr_timeframe")) or "M5",
        "market_session": _as_str(row.get("market_session")),
        "market_regime": _as_str(
            row.get("market_regime")
            or (
                (row.get("trend") or {}).get("market_regime")
                if isinstance(row.get("trend"), dict)
                else None
            )
        ),
        "market_data_timestamp": scan_as_of,
        "data_age": _as_float(row.get("data_age") or row.get("data_age_seconds")),
        "buy_score": _as_int(row.get("buy_score") or row.get("bullish_score")),
        "sell_score": _as_int(row.get("sell_score") or row.get("bearish_score")),
        "ltf_buy": _as_int(row.get("ltf_buy_score") or row.get("ltf_buy")),
        "ltf_sell": _as_int(row.get("ltf_sell_score") or row.get("ltf_sell")),
        "directional_edge": _as_int(row.get("directional_edge")),
        "opportunity_score": _as_int(row.get("opportunity_score")),
        "structure_score": _score_from(row, "structure_score", "structure"),
        "liquidity_score": _score_from(row, "liquidity_score", "liquidity"),
        "zone_score": _score_from(row, "zone_score", "zone"),
        "displacement_score": _score_from(row, "displacement_score", "displacement"),
        "timing_score": _score_from(row, "timing_score", "timing", "timing_retest"),
        "momentum_score": _score_from(row, "momentum_score", "momentum"),
        "mtf_score": _score_from(row, "mtf_score", "mtf", "ltf_mtf_alignment"),
        "consensus_score": _score_from(row, "consensus_score", "consensus"),
        "volatility_score": _score_from(row, "volatility_score", "volatility"),
        "regime_score": _score_from(row, "regime_score", "regime"),
        "price_action_score": _score_from(row, "price_action_score", "price_action", "pa"),
        "rr": _as_float(row.get("rr") or row.get("expected_rr") or _score_from(row, "rr")),
        "ob_state": _as_str(row.get("ob_state") or row.get("order_block_state")),
        "fvg_state": _as_str(row.get("fvg_state")),
        "bos_state": _as_str(row.get("bos_state")),
        "choch_state": _as_str(row.get("choch_state")),
        "setup_state": _as_str(row.get("setup_state")),
        "sniper_state": _as_str(row.get("sniper_state") or row.get("sniper")),
        "first_authoritative_blocker": _as_str(row.get("first_authoritative_blocker")),
        "blocker_source": _as_str(row.get("blocker_source")),
        "buy_families": list(row.get("buy_families") or []),
        "sell_families": list(row.get("sell_families") or []),
        "forwarded_to_oms": bool(row.get("forwarded_to_oms")),
        "mt5_ticket": ticket,
        "decision_action": _as_str(row.get("decision_action")),
        "order_id": _as_int(row.get("order_id") or row.get("order")),
        "deal_id": _as_int(row.get("deal_id")),
        "immutable": True,
        "decision_snapshot": {
            "opportunity_score": _as_int(row.get("opportunity_score")),
            "directional_edge": _as_int(row.get("directional_edge")),
            "buy_score": _as_int(row.get("buy_score") or row.get("bullish_score")),
            "sell_score": _as_int(row.get("sell_score") or row.get("bearish_score")),
            "ltf_buy": _as_int(row.get("ltf_buy_score") or row.get("ltf_buy")),
            "ltf_sell": _as_int(row.get("ltf_sell_score") or row.get("ltf_sell")),
            "setup_state": _as_str(row.get("setup_state")),
            "buy_families": list(row.get("buy_families") or []),
            "sell_families": list(row.get("sell_families") or []),
            "structure_score": _score_from(row, "structure_score", "structure"),
            "liquidity_score": _score_from(row, "liquidity_score", "liquidity"),
            "zone_score": _score_from(row, "zone_score", "zone"),
            "ob_state": _as_str(row.get("ob_state") or row.get("order_block_state")),
            "fvg_state": _as_str(row.get("fvg_state")),
            "displacement_score": _score_from(row, "displacement_score", "displacement"),
            "momentum_score": _score_from(row, "momentum_score", "momentum"),
            "timing_score": _score_from(row, "timing_score", "timing", "timing_retest"),
            "volatility_score": _score_from(row, "volatility_score", "volatility"),
            "rr": _as_float(row.get("rr") or row.get("expected_rr")),
            "session": _as_str(row.get("market_session")),
            "regime": _as_str(row.get("market_regime")),
            "spread": _as_float(row.get("spread")),
            "margin": _as_float(row.get("margin") or row.get("margin_level")),
            "entry": _as_float(row.get("entry") or row.get("entry_price") or row.get("bid")),
            "sl": _as_float(row.get("sl") or row.get("stop") or row.get("stop_loss")),
            "tp": _as_float(row.get("tp") or row.get("target") or row.get("take_profit")),
            "timestamp": _as_str(row.get("recorded_at") or row.get("scan_as_of")) or _now_iso(),
            "bos_state": _as_str(row.get("bos_state")),
            "choch_state": _as_str(row.get("choch_state")),
            "scan_as_of": _as_str(row.get("scan_as_of") or row.get("as_of")),
            "data_age": _as_float(row.get("data_age") or row.get("data_age_seconds")),
            "cycle_id": _as_str(row.get("cycle_id")),
            "snapshot_id": _as_str(row.get("snapshot_id")),
            "pa": _score_from(row, "price_action_score", "price_action", "pa"),
            "consensus": _score_from(row, "consensus_score", "consensus"),
            "mtf": _score_from(row, "mtf_score", "mtf", "ltf_mtf_alignment"),
        },
    }


def compact_submission_row(cycle: dict[str, Any] | None) -> dict[str, Any] | None:
    """Persist an OMS/gateway/MT5 submit only when a real ticket exists."""
    row = compact_signal_row(cycle)
    ticket = row.get("mt5_ticket")
    forwarded = bool(row.get("forwarded_to_oms"))
    if not forwarded or ticket is None:
        return None
    src = dict(cycle or {})
    handoff = src.get("execution_handoff") if isinstance(src.get("execution_handoff"), dict) else {}
    return {
        "record_kind": "submission",
        "advisory_only": True,
        "mutates_engines": False,
        "signal_id": row.get("signal_id"),
        "observation_id": row.get("observation_id"),
        "decision_hash": row.get("decision_hash"),
        "request_id": row.get("request_id"),
        "timestamp_utc": row.get("timestamp_utc"),
        "symbol": row.get("symbol"),
        "direction": row.get("direction"),
        "oms_request": src.get("oms_request") or handoff.get("oms_request"),
        "gateway_request": src.get("gateway_request") or handoff.get("gateway_request"),
        "mt5_request": src.get("mt5_request") or handoff.get("mt5_request"),
        "mt5_retcode": _as_int(src.get("mt5_retcode") or handoff.get("mt5_retcode")),
        "ticket": ticket,
        "entry_price": _as_float(src.get("entry_price") or src.get("entry") or src.get("price")),
        "requested_volume": _as_float(src.get("requested_volume") or src.get("volume")),
        "executed_volume": _as_float(src.get("executed_volume") or src.get("volume")),
        "sl": _as_float(src.get("sl") or src.get("stop") or src.get("stop_loss")),
        "tp": _as_float(src.get("tp") or src.get("target") or src.get("take_profit")),
        "spread": _as_float(src.get("spread")),
        "margin_level": _as_float(src.get("margin_level")),
        "equity": _as_float(
            src.get("equity")
            or (
                (src.get("sizing") or {}).get("account_balance")
                if isinstance(src.get("sizing"), dict)
                else None
            )
        ),
        "balance": _as_float(src.get("balance")),
        "setup_features": {
            "opportunity_score": row.get("opportunity_score"),
            "directional_edge": row.get("directional_edge"),
            "buy_score": row.get("buy_score"),
            "sell_score": row.get("sell_score"),
            "ltf_buy": row.get("ltf_buy"),
            "ltf_sell": row.get("ltf_sell"),
            "setup_state": row.get("setup_state"),
            "buy_families": row.get("buy_families"),
            "sell_families": row.get("sell_families"),
            "market_session": row.get("market_session"),
            "market_regime": row.get("market_regime"),
        },
        "decision_snapshot": dict(row.get("decision_snapshot") or {}),
        "order_id": _as_int(src.get("order_id") or src.get("order") or handoff.get("order_id")),
        "deal_id": _as_int(src.get("deal_id") or handoff.get("deal_id")),
        "immutable": True,
    }


def compact_close_row(cycle: dict[str, Any] | None) -> dict[str, Any] | None:
    """Persist a close only when a real ticket and exit evidence exist."""
    src = dict(cycle or {})
    ticket = _ticket(
        src.get("mt5_ticket")
        or src.get("ticket")
        or src.get("entry_ticket")
        or (
            (src.get("execution_handoff") or {}).get("mt5_ticket")
            if isinstance(src.get("execution_handoff"), dict)
            else None
        )
    )
    exit_px = _as_float(src.get("exit") or src.get("exit_price"))
    pnl = _as_float(src.get("net_pnl") if src.get("net_pnl") is not None else src.get("profit_loss"))
    if ticket is None or (exit_px is None and pnl is None):
        return None
    signal = compact_signal_row(src)
    return {
        "record_kind": "close",
        "advisory_only": True,
        "mutates_engines": False,
        "immutable": True,
        "signal_id": signal.get("signal_id"),
        "decision_hash": signal.get("decision_hash"),
        "request_id": signal.get("request_id"),
        "ticket": ticket,
        "order_id": _as_int(src.get("order_id") or src.get("order")),
        "deal_id": _as_int(src.get("deal_id") or src.get("deal")),
        "symbol": signal.get("symbol"),
        "direction": signal.get("direction"),
        "exit": exit_px,
        "exit_price": exit_px,
        "realized_pnl": pnl,
        "R": _as_float(src.get("R_multiple") or src.get("R") or src.get("risk_reward")),
        "holding_time": _as_float(src.get("holding_time") or src.get("holding_time_sec")),
        "exit_reason": _as_str(src.get("exit_reason") or src.get("comment")),
        "MAE": _as_float(src.get("MAE") or src.get("maximum_adverse_excursion")),
        "MFE": _as_float(src.get("MFE") or src.get("maximum_favorable_excursion")),
        "slippage": _as_float(src.get("slippage")),
        "commission": _as_float(src.get("commission")),
        "swap": _as_float(src.get("swap")),
        "excursion_statistics": {
            "MAE": _as_float(src.get("MAE") or src.get("maximum_adverse_excursion")),
            "MFE": _as_float(src.get("MFE") or src.get("maximum_favorable_excursion")),
        },
        "cycle_id": signal.get("cycle_id"),
        "snapshot_id": signal.get("snapshot_id"),
        "decision_snapshot": dict(signal.get("decision_snapshot") or {}),
        "timestamp_utc": _as_str(src.get("exit_time") or src.get("recorded_at")) or _now_iso(),
    }


def identity_overlap(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """True only when an explicit identity field matches on both sides."""
    for field in JOIN_FIELDS:
        a = _as_str(left.get(field))
        b = _as_str(right.get(field))
        if a and b and a == b:
            return True
    return False


def classify_closed_deal(
    deal: dict[str, Any],
    *,
    submissions: list[dict[str, Any]] | None = None,
    signals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Join a broker close to strategy only via ticket + identity. Never guess."""
    ticket = _ticket(
        deal.get("entry_ticket") or deal.get("ticket") or deal.get("order")
    )
    row = {
        "classification": UNMATCHED,
        "ticket": ticket,
        "signal_id": None,
        "decision_hash": None,
        "request_id": None,
        "join_method": None,
        "reason": "no_ticket" if ticket is None else "no_submission_for_ticket",
    }
    if ticket is None:
        return row
    matched_sub: dict[str, Any] | None = None
    for sub in submissions if submissions is not None else list_submissions():
        if _ticket(sub.get("ticket")) == ticket:
            matched_sub = sub
            break
    if matched_sub is None:
        return row
    signal: dict[str, Any] | None = None
    for sig in signals if signals is not None else list_signals():
        if identity_overlap(matched_sub, sig) or _ticket(sig.get("mt5_ticket")) == ticket:
            if identity_overlap(matched_sub, sig) or identity_overlap(deal, sig):
                signal = sig
                break
            if _ticket(sig.get("mt5_ticket")) == ticket and (
                identity_overlap(matched_sub, sig) or identity_overlap(matched_sub, deal)
            ):
                signal = sig
                break
    if signal is None and not identity_overlap(matched_sub, deal):
        # Submission ticket match is sufficient when the submission itself
        # already carries signal_id / decision_hash / request_id.
        if any(_as_str(matched_sub.get(f)) for f in JOIN_FIELDS):
            signal = matched_sub
        else:
            row["reason"] = "ticket_without_identity"
            return row
    ident = signal or matched_sub
    return {
        "classification": STRATEGY_MATCHED,
        "ticket": ticket,
        "signal_id": ident.get("signal_id"),
        "decision_hash": ident.get("decision_hash"),
        "request_id": ident.get("request_id"),
        "join_method": "ticket+identity",
        "reason": None,
        "submission": matched_sub,
        "signal": signal,
    }


def _ensure_loaded() -> None:
    global _LOADED
    if _LOADED:
        return
    load_ledger_from_disk()
    _LOADED = True


def persist_signal(cycle: dict[str, Any] | None) -> dict[str, Any]:
    _ensure_loaded()
    row = compact_signal_row(cycle)
    with _LOCK:
        _SIGNALS.append(row)
        if len(_SIGNALS) > _MAX_SIGNALS:
            del _SIGNALS[: len(_SIGNALS) - _MAX_SIGNALS]
        global _DIRTY
        _DIRTY += 1
        dirty = _DIRTY
    if dirty >= _PERSIST_EVERY:
        flush_ledger()
    submission = compact_submission_row(cycle)
    if submission is not None:
        persist_submission(submission)
    close = compact_close_row(cycle)
    if close is not None:
        persist_close(close)
    return row


def persist_submission(row: dict[str, Any]) -> dict[str, Any]:
    _ensure_loaded()
    ticket = _ticket(row.get("ticket"))
    if ticket is None:
        return row
    with _LOCK:
        existing_idx = next(
            (i for i, s in enumerate(_SUBMISSIONS) if _ticket(s.get("ticket")) == ticket),
            None,
        )
        if existing_idx is not None:
            _SUBMISSIONS[existing_idx] = _merge_immutable(
                dict(_SUBMISSIONS[existing_idx]), dict(row), IMMUTABLE_SUBMISSION_FIELDS
            )
            payload = dict(_SUBMISSIONS[existing_idx])
        else:
            _SUBMISSIONS.append(dict(row))
            if len(_SUBMISSIONS) > _MAX_SUBMISSIONS:
                del _SUBMISSIONS[: len(_SUBMISSIONS) - _MAX_SUBMISSIONS]
            payload = dict(row)
    _write_json("submissions.json", list_submissions())
    return payload


def persist_close(row: dict[str, Any]) -> dict[str, Any]:
    _ensure_loaded()
    payload = dict(row)
    payload.setdefault("record_kind", "close")
    payload.setdefault("advisory_only", True)
    payload.setdefault("immutable", True)
    ticket = _ticket(payload.get("ticket"))
    with _LOCK:
        if ticket is not None:
            existing_idx = next(
                (i for i, c in enumerate(_CLOSES) if _ticket(c.get("ticket")) == ticket),
                None,
            )
            if existing_idx is not None:
                _CLOSES[existing_idx] = _merge_immutable(
                    dict(_CLOSES[existing_idx]), payload, IMMUTABLE_CLOSE_FIELDS
                )
                stored = dict(_CLOSES[existing_idx])
                _write_json("closes.json", list(_CLOSES))
                return stored
        _CLOSES.append(payload)
        if len(_CLOSES) > _MAX_CLOSES:
            del _CLOSES[: len(_CLOSES) - _MAX_CLOSES]
    _write_json("closes.json", list_closes())
    return payload


def list_signals() -> list[dict[str, Any]]:
    _ensure_loaded()
    with _LOCK:
        return list(_SIGNALS)


def list_submissions() -> list[dict[str, Any]]:
    _ensure_loaded()
    with _LOCK:
        return list(_SUBMISSIONS)


def list_closes() -> list[dict[str, Any]]:
    _ensure_loaded()
    with _LOCK:
        return list(_CLOSES)


def _write_json(name: str, payload: Any) -> None:
    path = _data_root() / name
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, default=str), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        logger.exception("strategy_forensic_persist_failed", file=name)


def flush_ledger() -> None:
    global _DIRTY
    _write_json("signals.json", list_signals())
    _write_json("submissions.json", list_submissions())
    _write_json("closes.json", list_closes())
    with _LOCK:
        _DIRTY = 0


def load_ledger_from_disk() -> None:
    """Best-effort hydrate after process restart. Never invents rows."""
    global _SIGNALS, _SUBMISSIONS, _CLOSES
    root = _data_root()
    loaded: dict[str, list[dict[str, Any]]] = {
        "signals.json": [],
        "submissions.json": [],
        "closes.json": [],
    }
    for name in loaded:
        path = root / name
        if not path.is_file():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                loaded[name] = [r for r in raw if isinstance(r, dict)]
        except Exception:
            logger.exception("strategy_forensic_load_failed", file=name)
    with _LOCK:
        if loaded["signals.json"]:
            _SIGNALS = loaded["signals.json"][-_MAX_SIGNALS:]
        if loaded["submissions.json"]:
            _SUBMISSIONS = loaded["submissions.json"][-_MAX_SUBMISSIONS:]
        if loaded["closes.json"]:
            _CLOSES = loaded["closes.json"][-_MAX_CLOSES:]
