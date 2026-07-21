"""Multi-layer decision pipeline — Trend through Safety."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from app.domain.institutional_ai_decision.config import DecisionEngineV1Config
from app.domain.institutional_trading.session_filter import classify_session_utc

LayerName = Literal[
    "trend",
    "market_structure",
    "liquidity",
    "order_block",
    "fair_value_gap",
    "session",
    "spread",
    "risk",
    "safety",
]

PIPELINE_LAYERS: tuple[LayerName, ...] = (
    "trend",
    "market_structure",
    "liquidity",
    "order_block",
    "fair_value_gap",
    "session",
    "spread",
    "risk",
    "safety",
)


@dataclass(frozen=True, slots=True)
class LayerResult:
    name: LayerName
    passed: bool
    required: bool
    weight: Decimal
    score_contrib: Decimal
    reason: str
    detail: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "passed": self.passed,
            "required": self.required,
            "weight": str(self.weight),
            "score_contrib": str(self.score_contrib),
            "reason": self.reason,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class LayerHints:
    """Operator / analysis inputs for each institutional layer.

    When a hint is None, that layer fail-closes if required, or scores neutral
    if optional — never fabricates market structure.
    """

    trend_aligned: bool | None = None
    trend_label: str | None = None
    structure_valid: bool | None = None
    structure_bias: str | None = None
    liquidity_ok: bool | None = None
    liquidity_note: str | None = None
    order_block_valid: bool | None = None
    order_block_note: str | None = None
    fvg_valid: bool | None = None
    fvg_note: str | None = None
    spread: Decimal | None = None
    atr: Decimal | None = None
    price: Decimal | None = None
    risk_engine_passed: bool | None = None
    risk_reason: str | None = None
    safety_engine_passed: bool | None = None
    safety_reason: str | None = None
    as_of: datetime | None = None


def _bool_layer(
    *,
    name: LayerName,
    hint: bool | None,
    required: bool,
    weight: Decimal,
    ok_reason: str,
    fail_reason: str,
    missing_reason: str,
    detail: str = "",
) -> LayerResult:
    if hint is None:
        if required:
            return LayerResult(
                name=name,
                passed=False,
                required=True,
                weight=weight,
                score_contrib=Decimal("0"),
                reason=missing_reason,
                detail=detail,
            )
        return LayerResult(
            name=name,
            passed=True,
            required=False,
            weight=weight,
            score_contrib=(weight * Decimal("0.5")).quantize(Decimal("0.01")),
            reason=f"{name}: not supplied — optional/neutral",
            detail=detail,
        )
    passed = bool(hint)
    return LayerResult(
        name=name,
        passed=passed,
        required=required,
        weight=weight,
        score_contrib=(weight if passed else Decimal("0")).quantize(Decimal("0.01")),
        reason=ok_reason if passed else fail_reason,
        detail=detail,
    )


def evaluate_layers(
    config: DecisionEngineV1Config, hints: LayerHints
) -> tuple[LayerResult, ...]:
    """Run the nine-layer institutional pipeline (evaluate only)."""
    as_of = hints.as_of or datetime.now(UTC)
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=UTC)

    session = classify_session_utc(as_of)
    session_name = session.value if hasattr(session, "value") else str(session)
    session_ok = session_name in {
        "london",
        "new_york",
        "london_ny_overlap",
    }

    spread_ok: bool | None = (
        None if hints.spread is None else hints.spread <= config.max_spread
    )

    # Abnormal volatility detail for spread/risk context
    vol_note = ""
    if hints.atr is not None and hints.price is not None and hints.price > 0:
        atr_pct = (hints.atr / hints.price * Decimal("100")).quantize(Decimal("0.01"))
        if atr_pct > config.max_atr_pct_of_price:
            vol_note = f"Abnormal volatility: ATR {atr_pct}% above max."
        elif atr_pct < config.min_atr_pct_of_price:
            vol_note = f"Dead market: ATR {atr_pct}% below min."

    trend = _bool_layer(
        name="trend",
        hint=hints.trend_aligned,
        required=config.require_trend,
        weight=Decimal("12"),
        ok_reason=f"Trend aligned ({hints.trend_label or 'bias ok'})",
        fail_reason="Trend not aligned with proposed direction",
        missing_reason="Trend not assessed — fail closed",
        detail=hints.trend_label or "",
    )
    structure = _bool_layer(
        name="market_structure",
        hint=hints.structure_valid,
        required=config.require_structure,
        weight=Decimal("14"),
        ok_reason=f"Market structure valid ({hints.structure_bias or 'ok'})",
        fail_reason="Market structure invalid or broken",
        missing_reason="Market structure not assessed — fail closed",
        detail=hints.structure_bias or "",
    )
    liquidity = _bool_layer(
        name="liquidity",
        hint=hints.liquidity_ok,
        required=config.require_liquidity,
        weight=Decimal("10"),
        ok_reason=hints.liquidity_note or "Liquidity context acceptable",
        fail_reason=hints.liquidity_note or "Liquidity context unfavorable",
        missing_reason="Liquidity not assessed — optional/neutral",
        detail=hints.liquidity_note or "",
    )
    ob = _bool_layer(
        name="order_block",
        hint=hints.order_block_valid,
        required=config.require_order_block,
        weight=Decimal("10"),
        ok_reason=hints.order_block_note or "Order block context supportive",
        fail_reason=hints.order_block_note or "Order block invalid/mitigated",
        missing_reason="Order block not assessed — optional/neutral",
        detail=hints.order_block_note or "",
    )
    fvg = _bool_layer(
        name="fair_value_gap",
        hint=hints.fvg_valid,
        required=config.require_fvg,
        weight=Decimal("8"),
        ok_reason=hints.fvg_note or "Fair value gap context supportive",
        fail_reason=hints.fvg_note or "Fair value gap filled/invalid",
        missing_reason="FVG not assessed — optional/neutral",
        detail=hints.fvg_note or "",
    )
    session_layer = LayerResult(
        name="session",
        passed=session_ok or not config.require_session,
        required=config.require_session,
        weight=Decimal("10"),
        score_contrib=(
            Decimal("10") if session_ok else Decimal("0")
        ).quantize(Decimal("0.01")),
        reason=(
            f"Session {session_name} approved"
            if session_ok
            else f"Session {session_name} outside London/NY window"
        ),
        detail=session_name,
    )
    if spread_ok is None:
        spread_layer = LayerResult(
            name="spread",
            passed=not config.require_spread,
            required=config.require_spread,
            weight=Decimal("10"),
            score_contrib=Decimal("0"),
            reason="Spread unavailable — fail closed",
            detail=vol_note,
        )
    else:
        spread_layer = LayerResult(
            name="spread",
            passed=spread_ok or not config.require_spread,
            required=config.require_spread,
            weight=Decimal("10"),
            score_contrib=(
                Decimal("10") if spread_ok else Decimal("0")
            ).quantize(Decimal("0.01")),
            reason=(
                f"Spread {hints.spread} within {config.max_spread}"
                if spread_ok
                else f"Abnormal spread {hints.spread} exceeds {config.max_spread}"
            ),
            detail=vol_note,
        )

    # Risk + Safety — always required; fail closed when not assessed
    if hints.risk_engine_passed is None:
        risk_layer = LayerResult(
            name="risk",
            passed=False,
            required=True,
            weight=Decimal("13"),
            score_contrib=Decimal("0"),
            reason=(
                "Risk Engine not assessed — fail closed. "
                "Call /risk/check before any live path."
            ),
            detail=hints.risk_reason or "",
        )
    else:
        risk_layer = LayerResult(
            name="risk",
            passed=bool(hints.risk_engine_passed),
            required=True,
            weight=Decimal("13"),
            score_contrib=(
                Decimal("13") if hints.risk_engine_passed else Decimal("0")
            ).quantize(Decimal("0.01")),
            reason=(
                hints.risk_reason
                or (
                    "Risk Engine ALLOW"
                    if hints.risk_engine_passed
                    else "Risk Engine did not ALLOW"
                )
            ),
            detail=vol_note,
        )

    if hints.safety_engine_passed is None:
        safety_layer = LayerResult(
            name="safety",
            passed=False,
            required=True,
            weight=Decimal("13"),
            score_contrib=Decimal("0"),
            reason=(
                "Safety Engine not assessed — fail closed. "
                "Execution Safety must ALLOW before order_send."
            ),
            detail=hints.safety_reason or "",
        )
    else:
        safety_layer = LayerResult(
            name="safety",
            passed=bool(hints.safety_engine_passed),
            required=True,
            weight=Decimal("13"),
            score_contrib=(
                Decimal("13") if hints.safety_engine_passed else Decimal("0")
            ).quantize(Decimal("0.01")),
            reason=(
                hints.safety_reason
                or (
                    "Safety Engine ALLOW"
                    if hints.safety_engine_passed
                    else "Safety Engine did not ALLOW"
                )
            ),
            detail="",
        )

    return (
        trend,
        structure,
        liquidity,
        ob,
        fvg,
        session_layer,
        spread_layer,
        risk_layer,
        safety_layer,
    )


def required_layers_passed(layers: tuple[LayerResult, ...]) -> bool:
    return all(layer.passed for layer in layers if layer.required)
