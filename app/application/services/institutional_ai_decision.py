"""Application service — Institutional AI Decision Engine V1."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from app.domain.institutional_ai_decision import (
    DecisionEngineV1,
    DecisionEvaluateInput,
)
from app.domain.institutional_ai_decision.config import (
    DEFAULT_DECISION_CONFIG,
    DecisionEngineV1Config,
)
from app.domain.institutional_ai_decision.layers import LayerHints


def _dec(value: Any, default: str = "0") -> Decimal:
    if value is None:
        return Decimal(default)
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal(default)


def _opt_bool(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


class InstitutionalAiDecisionService:
    """HTTP facade — evaluate / status only; never order_send."""

    def __init__(self, config: DecisionEngineV1Config | None = None) -> None:
        self._engine = DecisionEngineV1(config or DEFAULT_DECISION_CONFIG)

    def status(self) -> dict[str, object]:
        return self._engine.status()

    def evaluate(self, payload: dict[str, Any]) -> dict[str, object]:
        layers_raw = payload.get("layers") or {}
        if not isinstance(layers_raw, dict):
            layers_raw = {}

        closed_raw = payload.get("closed_pnls") or []
        closed_pnls: tuple[Decimal, ...] = ()
        if isinstance(closed_raw, list):
            closed_pnls = tuple(_dec(x) for x in closed_raw)

        hints = LayerHints(
            trend_aligned=_opt_bool(layers_raw.get("trend_aligned")),
            trend_label=(
                str(layers_raw["trend_label"])
                if layers_raw.get("trend_label")
                else None
            ),
            structure_valid=_opt_bool(layers_raw.get("structure_valid")),
            structure_bias=(
                str(layers_raw["structure_bias"])
                if layers_raw.get("structure_bias")
                else None
            ),
            liquidity_ok=_opt_bool(layers_raw.get("liquidity_ok")),
            liquidity_note=(
                str(layers_raw["liquidity_note"])
                if layers_raw.get("liquidity_note")
                else None
            ),
            order_block_valid=_opt_bool(layers_raw.get("order_block_valid")),
            order_block_note=(
                str(layers_raw["order_block_note"])
                if layers_raw.get("order_block_note")
                else None
            ),
            fvg_valid=_opt_bool(layers_raw.get("fvg_valid")),
            fvg_note=(
                str(layers_raw["fvg_note"]) if layers_raw.get("fvg_note") else None
            ),
            spread=(
                _dec(layers_raw["spread"])
                if layers_raw.get("spread") is not None
                else (
                    _dec(payload["spread"])
                    if payload.get("spread") is not None
                    else None
                )
            ),
            atr=(
                _dec(layers_raw["atr"])
                if layers_raw.get("atr") is not None
                else (
                    _dec(payload["atr"]) if payload.get("atr") is not None else None
                )
            ),
            price=(
                _dec(layers_raw["price"])
                if layers_raw.get("price") is not None
                else (
                    _dec(payload["price"])
                    if payload.get("price") is not None
                    else None
                )
            ),
            risk_engine_passed=_opt_bool(
                layers_raw.get(
                    "risk_engine_passed", payload.get("risk_engine_passed")
                )
            ),
            risk_reason=(
                str(layers_raw["risk_reason"])
                if layers_raw.get("risk_reason")
                else None
            ),
            safety_engine_passed=_opt_bool(
                layers_raw.get(
                    "safety_engine_passed", payload.get("safety_engine_passed")
                )
            ),
            safety_reason=(
                str(layers_raw["safety_reason"])
                if layers_raw.get("safety_reason")
                else None
            ),
        )

        inp = DecisionEvaluateInput(
            side=str(payload.get("side") or "buy"),
            strategy_id=str(payload.get("strategy_id") or "default"),
            technique=(
                str(payload["technique"]) if payload.get("technique") else None
            ),
            dry_run=bool(payload.get("dry_run", True)),
            equity=_dec(payload.get("equity"), "10000"),
            stop_distance=_dec(payload.get("stop_distance"), "5"),
            consecutive_losses=int(payload.get("consecutive_losses") or 0),
            daily_drawdown_pct=_dec(payload.get("daily_drawdown_pct")),
            closed_pnls=closed_pnls,
            open_side=(
                str(payload["open_side"]) if payload.get("open_side") else None
            ),
            open_unrealized_pnl=(
                _dec(payload["open_unrealized_pnl"])
                if payload.get("open_unrealized_pnl") is not None
                else None
            ),
            layers=hints,
        )
        return self._engine.evaluate(inp).to_dict()
