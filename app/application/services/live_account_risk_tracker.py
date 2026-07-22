"""Persisted peak equity + authoritative session daily PnL for live risk.

Peak equity is a high-water mark that must survive restarts.
Daily PnL is computed from MT5 history deals (UTC session day) — never
from floating ``account.profit`` alone.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from threading import Lock
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


def _dec(value: Any, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value if value is not None else default))
    except Exception:
        return Decimal(default)


def utc_session_day(now: datetime | None = None) -> str:
    moment = now or datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC).date().isoformat()


@dataclass
class LiveAccountRiskRecord:
    """Per-account high-water mark and last observed equity."""

    login: int
    peak_equity: Decimal
    last_equity: Decimal
    session_day: str
    updated_at: str

    def to_dict(self) -> dict[str, str | int]:
        return {
            "login": int(self.login),
            "peak_equity": str(self.peak_equity),
            "last_equity": str(self.last_equity),
            "session_day": self.session_day,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LiveAccountRiskRecord:
        return cls(
            login=int(data.get("login") or 0),
            peak_equity=_dec(data.get("peak_equity")),
            last_equity=_dec(data.get("last_equity")),
            session_day=str(data.get("session_day") or utc_session_day()),
            updated_at=str(data.get("updated_at") or datetime.now(UTC).isoformat()),
        )


@dataclass
class LiveAccountRiskTracker:
    """Thread-safe peak equity store with optional durable JSON persistence."""

    persist_path: Path | None = None
    _records: dict[int, LiveAccountRiskRecord] = field(default_factory=dict, repr=False)
    _lock: Lock = field(default_factory=Lock, repr=False)
    _loaded: bool = field(default=False, repr=False)

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if self.persist_path is None or not self.persist_path.is_file():
            return
        try:
            raw = json.loads(self.persist_path.read_text(encoding="utf-8"))
            items = raw.get("accounts") if isinstance(raw, dict) else None
            if not isinstance(items, dict):
                return
            for key, row in items.items():
                if not isinstance(row, dict):
                    continue
                rec = LiveAccountRiskRecord.from_dict(row)
                login = rec.login or int(key)
                if login > 0:
                    rec.login = login
                    self._records[login] = rec
        except Exception as exc:
            logger.warning("live_risk_state_load_failed", error=str(exc))

    def _persist(self) -> None:
        if self.persist_path is None:
            return
        try:
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema_version": "1",
                "accounts": {
                    str(login): rec.to_dict() for login, rec in self._records.items()
                },
            }
            tmp = self.persist_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp.replace(self.persist_path)
        except Exception as exc:
            logger.warning("live_risk_state_persist_failed", error=str(exc))

    def observe_equity(
        self,
        *,
        login: int,
        equity: Decimal,
        now: datetime | None = None,
    ) -> Decimal:
        """Update high-water mark; return authoritative peak equity."""
        if login <= 0:
            return equity if equity > 0 else Decimal("0")
        eq = equity if equity > 0 else Decimal("0")
        day = utc_session_day(now)
        moment = (now or datetime.now(UTC)).astimezone(UTC).isoformat()
        with self._lock:
            self._ensure_loaded()
            rec = self._records.get(login)
            if rec is None:
                rec = LiveAccountRiskRecord(
                    login=login,
                    peak_equity=eq,
                    last_equity=eq,
                    session_day=day,
                    updated_at=moment,
                )
            else:
                # Peak is continuous HWM (not reset daily) — drawdown needs it.
                peak = max(rec.peak_equity, eq)
                rec = LiveAccountRiskRecord(
                    login=login,
                    peak_equity=peak,
                    last_equity=eq,
                    session_day=day,
                    updated_at=moment,
                )
            self._records[login] = rec
            self._persist()
            return rec.peak_equity

    def peak_for(self, login: int) -> Decimal | None:
        with self._lock:
            self._ensure_loaded()
            rec = self._records.get(login)
            return rec.peak_equity if rec is not None else None

    @staticmethod
    def daily_pnl_from_deals(
        deals: list[Any],
        *,
        now: datetime | None = None,
    ) -> Decimal:
        """Sum deal profits for the current UTC session day.

        Skips zero-volume / non-trade rows. Does not invent values when empty.
        """
        day = utc_session_day(now)
        total = Decimal("0")
        for deal in deals:
            profit = _dec(getattr(deal, "profit", None))
            # Include commission/swap when present on deal objects.
            profit += _dec(getattr(deal, "commission", None))
            profit += _dec(getattr(deal, "swap", None))
            vol = _dec(getattr(deal, "volume", None), "0")
            if vol <= 0 and profit == 0:
                continue
            raw_t = getattr(deal, "time", None)
            if raw_t is None:
                continue
            if isinstance(raw_t, datetime):
                deal_day = utc_session_day(raw_t)
            else:
                try:
                    ts = int(raw_t)
                    if ts > 10_000_000_000:
                        ts = ts // 1000
                    deal_day = utc_session_day(datetime.fromtimestamp(ts, tz=UTC))
                except (TypeError, ValueError, OSError):
                    continue
            if deal_day == day:
                total += profit
        return total

    def resolve_for_risk(
        self,
        *,
        login: int,
        equity: Decimal,
        balance: Decimal,
        deals: list[Any] | None = None,
        now: datetime | None = None,
    ) -> tuple[Decimal, Decimal]:
        """Return (peak_equity, daily_pnl) for RiskEngine.evaluate."""
        peak = self.observe_equity(login=login, equity=equity, now=now)
        # If peak somehow below balance (corrupt state), lift to balance.
        if balance > peak:
            peak = self.observe_equity(login=login, equity=balance, now=now)
        daily = (
            self.daily_pnl_from_deals(list(deals or []), now=now)
            if deals is not None
            else Decimal("0")
        )
        return peak, daily


_TRACKER: LiveAccountRiskTracker | None = None
_TRACKER_LOCK = Lock()


def default_persist_path() -> Path:
    root = os.environ.get("QUANTFORG_STATE_DIR", "").strip()
    if root:
        return Path(root) / "live_account_risk.json"
    return Path(".quantforg_state") / "live_account_risk.json"


def get_live_account_risk_tracker() -> LiveAccountRiskTracker:
    global _TRACKER
    with _TRACKER_LOCK:
        if _TRACKER is None:
            _TRACKER = LiveAccountRiskTracker(persist_path=default_persist_path())
        return _TRACKER


def reset_live_account_risk_tracker_for_tests() -> None:
    global _TRACKER
    with _TRACKER_LOCK:
        _TRACKER = None
