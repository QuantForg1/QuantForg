"""Per-symbol LIVE production scan/trade statistics for priority ranking.

File-backed (no DB migration). Does not change quality gates or risk.
Poor symbols get lower scan priority; strong symbols get higher priority.

Demotion is temporary: after consecutive broker hard-fails a symbol is
excluded from the dynamic universe, then re-probed after a cooldown.
Successful catalogue / market-data evidence clears demotion — never
permanent exclusion after a recovered terminal/session.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from core.config.settings import get_settings
from core.logging import get_logger

logger = get_logger(__name__)

# Consecutive hard broker failures → temporary demotion from dynamic universe.
_DEMOTE_FAIL_THRESHOLD = 8
# After demotion, wait before allowing the symbol back for a recovery probe.
_DEMOTE_COOLDOWN_SECONDS = 900.0
# Successful broker-ok probes required to clear demotion (1 is enough when MD loads).
_RECOVERY_OK_THRESHOLD = 1

# Backward-compatible alias used by older tests/imports.
_PERMANENT_FAIL_THRESHOLD = _DEMOTE_FAIL_THRESHOLD


@dataclass
class SymbolProductionStats:
    symbol: str
    scans: int = 0
    eligible: int = 0
    accepted: int = 0
    rejected: int = 0
    wins: int = 0
    losses: int = 0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    hold_minutes_sum: float = 0.0
    hold_count: int = 0
    rr_sum: float = 0.0
    rr_count: int = 0
    latency_ms_sum: float = 0.0
    latency_count: int = 0
    spread_sum: float = 0.0
    spread_count: int = 0
    atr_pct_sum: float = 0.0
    atr_pct_count: int = 0
    broker_hard_fails: int = 0
    demoted: bool = False
    demoted_at_mono: float | None = None
    consecutive_broker_ok: int = 0
    last_reject_reason: str | None = None
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        # Monotonic clock is process-local — persist wall time only.
        payload.pop("demoted_at_mono", None)
        if self.demoted and self.demoted_at_mono is not None:
            age = max(0.0, time.monotonic() - float(self.demoted_at_mono))
            payload["demotion_age_seconds"] = round(age, 1)
            payload["demotion_cooldown_seconds"] = _DEMOTE_COOLDOWN_SECONDS
            payload["demoted_at"] = (datetime.now(UTC) - timedelta(seconds=age)).isoformat()
        return payload

    @property
    def win_rate(self) -> float | None:
        n = self.wins + self.losses
        return round(100.0 * self.wins / n, 2) if n else None

    @property
    def profit_factor(self) -> float | None:
        if self.gross_loss > 0:
            return round(self.gross_profit / self.gross_loss, 3)
        if self.gross_profit > 0:
            return None  # infinite
        return None

    @property
    def avg_hold(self) -> float | None:
        return (
            round(self.hold_minutes_sum / self.hold_count, 2)
            if self.hold_count
            else None
        )

    @property
    def avg_rr(self) -> float | None:
        return round(self.rr_sum / self.rr_count, 3) if self.rr_count else None


@dataclass
class SymbolStatsBook:
    _by_symbol: dict[str, SymbolProductionStats] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _path: Path | None = field(default=None, repr=False)
    _demote_cooldown_seconds: float = _DEMOTE_COOLDOWN_SECONDS

    def __post_init__(self) -> None:
        if self._path is None:
            try:
                settings = get_settings()
                base = Path(
                    getattr(settings, "data_dir", None)
                    or getattr(settings, "ops_state_dir", None)
                    or "data"
                )
            except Exception:
                base = Path("data")
            self._path = base / "scalping_symbol_production_stats.json"
        self._load()

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            rows = raw.get("symbols", {}) if isinstance(raw, dict) else {}
            loaded: dict[str, SymbolProductionStats] = {}
            for sym, row in rows.items():
                if not isinstance(row, dict):
                    continue
                demoted = bool(row.get("demoted"))
                # Legacy sticky demotions (pre-recovery) have no cooldown clock —
                # clear on load so catalogue-healthy seeds re-enter after deploy.
                # Fresh demotions persist demoted_at (ISO) and resume cooldown.
                demoted_at_mono: float | None = None
                demoted_at_iso = row.get("demoted_at")
                if demoted and demoted_at_iso:
                    try:
                        started = datetime.fromisoformat(str(demoted_at_iso))
                        if started.tzinfo is None:
                            started = started.replace(tzinfo=UTC)
                        age = (datetime.now(UTC) - started).total_seconds()
                        if age >= _DEMOTE_COOLDOWN_SECONDS:
                            demoted = False
                        else:
                            demoted_at_mono = time.monotonic() - max(0.0, age)
                    except Exception:
                        demoted = False
                        demoted_at_mono = None
                elif demoted:
                    demoted = False
                    demoted_at_mono = None
                loaded[str(sym).upper()] = SymbolProductionStats(
                    symbol=str(sym).upper(),
                    scans=int(row.get("scans") or 0),
                    eligible=int(row.get("eligible") or 0),
                    accepted=int(row.get("accepted") or 0),
                    rejected=int(row.get("rejected") or 0),
                    wins=int(row.get("wins") or 0),
                    losses=int(row.get("losses") or 0),
                    gross_profit=float(row.get("gross_profit") or 0),
                    gross_loss=float(row.get("gross_loss") or 0),
                    hold_minutes_sum=float(row.get("hold_minutes_sum") or 0),
                    hold_count=int(row.get("hold_count") or 0),
                    rr_sum=float(row.get("rr_sum") or 0),
                    rr_count=int(row.get("rr_count") or 0),
                    latency_ms_sum=float(row.get("latency_ms_sum") or 0),
                    latency_count=int(row.get("latency_count") or 0),
                    spread_sum=float(row.get("spread_sum") or 0),
                    spread_count=int(row.get("spread_count") or 0),
                    atr_pct_sum=float(row.get("atr_pct_sum") or 0),
                    atr_pct_count=int(row.get("atr_pct_count") or 0),
                    broker_hard_fails=int(row.get("broker_hard_fails") or 0)
                    if demoted
                    else 0,
                    demoted=demoted,
                    demoted_at_mono=demoted_at_mono,
                    consecutive_broker_ok=int(row.get("consecutive_broker_ok") or 0),
                    last_reject_reason=row.get("last_reject_reason"),
                    updated_at=str(row.get("updated_at") or ""),
                )
            with self._lock:
                self._by_symbol = loaded
        except Exception:
            logger.exception("symbol_production_stats_load_failed")

    def _persist(self) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                payload = {
                    "updated_at": datetime.now(UTC).isoformat(),
                    "symbols": {k: v.to_dict() for k, v in self._by_symbol.items()},
                }
            self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            logger.exception("symbol_production_stats_persist_failed")

    def _row(self, symbol: str) -> SymbolProductionStats:
        code = (symbol or "").strip().upper()
        row = self._by_symbol.get(code)
        if row is None:
            row = SymbolProductionStats(symbol=code)
            self._by_symbol[code] = row
        return row

    def _clear_demotion_unlocked(self, row: SymbolProductionStats) -> None:
        was = row.demoted
        row.demoted = False
        row.demoted_at_mono = None
        row.broker_hard_fails = 0
        if was:
            logger.warning(
                "symbol_demotion_cleared",
                symbol=row.symbol,
                reason="broker_health_recovered",
            )

    def _expire_cooldown_unlocked(self) -> list[str]:
        """Release demotions whose cooldown elapsed so they can be re-probed."""
        now = time.monotonic()
        released: list[str] = []
        cooldown = float(self._demote_cooldown_seconds)
        for row in self._by_symbol.values():
            if not row.demoted:
                continue
            started = row.demoted_at_mono
            if started is None:
                # Legacy sticky demotion (no timestamp) — allow recovery probe.
                row.demoted = False
                row.demoted_at_mono = None
                row.broker_hard_fails = 0
                released.append(row.symbol)
                continue
            if (now - float(started)) >= cooldown:
                row.demoted = False
                row.demoted_at_mono = None
                # Keep a reduced fail count so a fresh storm can re-demote quickly,
                # but do not keep the symbol permanently excluded.
                row.broker_hard_fails = max(0, _DEMOTE_FAIL_THRESHOLD // 2)
                released.append(row.symbol)
        if released:
            logger.warning(
                "symbol_demotion_cooldown_expired",
                symbols=released,
                cooldown_seconds=cooldown,
            )
        return released

    def expire_stale_demotions(self) -> list[str]:
        """Public: clear demotions past cooldown (recovery probe eligibility)."""
        with self._lock:
            released = self._expire_cooldown_unlocked()
        if released:
            self._persist()
        return released

    def record_broker_ok(self, symbol: str, *, source: str = "market_data") -> bool:
        """Catalogue / quote / candle success — clear or reduce demotion.

        Returns True when demotion was cleared.
        """
        code = (symbol or "").strip().upper()
        if not code:
            return False
        cleared = False
        with self._lock:
            row = self._row(code)
            row.updated_at = datetime.now(UTC).isoformat()
            row.consecutive_broker_ok += 1
            row.broker_hard_fails = 0
            if row.demoted and row.consecutive_broker_ok >= _RECOVERY_OK_THRESHOLD:
                self._clear_demotion_unlocked(row)
                cleared = True
            elif not row.demoted:
                row.consecutive_broker_ok = min(
                    row.consecutive_broker_ok, _RECOVERY_OK_THRESHOLD + 3
                )
        self._persist()
        if cleared:
            logger.warning(
                "symbol_broker_ok_recovered",
                symbol=code,
                source=source,
            )
        return cleared

    def record_scan(
        self,
        symbol: str,
        *,
        eligible: bool,
        reject_reason: str | None = None,
        spread: float | None = None,
        atr_pct: float | None = None,
        broker_hard_fail: bool = False,
        broker_ok: bool = False,
    ) -> None:
        with self._lock:
            self._expire_cooldown_unlocked()
            row = self._row(symbol)
            row.scans += 1
            row.updated_at = datetime.now(UTC).isoformat()
            if eligible:
                row.eligible += 1
            else:
                row.rejected += 1
                if reject_reason:
                    row.last_reject_reason = str(reject_reason)[:240]
            if spread is not None:
                row.spread_sum += float(spread)
                row.spread_count += 1
            if atr_pct is not None:
                row.atr_pct_sum += float(atr_pct)
                row.atr_pct_count += 1
            if broker_hard_fail:
                row.broker_hard_fails += 1
                row.consecutive_broker_ok = 0
                if row.broker_hard_fails >= _DEMOTE_FAIL_THRESHOLD:
                    if not row.demoted:
                        logger.warning(
                            "symbol_temporarily_demoted",
                            symbol=row.symbol,
                            hard_fails=row.broker_hard_fails,
                            cooldown_seconds=self._demote_cooldown_seconds,
                        )
                    row.demoted = True
                    row.demoted_at_mono = time.monotonic()
            elif broker_ok or eligible:
                # Healthy MD (even with quality NO_TRADE) recovers the symbol.
                row.broker_hard_fails = 0
                row.consecutive_broker_ok += 1
                if row.demoted and row.consecutive_broker_ok >= _RECOVERY_OK_THRESHOLD:
                    self._clear_demotion_unlocked(row)
        self._persist()

    def record_accepted(self, symbol: str, *, latency_ms: float | None = None) -> None:
        with self._lock:
            row = self._row(symbol)
            row.accepted += 1
            row.updated_at = datetime.now(UTC).isoformat()
            if latency_ms is not None:
                row.latency_ms_sum += float(latency_ms)
                row.latency_count += 1
        self._persist()

    def record_closed_trade(
        self,
        symbol: str,
        *,
        win: bool,
        pnl: float,
        hold_minutes: float | None = None,
        r_multiple: float | None = None,
    ) -> None:
        with self._lock:
            row = self._row(symbol)
            row.updated_at = datetime.now(UTC).isoformat()
            if win:
                row.wins += 1
                row.gross_profit += max(0.0, float(pnl))
            else:
                row.losses += 1
                row.gross_loss += abs(min(0.0, float(pnl)))
            if hold_minutes is not None:
                row.hold_minutes_sum += float(hold_minutes)
                row.hold_count += 1
            if r_multiple is not None:
                row.rr_sum += float(r_multiple)
                row.rr_count += 1
        self._persist()

    def demoted_symbols(self) -> frozenset[str]:
        """Symbols currently excluded from the dynamic universe."""
        with self._lock:
            self._expire_cooldown_unlocked()
            return frozenset(s for s, r in self._by_symbol.items() if r.demoted)

    def performance_boost(self) -> dict[str, float]:
        """Soft boost (−30..+40) for scan ordering from LIVE outcomes."""
        with self._lock:
            self._expire_cooldown_unlocked()
            rows = list(self._by_symbol.values())
        out: dict[str, float] = {}
        for r in rows:
            if r.demoted:
                out[r.symbol] = -50.0
                continue
            score = 0.0
            # Eligibility rate encourages active but selective symbols
            if r.scans >= 5:
                elig_rate = r.eligible / max(1, r.scans)
                score += (elig_rate - 0.05) * 80.0
            closed = r.wins + r.losses
            if closed >= 2 and r.win_rate is not None:
                score += (r.win_rate - 50.0) * 0.4
            pf = r.profit_factor
            if pf is not None:
                score += max(-15.0, min(20.0, (pf - 1.0) * 12.0))
            elif r.gross_profit > 0 and r.gross_loss == 0:
                score += 15.0
            if r.accepted == 0 and r.scans >= 20 and r.eligible == 0:
                score -= 10.0
            out[r.symbol] = max(-30.0, min(40.0, score))
        return out

    def ranked_symbols(self, *, top: int = 10, worst: bool = False) -> list[dict[str, Any]]:
        with self._lock:
            rows = list(self._by_symbol.values())
        boost = self.performance_boost()

        def key(r: SymbolProductionStats) -> tuple:
            return (boost.get(r.symbol, 0.0), r.accepted, r.eligible, r.scans)

        rows.sort(key=key, reverse=not worst)
        out = []
        for r in rows[:top]:
            out.append(
                {
                    "symbol": r.symbol,
                    "scans": r.scans,
                    "eligible": r.eligible,
                    "accepted": r.accepted,
                    "rejected": r.rejected,
                    "win_rate": r.win_rate,
                    "profit_factor": r.profit_factor,
                    "avg_hold": r.avg_hold,
                    "avg_rr": r.avg_rr,
                    "demoted": r.demoted,
                    "priority_boost": round(boost.get(r.symbol, 0.0), 2),
                    "last_reject_reason": r.last_reject_reason,
                }
            )
        return out

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            rows = [r.to_dict() for r in self._by_symbol.values()]
        return {
            "symbols": rows,
            "top": self.ranked_symbols(top=10, worst=False),
            "worst": self.ranked_symbols(top=10, worst=True),
            "demoted": sorted(self.demoted_symbols()),
        }


_BOOK: SymbolStatsBook | None = None
_BOOK_LOCK = threading.Lock()


def get_symbol_stats_book() -> SymbolStatsBook:
    global _BOOK
    with _BOOK_LOCK:
        if _BOOK is None:
            _BOOK = SymbolStatsBook()
        return _BOOK


def reset_symbol_stats_book_for_tests() -> None:
    """Test helper — drop the process singleton."""
    global _BOOK
    with _BOOK_LOCK:
        _BOOK = None
