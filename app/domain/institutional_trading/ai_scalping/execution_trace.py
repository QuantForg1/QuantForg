"""Institutional execution trace — observe-only substages for NOC / PVM.

Annotates existing AI / Risk / PRE artefacts. Does not change decision logic,
bypass gates, or force trades.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


_TRACE_ORDER: tuple[str, ...] = (
    "Market Data",
    "Scanner",
    "SMC",
    "MTF",
    "Liquidity",
    "Volatility",
    "Quality",
    "Confidence",
    "Risk",
    "Position Sizing",
    "Portfolio",
    "PRE",
    "OMS",
    "MT5",
    "Broker",
    "Trade",
    "Management",
    "Close",
    "Analytics",
)


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _stage(
    name: str,
    *,
    ok: bool | None,
    reason: str = "",
    metrics: dict[str, Any] | None = None,
    blocking_gate: str | None = None,
    decision_id: str | None = None,
    symbol: str | None = None,
) -> dict[str, Any]:
    status = "PASS" if ok is True else ("FAIL" if ok is False else "PENDING")
    return {
        "stage": name,
        "status": status,
        "reason": reason or None,
        "metrics": dict(metrics or {}),
        "blocking_gate": blocking_gate,
        "decision_id": decision_id,
        "time": _now(),
        "symbol": symbol,
    }


def build_institutional_execution_trace(
    *,
    symbol: str | None = None,
    decision_id: str | None = None,
    ai_score: dict[str, Any] | None = None,
    scanner: dict[str, Any] | None = None,
    decision_action: str | None = None,
    risk_ok: bool | None = None,
    risk_reason: str | None = None,
    sizing: dict[str, Any] | None = None,
    portfolio: dict[str, Any] | None = None,
    pre: dict[str, Any] | None = None,
    oms: dict[str, Any] | None = None,
    mt5: dict[str, Any] | None = None,
    broker: dict[str, Any] | None = None,
    management: dict[str, Any] | None = None,
    close: dict[str, Any] | None = None,
    analytics: dict[str, Any] | None = None,
    market_ok: bool | None = None,
    market_reason: str | None = None,
) -> dict[str, Any]:
    """Build ordered substages from live artefacts (never invents fills)."""
    score = ai_score if isinstance(ai_score, dict) else {}
    factors = score.get("factors") if isinstance(score.get("factors"), dict) else {}
    vol = (
        score.get("volatility_decision")
        if isinstance(score.get("volatility_decision"), dict)
        else {}
    )
    reject = bool(score.get("reject"))
    reject_reason = str(score.get("reject_reason") or "") or None
    quality = score.get("trade_quality") or score.get("quality")
    confidence = score.get("ai_confidence") or score.get("confidence")
    direction = str(score.get("direction") or decision_action or "NONE").upper()

    stages: list[dict[str, Any]] = [
        _stage(
            "Market Data",
            ok=market_ok,
            reason=market_reason or "",
            decision_id=decision_id,
            symbol=symbol,
        ),
        _stage(
            "Scanner",
            ok=(
                True
                if isinstance(scanner, dict) and scanner.get("best_symbol")
                else (False if isinstance(scanner, dict) else None)
            ),
            reason=(
                f"best={scanner.get('best_symbol')}"
                if isinstance(scanner, dict)
                else ""
            ),
            metrics={
                "eligible_count": (
                    scanner.get("eligible_count") if isinstance(scanner, dict) else None
                ),
                "universe": (
                    scanner.get("universe") if isinstance(scanner, dict) else None
                ),
            },
            decision_id=decision_id,
            symbol=symbol,
        ),
        _stage(
            "SMC",
            ok=None if not score else (not reject or "structure" not in (reject_reason or "").lower()),
            reason="structure/order-block/fvg factors",
            metrics={
                "bos": factors.get("bos"),
                "choch": factors.get("choch"),
                "order_block": factors.get("order_block"),
                "fvg": factors.get("fvg"),
            },
            blocking_gate="structure" if reject and "structure" in (reject_reason or "").lower() else None,
            decision_id=decision_id,
            symbol=symbol,
        ),
        _stage(
            "MTF",
            ok=None if not score else int(factors.get("mtf") or score.get("mtf_alignment") or 0) >= 0,
            metrics={
                "mtf": factors.get("mtf") or score.get("mtf_alignment"),
                "h1_bias": factors.get("h1_bias"),
                "m15_structure": factors.get("m15_structure"),
            },
            blocking_gate=(
                "mtf_alignment"
                if reject and "mtf" in (reject_reason or "").lower()
                else None
            ),
            decision_id=decision_id,
            symbol=symbol,
        ),
        _stage(
            "Liquidity",
            ok=None if not score else True,
            metrics={"liquidity": score.get("liquidity") or factors.get("liquidity_sweep")},
            blocking_gate=(
                "liquidity"
                if reject and "liquidity" in (reject_reason or "").lower()
                else None
            ),
            decision_id=decision_id,
            symbol=symbol,
        ),
        _stage(
            "Volatility",
            ok=None if not vol else bool(vol.get("passed", True)),
            reason=str(vol.get("reason") or ""),
            metrics=dict(vol) if vol else {},
            blocking_gate=(
                "valid_volatility"
                if reject and "volatil" in (reject_reason or "").lower()
                else None
            ),
            decision_id=decision_id,
            symbol=symbol,
        ),
        _stage(
            "Quality",
            ok=None if quality is None else int(quality) >= 80,
            metrics={"quality": quality, "floor": 80},
            blocking_gate="quality" if reject and "quality" in (reject_reason or "").lower() else None,
            decision_id=decision_id,
            symbol=symbol,
        ),
        _stage(
            "Confidence",
            ok=None if confidence is None else int(confidence) >= 80,
            metrics={"confidence": confidence, "floor": 80},
            blocking_gate=(
                "confidence"
                if reject and "confidence" in (reject_reason or "").lower()
                else None
            ),
            decision_id=decision_id,
            symbol=symbol,
        ),
        _stage(
            "Risk",
            ok=risk_ok,
            reason=risk_reason or "",
            blocking_gate="risk" if risk_ok is False else None,
            decision_id=decision_id,
            symbol=symbol,
        ),
        _stage(
            "Position Sizing",
            ok=None if not sizing else not bool(sizing.get("rejected")),
            reason=str((sizing or {}).get("reason") or ""),
            metrics=dict(sizing or {}),
            decision_id=decision_id,
            symbol=symbol,
        ),
        _stage(
            "Portfolio",
            ok=None if not portfolio else not bool(portfolio.get("blocked")),
            reason=str((portfolio or {}).get("reason") or ""),
            metrics=dict(portfolio or {}),
            decision_id=decision_id,
            symbol=symbol,
        ),
        _stage(
            "PRE",
            ok=None if not pre else not bool(pre.get("rejected")),
            reason=str((pre or {}).get("reason") or ""),
            metrics=dict(pre or {}),
            decision_id=decision_id,
            symbol=symbol,
        ),
        _stage(
            "OMS",
            ok=None if not oms else bool(oms.get("ok", oms.get("accepted"))),
            reason=str((oms or {}).get("reason") or ""),
            metrics=dict(oms or {}),
            decision_id=decision_id,
            symbol=symbol,
        ),
        _stage(
            "MT5",
            ok=None if not mt5 else bool(mt5.get("ok", mt5.get("connected"))),
            metrics=dict(mt5 or {}),
            decision_id=decision_id,
            symbol=symbol,
        ),
        _stage(
            "Broker",
            ok=None if not broker else bool(broker.get("ok", broker.get("connected"))),
            metrics=dict(broker or {}),
            decision_id=decision_id,
            symbol=symbol,
        ),
        _stage(
            "Trade",
            ok=None if not decision_action else direction in {"BUY", "SELL"},
            reason=f"action={decision_action or direction}",
            metrics={"direction": direction, "reject": reject},
            blocking_gate=reject_reason if reject else None,
            decision_id=decision_id,
            symbol=symbol,
        ),
        _stage(
            "Management",
            ok=None if not management else True,
            reason=str((management or {}).get("reason") or ""),
            metrics=dict(management or {}),
            decision_id=decision_id,
            symbol=symbol,
        ),
        _stage(
            "Close",
            ok=None if not close else True,
            reason=str((close or {}).get("reason") or ""),
            metrics=dict(close or {}),
            decision_id=decision_id,
            symbol=symbol,
        ),
        _stage(
            "Analytics",
            ok=None if not analytics else True,
            metrics=dict(analytics or {}),
            decision_id=decision_id,
            symbol=symbol,
        ),
    ]

    first_blocker = next(
        (
            s
            for s in stages
            if s.get("status") == "FAIL"
            or (s.get("blocking_gate") and s.get("status") != "PASS")
        ),
        None,
    )
    return {
        "order": list(_TRACE_ORDER),
        "stages": stages,
        "first_blocker": first_blocker,
        "decision_id": decision_id,
        "symbol": symbol,
        "as_of": _now(),
        "observe_only": True,
    }
