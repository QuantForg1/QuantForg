"""Institutional Alpha analytics — sessions, symbols, latency, slippage."""

from __future__ import annotations

import json
import threading
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AlphaTradeAnalyticsRow:
    closed_at: str
    symbol: str
    session: str
    strategy: str
    win: bool
    pnl: float
    rr: float | None
    hold_minutes: float | None
    confidence: int | None
    opportunity_score: int | None
    execution_ms: float | None
    slippage: float | None
    spread: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AlphaAnalyticsStore:
    max_records: int = 5000
    _rows: list[AlphaTradeAnalyticsRow] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _path: Path | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._path is None:
            try:
                from core.config.settings import get_settings

                settings = get_settings()
                base = Path(
                    getattr(settings, "data_dir", None)
                    or getattr(settings, "ops_state_dir", None)
                    or "data"
                )
            except Exception:
                base = Path("data")
            self._path = base / "institutional_alpha_analytics.json"
        self._load()

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            rows = raw.get("records", []) if isinstance(raw, dict) else []
            loaded: list[AlphaTradeAnalyticsRow] = []
            for row in rows[-self.max_records :]:
                if not isinstance(row, dict):
                    continue
                loaded.append(
                    AlphaTradeAnalyticsRow(
                        closed_at=str(row.get("closed_at") or ""),
                        symbol=str(row.get("symbol") or ""),
                        session=str(row.get("session") or ""),
                        strategy=str(row.get("strategy") or "alpha"),
                        win=bool(row.get("win")),
                        pnl=float(row.get("pnl") or 0),
                        rr=float(row["rr"]) if row.get("rr") is not None else None,
                        hold_minutes=(
                            float(row["hold_minutes"])
                            if row.get("hold_minutes") is not None
                            else None
                        ),
                        confidence=(
                            int(row["confidence"])
                            if row.get("confidence") is not None
                            else None
                        ),
                        opportunity_score=(
                            int(row["opportunity_score"])
                            if row.get("opportunity_score") is not None
                            else None
                        ),
                        execution_ms=(
                            float(row["execution_ms"])
                            if row.get("execution_ms") is not None
                            else None
                        ),
                        slippage=(
                            float(row["slippage"])
                            if row.get("slippage") is not None
                            else None
                        ),
                        spread=(
                            float(row["spread"]) if row.get("spread") is not None else None
                        ),
                    )
                )
            with self._lock:
                self._rows = loaded
        except Exception:
            logger.exception("alpha_analytics_load_failed")

    def _persist(self) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                payload = {
                    "updated_at": datetime.now(UTC).isoformat(),
                    "records": [r.to_dict() for r in self._rows[-self.max_records :]],
                }
            self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            logger.exception("alpha_analytics_persist_failed")

    def record(self, row: AlphaTradeAnalyticsRow) -> None:
        with self._lock:
            self._rows.append(row)
            if len(self._rows) > self.max_records:
                self._rows = self._rows[-self.max_records :]
        self._persist()

    def summary(self) -> dict[str, Any]:
        with self._lock:
            rows = list(self._rows)
        if not rows:
            return {
                "trades": 0,
                "wins": 0,
                "win_rate": None,
                "avg_rr": None,
                "avg_hold_minutes": None,
                "avg_execution_ms": None,
                "avg_slippage": None,
                "avg_spread": None,
                "best_session": None,
                "worst_session": None,
                "best_symbol": None,
                "worst_symbol": None,
                "best_strategy": None,
                "worst_strategy": None,
                "daily_pnl": 0.0,
                "weekly_pnl": 0.0,
                "monthly_pnl": 0.0,
            }

        def _bucket_pnl(key_fn):
            buckets: dict[str, list[float]] = defaultdict(list)
            for r in rows:
                buckets[key_fn(r)].append(r.pnl)
            scored = {
                k: sum(v) for k, v in buckets.items() if k and k != "unknown"
            }
            if not scored:
                return None, None
            best = max(scored, key=scored.get)
            worst = min(scored, key=scored.get)
            return best, worst

        wins = sum(1 for r in rows if r.win)
        rrs = [r.rr for r in rows if r.rr is not None]
        holds = [r.hold_minutes for r in rows if r.hold_minutes is not None]
        lats = [r.execution_ms for r in rows if r.execution_ms is not None]
        slips = [r.slippage for r in rows if r.slippage is not None]
        spreads = [r.spread for r in rows if r.spread is not None]

        best_s, worst_s = _bucket_pnl(lambda r: r.session or "unknown")
        best_sym, worst_sym = _bucket_pnl(lambda r: r.symbol or "unknown")
        best_st, worst_st = _bucket_pnl(lambda r: r.strategy or "unknown")

        now = datetime.now(UTC)
        daily = weekly = monthly = 0.0
        for r in rows:
            try:
                ts = datetime.fromisoformat(r.closed_at.replace("Z", "+00:00"))
            except Exception:
                continue
            if ts.date() == now.date():
                daily += r.pnl
            if (now - ts).days <= 7:
                weekly += r.pnl
            if ts.year == now.year and ts.month == now.month:
                monthly += r.pnl

        def _avg(xs: list[float]) -> float | None:
            return round(sum(xs) / len(xs), 4) if xs else None

        return {
            "trades": len(rows),
            "wins": wins,
            "win_rate": round(100.0 * wins / len(rows), 2),
            "avg_rr": _avg(rrs),
            "avg_hold_minutes": _avg(holds),
            "avg_execution_ms": _avg(lats),
            "avg_slippage": _avg(slips),
            "avg_spread": _avg(spreads),
            "best_session": best_s,
            "worst_session": worst_s,
            "best_symbol": best_sym,
            "worst_symbol": worst_sym,
            "best_strategy": best_st,
            "worst_strategy": worst_st,
            "daily_pnl": round(daily, 2),
            "weekly_pnl": round(weekly, 2),
            "monthly_pnl": round(monthly, 2),
        }


_STORE: AlphaAnalyticsStore | None = None
_LOCK = threading.Lock()


def get_alpha_analytics_store() -> AlphaAnalyticsStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = AlphaAnalyticsStore()
        return _STORE
