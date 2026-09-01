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
    def _deal_value(deal: Any, *names: str) -> Any:
        if isinstance(deal, dict):
            for name in names:
                if deal.get(name) not in (None, ""):
                    return deal.get(name)
            return None
        for name in names:
            val = getattr(deal, name, None)
            if val not in (None, ""):
                return val
        return None

    @staticmethod
    def _deal_ticket(deal: Any) -> int:
        try:
            return int(LiveAccountRiskTracker._deal_value(deal, "ticket") or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _deal_cash_delta(deal: Any) -> Decimal:
        return (
            _dec(LiveAccountRiskTracker._deal_value(deal, "profit"))
            + _dec(LiveAccountRiskTracker._deal_value(deal, "commission"))
            + _dec(LiveAccountRiskTracker._deal_value(deal, "swap"))
        )

    @staticmethod
    def _deal_time(deal: Any) -> datetime | None:
        raw_t = LiveAccountRiskTracker._deal_value(deal, "time")
        if raw_t is None:
            return None
        if isinstance(raw_t, datetime):
            moment = raw_t
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=UTC)
            return moment.astimezone(UTC)
        try:
            ts = int(raw_t)
            if ts > 10_000_000_000:
                ts = ts // 1000
            return datetime.fromtimestamp(ts, tz=UTC)
        except (TypeError, ValueError, OSError):
            return None

    @staticmethod
    def _is_trade_deal(deal: Any) -> bool:
        """True for market buy/sell fills. Balance/credit/deposit never count."""
        dtype = str(
            LiveAccountRiskTracker._deal_value(deal, "deal_type", "type") or ""
        )
        low = dtype.lower()
        if any(
            tok in low
            for tok in (
                "balance",
                "credit",
                "charge",
                "correction",
                "bonus",
                "deposit",
                "withdraw",
            )
        ):
            return False
        vol = _dec(LiveAccountRiskTracker._deal_value(deal, "volume"), "0")
        return vol > 0

    @staticmethod
    def _is_verified_deposit(deal: Any) -> bool:
        """Broker cash/credit in. Never inferred from a balance increase."""
        vol = _dec(LiveAccountRiskTracker._deal_value(deal, "volume"), "0")
        if vol > 0:
            return False
        profit = _dec(LiveAccountRiskTracker._deal_value(deal, "profit"))
        if profit <= 0:
            return False
        raw_type = LiveAccountRiskTracker._deal_value(deal, "deal_type", "type")
        low = str(raw_type or "").strip().lower()
        if low in {"balance", "credit", "deposit"}:
            return True
        try:
            numeric = int(raw_type)
        except (TypeError, ValueError):
            numeric = -1
        return numeric in {2, 3}

    @staticmethod
    def session_pnl_resolution(
        deals: list[Any],
        *,
        now: datetime | None = None,
        ending_balance: Decimal | None = None,
    ) -> dict[str, Any]:
        """UTC-day trade P/L, optionally sliced after a verified deposit.

        Pre-deposit trade P/L is retained for audit. It is not deleted from
        broker history. Risk uses only post-baseline realized trade P/L.
        """
        day = utc_session_day(now)
        seen_trade: set[int] = set()
        seen_dep: set[int] = set()
        trades: list[tuple[datetime, int, Decimal]] = []
        deposits: list[tuple[datetime, int, Any]] = []
        for deal in deals:
            ticket = LiveAccountRiskTracker._deal_ticket(deal)
            moment = LiveAccountRiskTracker._deal_time(deal)
            if moment is None:
                continue
            if utc_session_day(moment) != day:
                continue
            if LiveAccountRiskTracker._is_verified_deposit(deal):
                if ticket > 0:
                    if ticket in seen_dep:
                        continue
                    seen_dep.add(ticket)
                deposits.append((moment, ticket, deal))
                continue
            if not LiveAccountRiskTracker._is_trade_deal(deal):
                continue
            if ticket > 0:
                if ticket in seen_trade:
                    continue
                seen_trade.add(ticket)
            trades.append(
                (moment, ticket, LiveAccountRiskTracker._deal_cash_delta(deal))
            )
        session_trade = sum((p for _t, _k, p in trades), Decimal("0"))
        baseline: dict[str, Any] | None = None
        cutoff: tuple[datetime, int] | None = None
        if deposits:
            deposits.sort(key=lambda row: (row[0], row[1]))
            moment, ticket, dep = deposits[-1]
            cutoff = (moment, ticket)
            before: Decimal | None = None
            after: Decimal | None = None
            amount = LiveAccountRiskTracker._deal_cash_delta(dep)
            if ending_balance is not None:
                snapshots = LiveAccountRiskTracker._balance_around_deals(
                    deals, ending_balance=ending_balance
                )
                pair = snapshots.get(ticket)
                if pair is not None:
                    before, after = pair
            baseline = {
                "deposit_timestamp": moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "deposit_amount": str(amount),
                "balance_before": str(before) if before is not None else None,
                "balance_after": str(after) if after is not None else None,
                "broker_deal_ticket": ticket or None,
                "utc_date": day,
                "baseline_source": "mt5_balance_credit_deal",
                "deal_type": str(
                    LiveAccountRiskTracker._deal_value(dep, "deal_type", "type")
                    or "balance"
                ),
            }
        pre = Decimal("0")
        post = Decimal("0")
        for moment, ticket, pnl in trades:
            if cutoff is None:
                post += pnl
                continue
            cut_t, cut_k = cutoff
            if moment < cut_t or (moment == cut_t and ticket <= cut_k):
                pre += pnl
            else:
                post += pnl
        risk_pnl = post if cutoff is not None else session_trade
        return {
            "risk_daily_pnl": risk_pnl,
            "session_trade_pnl": session_trade,
            "pre_deposit_trade_pnl": pre if cutoff is not None else Decimal("0"),
            "post_deposit_trade_pnl": post if cutoff is not None else session_trade,
            "new_capital_detected": cutoff is not None,
            "capital_baseline": baseline,
        }

    @staticmethod
    def _balance_around_deals(
        deals: list[Any],
        *,
        ending_balance: Decimal,
    ) -> dict[int, tuple[Decimal, Decimal]]:
        """Walk cash deltas backward from live balance. Never invents a deposit."""
        ordered: list[tuple[datetime, int, Decimal, int]] = []
        for deal in deals:
            ticket = LiveAccountRiskTracker._deal_ticket(deal)
            if ticket <= 0:
                continue
            moment = LiveAccountRiskTracker._deal_time(deal)
            if moment is None:
                continue
            delta = LiveAccountRiskTracker._deal_cash_delta(deal)
            ordered.append((moment, ticket, delta, ticket))
        ordered.sort(key=lambda row: (row[0], row[1]), reverse=True)
        cursor = Decimal(str(ending_balance))
        out: dict[int, tuple[Decimal, Decimal]] = {}
        for _moment, ticket, delta, _k in ordered:
            after = cursor
            before = after - delta
            out[ticket] = (before, after)
            cursor = before
        return out

    @staticmethod
    def daily_pnl_from_deals(
        deals: list[Any],
        *,
        now: datetime | None = None,
        ending_balance: Decimal | None = None,
    ) -> Decimal:
        """Sum realized trade P/L for the current UTC session day.

        Deduplicates by ticket. Skips balance/credit/deposit as P/L. After a
        verified UTC-day deposit, only post-deposit trade P/L is returned.
        """
        resolved = LiveAccountRiskTracker.session_pnl_resolution(
            deals, now=now, ending_balance=ending_balance
        )
        return Decimal(str(resolved["risk_daily_pnl"]))

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
            self.daily_pnl_from_deals(
                list(deals or []), now=now, ending_balance=balance
            )
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
