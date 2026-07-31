"""Execution evidence contracts — observability only."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

# Operator-facing timeline (subset / alias of PVM stages).
EXECUTION_TIMELINE: tuple[str, ...] = (
    "Scheduler",
    "Market",
    "AI",
    "Risk",
    "OMS",
    "Gateway",
    "MT5",
    "Broker",
    "Position Open",
    "Position Close",
)

# Map report stage → PVM ValidationStage.value keys.
_TIMELINE_TO_PVM: dict[str, tuple[str, ...]] = {
    "Scheduler": ("Scheduler",),
    "Market": ("Market Data",),
    "AI": ("AI",),
    "Risk": ("Risk", "Eligibility"),
    "OMS": ("OMS", "Execution Bridge"),
    "Gateway": ("Gateway",),
    "MT5": ("MT5",),
    "Broker": ("Broker",),
    "Position Open": ("Position Open",),
    "Position Close": ("Position Close",),
}


def timeline_source_stages(label: str) -> tuple[str, ...]:
    return _TIMELINE_TO_PVM.get(label, (label,))


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class TimelineStage:
    stage: str
    status: str  # PASS | FAIL | SKIP | PENDING
    latency_ms: float | None = None
    reason: str = ""
    timestamp: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "status": self.status,
            "latency_ms": self.latency_ms,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


@dataclass(slots=True)
class ExecutionEvidencePackage:
    """One real production BUY/SELL evidence package (observe-only)."""

    validation_id: str
    signal_id: str | None = None
    timestamp: str = field(default_factory=_now_iso)
    environment: str | None = None
    commit_sha: str | None = None
    deployment_id: str | None = None

    # AI
    decision: str | None = None
    quality_score: int | None = None
    confidence: int | None = None
    reasons: list[str] = field(default_factory=list)
    session: str | None = None
    symbol: str | None = None

    # Risk
    risk_score: int | None = None
    rr: str | None = None
    position_size: str | None = None
    eligibility_result: str | None = None

    # OMS
    oms_submit_timestamp: str | None = None
    oms_payload_hash: str | None = None
    oms_response: dict[str, Any] = field(default_factory=dict)
    oms_latency_ms: float | None = None

    # Gateway
    gateway_request_id: str | None = None
    gateway_http_status: int | None = None
    order_send_latency_ms: float | None = None
    gateway_latency_ms: float | None = None

    # MT5
    mt5_ticket: int | None = None
    mt5_retcode: int | None = None
    mt5_comment: str | None = None
    fill_price: str | None = None
    volume: str | None = None

    # Broker
    broker_execution_status: str | None = None
    slippage: str | None = None
    final_fill: str | None = None

    # Trade lifecycle (null until real close observed)
    entry: str | None = None
    exit: str | None = None
    stop_loss: str | None = None
    take_profit: str | None = None
    duration: str | None = None
    gross_pnl: str | None = None
    net_pnl: str | None = None
    swap: str | None = None
    commission: str | None = None

    # System (null when unavailable — never fabricated)
    cpu: float | None = None
    memory: float | None = None
    system_gateway_latency_ms: float | None = None
    system_oms_latency_ms: float | None = None

    timeline: list[TimelineStage] = field(default_factory=list)
    final_result: str = "IN_PROGRESS"
    accepted: bool = False
    certificate_eligible: bool = False
    observe_only: bool = True
    never_fabricated: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "validation_id": self.validation_id,
            "signal_id": self.signal_id,
            "timestamp": self.timestamp,
            "environment": self.environment,
            "commit_sha": self.commit_sha,
            "deployment_id": self.deployment_id,
            "ai": {
                "decision": self.decision,
                "quality_score": self.quality_score,
                "confidence": self.confidence,
                "reasons": list(self.reasons),
                "session": self.session,
                "symbol": self.symbol,
            },
            "risk": {
                "risk_score": self.risk_score,
                "rr": self.rr,
                "position_size": self.position_size,
                "eligibility_result": self.eligibility_result,
            },
            "oms": {
                "submit_timestamp": self.oms_submit_timestamp,
                "payload_hash": self.oms_payload_hash,
                "response": dict(self.oms_response),
                "latency_ms": self.oms_latency_ms,
            },
            "gateway": {
                "request_id": self.gateway_request_id,
                "http_status": self.gateway_http_status,
                "order_send_latency_ms": self.order_send_latency_ms,
                "gateway_latency_ms": self.gateway_latency_ms,
            },
            "mt5": {
                "ticket": self.mt5_ticket,
                "retcode": self.mt5_retcode,
                "comment": self.mt5_comment,
                "fill_price": self.fill_price,
                "volume": self.volume,
            },
            "broker": {
                "execution_status": self.broker_execution_status,
                "slippage": self.slippage,
                "final_fill": self.final_fill,
            },
            "trade": {
                "entry": self.entry,
                "exit": self.exit,
                "stop_loss": self.stop_loss,
                "take_profit": self.take_profit,
                "duration": self.duration,
                "gross_pnl": self.gross_pnl,
                "net_pnl": self.net_pnl,
                "swap": self.swap,
                "commission": self.commission,
            },
            "system": {
                "cpu": self.cpu,
                "memory": self.memory,
                "gateway_latency_ms": self.system_gateway_latency_ms,
                "oms_latency_ms": self.system_oms_latency_ms,
            },
            "timeline": [t.to_dict() for t in self.timeline],
            "final_result": self.final_result,
            "accepted": self.accepted,
            "certificate_eligible": self.certificate_eligible,
            "observe_only": self.observe_only,
            "never_fabricated": self.never_fabricated,
        }

    def execution_latency_ms(self) -> float | None:
        if self.order_send_latency_ms is not None:
            return self.order_send_latency_ms
        if self.oms_latency_ms is not None:
            return self.oms_latency_ms
        vals = [t.latency_ms for t in self.timeline if t.latency_ms is not None]
        if not vals:
            return None
        return round(sum(vals), 2)
