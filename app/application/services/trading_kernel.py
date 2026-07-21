"""Application service — QuantForg Trading Kernel V1."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from app.domain.institutional_trading.certification.platform import (
    get_certification_platform,
)
from app.domain.trading_kernel import KernelCycleInput, TradingKernel
from app.domain.trading_kernel.config import DEFAULT_KERNEL_CONFIG, KernelConfig


def _dec(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _opt_bool(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


class TradingKernelService:
    def __init__(self, config: KernelConfig | None = None) -> None:
        self._kernel = TradingKernel(config or DEFAULT_KERNEL_CONFIG)

    def status(self) -> dict[str, object]:
        return self._kernel.status()

    def policies(self) -> dict[str, object]:
        return self._kernel.config.to_dict()

    def update_policies(self, updates: dict[str, Any]) -> dict[str, object]:
        return self._kernel.update_policies(updates)

    def events(
        self, *, limit: int = 100, trace_id: str | None = None
    ) -> dict[str, Any]:
        return self._kernel.list_events(limit=limit, trace_id=trace_id)

    def stage_replay(
        self, *, trace_id: str, stage: str | None = None
    ) -> dict[str, Any]:
        return self._kernel.stage_replay(trace_id=trace_id, stage=stage)

    def deterministic_replay(self, trace_id: str) -> dict[str, Any]:
        return self._kernel.deterministic_replay_cycle(trace_id)

    def certification(self) -> dict[str, Any]:
        cert: dict[str, Any] | None
        go: str | None
        try:
            payload = get_certification_platform().dashboard_payload()
            cert = payload if isinstance(payload, dict) else None
            go = str(cert.get("go_nogo")) if cert else None
        except Exception:
            cert = None
            go = None
        return self._kernel.certification(certification=cert, go_nogo=go)

    def feature_flags(self) -> dict[str, Any]:
        return {"flags": self._kernel.flags.snapshot()}

    def set_feature_flag(self, flag: str, enabled: bool) -> dict[str, Any]:
        return {"flags": self._kernel.flags.set_flag(flag, enabled)}

    def plugins(self) -> dict[str, Any]:
        return {"plugins": self._kernel.plugins.list(), "isolated": True}

    def run_cycle(self, payload: dict[str, Any]) -> dict[str, Any]:
        inp = KernelCycleInput(
            side=str(payload.get("side") or "buy"),
            spread=_dec(payload.get("spread")),
            confidence=_dec(payload.get("confidence")),
            news_blackout=_opt_bool(payload.get("news_blackout")),
            kill_switch=_opt_bool(payload.get("kill_switch")),
            execution_mode=(
                str(payload["execution_mode"])
                if payload.get("execution_mode")
                else None
            ),
            alpha=payload.get("alpha")
            if isinstance(payload.get("alpha"), dict)
            else None,
            risk_engine_passed=_opt_bool(payload.get("risk_engine_passed")),
            safety_engine_passed=_opt_bool(payload.get("safety_engine_passed")),
            decision=(
                str(payload["decision"]) if payload.get("decision") else None
            ),
            plugin_snapshot=payload.get("plugin_snapshot")
            if isinstance(payload.get("plugin_snapshot"), dict)
            else None,
            certification=payload.get("certification")
            if isinstance(payload.get("certification"), dict)
            else None,
            go_nogo=str(payload["go_nogo"]) if payload.get("go_nogo") else None,
        )
        return self._kernel.run_cycle(inp)
