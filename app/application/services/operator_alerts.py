"""Private operator alerts on Telegram — never the public signals channel.

Sends only to ``TELEGRAM_OPERATOR_CHAT_ID`` (a private chat with the owner)
through the same bot token as the public dispatcher, but over its own queue
and sender: no getUpdates polling, no reply threads, no shared dedupe store.

``OperatorWatch`` checks broker truth every 30 s and alerts on:
order opened / closed, rule violations on open positions, gateway or MT5
offline > 2 min (and recovery), robot (Railway) restart, Live Trading Control
paused for safety > 2 min (and resume), daily stop hit (weekly stop and
loss-streak pause only if those limits are ever re-enabled; both are 0 =
disabled since 2026-10-23), equity 30% below the owner reference, repeated
errors, and sends a daily summary at 17:15 UTC and a weekly summary on Friday.

Opened / closed trades are journaled in Supabase ``live_trade_journal`` so
nothing is lost on restart. Observability only: never sends orders, never
changes trading state, never raises into the trading loop.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx

from core.logging import get_logger

logger = get_logger(__name__)

WATCH_INTERVAL_S = 30.0
OFFLINE_ALERT_S = 120.0
SAFETY_PAUSE_ALERT_S = 120.0
EQUITY_DROP_ALERT_PCT = Decimal("30")
STOPS_CHECK_INTERVAL_S = 300.0
REPEAT_ERROR_COUNT = 5
REPEAT_ERROR_WINDOW_S = 600.0
REPEAT_ERROR_THROTTLE_S = 3600.0
VIOLATION_THROTTLE_S = 900.0
DAILY_SUMMARY_UTC = (17, 15)
WEEKLY_SUMMARY_UTC = (17, 20)  # Friday
_JOURNAL_TABLE = "live_trade_journal"
_TELEGRAM_API = "https://api.telegram.org"
_CENT = Decimal("0.01")


def _dec(value: Any, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value)) if value not in (None, "") else Decimal(default)
    except Exception:
        return Decimal(default)


def _money(value: Decimal) -> str:
    q = value.quantize(_CENT)
    return f"+${q}" if q > 0 else f"-${abs(q)}" if q < 0 else "$0.00"


# --- Sender -------------------------------------------------------------------


class OperatorTelegramSender:
    """Minimal private-chat sender with its own queue. Never raises."""

    def __init__(
        self,
        *,
        token: str | None,
        chat_id: str | None,
        post: Callable[[str, dict[str, Any]], Any] | None = None,
        max_attempts: int = 3,
    ) -> None:
        self._token = (token or "").strip()
        self._chat_id = (chat_id or "").strip()
        self._post = post
        self._max_attempts = max(1, max_attempts)
        self._queue: deque[str] = deque(maxlen=200)
        self._task: asyncio.Task[Any] | None = None

    @property
    def configured(self) -> bool:
        return bool(self._token and self._chat_id)

    def enqueue(self, text: str) -> None:
        self._queue.append(text)

    async def drain(self) -> None:
        while self._queue:
            text = self._queue.popleft()
            await self._send(text)

    async def _send(self, text: str) -> None:
        if not self.configured:
            return
        url = f"{_TELEGRAM_API}/bot{self._token}/sendMessage"
        payload = {
            "chat_id": self._chat_id,
            "text": text[:4000],
            "disable_web_page_preview": True,
        }
        delay = 1.0
        for attempt in range(1, self._max_attempts + 1):
            try:
                if self._post is not None:
                    resp = await self._post(url, payload)
                else:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        resp = await client.post(url, json=payload)
                status = int(getattr(resp, "status_code", 0) or 0)
                if 200 <= status < 300:
                    return
                logger.warning(
                    "operator_alert_send_http", status=status, attempt=attempt
                )
            except Exception as exc:
                # Never log the URL: it contains the bot token.
                logger.warning(
                    "operator_alert_send_failed",
                    error=type(exc).__name__,
                    attempt=attempt,
                )
            await asyncio.sleep(delay)
            delay *= 2


# --- Alerter (dedupe / throttle) -------------------------------------------------


class OperatorAlerter:
    def __init__(
        self,
        sender: OperatorTelegramSender,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._sender = sender
        self._clock = clock
        self._sent: dict[str, float] = {}
        self.history: deque[tuple[str, str]] = deque(maxlen=50)

    def alert(
        self, kind: str, text: str, *, key: str | None = None, throttle_s: float = 0.0
    ) -> bool:
        """Queue one alert. ``key`` + ``throttle_s`` suppress repeats."""
        dedupe = key or ""
        now = self._clock()
        if dedupe:
            last = self._sent.get(dedupe)
            if last is not None and (throttle_s <= 0 or now - last < throttle_s):
                return False
            self._sent[dedupe] = now
        message = f"QuantForg [{kind}]\n{text}"
        self.history.append((kind, message))
        logger.warning("operator_alert", kind=kind, text=text)
        self._sender.enqueue(message)
        _persist_alert(kind, text)
        return True


def _supabase_rest() -> tuple[str, str] | None:
    try:
        from app.application.services.ops_state_persistence import (
            _supabase_rest_config,
        )

        return _supabase_rest_config()
    except Exception:
        return None


def _persist_alert(kind: str, text: str) -> None:
    cfg = _supabase_rest()
    if cfg is None:
        return
    base, key = cfg
    try:
        httpx.post(
            f"{base}/ite_ops_alerts",
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Prefer": "return=minimal",
            },
            json={
                "kind": f"operator:{kind}"[:64],
                "severity": "critical" if kind in _CRITICAL else "warning",
                "message": text[:2000],
            },
            timeout=5.0,
        )
    except Exception as exc:
        logger.info("operator_alert_persist_failed", error=type(exc).__name__)


_CRITICAL = frozenset(
    {"RULE VIOLATION", "GATEWAY OFFLINE", "MT5 OFFLINE", "DAILY STOP", "WEEKLY STOP"}
)


# --- Trade journal ------------------------------------------------------------------


@dataclass
class JournalEntry:
    ticket: int
    symbol: str
    side: str
    volume: Decimal
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    spread: Decimal | None
    planned_risk_usd: Decimal | None
    equity_at_open: Decimal | None
    opened_at: datetime
    status: str = "OPEN"
    closed_at: datetime | None = None
    close_price: Decimal | None = None
    pnl: Decimal | None = None
    r_multiple: Decimal | None = None

    def to_row(self) -> dict[str, Any]:
        def s(v: Any) -> Any:
            if isinstance(v, Decimal):
                return str(v)
            if isinstance(v, datetime):
                return v.isoformat()
            return v

        return {k: s(v) for k, v in self.__dict__.items()}

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> JournalEntry:
        def d(k: str) -> Decimal | None:
            return _dec(row[k]) if row.get(k) not in (None, "") else None

        def t(k: str) -> datetime | None:
            raw = row.get(k)
            return datetime.fromisoformat(str(raw)) if raw else None

        return cls(
            ticket=int(row["ticket"]),
            symbol=str(row.get("symbol") or ""),
            side=str(row.get("side") or ""),
            volume=_dec(row.get("volume")),
            entry_price=_dec(row.get("entry_price")),
            stop_loss=_dec(row.get("stop_loss")),
            take_profit=_dec(row.get("take_profit")),
            spread=d("spread"),
            planned_risk_usd=d("planned_risk_usd"),
            equity_at_open=d("equity_at_open"),
            opened_at=t("opened_at") or datetime.now(UTC),
            status=str(row.get("status") or "OPEN"),
            closed_at=t("closed_at"),
            close_price=d("close_price"),
            pnl=d("pnl"),
            r_multiple=d("r_multiple"),
        )


class TradeJournal:
    """Supabase-backed journal with an in-memory mirror (fail-open)."""

    def __init__(self, *, rest: tuple[str, str] | None = None) -> None:
        self._rest = rest
        self.entries: dict[int, JournalEntry] = {}

    def _headers(self) -> dict[str, str]:
        assert self._rest is not None
        key = self._rest[1]
        return {"apikey": key, "Authorization": f"Bearer {key}"}

    def load(self, *, since: datetime) -> None:
        if self._rest is None:
            return
        try:
            resp = httpx.get(
                f"{self._rest[0]}/{_JOURNAL_TABLE}",
                headers=self._headers(),
                params={
                    "select": "*",
                    "or": f"(status.eq.OPEN,closed_at.gte.{since.isoformat()})",
                },
                timeout=10.0,
            )
            if resp.status_code == 200:
                for row in resp.json():
                    entry = JournalEntry.from_row(row)
                    self.entries[entry.ticket] = entry
        except Exception as exc:
            logger.warning("trade_journal_load_failed", error=type(exc).__name__)

    def save(self, entry: JournalEntry) -> None:
        self.entries[entry.ticket] = entry
        if self._rest is None:
            return
        try:
            httpx.post(
                f"{self._rest[0]}/{_JOURNAL_TABLE}",
                headers={
                    **self._headers(),
                    "Prefer": "resolution=merge-duplicates,return=minimal",
                },
                params={"on_conflict": "ticket"},
                json=entry.to_row(),
                timeout=10.0,
            )
        except Exception as exc:
            logger.warning("trade_journal_save_failed", error=type(exc).__name__)

    def open_entries(self) -> list[JournalEntry]:
        return [e for e in self.entries.values() if e.status == "OPEN"]

    def closed_between(self, start: datetime, end: datetime) -> list[JournalEntry]:
        return sorted(
            (
                e
                for e in self.entries.values()
                if e.status == "CLOSED" and e.closed_at and start <= e.closed_at < end
            ),
            key=lambda e: e.closed_at or e.opened_at,
        )


def summarize(entries: list[JournalEntry]) -> dict[str, Any]:
    """Trades, win rate, average R, P/L and max drawdown of closed trades."""
    pnls = [e.pnl for e in entries if e.pnl is not None]
    rs = [e.r_multiple for e in entries if e.r_multiple is not None]
    wins = sum(1 for p in pnls if p > 0)
    total = sum(pnls, Decimal("0"))
    peak = Decimal("0")
    run = Decimal("0")
    max_dd = Decimal("0")
    for p in pnls:
        run += p
        peak = max(peak, run)
        max_dd = max(max_dd, peak - run)
    return {
        "trades": len(pnls),
        "wins": wins,
        "win_rate": (Decimal(wins) / Decimal(len(pnls)) * 100).quantize(Decimal("0.1"))
        if pnls
        else None,
        "avg_r": (sum(rs, Decimal("0")) / Decimal(len(rs))).quantize(_CENT)
        if rs
        else None,
        "pnl": total.quantize(_CENT),
        "max_dd": max_dd.quantize(_CENT),
    }


def format_summary(title: str, stats: dict[str, Any], equity: Decimal | None) -> str:
    wr = f"{stats['win_rate']}%" if stats["win_rate"] is not None else "n/a"
    ar = f"{stats['avg_r']}R" if stats["avg_r"] is not None else "n/a"
    eq = f"${equity.quantize(_CENT)}" if equity is not None else "n/a"
    return (
        f"{title}\n"
        f"Trades: {stats['trades']} (wins {stats['wins']}) | Win rate: {wr}\n"
        f"Average R: {ar} | P/L: {_money(stats['pnl'])}\n"
        f"Max drawdown (closed trades): ${stats['max_dd']} | Equity: {eq}"
    )


# --- Repeated-error counter -------------------------------------------------------


class RepeatedErrorHandler(logging.Handler):
    """Counts ERROR records per event; alerts at 5 within 10 minutes."""

    def __init__(self, alerter: OperatorAlerter) -> None:
        super().__init__(level=logging.ERROR)
        self._alerter = alerter
        self._events: dict[str, deque[float]] = {}

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.msg
            event = msg.get("event") if isinstance(msg, dict) else record.getMessage()
            name = f"{record.name}:{str(event)[:80]}"
            if "operator_alert" in name:
                return
            now = time.monotonic()
            bucket = self._events.setdefault(name, deque())
            bucket.append(now)
            while bucket and now - bucket[0] > REPEAT_ERROR_WINDOW_S:
                bucket.popleft()
            if len(bucket) >= REPEAT_ERROR_COUNT:
                self._alerter.alert(
                    "REPEATED ERROR",
                    f"{len(bucket)}x in 10 min: {event}\nlogger: {record.name}",
                    key=f"err:{name}",
                    throttle_s=REPEAT_ERROR_THROTTLE_S,
                )
        except Exception:  # noqa: S110  # never let alerting break logging
            pass


# --- Watcher -----------------------------------------------------------------------


@dataclass
class _Down:
    since: float | None = None
    alerted: bool = False


@dataclass
class OperatorWatch:
    adapter: Any
    alerter: OperatorAlerter
    journal: TradeJournal
    clock: Callable[[], float] = time.monotonic
    now_utc: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    _gateway: _Down = field(default_factory=_Down)
    _mt5: _Down = field(default_factory=_Down)
    _ltc: _Down = field(default_factory=_Down)
    _stops_checked_at: float = -1e9
    _summary_marks: dict[str, str] = field(default_factory=dict)

    # -- public ------------------------------------------------------------------

    def startup(self, *, reason: str = "process start") -> None:
        sha = (os.environ.get("RAILWAY_GIT_COMMIT_SHA") or "")[:8] or "n/a"
        dep = (os.environ.get("RAILWAY_DEPLOYMENT_ID") or "")[:8] or "n/a"
        state = _ltc_state()
        self.journal.load(since=self.now_utc() - timedelta(days=8))
        self._summary_marks = _load_summary_marks()
        self.alerter.alert(
            "ROBOT RESTARTED",
            f"Robot process started ({reason}). commit {sha}, deployment {dep}.\n"
            f"Live Trading Control: {state}. Open journal trades: "
            f"{len(self.journal.open_entries())}.\n"
            "Positions are reconciled with MT5 before any new entry.",
        )

    def tick(self) -> None:
        """One synchronous pass (run in a worker thread). Never raises."""
        try:
            self._tick()
        except Exception as exc:
            logger.warning("operator_watch_tick_failed", error=type(exc).__name__)

    # -- internals ---------------------------------------------------------------

    def _tick(self) -> None:
        now = self.clock()
        utc = self.now_utc()
        try:
            health = self.adapter.health()
            account = self.adapter.account_info()
            gateway_ok = True
        except Exception as exc:
            gateway_ok = False
            health = None
            account = None
            reason = type(exc).__name__
        self._track(
            self._gateway,
            ok=gateway_ok,
            now=now,
            down_kind="GATEWAY OFFLINE",
            up_kind="GATEWAY RECOVERED",
            what="Gateway https://gateway.quantforg.com is unreachable from Railway"
            + ("" if gateway_ok else f" ({reason})")
            + ". New entries are blocked until it returns.",
        )
        if not gateway_ok:
            return
        mt5_ok = bool(getattr(health, "connected", False))
        self._track(
            self._mt5,
            ok=mt5_ok,
            now=now,
            down_kind="MT5 OFFLINE",
            up_kind="MT5 RECOVERED",
            what=(
                "MT5 terminal is not connected to the broker. New entries are blocked."
            ),
        )
        equity = _dec(getattr(account, "equity", None))
        balance = _dec(getattr(account, "balance", None))
        positions = list(self.adapter.list_positions() or [])
        self._positions(positions, equity=equity, utc=utc)
        self._ltc_watch(now=now)
        self._loss_streak()
        self._equity_drop(equity=equity, utc=utc)
        if now - self._stops_checked_at >= STOPS_CHECK_INTERVAL_S:
            self._stops_checked_at = now
            self._stops(balance=balance, utc=utc)
        self._summaries(equity=equity, utc=utc)

    def _track(
        self, d: _Down, *, ok: bool, now: float, down_kind: str, up_kind: str, what: str
    ) -> None:
        if ok:
            if d.alerted and d.since is not None:
                minutes = (now - d.since) / 60.0
                self.alerter.alert(up_kind, f"Back online after {minutes:.1f} min.")
            d.since = None
            d.alerted = False
            return
        if d.since is None:
            d.since = now
        if not d.alerted and now - d.since >= OFFLINE_ALERT_S:
            d.alerted = True
            self.alerter.alert(
                down_kind, f"{what}\nOffline for {(now - d.since) / 60:.1f} min."
            )

    def _positions(
        self, positions: list[Any], *, equity: Decimal, utc: datetime
    ) -> None:
        open_now = {int(p.ticket): p for p in positions}
        for ticket, pos in open_now.items():
            entry = self.journal.entries.get(ticket)
            if entry is None or entry.status != "OPEN":
                entry = self._open(pos, equity=equity, utc=utc)
            self._violations(pos, entry, equity=equity)
        for entry in self.journal.open_entries():
            if entry.ticket not in open_now:
                self._close(entry, utc=utc)

    def _open(self, pos: Any, *, equity: Decimal, utc: datetime) -> JournalEntry:
        from app.domain.institutional_trading.owner_live_limits import planned_risk_usd

        spread: Decimal | None = None
        try:
            tick = self.adapter.latest_tick(pos.symbol)
            bid, ask = (
                _dec(getattr(tick, "bid", None)),
                _dec(getattr(tick, "ask", None)),
            )
            if bid > 0 and ask > 0:
                spread = ask - bid
        except Exception:
            spread = None
        sl = _dec(pos.stop_loss)
        risk = None
        if sl > 0:
            risk = planned_risk_usd(
                stop_distance=abs(_dec(pos.open_price) - sl),
                spread=spread or Decimal("0"),
                contract_size=Decimal("100"),
                volume=_dec(pos.volume),
            )
        entry = JournalEntry(
            ticket=int(pos.ticket),
            symbol=str(pos.symbol),
            side=str(pos.side).upper(),
            volume=_dec(pos.volume),
            entry_price=_dec(pos.open_price),
            stop_loss=sl,
            take_profit=_dec(pos.take_profit),
            spread=spread,
            planned_risk_usd=risk,
            equity_at_open=equity if equity > 0 else None,
            opened_at=getattr(pos, "opened_at", None) or utc,
        )
        self.journal.save(entry)
        pct = (
            f" ({(risk / equity * 100).quantize(_CENT)}% of equity)"
            if risk is not None and equity > 0
            else ""
        )
        self.alerter.alert(
            "ORDER OPENED",
            f"#{entry.ticket} {entry.side} {entry.volume} {entry.symbol} "
            f"@ {entry.entry_price}\n"
            f"SL {entry.stop_loss} | TP {entry.take_profit} | spread "
            f"{spread.quantize(Decimal('0.001')) if spread is not None else 'n/a'}\n"
            f"Planned risk ${risk if risk is not None else 'n/a'}{pct}",
            key=f"open:{entry.ticket}",
        )
        return entry

    def _violations(self, pos: Any, entry: JournalEntry, *, equity: Decimal) -> None:
        from app.domain.institutional_trading.owner_live_limits import (
            OWNER_MAX_LOT,
            max_planned_risk_usd,
        )
        from app.domain.trading.gold_only import is_gold_symbol

        problems: list[str] = []
        if not is_gold_symbol(str(pos.symbol)):
            problems.append(f"non-Gold symbol {pos.symbol}")
        if _dec(pos.volume) > OWNER_MAX_LOT:
            problems.append(f"volume {pos.volume} > {OWNER_MAX_LOT}")
        if _dec(pos.stop_loss) <= 0:
            problems.append("missing stop loss")
        if _dec(pos.take_profit) <= 0:
            problems.append("missing take profit")
        if entry.planned_risk_usd is not None and equity > 0:
            cap = max_planned_risk_usd(equity)
            if entry.planned_risk_usd > cap:
                problems.append(
                    f"planned risk ${entry.planned_risk_usd} > 9% cap ${cap}"
                )
        for problem in problems:
            self.alerter.alert(
                "RULE VIOLATION",
                f"#{pos.ticket} {pos.symbol}: {problem}.\n"
                "Press Pause on /admin/live-trading and check the position in MT5.",
                key=f"viol:{pos.ticket}:{problem.split(' ')[0]}",
                throttle_s=VIOLATION_THROTTLE_S,
            )

    def _close(self, entry: JournalEntry, *, utc: datetime) -> None:
        try:
            deals = list(
                self.adapter.history_deals(
                    date_from=entry.opened_at - timedelta(minutes=5),
                    date_to=utc + timedelta(days=1),
                )
                or []
            )
        except Exception:
            return  # retry next tick
        outs = [
            d
            for d in deals
            if int(getattr(d, "position_id", 0) or 0) == entry.ticket
            and str(getattr(d, "deal_type", "")).lower()
            not in {"entry_in", "balance", "credit"}
        ]
        if not outs:
            return  # broker history not visible yet; retry next tick
        pnl = sum(
            (_dec(d.profit) + _dec(d.commission) + _dec(d.swap) for d in outs),
            Decimal("0"),
        )
        last = max(outs, key=lambda d: d.time)
        entry.status = "CLOSED"
        entry.closed_at = last.time
        entry.close_price = _dec(last.price)
        entry.pnl = pnl.quantize(_CENT)
        if entry.planned_risk_usd and entry.planned_risk_usd > 0:
            entry.r_multiple = (pnl / entry.planned_risk_usd).quantize(_CENT)
        self.journal.save(entry)
        r = f"{entry.r_multiple}R" if entry.r_multiple is not None else "n/a"
        self.alerter.alert(
            "ORDER CLOSED",
            f"#{entry.ticket} {entry.side} {entry.volume} {entry.symbol}\n"
            f"Entry {entry.entry_price} -> exit {entry.close_price} | "
            f"SL {entry.stop_loss} | TP {entry.take_profit}\n"
            f"P/L {_money(entry.pnl)} ({r})",
            key=f"close:{entry.ticket}",
        )

    def _ltc_watch(self, *, now: float) -> None:
        try:
            from app.domain.institutional_trading.live_trading_control import (
                get_live_trading_controller,
            )

            ctrl = get_live_trading_controller()
            state = str(ctrl.snapshot_state())
            safety = bool(ctrl.paused_for_safety or ctrl.recovered_from_enabled)
        except Exception:
            return
        paused_for_safety = state == "PAUSED" and safety
        self._track(
            self._ltc,
            ok=not paused_for_safety,
            now=now,
            down_kind="ROBOT PAUSED",
            up_kind="ROBOT RESUMED",
            what=(
                "Live Trading Control is PAUSED for safety (restart recovery or "
                "gateway/MT5 checks failing). It resumes by itself when checks pass."
            ),
        )

    def _loss_streak(self) -> None:
        from app.domain.institutional_trading.owner_live_limits import (
            OWNER_MAX_CONSECUTIVE_LOSSES,
        )

        if OWNER_MAX_CONSECUTIVE_LOSSES <= 0:
            return  # no loss-streak pause (owner 2026-10-23)
        try:
            from app.domain.institutional_trading.live_trading_control import (
                get_live_trading_controller,
            )

            ctrl = get_live_trading_controller()
            if not ctrl.loss_streak_cooldown_active():
                return
            until = ctrl.loss_streak_cooldown_until
        except Exception:
            return
        self.alerter.alert(
            "LOSS-STREAK PAUSE",
            f"{ctrl.consecutive_losses} consecutive losses: new entries paused until "
            f"{until.isoformat() if until else 'next UTC day'}.",
            key=f"streak:{until.isoformat() if until else ''}",
        )

    def _equity_drop(self, *, equity: Decimal, utc: datetime) -> None:
        from app.domain.institutional_trading.owner_live_limits import (
            OWNER_RISK_REFERENCE_USD,
        )

        ref = _dec(OWNER_RISK_REFERENCE_USD)
        if ref <= 0 or equity <= 0:
            return
        floor = ref * (Decimal("1") - EQUITY_DROP_ALERT_PCT / 100)
        if equity <= floor:
            self.alerter.alert(
                "EQUITY ALERT",
                f"Equity ${equity.quantize(_CENT)} is {EQUITY_DROP_ALERT_PCT}% or more "
                f"below the ${ref} reference (alert level ${floor.quantize(_CENT)}).",
                key=f"equity:{utc.date().isoformat()}",
            )

    def _stops(self, *, balance: Decimal, utc: datetime) -> None:
        from app.application.services.live_account_risk_tracker import (
            LiveAccountRiskTracker,
        )
        from app.domain.institutional_trading.owner_live_limits import (
            OWNER_DAILY_LOSS_PCT,
            OWNER_WEEKLY_LOSS_PCT,
            daily_loss_exceeded,
        )

        day = utc.replace(hour=0, minute=0, second=0, microsecond=0)
        week = day - timedelta(days=day.weekday())
        try:
            deals = list(
                self.adapter.history_deals(
                    date_from=week, date_to=utc + timedelta(days=1)
                )
                or []
            )
        except Exception:
            return
        daily = LiveAccountRiskTracker.daily_pnl_from_deals(
            deals, now=utc, ending_balance=balance
        )
        weekly = LiveAccountRiskTracker.trade_pnl_since(deals, since=week)
        if balance > 0 and daily_loss_exceeded(daily_pnl=daily, base_now=balance):
            self.alerter.alert(
                "DAILY STOP",
                f"Daily loss {_money(daily)} reached the "
                f"{OWNER_DAILY_LOSS_PCT}% daily stop. "
                "No new entries until 00:00 UTC.",
                key=f"daily:{day.date().isoformat()}",
            )
        # 0 = weekly limit disabled (owner 2026-10-23: daily stop only).
        if OWNER_WEEKLY_LOSS_PCT > 0 and balance > 0 and weekly < 0:
            pct = (-weekly) / (balance - weekly) * 100
            if pct > OWNER_WEEKLY_LOSS_PCT:
                self.alerter.alert(
                    "WEEKLY STOP",
                    f"Weekly loss {_money(weekly)} ({pct.quantize(_CENT)}%) "
                    "exceeds the "
                    f"{OWNER_WEEKLY_LOSS_PCT}% weekly stop. "
                    "No new entries until Monday 00:00 UTC.",
                    key=f"weekly:{week.date().isoformat()}",
                )

    def _summaries(self, *, equity: Decimal, utc: datetime) -> None:
        today = utc.date()
        h, m = DAILY_SUMMARY_UTC
        if (utc.hour, utc.minute) >= (h, m) and self._summary_marks.get(
            "daily"
        ) != today.isoformat():
            start = datetime.combine(today, datetime.min.time(), tzinfo=UTC)
            stats = summarize(
                self.journal.closed_between(start, start + timedelta(days=1))
            )
            self.alerter.alert(
                "DAILY SUMMARY",
                format_summary(
                    f"Daily summary {today.isoformat()} (UTC)", stats, equity
                ),
                key=f"daily_summary:{today.isoformat()}",
            )
            self._mark("daily", today)
        h, m = WEEKLY_SUMMARY_UTC
        if (
            today.weekday() == 4
            and (utc.hour, utc.minute) >= (h, m)
            and self._summary_marks.get("weekly") != today.isoformat()
        ):
            monday = today - timedelta(days=today.weekday())
            start = datetime.combine(monday, datetime.min.time(), tzinfo=UTC)
            stats = summarize(
                self.journal.closed_between(start, utc + timedelta(seconds=1))
            )
            self.alerter.alert(
                "WEEKLY SUMMARY",
                format_summary(
                    f"Weekly summary {monday.isoformat()} - {today.isoformat()}",
                    stats,
                    equity,
                ),
                key=f"weekly_summary:{today.isoformat()}",
            )
            self._mark("weekly", today)

    def _mark(self, which: str, day: date) -> None:
        self._summary_marks[which] = day.isoformat()
        try:
            from app.application.services.ops_state_persistence import save_ops_state

            save_ops_state({f"operator_last_{which}_summary": day.isoformat()})
        except Exception:
            logger.info("operator_summary_mark_persist_failed")


def _ltc_state() -> str:
    try:
        from app.domain.institutional_trading.live_trading_control import (
            get_live_trading_controller,
        )

        return str(get_live_trading_controller().snapshot_state())
    except Exception:
        return "unknown"


def _load_summary_marks() -> dict[str, str]:
    try:
        from app.application.services.ops_state_persistence import load_ops_state

        state = load_ops_state()
    except Exception:
        return {}
    marks: dict[str, str] = {}
    for which in ("daily", "weekly"):
        val = state.get(f"operator_last_{which}_summary")
        if val:
            marks[which] = str(val)
    return marks


# --- Wiring ----------------------------------------------------------------------


_watch: OperatorWatch | None = None


def get_operator_watch() -> OperatorWatch | None:
    return _watch


async def run_operator_watch(adapter: Any, settings: Any) -> None:
    """Long-running task started from the app lifespan. Never raises."""
    global _watch
    token_obj = getattr(settings, "telegram_bot_token", None)
    reveal = getattr(token_obj, "get_secret_value", None)
    token = reveal() if callable(reveal) else token_obj
    chat = getattr(settings, "telegram_operator_chat_id", "") or ""
    sender = OperatorTelegramSender(token=token, chat_id=chat)
    alerter = OperatorAlerter(sender)
    journal = TradeJournal(rest=_supabase_rest())
    watch = OperatorWatch(adapter=adapter, alerter=alerter, journal=journal)
    _watch = watch
    logging.getLogger().addHandler(RepeatedErrorHandler(alerter))
    logger.info("operator_watch_started", telegram_configured=sender.configured)
    await asyncio.to_thread(watch.startup)
    while True:
        try:
            await asyncio.to_thread(watch.tick)
            await sender.drain()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("operator_watch_loop_failed", error=type(exc).__name__)
        await asyncio.sleep(WATCH_INTERVAL_S)
