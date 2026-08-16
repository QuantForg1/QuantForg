"""Phase A institutional safety control plane facade."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from app.domain.institutional_trading.phase_a.burst_latch import BurstLatch
from app.domain.institutional_trading.phase_a.config import (
    DEFAULT_PHASE_A_CONFIG,
    PhaseAConfig,
    phase_a_config_from_settings,
)
from app.domain.institutional_trading.phase_a.control_vocab import (
    FinalControlState,
    map_to_final_control_state,
)
from app.domain.institutional_trading.phase_a.decision_journal import DecisionJournal
from app.domain.institutional_trading.phase_a.kill_state import (
    DurableHaltController,
    HaltMode,
)
from app.domain.institutional_trading.phase_a.market_data_firewall import (
    MarketDataVerdict,
    evaluate_market_data_firewall,
)
from app.domain.institutional_trading.phase_a.order_ambiguity import OrderAmbiguityGate


@dataclass
class PhaseAControlPlane:
    config: PhaseAConfig = field(default_factory=lambda: DEFAULT_PHASE_A_CONFIG)
    halt: DurableHaltController = field(default_factory=DurableHaltController)
    ambiguity: OrderAmbiguityGate = field(default_factory=OrderAmbiguityGate)
    burst: BurstLatch = field(default_factory=BurstLatch)
    journal: DecisionJournal = field(default_factory=DecisionJournal)
    last_md: MarketDataVerdict | None = None
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def __post_init__(self) -> None:
        self.burst.entry_window_s = self.config.entry_burst_window_seconds
        self.burst.max_entries_per_minute = self.config.max_entries_per_minute
        self.burst.reject_window_s = self.config.reject_burst_window_seconds
        self.burst.reject_threshold = self.config.reject_burst_threshold
        self.burst.failure_threshold = self.config.failure_burst_threshold
        self.burst.ambiguous_threshold = self.config.ambiguous_burst_threshold
        self.burst.cooldown_s = self.config.burst_cooldown_seconds

    def apply_config(self, config: PhaseAConfig) -> None:
        self.config = config
        self.__post_init__()

    def persist(self) -> None:
        # Unit tests must not block on Postgres / volume I/O.
        try:
            import os

            if os.environ.get("PYTEST_CURRENT_TEST"):
                return
        except Exception:
            pass
        try:
            from app.application.services.ops_state_persistence import save_ops_state

            patch = {
                **self.halt.to_persist(),
                **self.ambiguity.to_persist(),
            }
            save_ops_state(patch)
        except Exception:
            pass

    def hydrate(self, state: dict[str, Any]) -> None:
        # Rollback: persistence enforcement off → do not restore halt from disk
        # (in-memory kill logic remains; persisted fields are retained on disk).
        if self.config.kill_persistence_enabled:
            self.halt.hydrate(state)
        self.ambiguity.hydrate(state)

    def sync_legacy_kill_flag(self, plane: Any) -> None:
        """Keep OperationsControlPlane.kill_switch_armed aligned with HALT_ALL."""
        try:
            armed = self.halt.mode is HaltMode.HALT_ALL_TRADING
            with plane._lock:
                plane.kill_switch_armed = armed
        except Exception:
            pass

    def set_halt(
        self,
        mode: HaltMode,
        *,
        actor: str,
        reason: str,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        tr = self.halt.set_mode(
            mode, actor=actor, reason=reason, correlation_id=correlation_id
        )
        self.persist()
        return tr.to_dict()

    def evaluate_new_entry_gate(
        self,
        *,
        symbol: str = "",
        bid: float | None = None,
        ask: float | None = None,
        quote_age_seconds: float | None = None,
        market_open: bool | None = True,
        symbol_valid: bool = True,
        candles_ok: bool = True,
        risk_decision: str | None = None,
        safety_allowed: bool | None = None,
        strategy: str = "",
        direction: str = "",
        record_journal: bool = True,
    ) -> dict[str, Any]:
        """Authoritative Phase A gate for NEW ENTRIES only."""
        cfg = self.config
        first_gate: str | None = None

        # Kill / halt
        halt_blocks = False
        if cfg.kill_persistence_enabled or True:
            # Halt mode always consulted; feature flag only disables *persistence*
            # enforcement of reopen — mode still blocks when set.
            halt_blocks = not self.halt.new_entries_allowed()
            if halt_blocks:
                first_gate = f"KILL_SWITCH:{self.halt.mode.value}"

        # Burst latch
        burst_blocks = False
        if cfg.burst_latch_enabled and self.burst.is_latched():
            burst_blocks = True
            first_gate = first_gate or "REJECT_BURST"

        # Recon / UNKNOWN
        recon_blocks = False
        if cfg.recon_gate_enabled and self.ambiguity.has_blocking_ambiguity():
            recon_blocks = True
            first_gate = first_gate or "UNKNOWN_ORDER_RECONCILIATION"

        # Market data — only when quote facts are supplied (symbol alone is not enough)
        md_allow = True
        md_state = "SKIPPED"
        md_context = bool(
            bid is not None or ask is not None or quote_age_seconds is not None
        )
        if cfg.md_firewall_enabled and md_context:
            md = evaluate_market_data_firewall(
                symbol=symbol,
                bid=bid,
                ask=ask,
                quote_age_seconds=quote_age_seconds,
                max_tick_age_seconds=cfg.max_tick_age_seconds,
                degraded_tick_age_seconds=cfg.degraded_tick_age_seconds,
                market_open=market_open,
                symbol_valid=symbol_valid,
                candles_ok=candles_ok,
            )
            self.last_md = md
            md_allow = md.allow_new_entry
            md_state = md.state.value
            if not md_allow:
                first_gate = first_gate or md.first_blocking_gate

        final, gate = map_to_final_control_state(
            halt_mode=self.halt.mode.value,
            burst_latched=cfg.burst_latch_enabled and self.burst.is_latched(),
            recon_blocking=cfg.recon_gate_enabled
            and self.ambiguity.has_blocking_ambiguity(),
            market_data_allow=md_allow if (cfg.md_firewall_enabled and md_context) else True,
            risk_decision=risk_decision,
            safety_allowed=safety_allowed,
            first_blocking_gate=first_gate,
        )
        allow = final in {FinalControlState.ALLOW, FinalControlState.REDUCE}

        if record_journal and cfg.decision_journal_enabled:
            self.journal.record(
                symbol=symbol,
                strategy=strategy,
                direction=direction,
                signal_state="CANDIDATE",
                market_data_state=md_state,
                safety_state=(
                    "PASS"
                    if safety_allowed is True
                    else ("FAIL" if safety_allowed is False else "UNKNOWN")
                ),
                risk_state=str(risk_decision or "UNKNOWN"),
                sizing_state="UNKNOWN",
                portfolio_state="UNKNOWN",
                execution_state="PENDING",
                kill_switch_state=self.halt.mode.value,
                burst_latch_state="LATCHED" if burst_blocks else "CLEAR",
                final_control_state=final.value,
                first_blocking_gate=gate or "UNKNOWN_REASON",
            )

        return {
            "allow_new_entry": bool(allow),
            "final_control_state": final.value,
            "first_blocking_gate": gate,
            "kill_switch": self.halt.snapshot(),
            "burst_latch": self.burst.snapshot(),
            "reconciliation": self.ambiguity.snapshot(),
            "market_data": self.last_md.to_dict() if self.last_md else None,
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "phase": "A",
            "config": self.config.to_dict(),
            "kill_switch": self.halt.snapshot(),
            "reconciliation": self.ambiguity.snapshot(),
            "burst_latch": self.burst.snapshot(),
            "market_data": self.last_md.to_dict() if self.last_md else None,
            "recent_decisions": self.journal.recent(15),
        }


_PLANE: PhaseAControlPlane | None = None
_PLANE_LOCK = threading.Lock()


def get_phase_a_plane(*, refresh_config: bool = False) -> PhaseAControlPlane:
    global _PLANE
    with _PLANE_LOCK:
        if _PLANE is None:
            cfg = phase_a_config_from_settings()
            _PLANE = PhaseAControlPlane(config=cfg)
        elif refresh_config:
            _PLANE.apply_config(phase_a_config_from_settings())
        return _PLANE


def reset_phase_a_plane_for_tests() -> PhaseAControlPlane:
    global _PLANE
    with _PLANE_LOCK:
        _PLANE = PhaseAControlPlane(config=DEFAULT_PHASE_A_CONFIG)
        return _PLANE
