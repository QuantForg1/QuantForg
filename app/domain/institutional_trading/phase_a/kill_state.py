"""Phase A durable kill / halt modes.

ACTIVE — normal
HALT_NEW_ENTRIES — no new risk; PME continues
HALT_ALL_TRADING — no new risk; OMS market submits blocked; PME safety continues
                (no automatic flatten solely because of this halt mode)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from threading import RLock
from typing import Any
from uuid import uuid4


class HaltMode(str, Enum):
    ACTIVE = "ACTIVE"
    HALT_NEW_ENTRIES = "HALT_NEW_ENTRIES"
    HALT_ALL_TRADING = "HALT_ALL_TRADING"


@dataclass(frozen=True, slots=True)
class HaltTransition:
    timestamp: str
    actor: str
    previous_state: str
    new_state: str
    reason: str
    correlation_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "actor": self.actor,
            "previous_state": self.previous_state,
            "new_state": self.new_state,
            "reason": self.reason,
            "correlation_id": self.correlation_id,
        }


@dataclass
class DurableHaltController:
    """Process + durable ops-state backed halt mode."""

    mode: HaltMode = HaltMode.ACTIVE
    last_reason: str = ""
    last_actor: str = ""
    last_correlation_id: str = ""
    history: list[HaltTransition] = field(default_factory=list)
    _lock: RLock = field(default_factory=RLock, repr=False)

    def new_entries_allowed(self) -> bool:
        return self.mode is HaltMode.ACTIVE

    def oms_market_submit_allowed(self) -> bool:
        """Both halt modes block new market entries."""
        return self.mode is HaltMode.ACTIVE

    def pme_safety_allowed(self) -> bool:
        """Both halt modes keep position safety / reconciliation alive."""
        return True

    def suppress_auto_flatten(self) -> bool:
        """Phase A halt must not blindly flatten solely due to halt mode."""
        return self.mode is not HaltMode.ACTIVE

    def set_mode(
        self,
        mode: HaltMode,
        *,
        actor: str,
        reason: str,
        correlation_id: str | None = None,
    ) -> HaltTransition:
        with self._lock:
            prev = self.mode
            cid = correlation_id or str(uuid4())
            self.mode = mode
            self.last_reason = reason
            self.last_actor = actor
            self.last_correlation_id = cid
            transition = HaltTransition(
                timestamp=datetime.now(UTC).isoformat(),
                actor=actor,
                previous_state=prev.value,
                new_state=mode.value,
                reason=reason,
                correlation_id=cid,
            )
            self.history.append(transition)
            if len(self.history) > 100:
                self.history = self.history[-100:]
            return transition

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "state": self.mode.value,
                "new_entries_allowed": self.new_entries_allowed(),
                "oms_market_submit_allowed": self.oms_market_submit_allowed(),
                "pme_safety_allowed": self.pme_safety_allowed(),
                "last_reason": self.last_reason or None,
                "last_actor": self.last_actor or None,
                "last_correlation_id": self.last_correlation_id or None,
                "recent_transitions": [t.to_dict() for t in self.history[-10:]],
            }

    def to_persist(self) -> dict[str, Any]:
        with self._lock:
            return {
                "phase_a_halt_mode": self.mode.value,
                "phase_a_halt_reason": self.last_reason,
                "phase_a_halt_actor": self.last_actor,
                "phase_a_halt_correlation_id": self.last_correlation_id,
                # Keep legacy key for operators / hydrate fallback
                "kill_switch_armed": self.mode is HaltMode.HALT_ALL_TRADING,
            }

    def hydrate(self, state: dict[str, Any]) -> None:
        raw = str(state.get("phase_a_halt_mode") or "").strip().upper()
        if raw in {m.value for m in HaltMode}:
            with self._lock:
                self.mode = HaltMode(raw)
                self.last_reason = str(state.get("phase_a_halt_reason") or "")
                self.last_actor = str(state.get("phase_a_halt_actor") or "hydrate")
                self.last_correlation_id = str(
                    state.get("phase_a_halt_correlation_id") or ""
                )
        # Legacy: kill_switch_armed True without phase_a mode → HALT_ALL_TRADING
        elif bool(state.get("kill_switch_armed")):
            with self._lock:
                self.mode = HaltMode.HALT_ALL_TRADING
                self.last_reason = str(
                    state.get("phase_a_halt_reason") or "legacy_kill_switch_armed"
                )
                self.last_actor = "hydrate"
