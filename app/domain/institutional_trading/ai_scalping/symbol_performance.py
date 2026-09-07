"""Per-symbol measured performance states — loss containment without a global freeze.

States: STRONG / NORMAL / CAUTIOUS / QUARANTINED / OBSERVE

- Scanning and signal research continue for every symbol.
- QUARANTINED blocks new LIVE entries for that symbol only.
- One symbol's losing streak must never pause the rest of the universe.
- Never martingale, never widen SL, never lower P>70 / Sniper / RR>1.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

STATE_STRONG = "STRONG"
STATE_NORMAL = "NORMAL"
STATE_CAUTIOUS = "CAUTIOUS"
STATE_QUARANTINED = "QUARANTINED"
STATE_OBSERVE = "OBSERVE"

WAIT_SYMBOL_QUARANTINED = "WAIT_SYMBOL_QUARANTINED"
WAIT_INSUFFICIENT_SAMPLE = "WAIT_INSUFFICIENT_SAMPLE"
WAIT_WEAK_EXPECTANCY = "WAIT_WEAK_EXPECTANCY"

# Minimum closed trades before calling a symbol STRONG or judging expectancy.
MIN_SAMPLE_STRONG = 3
# Two consecutive losses → CAUTIOUS (still executable under existing gates +
# stronger RR already supported by TIGHTENED adaptation). Three → quarantine.
CONSECUTIVE_CAUTIOUS = 2
CONSECUTIVE_QUARANTINE = 3
ROLLING_WINDOW = 20
MAX_STORED_OUTCOMES = 50
# Match existing RiskEngineConfig.cooldown_minutes_after_loss_streak default.
DEFAULT_QUARANTINE_MINUTES = 60
# Same soft RR used by DEFENSIVE loss-streak adaptation — already in architecture.
# Hard RR>1 / config min_expected_rr are never lowered.
CAUTIOUS_MIN_RR_SOFT = 1.35


@dataclass(frozen=True, slots=True)
class ClosedOutcome:
    symbol: str
    pnl: float
    won: bool
    closed_at: str
    close_reason: str | None = None
    planned_risk_usd: float | None = None
    realized_r: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ClosedOutcome:
        pnl = float(raw.get("pnl") or 0.0)
        return cls(
            symbol=str(raw.get("symbol") or "").strip().upper(),
            pnl=pnl,
            won=bool(raw.get("won") if "won" in raw else pnl > 0),
            closed_at=str(raw.get("closed_at") or ""),
            close_reason=(
                str(raw.get("close_reason")) if raw.get("close_reason") else None
            ),
            planned_risk_usd=(
                float(raw["planned_risk_usd"])
                if raw.get("planned_risk_usd") not in (None, "")
                else None
            ),
            realized_r=(
                float(raw["realized_r"])
                if raw.get("realized_r") not in (None, "")
                else None
            ),
        )


@dataclass(frozen=True, slots=True)
class SymbolPerformanceSnapshot:
    symbol: str
    symbol_state: str
    trades: int
    wins: int
    losses: int
    win_rate: float | None
    net_pnl: float
    avg_win: float | None
    avg_loss: float | None
    payoff_ratio: float | None
    expectancy: float | None
    loss_streak: int
    last_trade: str | None
    last_close_reason: str | None
    market_regime: str | None
    intelligence_alignment: str | None
    spread_status: str | None
    execution_quality: str | None
    requalification_status: str
    next_eligible_reason: str | None
    allow_live_execution: bool
    wait_code: str | None
    quarantine_until: str | None
    quarantine_remaining_minutes: int
    sample_sufficient: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "symbol_state": self.symbol_state,
            "trades": self.trades,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": self.win_rate,
            "net_pnl": self.net_pnl,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "payoff_ratio": self.payoff_ratio,
            "expectancy": self.expectancy,
            "loss_streak": self.loss_streak,
            "last_trade": self.last_trade,
            "last_close_reason": self.last_close_reason,
            "market_regime": self.market_regime,
            "intelligence_alignment": self.intelligence_alignment,
            "spread_status": self.spread_status,
            "execution_quality": self.execution_quality,
            "requalification_status": self.requalification_status,
            "next_eligible_reason": self.next_eligible_reason,
            "allow_live_execution": self.allow_live_execution,
            "wait_code": self.wait_code,
            "quarantine_until": self.quarantine_until,
            "quarantine_remaining_minutes": self.quarantine_remaining_minutes,
            "sample_sufficient": self.sample_sufficient,
            "reason": self.reason,
            "never_disables_universe": True,
            "never_martingale": True,
        }


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _consecutive_losses(outcomes: list[ClosedOutcome]) -> int:
    streak = 0
    for row in reversed(outcomes):
        if row.won:
            break
        streak += 1
    return streak


def _metrics(outcomes: list[ClosedOutcome]) -> dict[str, Any]:
    n = len(outcomes)
    wins = [row for row in outcomes if row.won]
    losses = [row for row in outcomes if not row.won]
    win_rate = (len(wins) / n) if n else None
    avg_win = (
        sum(row.pnl for row in wins) / len(wins) if wins else None
    )
    avg_loss_mag = (
        abs(sum(row.pnl for row in losses) / len(losses)) if losses else None
    )
    net = sum(row.pnl for row in outcomes)
    payoff = None
    if avg_win is not None and avg_loss_mag and avg_loss_mag > 0:
        payoff = avg_win / avg_loss_mag
    expectancy = None
    if n and win_rate is not None:
        if avg_win is not None and avg_loss_mag is not None:
            expectancy = (win_rate * avg_win) - ((1.0 - win_rate) * avg_loss_mag)
        elif avg_win is not None and not losses:
            expectancy = avg_win
        elif avg_loss_mag is not None and not wins:
            expectancy = -avg_loss_mag
    last = outcomes[-1] if outcomes else None
    return {
        "trades": n,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 4) if win_rate is not None else None,
        "net_pnl": round(net, 4),
        "avg_win": round(avg_win, 4) if avg_win is not None else None,
        "avg_loss": round(avg_loss_mag, 4) if avg_loss_mag is not None else None,
        "payoff_ratio": round(payoff, 4) if payoff is not None else None,
        "expectancy": round(expectancy, 4) if expectancy is not None else None,
        "loss_streak": _consecutive_losses(outcomes),
        "last_trade": last.closed_at if last else None,
        "last_close_reason": last.close_reason if last else None,
    }


def resolve_symbol_performance(
    outcomes: list[ClosedOutcome],
    *,
    now: datetime | None = None,
    quarantine_until: datetime | None = None,
    quarantine_minutes: int = DEFAULT_QUARANTINE_MINUTES,
    require_requalify: bool = False,
    market_regime: str | None = None,
    intelligence_alignment: str | None = None,
    spread_reject: bool | None = None,
    execution_quality_ok: bool | None = None,
    symbol: str = "",
) -> SymbolPerformanceSnapshot:
    """Confidence-aware state from measured closes — never from 1-2 trades alone."""
    clock = now or _utc_now()
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=UTC)
    window = list(outcomes[-ROLLING_WINDOW:])
    stats = _metrics(window)
    n = int(stats["trades"])
    streak = int(stats["loss_streak"])
    expectancy = stats["expectancy"]
    payoff = stats["payoff_ratio"]
    remaining = 0
    until = quarantine_until
    if until is not None and until.tzinfo is None:
        until = until.replace(tzinfo=UTC)
    if until is not None and clock < until:
        remaining = max(1, int((until - clock).total_seconds() // 60))

    spread_status = None
    if spread_reject is True:
        spread_status = "REJECT"
    elif spread_reject is False:
        spread_status = "OK"
    exec_quality = None
    if execution_quality_ok is True:
        exec_quality = "OK"
    elif execution_quality_ok is False:
        exec_quality = "DEGRADED"

    requal = "REQUIRED" if require_requalify else "NOT_REQUIRED"

    # Time-boxed quarantine: consecutive-loss evidence, never permanent.
    enter_quarantine = streak >= CONSECUTIVE_QUARANTINE
    still_quarantined = remaining > 0
    if enter_quarantine and until is None:
        still_quarantined = True
        remaining = max(1, int(quarantine_minutes or DEFAULT_QUARANTINE_MINUTES))

    if still_quarantined or (enter_quarantine and remaining > 0):
        state = STATE_QUARANTINED
        wait_code = WAIT_SYMBOL_QUARANTINED
        next_reason = WAIT_SYMBOL_QUARANTINED
        allow = False
        reason = (
            f"{streak} consecutive losses on this symbol — QUARANTINED "
            f"({remaining}m); scanning continues; other symbols unaffected"
        )
    elif streak >= CONSECUTIVE_CAUTIOUS:
        state = STATE_CAUTIOUS
        wait_code = None
        next_reason = None
        allow = True
        reason = (
            f"{streak} consecutive losses — CAUTIOUS: existing gates plus "
            f"stronger RR soft ({CAUTIOUS_MIN_RR_SOFT}); not a universe freeze"
        )
    elif n < MIN_SAMPLE_STRONG:
        state = STATE_OBSERVE
        wait_code = None
        next_reason = WAIT_INSUFFICIENT_SAMPLE
        allow = True
        reason = (
            f"Insufficient sample ({n} < {MIN_SAMPLE_STRONG}) — OBSERVE; "
            "do not force trades and do not disable the symbol"
        )
    elif (
        expectancy is not None
        and expectancy < 0
        and stats["win_rate"] is not None
        and float(stats["win_rate"]) < 0.40
    ):
        state = STATE_CAUTIOUS
        wait_code = None
        next_reason = WAIT_WEAK_EXPECTANCY
        allow = True
        reason = (
            "Negative rolling expectancy on sufficient sample — CAUTIOUS; "
            "keep scanning, require stronger confirmation already in architecture"
        )
    elif (
        expectancy is not None
        and expectancy > 0
        and streak == 0
        and (payoff is None or float(payoff) >= 1.0)
    ):
        state = STATE_STRONG
        wait_code = None
        next_reason = None
        allow = True
        reason = "Measured positive expectancy — STRONG; all existing gates still apply"
    else:
        state = STATE_NORMAL
        wait_code = None
        next_reason = None
        allow = True
        reason = "NORMAL — compete under existing Safety / Risk / OMS gates"

    until_iso = until.isoformat() if until is not None and remaining > 0 else None
    return SymbolPerformanceSnapshot(
        symbol=str(symbol or "").strip().upper(),
        symbol_state=state,
        trades=n,
        wins=int(stats["wins"]),
        losses=int(stats["losses"]),
        win_rate=stats["win_rate"],
        net_pnl=float(stats["net_pnl"]),
        avg_win=stats["avg_win"],
        avg_loss=stats["avg_loss"],
        payoff_ratio=stats["payoff_ratio"],
        expectancy=stats["expectancy"],
        loss_streak=streak,
        last_trade=stats["last_trade"],
        last_close_reason=stats["last_close_reason"],
        market_regime=market_regime,
        intelligence_alignment=intelligence_alignment,
        spread_status=spread_status,
        execution_quality=exec_quality,
        requalification_status=requal,
        next_eligible_reason=next_reason,
        allow_live_execution=allow,
        wait_code=wait_code,
        quarantine_until=until_iso,
        quarantine_remaining_minutes=remaining if state == STATE_QUARANTINED else 0,
        sample_sufficient=n >= MIN_SAMPLE_STRONG,
        reason=reason,
    )


def apply_symbol_performance_gate(
    snapshot: SymbolPerformanceSnapshot,
    *,
    expected_rr: float | None,
    base_min_rr: float = 1.0,
) -> tuple[str | None, str]:
    """Execution-only wait codes. Scanning/research are never stopped here.

    Does not lower P>70, Sniper, or hard RR>1. CAUTIOUS uses the existing
    TIGHTENED soft RR (1.25) already supported by loss-streak adaptation.
    """
    _ = base_min_rr
    if snapshot.symbol_state == STATE_QUARANTINED:
        return WAIT_SYMBOL_QUARANTINED, snapshot.reason
    if snapshot.symbol_state == STATE_CAUTIOUS and expected_rr is not None:
        soft = max(float(base_min_rr or 1.0), CAUTIOUS_MIN_RR_SOFT)
        if float(expected_rr) < soft:
            return (
                WAIT_WEAK_EXPECTANCY,
                (
                    f"CAUTIOUS symbol requires stronger RR "
                    f"({expected_rr} < {soft}); hard RR>1 unchanged"
                ),
            )
    return None, snapshot.reason


@dataclass
class _SymbolLedger:
    symbol: str
    outcomes: list[ClosedOutcome] = field(default_factory=list)
    quarantine_until: datetime | None = None


@dataclass
class SymbolPerformanceBook:
    _ledgers: dict[str, _SymbolLedger] = field(default_factory=dict, repr=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)
    _path: Any = field(default=None, repr=False)
    quarantine_minutes: int = DEFAULT_QUARANTINE_MINUTES

    def __post_init__(self) -> None:
        if self._path is None:
            try:
                from pathlib import Path

                from core.config.settings import get_settings

                settings = get_settings()
                base = Path(
                    getattr(settings, "data_dir", None)
                    or getattr(settings, "ops_state_dir", None)
                    or "data"
                )
            except Exception:
                from pathlib import Path

                base = Path("data")
            self._path = base / "scalping_symbol_performance.json"
        self._load()

    def _key(self, symbol: str) -> str:
        return (symbol or "").strip().upper()

    def _ledger(self, symbol: str) -> _SymbolLedger:
        key = self._key(symbol)
        row = self._ledgers.get(key)
        if row is None:
            row = _SymbolLedger(symbol=key)
            self._ledgers[key] = row
        return row

    def _load(self) -> None:
        path = self._path
        if path is None or not getattr(path, "exists", lambda: False)():
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            rows = raw.get("symbols", {}) if isinstance(raw, dict) else {}
            loaded: dict[str, _SymbolLedger] = {}
            for sym, payload in rows.items():
                if not isinstance(payload, dict):
                    continue
                key = str(sym).strip().upper()
                outcomes = [
                    ClosedOutcome.from_dict(item)
                    for item in (payload.get("outcomes") or [])
                    if isinstance(item, dict)
                ]
                loaded[key] = _SymbolLedger(
                    symbol=key,
                    outcomes=outcomes[-MAX_STORED_OUTCOMES:],
                    quarantine_until=_parse_iso(payload.get("quarantine_until")),
                )
            with self._lock:
                self._ledgers = loaded
        except Exception:
            logger.exception("symbol_performance_load_failed")

    def _persist(self) -> None:
        path = self._path
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                payload = {
                    "updated_at": _utc_now().isoformat(),
                    "symbols": {
                        key: {
                            "outcomes": [row.to_dict() for row in led.outcomes],
                            "quarantine_until": (
                                led.quarantine_until.isoformat()
                                if led.quarantine_until is not None
                                else None
                            ),
                        }
                        for key, led in self._ledgers.items()
                    },
                }
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            logger.exception("symbol_performance_persist_failed")

    def record_closed(
        self,
        symbol: str,
        *,
        pnl: float,
        close_reason: str | None = None,
        planned_risk_usd: float | None = None,
        realized_r: float | None = None,
        closed_at: datetime | None = None,
        persist: bool = True,
    ) -> SymbolPerformanceSnapshot:
        key = self._key(symbol)
        if not key:
            return resolve_symbol_performance([], symbol=key)
        stamp = closed_at or _utc_now()
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=UTC)
        outcome = ClosedOutcome(
            symbol=key,
            pnl=float(pnl),
            won=float(pnl) > 0,
            closed_at=stamp.isoformat(),
            close_reason=str(close_reason) if close_reason else None,
            planned_risk_usd=planned_risk_usd,
            realized_r=realized_r,
        )
        with self._lock:
            led = self._ledger(key)
            led.outcomes.append(outcome)
            led.outcomes = led.outcomes[-MAX_STORED_OUTCOMES:]
            streak = _consecutive_losses(led.outcomes)
            if streak >= CONSECUTIVE_QUARANTINE:
                led.quarantine_until = stamp + timedelta(
                    minutes=max(1, int(self.quarantine_minutes))
                )
            elif outcome.won:
                led.quarantine_until = None
        if persist:
            self._persist()
        return self.evaluate(key, now=stamp)

    def evaluate(
        self,
        symbol: str,
        *,
        now: datetime | None = None,
        market_regime: str | None = None,
        intelligence_alignment: str | None = None,
        spread_reject: bool | None = None,
        execution_quality_ok: bool | None = None,
        require_requalify: bool | None = None,
    ) -> SymbolPerformanceSnapshot:
        key = self._key(symbol)
        requal = bool(require_requalify)
        if require_requalify is None:
            try:
                from app.domain.institutional_trading.ai_scalping.symbol_state import (
                    get_symbol_state_book,
                )

                requal = bool(get_symbol_state_book().get(key).require_requalify)
            except Exception:
                requal = False
        with self._lock:
            led = self._ledger(key) if key else _SymbolLedger(symbol=key)
            outcomes = list(led.outcomes)
            until = led.quarantine_until
        return resolve_symbol_performance(
            outcomes,
            now=now,
            quarantine_until=until,
            quarantine_minutes=self.quarantine_minutes,
            require_requalify=requal,
            market_regime=market_regime,
            intelligence_alignment=intelligence_alignment,
            spread_reject=spread_reject,
            execution_quality_ok=execution_quality_ok,
            symbol=key,
        )

    def snapshot(
        self, symbols: list[str] | tuple[str, ...] | None = None
    ) -> dict[str, Any]:
        with self._lock:
            keys = (
                [self._key(s) for s in symbols]
                if symbols is not None
                else list(self._ledgers.keys())
            )
        rows = [self.evaluate(k).to_dict() for k in keys if k]
        return {"symbols": rows, "count": len(rows)}

    def reset(self, symbol: str | None = None) -> None:
        with self._lock:
            if symbol is None:
                self._ledgers.clear()
                return
            self._ledgers.pop(self._key(symbol), None)


_BOOK: SymbolPerformanceBook | None = None
_BOOK_LOCK = threading.Lock()


def get_symbol_performance_book() -> SymbolPerformanceBook:
    global _BOOK
    with _BOOK_LOCK:
        if _BOOK is None:
            _BOOK = SymbolPerformanceBook()
        return _BOOK


def reset_symbol_performance_book_for_tests() -> None:
    global _BOOK
    with _BOOK_LOCK:
        _BOOK = None


def set_symbol_performance_book_for_tests(
    book: SymbolPerformanceBook | None,
) -> None:
    """Test helper — inject or drop the process singleton."""
    global _BOOK
    with _BOOK_LOCK:
        _BOOK = book
