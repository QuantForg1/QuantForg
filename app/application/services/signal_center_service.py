"""Signal Center — LIVE signal projection from existing AI scan / diagnostics.

Read-only. Never fabricates signals. Never bypasses Trading Core.
Uses ``get_last_multi_asset_scan`` and strategy diagnostics only.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.application.services.institutional_multi_asset_scanner import (
    get_last_multi_asset_scan,
)
from app.application.services.strategy_diagnostics import get_strategy_diagnostics_store
from app.application.services.symbol_management_service import (
    enabled_symbols_ordered,
    load_preferences,
)
from app.domain.institutional_trading.session_filter import classify_session_utc
from core.logging import get_logger

logger = get_logger(__name__)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _session() -> str:
    try:
        return classify_session_utc(datetime.now(UTC)).value
    except Exception:
        return "unknown"


def _signal_badge(
    *,
    direction: str,
    quality: int,
    confidence: int,
    reject: bool,
) -> str:
    if reject or direction in {"", "NONE", "NO_TRADE", "WAIT"}:
        if direction == "WAIT":
            return "WAIT"
        return "No Trade"
    d = direction.upper()
    strength = min(quality, confidence)
    if d == "BUY":
        if strength >= 90:
            return "STRONG BUY"
        if strength >= 80:
            return "BUY"
        if strength >= 70:
            return "WEAK BUY"
        return "WAIT"
    if d == "SELL":
        if strength >= 90:
            return "STRONG SELL"
        if strength >= 80:
            return "SELL"
        if strength >= 70:
            return "WEAK SELL"
        return "WAIT"
    return "No Trade"


def _factors(score: dict[str, Any]) -> dict[str, Any]:
    f = score.get("factors")
    return f if isinstance(f, dict) else {}


def _block_code_from_reason(reason: str | None) -> str:
    low = str(reason or "").lower()
    if _is_min_lot_constraint(reason):
        return "MIN_LOT_CONSTRAINT"
    if "risk" in low:
        return "RISK_BLOCK"
    if "safety" in low or "kill" in low:
        return "SAFETY_BLOCK"
    if "portfolio" in low:
        return "PORTFOLIO_BLOCK"
    if "oms" in low:
        return "OMS_BLOCK"
    if "gateway" in low or "trade_mode" in low or "symbol unavailable" in low:
        return "SYMBOL_ROUTING_BLOCK"
    if "reconcil" in low or "unknown" in low:
        return "RECONCILIATION_REQUIRED"
    return "SAFETY_BLOCK"


def _is_min_lot_constraint(text: str | None) -> bool:
    low = str(text or "").lower()
    return any(
        token in low
        for token in (
            "min_lot_constraint",
            "below_min_lot",
            "below broker volume_min",
            "below broker minimum",
            "reduced size below min_lot",
            "below broker min",
        )
    )


def _execution_classification(
    *,
    direction: str,
    reject: bool,
    reason: str | None,
    quality: int,
    confidence: int,
) -> dict[str, str | None]:
    """Map sizing blocks to Signal Center lifecycle labels.

    VALID_SIGNAL -> EXECUTION_BLOCKED -> MIN_LOT_CONSTRAINT when a real
    directional setup exists but broker min volume exceeds safe risk.
    """
    min_lot = _is_min_lot_constraint(reason)
    directional = direction in {"BUY", "SELL"}
    strong_enough = quality >= 70 and confidence >= 70
    if min_lot and (directional or strong_enough or reject):
        return {
            "signal_state": "VALID_SIGNAL",
            "execution_state": "EXECUTION_BLOCKED",
            "block_code": "MIN_LOT_CONSTRAINT",
            "decision": direction if directional else "EXECUTION_BLOCKED",
            "status": "MIN_LOT_CONSTRAINT",
        }
    if directional and reject:
        code = _block_code_from_reason(reason)
        return {
            "signal_state": "VALID_SIGNAL",
            "execution_state": "EXECUTION_BLOCKED",
            "block_code": code,
            "decision": direction,
            "status": code,
        }
    if reject or direction in {"", "NONE", "NO_TRADE"}:
        return {
            "signal_state": "NO_TRADE",
            "execution_state": None,
            "block_code": (
                "NO_DIRECTION"
                if direction in {"", "NONE", "NO_TRADE"}
                else None
            ),
            "decision": "NO_TRADE",
            "status": "NO_TRADE",
        }
    return {
        "signal_state": "VALID_SIGNAL",
        "execution_state": "ELIGIBLE",
        "block_code": None,
        "decision": direction,
        "status": direction,
    }


def _row_from_score(score: dict[str, Any], *, strategy: str | None = None) -> dict[str, Any]:
    factors = _factors(score)
    quality = int(score.get("trade_quality") or score.get("quality") or 0)
    confidence = int(score.get("ai_confidence") or score.get("confidence") or 0)
    reject = bool(score.get("reject"))
    direction = str(score.get("direction") or "NONE").upper()
    reason_early = (
        score.get("reject_reason")
        or score.get("reason")
        or score.get("summary")
        or score.get("blocking_gate")
    )
    # Min-lot blocks are execution constraints, not "missing signals".
    min_lot_block = _is_min_lot_constraint(str(reason_early or ""))
    # Keep BUY/SELL through later blockers. Relabel the block, not the direction.
    direction_out = direction if direction in {"BUY", "SELL"} else "NONE"
    badge = _signal_badge(
        direction=direction_out,
        quality=quality,
        confidence=confidence,
        reject=False if direction_out in {"BUY", "SELL"} else reject,
    )
    if (min_lot_block or reject) and direction_out in {"BUY", "SELL"}:
        badge = f"{direction_out} BLOCKED"
    momentum = int(
        score.get("momentum")
        or factors.get("momentum")
        or factors.get("momentum_score")
        or 0
    )
    structure = int(
        score.get("structure")
        or factors.get("structure")
        or factors.get("structure_score")
        or 0
    )
    trend = str(
        score.get("trend")
        or factors.get("trend")
        or factors.get("h1_bias")
        or score.get("mtf_alignment")
        or "—"
    )
    atr = score.get("atr") or factors.get("atr")
    spread = score.get("spread") or factors.get("spread")
    liquidity = score.get("liquidity") or factors.get("liquidity") or factors.get(
        "liquidity_sweep"
    )
    risk = score.get("risk") or factors.get("risk") or score.get("risk_pct")
    rr = score.get("rr") or score.get("reward_risk") or factors.get("rr")
    hold = score.get("expected_hold") or score.get("hold_minutes") or factors.get(
        "expected_hold"
    )
    price = score.get("price") or score.get("mid") or score.get("bid") or score.get("ask")
    reason = score.get("reject_reason") or score.get("reason") or score.get("summary")
    explanation = (
        score.get("ai_explanation")
        or score.get("explanation")
        or score.get("reasoning")
        or reason
    )
    exec_cls = _execution_classification(
        direction=direction if direction in {"BUY", "SELL"} else direction_out,
        reject=reject,
        reason=str(reason or reason_early or ""),
        quality=quality,
        confidence=confidence,
    )
    detail = {
        "structure": structure,
        "bos": factors.get("bos") or score.get("bos"),
        "choch": factors.get("choch") or score.get("choch"),
        "order_block": factors.get("order_block") or score.get("order_block"),
        "fvg": factors.get("fvg") or score.get("fvg"),
        "liquidity": liquidity,
        "trend": trend,
        "momentum": momentum,
        "atr": atr,
        "spread": spread,
        "risk": risk,
        "why_buy": score.get("why_buy") or factors.get("why_buy"),
        "why_sell": score.get("why_sell") or factors.get("why_sell"),
        "why_no_trade": reason if reject else score.get("why_no_trade"),
        "signal_state": exec_cls["signal_state"],
        "execution_state": exec_cls["execution_state"],
        "block_code": exec_cls["block_code"],
        "raw_factors": factors,
    }
    probability = (
        round((quality * 0.55 + confidence * 0.45), 1)
        if (not reject or min_lot_block)
        else 0.0
    )
    test_synthetic = bool(
        score.get("test_synthetic")
        or str(score.get("strategy") or "").upper() == "TEST_SYNTHETIC"
        or str(score.get("strategy_id") or "").upper() == "TEST_SYNTHETIC"
    )
    signal_id = score.get("signal_id")
    out_badge = f"TEST {badge}" if test_synthetic else badge
    return {
        "symbol": str(score.get("symbol") or "").upper(),
        "direction": direction_out,
        "badge": out_badge,
        "current_price": price,
        "confidence": confidence,
        "quality": quality,
        "momentum": momentum,
        "structure": structure,
        "trend": trend,
        "atr": atr,
        "spread": spread,
        "liquidity": liquidity,
        "risk": risk,
        "rr": rr,
        "expected_hold": hold,
        "time_generated": score.get("as_of") or score.get("scored_at") or _now_iso(),
        "session": score.get("session") or _session(),
        "strategy": strategy
        or score.get("strategy_id")
        or score.get("strategy")
        or "scalping",
        "probability": probability,
        "reasoning": str(reason or explanation or "")[:500] or None,
        "ai_explanation": str(explanation or reason or "")[:2000] or None,
        "reject": reject,
        "test_synthetic": test_synthetic,
        "signal_id": signal_id,
        "signal_state": exec_cls["signal_state"],
        "execution_state": exec_cls["execution_state"],
        "block_code": exec_cls["block_code"],
        "decision": exec_cls["decision"],
        "status": exec_cls["status"],
        "detail": detail,
        "gauges": {
            "confidence": confidence,
            "quality": quality,
            "momentum": momentum,
            "rr": float(rr) if isinstance(rr, (int, float)) else None,
        },
    }


def _scores_from_scan(scan: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in ("rows", "noc_rows", "ranked", "scores"):
        block = scan.get(key)
        if isinstance(block, list):
            for item in block:
                if isinstance(item, dict) and item.get("symbol"):
                    rows.append(item)
    # Dedupe by symbol keeping highest quality
    best: dict[str, dict[str, Any]] = {}
    for row in rows:
        sym = str(row.get("symbol") or "").upper()
        if not sym:
            continue
        q = int(row.get("trade_quality") or row.get("quality") or 0)
        prev = best.get(sym)
        if prev is None or q >= int(prev.get("trade_quality") or prev.get("quality") or 0):
            best[sym] = row
    return list(best.values())


def list_live_signals(
    *,
    q: str = "",
    direction: str | None = None,
    asset_class: str | None = None,
    strong_only: bool = False,
    high_confidence: bool = False,
    enabled_only: bool = True,
) -> dict[str, Any]:
    scan = get_last_multi_asset_scan() or {}
    prefs = load_preferences()
    enabled = set(enabled_symbols_ordered(prefs)) if enabled_only else set()
    # If operator has never saved prefs, show all scan symbols (backward compatible).
    manage_active = bool(prefs)

    scores = _scores_from_scan(scan)
    as_of = str(scan.get("as_of") or _now_iso())
    strategy = None
    try:
        best = scan.get("best") if isinstance(scan.get("best"), dict) else {}
        strategy = best.get("strategy_id") or best.get("strategy")
    except Exception:
        strategy = None

    from app.domain.institutional_trading.ai_scalping.asset_class import (
        desk_symbol_code,
    )

    def _enabled_match(sym: str) -> bool:
        """Desk-aware: prefs for XAUUSD also show catalogue XAUUSD_I rows."""
        if not enabled:
            return True
        if sym in enabled:
            return True
        desk = desk_symbol_code(sym)
        if desk and desk in enabled:
            return True
        return any(desk_symbol_code(e) == desk for e in enabled if desk)

    signals: list[dict[str, Any]] = []
    for score in scores:
        sym = str(score.get("symbol") or "").upper()
        if not sym:
            continue
        if manage_active and enabled_only and enabled and not _enabled_match(sym):
            continue
        score = dict(score)
        score.setdefault("as_of", as_of)
        score.setdefault("session", scan.get("session") or _session())
        row = _row_from_score(score, strategy=strategy)
        desk = desk_symbol_code(sym)
        pref = prefs.get(sym) or (prefs.get(desk) if desk else None) or {}
        row["asset_class"] = str(pref.get("asset_class") or "other")
        # Explicit empty-state for NO_TRADE so UI never looks "broken".
        # Preserve MIN_LOT_CONSTRAINT execution blocks (valid signal, blocked).
        if row.get("block_code") == "MIN_LOT_CONSTRAINT":
            row.setdefault("decision", "EXECUTION_BLOCKED")
            row.setdefault("status", "MIN_LOT_CONSTRAINT")
        elif not row.get("direction") or str(row.get("direction")).upper() in {
            "",
            "NONE",
            "NO_TRADE",
        }:
            row.setdefault("decision", "NO_TRADE")
            row.setdefault("status", "NO_TRADE")
        signals.append(row)

    # Enrich with latest strategy diagnostics when scan empty for a symbol.
    if not signals:
        try:
            snap = get_strategy_diagnostics_store().snapshot(limit=40)
            latest = snap.get("latest") if isinstance(snap, dict) else None
            if isinstance(latest, dict) and latest.get("symbol"):
                signals.append(
                    _row_from_score(
                        {
                            "symbol": latest.get("symbol"),
                            "direction": latest.get("decision_action")
                            or latest.get("action")
                            or "NONE",
                            "trade_quality": (latest.get("quality") or {}).get("score")
                            if isinstance(latest.get("quality"), dict)
                            else latest.get("quality"),
                            "ai_confidence": (latest.get("confluence") or {}).get("score")
                            if isinstance(latest.get("confluence"), dict)
                            else latest.get("confluence"),
                            "reject": str(latest.get("cycle_outcome") or "")
                            .upper()
                            .find("EXEC")
                            < 0,
                            "reason": (
                                (latest.get("rejection") or {}).get("primary_label")
                                if isinstance(latest.get("rejection"), dict)
                                else None
                            ),
                            "explanation": latest.get("explain"),
                            "as_of": latest.get("recorded_at") or as_of,
                        }
                    )
                )
        except Exception:
            logger.exception("signal_center_diagnostics_fallback_failed")

    qn = (q or "").strip().upper()
    if qn:
        signals = [s for s in signals if qn in s["symbol"]]
    if direction:
        d = direction.strip().upper()
        if d in {"BUY", "SELL", "NONE", "WAIT", "NO_TRADE", "NO TRADE"}:
            if d in {"NO_TRADE", "NO TRADE"}:
                signals = [s for s in signals if s["badge"] == "No Trade"]
            elif d == "WAIT":
                signals = [s for s in signals if s["badge"] == "WAIT"]
            else:
                signals = [s for s in signals if s["direction"] == d]
    if asset_class:
        ac = asset_class.strip().lower()
        if ac not in {"all", "*"}:
            signals = [s for s in signals if s.get("asset_class") == ac]
    if strong_only:
        signals = [
            s
            for s in signals
            if s["badge"] in {"STRONG BUY", "STRONG SELL", "BUY", "SELL"}
        ]
    if high_confidence:
        signals = [s for s in signals if int(s.get("confidence") or 0) >= 80]

    signals.sort(
        key=lambda s: (
            0 if s["direction"] in {"BUY", "SELL"} else 1,
            -int(s.get("quality") or 0),
            -int(s.get("confidence") or 0),
            s["symbol"],
        )
    )

    buy_n = sum(1 for s in signals if s["direction"] == "BUY")
    sell_n = sum(1 for s in signals if s["direction"] == "SELL")
    wait_n = sum(1 for s in signals if s["badge"] == "WAIT")
    none_n = sum(1 for s in signals if s["badge"] == "No Trade")
    confs = [int(s["confidence"]) for s in signals if s.get("confidence") is not None]
    quals = [int(s["quality"]) for s in signals if s.get("quality") is not None]
    all_prefs = load_preferences()
    test_synthetic = bool(scan.get("test_synthetic")) or str(
        scan.get("source") or ""
    ).upper() == "TEST_SYNTHETIC"
    return {
        "as_of": as_of,
        "session": _session(),
        "source": "TEST_SYNTHETIC" if test_synthetic else "live_multi_asset_scan",
        "fabricated": bool(test_synthetic),
        "test_synthetic": bool(test_synthetic),
        "signal_id": scan.get("signal_id"),
        "scan_note": scan.get("note"),
        "universe_size": len(scan.get("universe") or []),
        "dashboard": {
            "total_symbols": len(scan.get("universe") or []) or len(signals),
            "enabled_symbols": len(enabled)
            if manage_active
            else len(scan.get("universe") or []),
            "buy_signals": buy_n,
            "sell_signals": sell_n,
            "wait": wait_n,
            "no_trade": none_n,
            "average_confidence": round(sum(confs) / len(confs), 1) if confs else None,
            "average_quality": round(sum(quals) / len(quals), 1) if quals else None,
            "managed_prefs": len(all_prefs),
        },
        "count": len(signals),
        "items": signals,
    }


def get_signal(symbol: str) -> dict[str, Any] | None:
    code = (symbol or "").strip().upper()
    if not code:
        return None
    payload = list_live_signals(q=code, enabled_only=False)
    for item in payload.get("items") or []:
        if item.get("symbol") == code:
            return item
    return None
