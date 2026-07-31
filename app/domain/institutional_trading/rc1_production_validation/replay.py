"""Replay verification across regimes and sessions — no strategy changes."""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.domain.institutional_trading.rc1_production_validation.config import (
    CONFIDENCE_FLOOR,
    QUALITY_FLOOR,
)
from app.domain.institutional_trading.rc1_production_validation.trade_record import (
    TradeRecord,
)
from app.domain.institutional_trading.rc1_production_validation.trade_recorder import (
    TradeRecorder,
    get_trade_recorder,
)

# Canonical condition buckets required by RC1 Phase 3.
REQUIRED_REGIMES = (
    "trending",
    "ranging",
    "high_volatility",
    "low_volatility",
)
REQUIRED_SESSIONS = (
    "london",
    "new_york",
    "tokyo",
    "mixed",
)


def _int(raw: Any) -> int | None:
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _histogram(values: list[int], *, bucket: int = 5) -> dict[str, int]:
    hist: Counter[str] = Counter()
    for v in values:
        lo = (v // bucket) * bucket
        hi = lo + bucket - 1
        hist[f"{lo}-{hi}"] += 1
    return dict(sorted(hist.items(), key=lambda kv: int(kv[0].split("-")[0])))


def _normalize_event(raw: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    symbol = str(raw.get("symbol") or "XAUUSD").upper()
    quality = _int(raw.get("quality") if "quality" in raw else raw.get("quality_score"))
    confidence = _int(
        raw.get("confidence") if "confidence" in raw else raw.get("ai_confidence")
    )
    regime = str(raw.get("market_regime") or raw.get("regime") or "mixed").lower()
    session = str(raw.get("session") or raw.get("market_session") or "mixed").lower()
    session = session.replace(" ", "_")
    accepted_flag = raw.get("accepted")
    reasons_rej = raw.get("reason_rejected") or raw.get("rejection_reason") or ""
    reasons_acc = raw.get("reason_accepted") or raw.get("acceptance_reason") or ""

    # Apply locked floors — never lower them.
    floor_ok = True
    reject_parts: list[str] = []
    if quality is not None and quality < QUALITY_FLOOR:
        floor_ok = False
        reject_parts.append(f"quality {quality} < {QUALITY_FLOOR}")
    if confidence is not None and confidence < CONFIDENCE_FLOOR:
        floor_ok = False
        reject_parts.append(f"confidence {confidence} < {CONFIDENCE_FLOOR}")
    if accepted_flag is False:
        floor_ok = False
    if reasons_rej and accepted_flag is not True:
        floor_ok = False
        if not reject_parts:
            reject_parts.append(str(reasons_rej))

    accepted = bool(floor_ok and (accepted_flag is not False))
    if accepted and not reasons_acc:
        reasons_acc = "replay_eligible_floors_met"
    if not accepted and not reasons_rej:
        reasons_rej = "; ".join(reject_parts) or "replay_rejected"

    return {
        "symbol": symbol,
        "quality": quality,
        "confidence": confidence,
        "market_regime": regime,
        "session": session,
        "accepted": accepted,
        "reason_accepted": reasons_acc if accepted else "",
        "reason_rejected": reasons_rej if not accepted else "",
        "entry": raw.get("entry"),
        "stop_loss": raw.get("SL") or raw.get("stop_loss") or raw.get("sl"),
        "take_profit": raw.get("TP") or raw.get("take_profit") or raw.get("tp"),
        "risk_reward": raw.get("RR") or raw.get("risk_reward") or raw.get("rr"),
        "expected_lot_size": raw.get("expected_lot_size") or raw.get("lots"),
        "portfolio_allocation": raw.get("portfolio_allocation"),
        "risk_profile": str(raw.get("risk_profile") or ""),
        "oms_latency_ms": raw.get("oms_latency_ms") or raw.get("OMS_latency"),
        "ai_latency_ms": raw.get("ai_latency_ms") or raw.get("AI_latency"),
        "gateway_latency_ms": raw.get("gateway_latency_ms")
        or raw.get("gateway_latency"),
        "order_payload": raw.get("order_payload") or {},
    }


def run_replay_verification(
    events: list[dict[str, Any]],
    *,
    recorder: TradeRecorder | None = None,
    execution_mode: str = "shadow",
) -> dict[str, Any]:
    """Replay historical tagged events; record eligible/rejected trades."""
    rec = recorder or get_trade_recorder()
    eligible: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    qualities: list[int] = []
    confidences: list[int] = []
    regimes_seen: set[str] = set()
    sessions_seen: set[str] = set()
    expected_broker: list[dict[str, Any]] = []

    for raw in events:
        norm = _normalize_event(raw)
        if norm is None:
            continue
        regimes_seen.add(norm["market_regime"])
        sessions_seen.add(norm["session"])
        trade = TradeRecord(
            symbol=norm["symbol"],
            market_regime=norm["market_regime"],
            session=norm["session"],
            quality=norm["quality"],
            confidence=norm["confidence"],
            risk_profile=norm["risk_profile"],
            entry=str(norm["entry"]) if norm["entry"] is not None else None,
            stop_loss=(
                str(norm["stop_loss"]) if norm["stop_loss"] is not None else None
            ),
            take_profit=(
                str(norm["take_profit"]) if norm["take_profit"] is not None else None
            ),
            risk_reward=(
                str(norm["risk_reward"]) if norm["risk_reward"] is not None else None
            ),
            expected_lot_size=(
                str(norm["expected_lot_size"])
                if norm["expected_lot_size"] is not None
                else None
            ),
            portfolio_allocation=(
                str(norm["portfolio_allocation"])
                if norm["portfolio_allocation"] is not None
                else None
            ),
            reason_accepted=norm["reason_accepted"],
            reason_rejected=norm["reason_rejected"],
            accepted=norm["accepted"],
            oms_latency_ms=(
                float(norm["oms_latency_ms"])
                if norm["oms_latency_ms"] is not None
                else None
            ),
            ai_latency_ms=(
                float(norm["ai_latency_ms"])
                if norm["ai_latency_ms"] is not None
                else None
            ),
            gateway_latency_ms=(
                float(norm["gateway_latency_ms"])
                if norm["gateway_latency_ms"] is not None
                else None
            ),
            execution_mode=execution_mode,
            order_payload=dict(norm["order_payload"] or {}),
            notes="replay_verification",
        )
        rec.record(trade)
        row = trade.to_dict()
        if trade.accepted:
            eligible.append(row)
            if trade.quality is not None:
                qualities.append(trade.quality)
            if trade.confidence is not None:
                confidences.append(trade.confidence)
            expected_broker.append(
                {
                    "trade_id": trade.trade_id,
                    "symbol": trade.symbol,
                    "side": (trade.order_payload or {}).get("side"),
                    "lots": trade.expected_lot_size,
                    "entry": trade.entry,
                    "SL": trade.stop_loss,
                    "TP": trade.take_profit,
                    "would_submit": True,
                    "submitted": False,
                }
            )
        else:
            rejected.append(row)

    score_dist = {
        "quality": _histogram(qualities) if qualities else {},
        "confidence": _histogram(confidences) if confidences else {},
    }
    coverage = {
        "regimes_required": list(REQUIRED_REGIMES),
        "regimes_seen": sorted(regimes_seen),
        "regimes_missing": sorted(set(REQUIRED_REGIMES) - regimes_seen),
        "sessions_required": list(REQUIRED_SESSIONS),
        "sessions_seen": sorted(sessions_seen),
        "sessions_missing": sorted(set(REQUIRED_SESSIONS) - sessions_seen),
    }
    return {
        "events_processed": len(eligible) + len(rejected),
        "eligible_trades": len(eligible),
        "rejected_trades": len(rejected),
        "score_distribution": score_dist,
        "quality_histogram": score_dist["quality"],
        "confidence_histogram": score_dist["confidence"],
        "expected_broker_submissions": expected_broker,
        "coverage": coverage,
        "quality_floor": QUALITY_FLOOR,
        "confidence_floor": CONFIDENCE_FLOOR,
        "eligible_sample": eligible[:20],
        "rejected_sample": rejected[:20],
    }


def build_synthetic_replay_dataset() -> list[dict[str, Any]]:
    """Deterministic multi-condition dataset for offline RC1 replay (not live)."""
    base_q = QUALITY_FLOOR
    base_c = CONFIDENCE_FLOOR
    rows: list[dict[str, Any]] = []
    # Mix of eligible (>= floors) and rejected (< floors) across conditions
    specs = [
        ("trending", "london", base_q + 5, base_c + 5, True),
        ("trending", "new_york", base_q + 2, base_c + 1, True),
        ("ranging", "tokyo", base_q + 3, base_c + 4, True),
        ("ranging", "london", base_q - 10, base_c + 2, False),
        ("high_volatility", "new_york", base_q + 8, base_c + 6, True),
        ("high_volatility", "mixed", base_q + 1, base_c - 5, False),
        ("low_volatility", "tokyo", base_q + 4, base_c + 3, True),
        ("low_volatility", "london", base_q - 2, base_c - 2, False),
        ("trending", "mixed", base_q + 10, base_c + 10, True),
        ("ranging", "mixed", base_q, base_c, True),
    ]
    for i, (regime, session, q, c, ok) in enumerate(specs):
        rows.append(
            {
                "symbol": "XAUUSD",
                "market_regime": regime,
                "session": session,
                "quality": q,
                "confidence": c,
                "accepted": ok,
                "reason_rejected": "" if ok else "below_floor_or_tagged",
                "reason_accepted": "floors_met" if ok else "",
                "entry": 2350.0 + i,
                "SL": 2345.0 + i,
                "TP": 2360.0 + i,
                "RR": "2.0",
                "expected_lot_size": "0.01",
                "portfolio_allocation": "1.0%",
                "risk_profile": "standard",
                "oms_latency_ms": 12.0 + i,
                "ai_latency_ms": 40.0 + i,
                "gateway_latency_ms": 8.0 + i,
                "order_payload": {
                    "symbol": "XAUUSD",
                    "side": "buy" if i % 2 == 0 else "sell",
                    "volume": "0.01",
                },
            }
        )
    return rows
