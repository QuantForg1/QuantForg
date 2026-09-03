"""Per-symbol institutional state — independent quality/cooldown/spread/regime/health.

v7 multi-asset layer. Does not alter v6.3 quality floors or risk knobs.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.domain.institutional_trading.ai_scalping.adaptive_cooldown import (
    AdaptiveCooldownDecision,
    AdaptiveCooldownGate,
)
from app.domain.institutional_trading.ai_scalping.same_symbol_requalification import (
    SetupFingerprint,
    fresh_setup_evidence,
)


@dataclass
class SymbolExecutionState:
    """Live per-symbol desk state (never shared across symbols)."""

    symbol: str
    last_quality: int | None = None
    last_confidence: int | None = None
    last_regime: str | None = None
    last_spread_score: int | None = None
    last_setup_family: str | None = None
    execution_health_ok: bool = True
    recent_rejects: int = 0
    last_updated: str | None = None
    last_observed: SetupFingerprint | None = None
    last_closed: SetupFingerprint | None = None
    last_closed_pnl: float | None = None
    require_requalify: bool = False
    _cooldown: AdaptiveCooldownGate = field(
        default_factory=AdaptiveCooldownGate, repr=False
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "last_quality": self.last_quality,
            "last_confidence": self.last_confidence,
            "last_regime": self.last_regime,
            "last_spread_score": self.last_spread_score,
            "last_setup_family": self.last_setup_family,
            "execution_health_ok": self.execution_health_ok,
            "recent_rejects": self.recent_rejects,
            "last_updated": self.last_updated,
            "require_requalify": self.require_requalify,
            "last_closed_pnl": self.last_closed_pnl,
            "last_closed": (
                self.last_closed.to_dict() if self.last_closed is not None else None
            ),
        }


@dataclass
class SymbolStateBook:
    """Thread-safe book of independent symbol states."""

    _states: dict[str, SymbolExecutionState] = field(default_factory=dict, repr=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def _key(self, symbol: str) -> str:
        return (symbol or "").strip().upper()

    def get(self, symbol: str) -> SymbolExecutionState:
        key = self._key(symbol)
        with self._lock:
            state = self._states.get(key)
            if state is None:
                state = SymbolExecutionState(symbol=key)
                self._states[key] = state
            return state

    def update_scan(
        self,
        symbol: str,
        *,
        quality: int | None = None,
        confidence: int | None = None,
        regime: str | None = None,
        spread_score: int | None = None,
        setup_family: str | None = None,
        execution_health_ok: bool | None = None,
    ) -> SymbolExecutionState:
        state = self.get(symbol)
        with self._lock:
            if quality is not None:
                state.last_quality = int(quality)
            if confidence is not None:
                state.last_confidence = int(confidence)
            if regime is not None:
                state.last_regime = str(regime)
            if spread_score is not None:
                state.last_spread_score = int(spread_score)
            if setup_family is not None:
                state.last_setup_family = str(setup_family)
            if execution_health_ok is not None:
                state.execution_health_ok = bool(execution_health_ok)
            state.last_updated = datetime.now(UTC).isoformat()
            return state

    def note_entry(self, symbol: str, *, seconds: int) -> None:
        self.get(symbol)._cooldown.note_entry(seconds=seconds)

    def note_reject(self, symbol: str, *, seconds: int | None = None) -> None:
        state = self.get(symbol)
        with self._lock:
            state.recent_rejects = min(99, int(state.recent_rejects) + 1)
            state.execution_health_ok = state.recent_rejects < 5
        if seconds is not None:
            state._cooldown.note_reject_burst(seconds=int(seconds))

    def clear_reject_streak(self, symbol: str) -> None:
        state = self.get(symbol)
        with self._lock:
            state.recent_rejects = 0
            state.execution_health_ok = True

    def evaluate_cooldown(
        self, symbol: str, decision: AdaptiveCooldownDecision
    ) -> AdaptiveCooldownDecision:
        return self.get(symbol)._cooldown.evaluate(decision)

    def observe_setup(self, symbol: str, fingerprint: SetupFingerprint) -> None:
        state = self.get(symbol)
        with self._lock:
            state.last_observed = fingerprint

    def note_closed(
        self,
        symbol: str,
        *,
        pnl: float | None = None,
        fingerprint: SetupFingerprint | None = None,
    ) -> None:
        """Keep desk state after a close. Do not wipe cooldown or fingerprints."""
        state = self.get(symbol)
        with self._lock:
            state.last_closed = fingerprint or state.last_observed
            if pnl is not None:
                try:
                    state.last_closed_pnl = float(pnl)
                except (TypeError, ValueError):
                    state.last_closed_pnl = None
            state.require_requalify = state.last_closed is not None

    def evaluate_requalification(
        self, symbol: str, current: SetupFingerprint
    ) -> tuple[bool, str]:
        """Allow only when the new scan is a proven different setup."""
        state = self.get(symbol)
        with self._lock:
            if not state.require_requalify:
                return True, "requalify_not_required"
            ok, why = fresh_setup_evidence(state.last_closed, current)
            return ok, why

    def snapshot(
        self, symbols: tuple[str, ...] | list[str] | None = None
    ) -> dict[str, Any]:
        with self._lock:
            if symbols is None:
                rows = list(self._states.values())
            else:
                keys = [self._key(s) for s in symbols]
                rows = [self.get(k) for k in keys]
            return {
                "symbols": {r.symbol: r.to_dict() for r in rows},
                "count": len(rows),
            }

    def reset(self, symbol: str | None = None) -> None:
        with self._lock:
            if symbol is None:
                self._states.clear()
                return
            key = self._key(symbol)
            self._states.pop(key, None)


_BOOK: SymbolStateBook | None = None
_BOOK_LOCK = threading.Lock()


def get_symbol_state_book() -> SymbolStateBook:
    global _BOOK
    with _BOOK_LOCK:
        if _BOOK is None:
            _BOOK = SymbolStateBook()
        return _BOOK
