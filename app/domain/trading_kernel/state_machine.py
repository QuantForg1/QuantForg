"""Trading Kernel state machine — advisory path only."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class KernelState(StrEnum):
    IDLE = "IDLE"
    EVALUATING = "EVALUATING"
    ALPHA = "ALPHA"
    RISK = "RISK"
    SAFETY = "SAFETY"
    DECISION = "DECISION"
    HOLD = "HOLD"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    ERROR = "ERROR"


_ALLOWED: dict[KernelState, frozenset[KernelState]] = {
    KernelState.IDLE: frozenset({KernelState.EVALUATING, KernelState.ERROR}),
    KernelState.EVALUATING: frozenset(
        {KernelState.ALPHA, KernelState.RISK, KernelState.ERROR}
    ),
    KernelState.ALPHA: frozenset({KernelState.RISK, KernelState.ERROR}),
    KernelState.RISK: frozenset(
        {KernelState.SAFETY, KernelState.HOLD, KernelState.ERROR}
    ),
    KernelState.SAFETY: frozenset(
        {KernelState.DECISION, KernelState.HOLD, KernelState.ERROR}
    ),
    KernelState.DECISION: frozenset(
        {
            KernelState.HOLD,
            KernelState.APPROVE,
            KernelState.REJECT,
            KernelState.ERROR,
        }
    ),
    KernelState.HOLD: frozenset({KernelState.IDLE}),
    KernelState.APPROVE: frozenset({KernelState.IDLE}),
    KernelState.REJECT: frozenset({KernelState.IDLE}),
    KernelState.ERROR: frozenset({KernelState.IDLE}),
}


@dataclass
class TradingStateMachine:
    state: KernelState = KernelState.IDLE
    history: list[str] = field(default_factory=list)

    def reset(self) -> None:
        self.state = KernelState.IDLE
        self.history = []

    def can_transition(self, target: KernelState) -> bool:
        return target in _ALLOWED.get(self.state, frozenset())

    def transition(self, target: KernelState, *, reason: str = "") -> bool:
        if not self.can_transition(target):
            return False
        self.history.append(f"{self.state.value}->{target.value}:{reason}")
        self.state = target
        return True

    def to_dict(self) -> dict[str, object]:
        return {
            "state": self.state.value,
            "history": list(self.history),
            "terminal": self.state
            in {
                KernelState.HOLD,
                KernelState.APPROVE,
                KernelState.REJECT,
                KernelState.ERROR,
            },
            "advisory_only": True,
            "never_order_send": True,
        }
