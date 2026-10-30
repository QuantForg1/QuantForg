"""Shadow mode: the robot trades on paper with live prices (owner 2026-10-24).

When ``QUANTFORG_SHADOW_MODE=true`` no robot entry reaches the broker. Every
entry that passed all live checks (owner guard, pre-send check on the exact
send tick, Risk Engine) is recorded here instead, at the checked request
price, and its outcome is followed with live prices: M1 bar high/low (plus
spread for the closing side) and the latest tick, SL before TP when both are
touched in one bar (conservative).

Limits applied as if live: one shadow position at a time and the owner daily
stop on shadow P/L. Gold / 0.01 lot / RR / spread / 14% / session are already
enforced upstream before an entry reaches the book. Never sends an order.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import ROUND_DOWN, Decimal
from threading import RLock
from typing import Any
from uuid import uuid4

from app.domain.institutional_trading.owner_live_limits import (
    OWNER_DAILY_LOSS_PCT,
    OWNER_MAX_PLANNED_RISK_PCT,
    reward_risk_after_spread,
)
from core.logging import get_logger

logger = get_logger(__name__)

CONTRACT_SIZE = Decimal("100")
_CENT = Decimal("0.01")
_PCT = Decimal("100")
_KEEP = 500


def utc_now() -> datetime:
    return datetime.now(UTC)


def shadow_mode_enabled() -> bool:
    raw = (os.environ.get("QUANTFORG_SHADOW_MODE") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


@dataclass
class ShadowTrade:
    id: str
    opened_at: datetime
    symbol: str
    side: str  # BUY | SELL
    volume: Decimal
    entry: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    spread: Decimal
    equity: Decimal
    plan_price: Decimal | None = None
    closed_at: datetime | None = None
    exit_price: Decimal | None = None
    outcome: str | None = None  # TP | SL
    pnl_usd: Decimal | None = None

    @property
    def planned_risk_usd(self) -> Decimal:
        return (
            (abs(self.entry - self.stop_loss) + self.spread)
            * CONTRACT_SIZE
            * self.volume
        )

    @property
    def rr(self) -> Decimal | None:
        return reward_risk_after_spread(
            tp_distance=abs(self.take_profit - self.entry),
            stop_distance=abs(self.entry - self.stop_loss),
            spread=self.spread,
        )

    @property
    def r_multiple(self) -> Decimal | None:
        risk = self.planned_risk_usd
        if self.pnl_usd is None or risk <= 0:
            return None
        return (self.pnl_usd / risk).quantize(Decimal("0.01"))

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        for k, v in list(out.items()):
            if isinstance(v, datetime):
                out[k] = v.isoformat()
            elif isinstance(v, Decimal):
                out[k] = str(v)
        out["planned_risk_usd"] = str(self.planned_risk_usd)
        out["r_multiple"] = (
            str(self.r_multiple) if self.r_multiple is not None else None
        )
        return out

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ShadowTrade:
        def dec(key: str) -> Decimal | None:
            v = raw.get(key)
            return Decimal(str(v)) if v not in (None, "") else None

        def dt(key: str) -> datetime | None:
            v = raw.get(key)
            return _utc(datetime.fromisoformat(str(v))) if v else None

        return cls(
            id=str(raw["id"]),
            opened_at=dt("opened_at") or datetime.now(UTC),
            symbol=str(raw.get("symbol") or ""),
            side=str(raw.get("side") or ""),
            volume=dec("volume") or Decimal("0"),
            entry=dec("entry") or Decimal("0"),
            stop_loss=dec("stop_loss") or Decimal("0"),
            take_profit=dec("take_profit") or Decimal("0"),
            spread=dec("spread") or Decimal("0"),
            equity=dec("equity") or Decimal("0"),
            plan_price=dec("plan_price"),
            closed_at=dt("closed_at"),
            exit_price=dec("exit_price"),
            outcome=raw.get("outcome"),
            pnl_usd=dec("pnl_usd"),
        )


@dataclass
class ShadowBook:
    trades: list[ShadowTrade] = field(default_factory=list)
    _lock: RLock = field(default_factory=RLock, repr=False)

    # -- queries -----------------------------------------------------------------

    def open_trade(self) -> ShadowTrade | None:
        with self._lock:
            return next((t for t in self.trades if t.closed_at is None), None)

    def realized_pnl_on(self, day: str) -> Decimal:
        with self._lock:
            return sum(
                (
                    t.pnl_usd
                    for t in self.trades
                    if t.closed_at is not None
                    and t.pnl_usd is not None
                    and t.closed_at.astimezone(UTC).date().isoformat() == day
                ),
                Decimal("0"),
            )

    def realized_pnl_total(self) -> Decimal:
        with self._lock:
            return sum(
                (t.pnl_usd for t in self.trades if t.pnl_usd is not None), Decimal("0")
            )

    def shadow_equity(self, real_equity: Decimal) -> Decimal:
        """Equity as if the shadow trades had been real (real + shadow P/L)."""
        return Decimal(str(real_equity)) + self.realized_pnl_total()

    def entry_block_reason(
        self,
        *,
        equity: Decimal,
        now: datetime,
        planned_risk_usd: Decimal | None = None,
    ) -> str | None:
        """Limits applied on shadow equity: 1 position, 14% cap, daily stop."""
        if self.open_trade() is not None:
            return "SHADOW_POSITION_OPEN: max 1 shadow position"
        eq = self.shadow_equity(equity)
        if eq <= 0:
            return "SHADOW_EQUITY_EXHAUSTED: shadow equity <= 0"
        cap = (eq * OWNER_MAX_PLANNED_RISK_PCT / _PCT).quantize(_CENT, ROUND_DOWN)
        if planned_risk_usd is not None and planned_risk_usd > cap:
            return (
                f"SHADOW_SL_RISK: planned risk {planned_risk_usd.quantize(_CENT)} "
                f"> {cap} ({OWNER_MAX_PLANNED_RISK_PCT}% of shadow equity {eq})"
            )
        day = _utc(now).astimezone(UTC).date().isoformat()
        pnl = self.realized_pnl_on(day)
        if pnl < 0:
            day_start = eq - pnl  # shadow equity before today's shadow losses
            if -pnl > day_start * OWNER_DAILY_LOSS_PCT / _PCT:
                return (
                    f"SHADOW_DAILY_STOP: shadow loss {(-pnl).quantize(_CENT)} > "
                    f"{OWNER_DAILY_LOSS_PCT}% of day-start {day_start.quantize(_CENT)}"
                )
        return None

    # -- mutations -----------------------------------------------------------------

    def record_entry(
        self,
        *,
        symbol: str,
        side: str,
        volume: Decimal,
        entry: Decimal,
        stop_loss: Decimal,
        take_profit: Decimal,
        bid: Decimal,
        ask: Decimal,
        equity: Decimal,
        plan_price: Decimal | None = None,
        now: datetime | None = None,
    ) -> ShadowTrade:
        trade = ShadowTrade(
            id=f"shadow-{uuid4().hex[:12]}",
            opened_at=_utc(now or datetime.now(UTC)),
            symbol=symbol,
            side=str(side).upper(),
            volume=Decimal(str(volume)),
            entry=Decimal(str(entry)),
            stop_loss=Decimal(str(stop_loss)),
            take_profit=Decimal(str(take_profit)),
            spread=Decimal(str(ask)) - Decimal(str(bid)),
            equity=Decimal(str(equity)),
            plan_price=plan_price,
        )
        with self._lock:
            self.trades.append(trade)
            del self.trades[:-_KEEP]
        logger.warning("shadow_order_opened", **trade.to_dict())
        return trade

    def _close(
        self, trade: ShadowTrade, *, price: Decimal, outcome: str, at: datetime
    ) -> None:
        trade.exit_price = price
        trade.outcome = outcome
        trade.closed_at = _utc(at)
        sign = Decimal("1") if trade.side == "BUY" else Decimal("-1")
        trade.pnl_usd = (
            sign * (price - trade.entry) * CONTRACT_SIZE * trade.volume
        ).quantize(Decimal("0.01"))
        logger.warning("shadow_order_closed", **trade.to_dict())

    def update(
        self,
        *,
        bars: list[tuple[datetime, Decimal, Decimal, Decimal]],
        bid: Decimal | None = None,
        ask: Decimal | None = None,
        now: datetime | None = None,
    ) -> ShadowTrade | None:
        """Close the open shadow trade on SL/TP touch. Returns it when closed.

        ``bars``: (UTC open time, bid high, bid low, spread) for M1 bars. Only
        bars opening after the entry minute count (the entry bar's earlier
        prices happened before the entry). SL is checked before TP.
        """
        trade = self.open_trade()
        if trade is None:
            return None
        start = trade.opened_at.replace(second=0, microsecond=0) + timedelta(minutes=1)
        sell = trade.side == "SELL"
        with self._lock:
            for t, hi, lo, sp in sorted(bars, key=lambda b: b[0]):
                if _utc(t) < start:
                    continue
                # A SELL closes at the ask (bid + spread); a BUY at the bid.
                close_hi = hi + sp if sell else hi
                close_lo = lo + sp if sell else lo
                sl_hit = (
                    close_hi >= trade.stop_loss if sell else close_lo <= trade.stop_loss
                )
                tp_hit = (
                    close_lo <= trade.take_profit
                    if sell
                    else close_hi >= trade.take_profit
                )
                if sl_hit:
                    self._close(trade, price=trade.stop_loss, outcome="SL", at=t)
                    return trade
                if tp_hit:
                    self._close(trade, price=trade.take_profit, outcome="TP", at=t)
                    return trade
            if bid is not None and ask is not None:
                px = Decimal(str(ask)) if sell else Decimal(str(bid))
                at = now or datetime.now(UTC)
                if (sell and px >= trade.stop_loss) or (
                    not sell and px <= trade.stop_loss
                ):
                    self._close(trade, price=trade.stop_loss, outcome="SL", at=at)
                    return trade
                if (sell and px <= trade.take_profit) or (
                    not sell and px >= trade.take_profit
                ):
                    self._close(trade, price=trade.take_profit, outcome="TP", at=at)
                    return trade
        return None

    # -- persistence -----------------------------------------------------------------

    def to_payload(self) -> dict[str, Any]:
        with self._lock:
            return {"shadow_trades": [t.to_dict() for t in self.trades[-_KEEP:]]}

    def hydrate(self, payload: dict[str, Any] | None) -> None:
        rows = (payload or {}).get("shadow_trades") or []
        with self._lock:
            self.trades = []
            for raw in rows:
                try:
                    self.trades.append(ShadowTrade.from_dict(raw))
                except (KeyError, TypeError, ValueError, ArithmeticError):
                    continue


_BOOK: ShadowBook | None = None
_BOOK_LOCK = RLock()


def get_shadow_book() -> ShadowBook:
    global _BOOK
    with _BOOK_LOCK:
        if _BOOK is None:
            book = ShadowBook()
            try:
                from app.application.services.ops_state_persistence import (
                    load_ops_state,
                )

                book.hydrate(load_ops_state())
            except Exception as exc:
                logger.warning("shadow_book_hydrate_failed", error=type(exc).__name__)
            _BOOK = book
        return _BOOK


def persist_shadow_book(book: ShadowBook | None = None) -> None:
    try:
        from app.application.services.ops_state_persistence import save_ops_state

        save_ops_state((book or get_shadow_book()).to_payload())
    except Exception as exc:
        logger.warning("shadow_book_persist_failed", error=type(exc).__name__)


def reset_shadow_book_for_tests() -> ShadowBook:
    global _BOOK
    with _BOOK_LOCK:
        _BOOK = ShadowBook()
        return _BOOK
