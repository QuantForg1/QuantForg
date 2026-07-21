"""Application service — QuantForg Alpha Engine V1."""

from __future__ import annotations

from typing import Any

from app.domain.alpha_engine import AlphaEngine, AlphaEngineInput
from app.domain.alpha_engine.config import DEFAULT_ALPHA_CONFIG, AlphaEngineConfig


class AlphaEngineService:
    """Evaluate / status / history — never order_send."""

    def __init__(self, config: AlphaEngineConfig | None = None) -> None:
        self._engine = AlphaEngine(config or DEFAULT_ALPHA_CONFIG)

    def status(self) -> dict[str, object]:
        return self._engine.status()

    def policies(self) -> dict[str, object]:
        return self._engine.config.to_dict()

    def update_policies(self, updates: dict[str, Any]) -> dict[str, object]:
        return self._engine.update_policies(updates)

    def history(self, *, limit: int = 50) -> dict[str, object]:
        return {"evaluations": self._engine.list_history(limit=limit)}

    def replay(self, audit_id: str) -> dict[str, object]:
        return self._engine.replay(audit_id)

    def evaluate(self, payload: dict[str, Any]) -> dict[str, object]:
        def _dict(key: str) -> dict[str, Any] | None:
            raw = payload.get(key)
            return raw if isinstance(raw, dict) else None

        def _list(key: str) -> list[dict[str, Any]] | None:
            if key not in payload:
                return None
            raw = payload.get(key)
            if raw is None:
                return None
            if not isinstance(raw, list):
                return []
            return [r for r in raw if isinstance(r, dict)]

        inp = AlphaEngineInput(
            regime=_dict("regime"),
            liquidity=_dict("liquidity"),
            structure=_dict("structure"),
            order_flow=_dict("order_flow"),
            opportunities=_list("opportunities"),
            execution=_dict("execution"),
            exit_context=_dict("exit_context"),
            trade_factors=_dict("trade_factors"),
            closed_trades=_list("closed_trades"),
            side=str(payload.get("side") or "buy"),
            technique=(
                str(payload["technique"]) if payload.get("technique") else None
            ),
        )
        return self._engine.evaluate(inp).to_dict()
