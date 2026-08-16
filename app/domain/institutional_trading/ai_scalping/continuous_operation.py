"""Continuous autonomous operation controller (v7.1).

Ties existing heartbeat + recovery into a single production tick.
Never retries order_send. Never abandons open positions.
Pauses NEW entries only on capital/broker/gateway/market/portfolio blocks.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    AiScalpingConfig,
)
from app.domain.institutional_trading.reliability.heartbeat import HeartbeatRegistry
from app.domain.institutional_trading.reliability.models import ComponentName
from app.domain.institutional_trading.reliability.recovery import RecoveryOrchestrator

ReconnectFn = Callable[[], bool]


@dataclass(frozen=True, slots=True)
class NewEntryPauseDecision:
    pause_new_entries: bool
    reasons: tuple[str, ...]
    manage_open_positions: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "pause_new_entries": self.pause_new_entries,
            "reasons": list(self.reasons),
            "manage_open_positions": self.manage_open_positions,
            "note": "Open positions are always managed — never abandoned.",
        }


@dataclass(frozen=True, slots=True)
class ContinuousOpSnapshot:
    as_of: str
    heartbeats: dict[str, Any]
    recovery: list[dict[str, Any]]
    pause: dict[str, Any]
    resumed_positions: bool
    pending_rescan: bool
    version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "as_of": self.as_of,
            "heartbeats": dict(self.heartbeats),
            "recovery": list(self.recovery),
            "pause": dict(self.pause),
            "resumed_positions": self.resumed_positions,
            "pending_rescan": self.pending_rescan,
            "version": self.version,
        }


@dataclass
class ContinuousOperationController:
    """Production continuous-ops desk — self-heal deps, never force trades."""

    config: AiScalpingConfig = field(default_factory=lambda: DEFAULT_AI_SCALPING_CONFIG)
    heartbeats: HeartbeatRegistry = field(default_factory=HeartbeatRegistry)
    recovery: RecoveryOrchestrator = field(default_factory=RecoveryOrchestrator)
    pending_rescan: bool = False
    positions_resumed: bool = False
    _oms_fn: ReconnectFn | None = field(default=None, repr=False)
    _feed_fn: ReconnectFn | None = field(default=None, repr=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def bind_reconnects(
        self,
        *,
        gateway: ReconnectFn | None = None,
        mt5: ReconnectFn | None = None,
        oms: ReconnectFn | None = None,
        feed: ReconnectFn | None = None,
        safe_read: Callable[[], bool] | None = None,
    ) -> None:
        """Attach safe reconnect callables (no order_send)."""
        if gateway is not None:
            self.recovery.gateway_reconnect_fn = gateway
        if mt5 is not None:
            self.recovery.mt5_reconnect_fn = mt5
        if safe_read is not None:
            self.recovery.safe_read_fn = safe_read
        if oms is not None:
            self._oms_fn = oms
        if feed is not None:
            self._feed_fn = feed

    def publish_heartbeats(self, *, now: datetime | None = None) -> None:
        moment = now or datetime.now(UTC)
        for comp in (
            ComponentName.GATEWAY,
            ComponentName.MT5,
            ComponentName.OMS,
            ComponentName.EXECUTION,
            ComponentName.DECISION,
            ComponentName.PME,
        ):
            self.heartbeats.publish(comp, now=moment)

    def evaluate_new_entry_pause(
        self,
        *,
        daily_loss_exceeded: bool = False,
        broker_available: bool = True,
        gateway_available: bool = True,
        market_open: bool = True,
        portfolio_risk_exceeded: bool = False,
        missing_heartbeats: tuple[str, ...] = (),
        margin_danger: bool = False,
        abnormal_spread: bool = False,
        flash_crash: bool = False,
        network_failure: bool = False,
        mt5_connected: bool = True,
        symbol: str = "",
        bid: float | None = None,
        ask: float | None = None,
        quote_age_seconds: float | None = None,
        symbol_valid: bool = True,
        candles_ok: bool = True,
        strategy: str = "",
        direction: str = "",
    ) -> NewEntryPauseDecision:
        """Pause NEW entries only — open positions always continue."""
        reasons: list[str] = []
        if daily_loss_exceeded:
            reasons.append("daily loss exceeded")
        if not broker_available:
            reasons.append("broker unavailable")
        if not gateway_available:
            reasons.append("gateway unavailable")
        if not mt5_connected:
            reasons.append("mt5 disconnected")
        if not market_open:
            reasons.append("market closed")
        if portfolio_risk_exceeded:
            reasons.append("portfolio risk exceeded")
        if margin_danger:
            reasons.append("margin danger")
        if abnormal_spread:
            reasons.append("abnormal spread")
        if flash_crash:
            reasons.append("flash crash protection")
        if network_failure:
            reasons.append("network failure")
        # Missing critical heartbeats → treat as unavailable (recoverable)
        critical = {"gateway", "mt5", "oms"}
        miss = {m.lower() for m in missing_heartbeats}
        if miss & critical:
            reasons.append(f"stale heartbeat:{','.join(sorted(miss & critical))}")

        # Phase A control plane — fail closed for NEW risk on gate errors
        try:
            from app.domain.institutional_trading.phase_a import get_phase_a_plane

            gate = get_phase_a_plane().evaluate_new_entry_gate(
                symbol=symbol,
                bid=bid,
                ask=ask,
                quote_age_seconds=quote_age_seconds,
                market_open=market_open,
                symbol_valid=symbol_valid,
                candles_ok=candles_ok,
                strategy=strategy,
                direction=direction,
            )
            if not gate.get("allow_new_entry", False):
                gate_name = str(
                    gate.get("first_blocking_gate")
                    or gate.get("final_control_state")
                    or "UNKNOWN_REASON"
                )
                reasons.append(f"phase_a:{gate_name}")
            # Phase B explain journal — observe only
            try:
                from app.domain.institutional_trading.phase_b import get_phase_b_plane

                pb = get_phase_b_plane()
                md = gate.get("market_data") or {}
                pb.explain.record(
                    symbol=symbol,
                    strategy=strategy,
                    direction=direction,
                    signal_state="CANDIDATE",
                    market_data_state=str(md.get("state") or "UNKNOWN"),
                    regime=(pb.last_regime or {}).get("operational_regime")
                    or "UNKNOWN",
                    safety_state="PASS" if not reasons else "REVIEW",
                    risk_state="UNKNOWN",
                    portfolio_state="UNKNOWN",
                    execution_quality_state="UNKNOWN",
                    control_state=str(gate.get("final_control_state") or "UNKNOWN"),
                    first_blocking_gate=str(
                        gate.get("first_blocking_gate") or "UNKNOWN_REASON"
                    ),
                    why_signalled=(
                        f"{strategy or 'strategy'} candidate"
                        if strategy
                        else "UNKNOWN_REASON"
                    ),
                    why_ranked="UNKNOWN_REASON",
                )
            except Exception:
                pass
        except Exception:
            reasons.append("phase_a:gate_unavailable")

        return NewEntryPauseDecision(
            pause_new_entries=bool(reasons),
            reasons=tuple(reasons),
            manage_open_positions=True,
        )

    def heal_dependencies(
        self,
        *,
        gateway_ok: bool = True,
        mt5_ok: bool = True,
        oms_ok: bool = True,
        feed_ok: bool = True,
    ) -> list[dict[str, Any]]:
        """Attempt safe reconnects for failed deps. Never retries order_send."""
        events: list[dict[str, Any]] = []
        if not gateway_ok:
            ev = self.recovery.recover_gateway()
            events.append(ev.to_dict() if hasattr(ev, "to_dict") else {"ok": False})
        if not mt5_ok:
            ev = self.recovery.recover_mt5()
            events.append(ev.to_dict() if hasattr(ev, "to_dict") else {"ok": False})
        if not oms_ok and self._oms_fn is not None:
            try:
                ok = bool(self._oms_fn())
                events.append({"action": "oms_reconnect", "success": ok})
            except Exception as exc:
                events.append(
                    {"action": "oms_reconnect", "success": False, "detail": str(exc)}
                )
        if not feed_ok and self._feed_fn is not None:
            try:
                ok = bool(self._feed_fn())
                events.append({"action": "feed_reconnect", "success": ok})
            except Exception as exc:
                events.append(
                    {"action": "feed_reconnect", "success": False, "detail": str(exc)}
                )
        if not feed_ok and self._feed_fn is None:
            # Fallback: safe read retry (idempotent)
            ev = self.recovery.retry_safe_read()
            events.append(ev.to_dict() if hasattr(ev, "to_dict") else {"ok": False})
        return events

    def mark_startup_resume(self) -> None:
        """After restart — positions continue under PME; hashes hydrated elsewhere."""
        with self._lock:
            self.positions_resumed = True

    def request_rescan_after_close(self) -> None:
        """After a trade closes, scan again for a NEW valid setup only."""
        self.request_opportunity_rescan("position_closed")

    def request_opportunity_rescan(self, reason: str = "event") -> None:
        """Arm an immediate opportunity rescan — never forces a trade."""
        with self._lock:
            self.pending_rescan = True
        try:
            from app.domain.institutional_trading.ai_scalping.daily_opportunity_target import (
                get_daily_opportunity_tracker,
            )

            get_daily_opportunity_tracker(
                target_trades_per_day=int(
                    getattr(self.config, "target_trades_per_day", 3) or 3
                )
            ).note_rescan(reason)
        except Exception:
            pass

    def consume_rescan(self) -> bool:
        with self._lock:
            flag = self.pending_rescan
            self.pending_rescan = False
            return flag

    def tick(
        self,
        *,
        gateway_ok: bool = True,
        mt5_ok: bool = True,
        oms_ok: bool = True,
        feed_ok: bool = True,
        daily_loss_exceeded: bool = False,
        broker_available: bool = True,
        market_open: bool = True,
        portfolio_risk_exceeded: bool = False,
    ) -> ContinuousOpSnapshot:
        now = datetime.now(UTC)
        # Only refresh heartbeats for healthy deps so missing()/pause can observe
        # real staleness. Failed deps are also reported explicitly below (OMS has
        # no dedicated pause flag other than missing_heartbeats).
        if gateway_ok:
            self.heartbeats.publish(ComponentName.GATEWAY, now=now)
        if mt5_ok:
            self.heartbeats.publish(ComponentName.MT5, now=now)
        if oms_ok:
            self.heartbeats.publish(ComponentName.OMS, now=now)
        for comp in (
            ComponentName.EXECUTION,
            ComponentName.DECISION,
            ComponentName.PME,
        ):
            self.heartbeats.publish(comp, now=now)
        recovery = self.heal_dependencies(
            gateway_ok=gateway_ok,
            mt5_ok=mt5_ok,
            oms_ok=oms_ok,
            feed_ok=feed_ok,
        )
        failed_deps: list[str] = []
        if not gateway_ok:
            failed_deps.append("gateway")
        if not mt5_ok:
            failed_deps.append("mt5")
        if not oms_ok:
            failed_deps.append("oms")
        # Also respect age-based registry staleness (publisher forgot to refresh).
        # Components just published above will not appear here.
        age_missing = [
            c.value
            for c in self.heartbeats.missing(
                (
                    ComponentName.GATEWAY,
                    ComponentName.MT5,
                    ComponentName.OMS,
                ),
                now=now,
            )
        ]
        missing_hb = tuple(dict.fromkeys([*failed_deps, *age_missing]))
        pause = self.evaluate_new_entry_pause(
            daily_loss_exceeded=daily_loss_exceeded,
            broker_available=broker_available and mt5_ok,
            gateway_available=gateway_ok,
            market_open=market_open,
            portfolio_risk_exceeded=portfolio_risk_exceeded,
            missing_heartbeats=missing_hb,
        )
        with self._lock:
            resumed = self.positions_resumed
            pending = self.pending_rescan
        return ContinuousOpSnapshot(
            as_of=now.isoformat(),
            heartbeats=self.heartbeats.snapshot(),
            recovery=recovery,
            pause=pause.to_dict(),
            resumed_positions=resumed,
            pending_rescan=pending,
            version=getattr(self.config, "continuous_version", None)
            or self.config.version,
        )


_CTRL: ContinuousOperationController | None = None
_CTRL_LOCK = threading.Lock()


def get_continuous_operation_controller(
    config: AiScalpingConfig | None = None,
) -> ContinuousOperationController:
    global _CTRL
    with _CTRL_LOCK:
        if _CTRL is None:
            _CTRL = ContinuousOperationController(
                config=config or DEFAULT_AI_SCALPING_CONFIG
            )
        elif config is not None:
            _CTRL.config = config
        return _CTRL
