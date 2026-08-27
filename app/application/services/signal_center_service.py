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


_WAIT_REASON_LABELS: dict[str, str] = {
    "WAIT_NO_SNIPER_TRIGGER": "WAIT — no liquidity event or structure confirmation",
    "WAIT_NO_DIRECTIONAL_EDGE": "WAIT — no directional edge",
    "WAIT_NO_LIQUIDITY": "WAIT — no liquidity event",
    "NO_LIQUIDITY_EVENT": "WAIT — no liquidity event",
    "WAIT_NO_STRUCTURE": "WAIT — no structure confirmation",
    "NO_STRUCTURE_CONFIRMATION": "WAIT — no structure confirmation",
    "WAIT_NO_DISPLACEMENT": "WAIT — no displacement",
    "NO_DISPLACEMENT": "WAIT — no displacement",
    "WAIT_NO_MOMENTUM": "WAIT — no momentum",
    "NO_MOMENTUM": "WAIT — no momentum",
    "WAIT_NO_INVALIDATION": "WAIT — invalidation invalid",
    "INVALIDATION_INVALID": "WAIT — invalidation invalid",
    "WAIT_INSUFFICIENT_RR": "WAIT — RR too low",
    "RR_TOO_LOW": "WAIT — RR too low",
    "WAIT_CHASE": "WAIT — chase detected",
    "CHASE_DETECTED": "WAIT — chase detected",
    "WAIT_STALE_FVG": "WAIT — stale FVG",
    "WAIT_ABNORMAL_SPREAD": "WAIT — abnormal spread",
    "ABNORMAL_SPREAD": "WAIT — abnormal spread",
    "WAIT_CONFLICTING_BUY_SELL": "WAIT — BUY/SELL conflict",
    "WAIT_CONFLICT": "WAIT — BUY/SELL conflict",
    "BUY_SELL_CONFLICT": "WAIT — BUY/SELL conflict",
    "WAIT_NO_CLEAR_EDGE": "WAIT — no clear BUY/SELL edge",
    "WAIT_STALE_DATA": "WAIT — stale data",
    "STALE_DATA": "WAIT — stale data",
    "WAIT_SNIPER_INCOMPLETE": "WAIT — sniper setup incomplete",
    "SETUP_NOT_READY": "WAIT — opportunity score below threshold",
    "OPPORTUNITY_SCORE_BELOW_THRESHOLD": "WAIT — opportunity score below threshold",
}


def _block_code_from_reason(reason: str | None) -> str:
    wait_code = _wait_block_code(reason)
    if wait_code:
        return wait_code
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


def _wait_block_code(reason: str | None) -> str | None:
    upper = str(reason or "").upper()
    if not upper:
        return None
    for code in _WAIT_REASON_LABELS:
        if code in upper:
            return code
    if "NO CLEAR BUY/SELL" in upper or "BALANCED SCORES" in upper:
        return "WAIT_NO_DIRECTIONAL_EDGE"
    if "OPPORTUNITY_SCORE" in upper and "THRESHOLD" in upper:
        return "OPPORTUNITY_SCORE_BELOW_THRESHOLD"
    if upper.startswith("WAIT_") or " WAIT" in f" {upper}":
        token = upper.split(";")[0].split(":")[0].strip()
        return token or "WAIT"
    return None


def _is_strategy_wait(
    *,
    reason: str | None,
    signal_action: str | None,
    direction: str,
    reject: bool,
) -> bool:
    if _is_min_lot_constraint(reason):
        return False
    action = str(signal_action or "").upper()
    if action == "WAIT":
        return True
    if not reject:
        return False
    if _wait_block_code(reason):
        return True
    low = str(reason or "").lower()
    if any(
        token in low
        for token in ("risk", "safety", "kill", "portfolio", "oms", "gateway")
    ):
        return False
    return str(direction or "").upper() in {"BUY", "SELL"}


def _operator_signal_reason(
    *,
    signal_action: str,
    reason: str | None,
    sniper: dict[str, Any] | None,
) -> str:
    action = str(signal_action or "").upper()
    text = str(reason or "").strip()
    upper = text.upper()
    for code, label in _WAIT_REASON_LABELS.items():
        if code in upper:
            return label
    if "OPPORTUNITY_SCORE" in upper and "THRESHOLD" in upper:
        return "WAIT — opportunity score below threshold"
    sniper_reasons = []
    if isinstance(sniper, dict):
        raw = sniper.get("reasons")
        if isinstance(raw, (list, tuple)):
            sniper_reasons = [str(r) for r in raw if str(r).strip()]
    if action in {"BUY", "SELL"}:
        last = sniper_reasons[-1] if sniper_reasons else None
        if last:
            return f"{action} — {last}"
        return (
            "BUY — sniper setup confirmed"
            if action == "BUY"
            else "SELL — bearish liquidity sweep + BOS"
        )
    if action == "WAIT":
        if text:
            return text if text.upper().startswith("WAIT") else f"WAIT — {text}"
        if sniper_reasons:
            return str(sniper_reasons[-1])
        return "WAIT — setup not confirmed"
    return text or action or "NO_TRADE"


def _present(value: Any) -> bool:
    if value is None or value == "":
        return False
    if isinstance(value, (list, dict, tuple)) and len(value) == 0:
        return False
    return True


def _first_present(*values: Any) -> Any:
    for value in values:
        if _present(value):
            return value
    return None


def _is_min_lot_constraint(text: str | None) -> bool:
    low = str(text or "").lower()
    return any(
        token in low
        for token in (
            "min_lot_constraint",
            "min_lot_infeasible",
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
    signal_action: str | None = None,
) -> dict[str, str | None]:
    """Map sizing blocks to Signal Center lifecycle labels.

    VALID_SIGNAL -> EXECUTION_BLOCKED -> MIN_LOT_CONSTRAINT when a real
    directional setup exists but broker min volume exceeds safe risk.
    Strategy WAIT (sniper / opportunity) is not a Safety block.
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
    if _is_strategy_wait(
        reason=reason,
        signal_action=signal_action,
        direction=direction,
        reject=reject,
    ):
        code = _wait_block_code(reason) or "WAIT"
        return {
            "signal_state": "WAIT",
            "execution_state": None,
            "block_code": code,
            "decision": "WAIT",
            "status": code,
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
    sniper = score.get("sniper_entry") if isinstance(score.get("sniper_entry"), dict) else {}
    signal_action = str(
        score.get("signal_action")
        or (sniper.get("action") if isinstance(sniper, dict) else "")
        or ""
    ).upper()
    strategy_wait = _is_strategy_wait(
        reason=str(reason_early or ""),
        signal_action=signal_action,
        direction=direction,
        reject=reject,
    )
    if signal_action not in {"BUY", "SELL", "WAIT", "NO_TRADE"}:
        if min_lot_block and direction in {"BUY", "SELL"}:
            signal_action = direction
        elif strategy_wait:
            signal_action = "WAIT"
        elif direction in {"BUY", "SELL"} and not reject:
            signal_action = direction
        elif reject:
            signal_action = "NO_TRADE"
        else:
            signal_action = direction if direction in {"BUY", "SELL"} else "WAIT"
    # Keep BUY/SELL through execution blockers. Strategy WAIT is the operator signal.
    if min_lot_block and direction in {"BUY", "SELL"}:
        direction_out = direction
    elif strategy_wait:
        direction_out = "WAIT"
    else:
        direction_out = direction if direction in {"BUY", "SELL"} else "NONE"
    badge = _signal_badge(
        direction=direction_out,
        quality=quality,
        confidence=confidence,
        reject=False if direction_out in {"BUY", "SELL", "WAIT"} else reject,
    )
    if min_lot_block and direction in {"BUY", "SELL"}:
        badge = f"{direction} BLOCKED"
    elif strategy_wait:
        badge = "WAIT"
    elif reject and direction_out in {"BUY", "SELL"}:
        badge = f"{direction_out} BLOCKED"
    indicators = score.get("indicators") if isinstance(score.get("indicators"), dict) else {}
    momentum = int(
        score.get("momentum")
        or factors.get("momentum")
        or factors.get("momentum_score")
        or 0
    )
    structure = int(
        score.get("structure")
        or score.get("structure_score")
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
    atr = _first_present(
        score.get("atr"),
        factors.get("atr"),
        score.get("atr_pct"),
        indicators.get("atr"),
    )
    spread = _first_present(
        score.get("spread"),
        factors.get("spread"),
        score.get("spread_score"),
        indicators.get("spread"),
    )
    liquidity = _first_present(
        score.get("liquidity"),
        factors.get("liquidity"),
        factors.get("liquidity_sweep"),
    )
    risk = score.get("risk") or factors.get("risk") or score.get("risk_pct")
    rr = _first_present(
        score.get("rr"),
        score.get("expected_rr"),
        score.get("reward_risk"),
        factors.get("rr"),
    )
    hold = score.get("expected_hold") or score.get("expected_hold_time") or score.get(
        "hold_minutes"
    ) or factors.get("expected_hold")
    price = _first_present(
        score.get("price"),
        score.get("mid"),
        score.get("bid"),
        score.get("ask"),
        indicators.get("mid"),
        indicators.get("bid"),
    )
    reason = score.get("reject_reason") or score.get("reason") or score.get("summary")
    operator_reason = _operator_signal_reason(
        signal_action=direction_out if direction_out in {"BUY", "SELL", "WAIT"} else signal_action,
        reason=str(reason or reason_early or ""),
        sniper=sniper if isinstance(sniper, dict) else None,
    )
    explanation = (
        score.get("ai_explanation")
        or score.get("explanation")
        or score.get("reasoning")
        or operator_reason
        or reason
    )
    exec_cls = _execution_classification(
        direction=direction if direction in {"BUY", "SELL"} else direction_out,
        reject=reject,
        reason=str(reason or reason_early or ""),
        quality=quality,
        confidence=confidence,
        signal_action=signal_action,
    )
    buy_score = int(score.get("buy_score") or score.get("bullish_score") or 0)
    sell_score = int(score.get("sell_score") or score.get("bearish_score") or 0)
    opportunity_score = score.get("opportunity_score")
    confluence = score.get("confluence")
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
        "bid": score.get("bid"),
        "ask": score.get("ask"),
        "tick_time": score.get("tick_time") or score.get("server_time"),
        "quote_age_seconds": score.get("quote_age_seconds"),
        "bullish_score": buy_score,
        "bearish_score": sell_score,
        "opportunity_score": opportunity_score,
        "ai_confidence": confidence,
        "confluence": confluence,
        "bias": direction if direction in {"BUY", "SELL"} else None,
        "signal_action": signal_action,
        "sniper": sniper,
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
        "reasoning": str(operator_reason or reason or explanation or "")[:500] or None,
        "ai_explanation": str(explanation or operator_reason or reason or "")[:2000]
        or None,
        "reject": reject,
        "test_synthetic": test_synthetic,
        "signal_id": signal_id,
        "signal_state": exec_cls["signal_state"],
        "execution_state": exec_cls["execution_state"],
        "block_code": exec_cls["block_code"],
        "decision": exec_cls["decision"],
        "status": exec_cls["status"],
        "bullish_score": buy_score,
        "bearish_score": sell_score,
        "opportunity_score": opportunity_score,
        "opportunity_threshold": score.get("opportunity_threshold") or 70,
        "confluence": confluence,
        "first_blocker": exec_cls["block_code"]
        if (reject or direction_out in {"WAIT", "NO_TRADE"})
        else None,
        "pipeline": _pipeline_snapshot(
            decision=str(exec_cls["decision"] or direction_out),
            block_code=exec_cls["block_code"],
            sniper=sniper if isinstance(sniper, dict) else None,
            quote_age_seconds=score.get("quote_age_seconds"),
            tick_time=score.get("tick_time"),
            market_data_live=score.get("market_data_live"),
            buy_score=buy_score,
            sell_score=sell_score,
            opportunity_score=opportunity_score,
            opportunity_threshold=score.get("opportunity_threshold") or 70,
            order_status=score.get("order_status") or score.get("fill_status"),
            order_ticket=score.get("order_ticket") or score.get("ticket"),
            score_breakdown=score.get("score_breakdown")
            if isinstance(score.get("score_breakdown"), dict)
            else None,
            candidate=direction if direction in {"BUY", "SELL"} else "NONE",
            spread=spread,
            atr=atr,
            market_regime=score.get("market_regime") or factors.get("volatility"),
        ),
        "detail": detail,
        "gauges": {
            "confidence": confidence,
            "quality": quality,
            "momentum": momentum,
            "rr": float(rr) if isinstance(rr, (int, float)) else None,
        },
    }


def _pipeline_snapshot(
    *,
    decision: str,
    block_code: str | None,
    sniper: dict[str, Any] | None,
    quote_age_seconds: Any,
    tick_time: Any,
    market_data_live: Any,
    buy_score: int,
    sell_score: int,
    opportunity_score: Any,
    opportunity_threshold: Any,
    order_status: Any = None,
    order_ticket: Any = None,
    score_breakdown: dict[str, Any] | None = None,
    candidate: str = "NONE",
    spread: Any = None,
    atr: Any = None,
    market_regime: Any = None,
) -> dict[str, Any]:
    """Observe-only gate strip. Never invents Risk/Safety/OMS PASS on WAIT."""
    code = str(block_code or "").upper()
    action = str(decision or "").upper()
    execution_codes = {
        "RISK_BLOCK",
        "SAFETY_BLOCK",
        "OMS_BLOCK",
        "MIN_LOT_CONSTRAINT",
        "SYMBOL_ROUTING_BLOCK",
        "PORTFOLIO_BLOCK",
    }
    reached_risk = action in {"BUY", "SELL"} or code in execution_codes
    age: float | None
    try:
        age = float(quote_age_seconds) if quote_age_seconds is not None else None
    except (TypeError, ValueError):
        age = None
    if market_data_live is False:
        data = "STALE"
    elif age is None:
        data = "LIVE" if tick_time or market_data_live else "UNKNOWN"
    elif age > 120:
        data = "STALE"
    else:
        data = "LIVE"
    sniper_passed = bool(sniper and sniper.get("passed"))
    if sniper_passed:
        sniper_state = "READY"
    elif sniper:
        sniper_state = "WAIT"
    else:
        sniper_state = "NOT_RUN"
    not_reached = "NOT_REACHED"
    risk_state = not_reached
    safety_state = not_reached
    oms_state = not_reached
    if reached_risk:
        if code == "RISK_BLOCK":
            risk_state = "BLOCK"
        else:
            risk_state = "READY"
        if code == "SAFETY_BLOCK":
            safety_state = "BLOCK"
        elif code not in {"RISK_BLOCK", "MIN_LOT_CONSTRAINT"}:
            safety_state = "READY"
        if code == "OMS_BLOCK":
            oms_state = "BLOCK"
        elif action in {"BUY", "SELL"} and code not in execution_codes:
            oms_state = "READY"
    optimizer_state = not_reached
    if reached_risk and risk_state == "READY" and safety_state != "BLOCK":
        optimizer_state = "READY"
    fill = str(order_status or "").upper()
    execution_lifecycle = None
    if fill in {"FILLED", "PARTIAL", "PARTIALLY_FILLED"}:
        execution_lifecycle = "FILLED"
    elif order_ticket:
        execution_lifecycle = "ORDER_SENT"
    elif action in {"BUY", "SELL"} and sniper_passed and code not in execution_codes:
        execution_lifecycle = "EXECUTION_READY"
    broker_state = not_reached
    mt5_state = not_reached
    if execution_lifecycle == "FILLED":
        broker_state = "ACK"
        mt5_state = "FILLED"
    elif execution_lifecycle == "ORDER_SENT":
        broker_state = "SUBMITTED"
        mt5_state = "PENDING"
    cand = str(candidate or "NONE").upper()
    if cand not in {"BUY", "SELL"}:
        cand = "NONE"
    take = action in {"BUY", "SELL"} and sniper_passed and code not in execution_codes
    pillars = sniper.get("pillars") if isinstance(sniper, dict) else None
    return {
        "market": "OPEN" if market_data_live is not False else "UNKNOWN",
        "data": data,
        "data_age_seconds": age,
        "tick_time": tick_time,
        "market_data_valid": data == "LIVE",
        "buy_score": buy_score,
        "sell_score": sell_score,
        "candidate": cand,
        "opportunity_score": opportunity_score,
        "opportunity_threshold": opportunity_threshold,
        "score_breakdown": dict(score_breakdown or {}),
        "decision": action,
        "final_decision": "TAKE" if take else "WAIT",
        "first_blocker": code or None,
        "sniper": sniper_state,
        "risk": risk_state,
        "safety": safety_state,
        "optimizer": optimizer_state,
        "oms": oms_state,
        "broker": broker_state,
        "mt5": mt5_state,
        "execution_lifecycle": execution_lifecycle,
        "spread": spread,
        "atr": atr,
        "volatility_regime": market_regime,
        "chase_distance": (sniper or {}).get("chase_distance") if sniper else None,
        "fvg_age_bars": (sniper or {}).get("fvg_age_bars") if sniper else None,
        "bos": (
            bool(pillars.get("structure_confirmation"))
            if isinstance(pillars, dict)
            else None
        ),
        "liquidity_event": (
            bool(pillars.get("liquidity_event")) if isinstance(pillars, dict) else None
        ),
        "entry_zone": (
            bool(pillars.get("entry_zone")) if isinstance(pillars, dict) else None
        ),
        "not_chasing": (
            bool(pillars.get("not_chasing")) if isinstance(pillars, dict) else None
        ),
    }


def _merge_score_row(prev: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(prev)
    for key, value in incoming.items():
        if not _present(value):
            continue
        if not _present(merged.get(key)):
            merged[key] = value
            continue
        if key in {"trade_quality", "quality", "ai_confidence", "confidence"}:
            try:
                if int(value) >= int(merged.get(key) or 0):
                    merged[key] = value
            except (TypeError, ValueError):
                merged[key] = value
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            nested = dict(merged[key])
            nested.update({k: v for k, v in value.items() if _present(v)})
            merged[key] = nested
            continue
        if isinstance(value, list) and isinstance(merged.get(key), list):
            if len(value) >= len(merged[key]):
                merged[key] = value
            continue
        merged[key] = value
    return merged


def _scores_from_scan(scan: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    # Slim NOC rows first; richer portfolio/score rows overlay missing fields.
    for key in ("noc_rows", "ranked", "rows", "scores", "opportunity_ranked"):
        block = scan.get(key)
        if isinstance(block, list):
            for item in block:
                if isinstance(item, dict) and item.get("symbol"):
                    rows.append(item)
    best: dict[str, dict[str, Any]] = {}
    for row in rows:
        sym = str(row.get("symbol") or "").upper()
        if not sym:
            continue
        incoming = dict(row)
        incoming["symbol"] = sym
        prev = best.get(sym)
        best[sym] = incoming if prev is None else _merge_score_row(prev, incoming)
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
    wait_n = sum(
        1
        for s in signals
        if s["direction"] == "WAIT" or str(s.get("badge") or "") == "WAIT"
    )
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
