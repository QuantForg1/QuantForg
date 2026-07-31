"""Production Validation Mode contracts — observability only.

Never influences trading decisions, safety, OMS, gateway, or MT5.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class ValidationStage(StrEnum):
    SCHEDULER = "Scheduler"
    MARKET_DATA = "Market Data"
    CONTEXT = "Context"
    AI = "AI"
    RISK = "Risk"
    ELIGIBILITY = "Eligibility"
    EXECUTION_BRIDGE = "Execution Bridge"
    OMS = "OMS"
    GATEWAY = "Gateway"
    MT5 = "MT5"
    BROKER = "Broker"
    POSITION_OPEN = "Position Open"
    POSITION_CLOSE = "Position Close"


class StageStatus(StrEnum):
    PASS = "PASS"  # noqa: S105
    FAIL = "FAIL"
    SKIP = "SKIP"
    PENDING = "PENDING"


# Ordered pipeline for reports / first-blocker classification.
PIPELINE_ORDER: tuple[ValidationStage, ...] = (
    ValidationStage.SCHEDULER,
    ValidationStage.MARKET_DATA,
    ValidationStage.CONTEXT,
    ValidationStage.AI,
    ValidationStage.RISK,
    ValidationStage.ELIGIBILITY,
    ValidationStage.EXECUTION_BRIDGE,
    ValidationStage.OMS,
    ValidationStage.GATEWAY,
    ValidationStage.MT5,
    ValidationStage.BROKER,
    ValidationStage.POSITION_OPEN,
    ValidationStage.POSITION_CLOSE,
)

# Stages required for a successful live validation (ticket created).
ACCEPTANCE_STAGES: tuple[ValidationStage, ...] = (
    ValidationStage.SCHEDULER,
    ValidationStage.MARKET_DATA,
    ValidationStage.AI,
    ValidationStage.RISK,
    ValidationStage.OMS,
    ValidationStage.GATEWAY,
    ValidationStage.MT5,
    ValidationStage.BROKER,
)


@dataclass(slots=True)
class StageRecord:
    stage: ValidationStage
    status: StageStatus
    timestamp: str
    latency_ms: float | None = None
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage.value,
            "status": self.status.value,
            "timestamp": self.timestamp,
            "latency_ms": self.latency_ms,
            "reason": self.reason,
        }


@dataclass(slots=True)
class OmsRecord:
    payload: dict[str, Any] = field(default_factory=dict)
    response: dict[str, Any] = field(default_factory=dict)
    latency_ms: float | None = None
    retry_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "payload": dict(self.payload),
            "response": dict(self.response),
            "latency_ms": self.latency_ms,
            "retry_count": self.retry_count,
        }


@dataclass(slots=True)
class GatewayRecord:
    request: dict[str, Any] = field(default_factory=dict)
    response: dict[str, Any] = field(default_factory=dict)
    http_code: int | None = None
    gateway_latency_ms: float | None = None
    order_send_latency_ms: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "request": dict(self.request),
            "response": dict(self.response),
            "http_code": self.http_code,
            "gateway_latency_ms": self.gateway_latency_ms,
            "order_send_latency_ms": self.order_send_latency_ms,
        }


@dataclass(slots=True)
class Mt5Record:
    ticket: int | None = None
    retcode: int | None = None
    comment: str = ""
    execution_time_ms: float | None = None
    fill_price: str | None = None
    slippage: str | None = None
    broker_response: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticket": self.ticket,
            "retcode": self.retcode,
            "comment": self.comment,
            "execution_time_ms": self.execution_time_ms,
            "fill_price": self.fill_price,
            "slippage": self.slippage,
            "broker_response": dict(self.broker_response),
        }


@dataclass(slots=True)
class ValidationAttempt:
    """One execution-attempt evidence package (observe-only)."""

    validation_id: str = field(default_factory=lambda: f"val_{uuid4().hex[:16]}")
    timestamp: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat().replace("+00:00", "Z")
    )
    signal_id: str | None = None
    symbol: str = ""
    market_session: str = ""
    execution_mode: str = ""
    ai_confidence: int | None = None
    quality_score: int | None = None
    confluence: int | None = None
    mtf_alignment: int | None = None
    risk_score: int | None = None
    expected_rr: str | None = None
    spread: str | None = None
    atr: str | None = None
    liquidity: Any = None
    order_blocks: Any = None
    fvg: Any = None
    bos: Any = None
    choch: Any = None
    ai_action: str | None = None
    stages: dict[str, StageRecord] = field(default_factory=dict)
    no_trade_reasons: list[str] = field(default_factory=list)
    oms: OmsRecord | None = None
    gateway: GatewayRecord | None = None
    mt5: Mt5Record | None = None
    first_blocker: str | None = None
    final_result: str = "IN_PROGRESS"
    accepted: bool = False
    export_paths: dict[str, str] = field(default_factory=dict)
    closed: bool = False

    def stage(self, name: ValidationStage | str) -> StageRecord | None:
        key = name.value if isinstance(name, ValidationStage) else str(name)
        return self.stages.get(key)

    def to_dict(self) -> dict[str, Any]:
        return {
            "validation_id": self.validation_id,
            "timestamp": self.timestamp,
            "signal_id": self.signal_id,
            "symbol": self.symbol,
            "market_session": self.market_session,
            "execution_mode": self.execution_mode,
            "ai_confidence": self.ai_confidence,
            "quality_score": self.quality_score,
            "confluence": self.confluence,
            "mtf_alignment": self.mtf_alignment,
            "risk_score": self.risk_score,
            "expected_rr": self.expected_rr,
            "spread": self.spread,
            "atr": self.atr,
            "liquidity": self.liquidity,
            "order_blocks": self.order_blocks,
            "fvg": self.fvg,
            "bos": self.bos,
            "choch": self.choch,
            "ai_action": self.ai_action,
            "stages": {k: v.to_dict() for k, v in self.stages.items()},
            "pipeline": [
                (
                    self.stages[s.value].to_dict()
                    if s.value in self.stages
                    else {
                        "stage": s.value,
                        "status": StageStatus.PENDING.value,
                        "timestamp": None,
                        "latency_ms": None,
                        "reason": "",
                    }
                )
                for s in PIPELINE_ORDER
            ],
            "no_trade_reasons": list(self.no_trade_reasons),
            "oms": self.oms.to_dict() if self.oms else None,
            "gateway": self.gateway.to_dict() if self.gateway else None,
            "mt5": self.mt5.to_dict() if self.mt5 else None,
            "first_blocker": self.first_blocker,
            "final_result": self.final_result,
            "accepted": self.accepted,
            "export_paths": dict(self.export_paths),
            "closed": self.closed,
        }
