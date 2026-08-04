"""Per-strategy LIVE production statistics (file-backed, no DB migration)."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.config.settings import get_settings
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class StrategyProductionStats:
    strategy_id: str
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
    peak_equity_delta: float = 0.0
    trough_equity_delta: float = 0.0
    running_pnl: float = 0.0
    max_drawdown: float = 0.0
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["win_rate"] = self.win_rate
        d["profit_factor"] = self.profit_factor
        d["avg_hold"] = self.avg_hold
        d["avg_rr"] = self.avg_rr
        d["avg_latency_ms"] = self.avg_latency_ms
        return d

    @property
    def win_rate(self) -> float | None:
        n = self.wins + self.losses
        return round(100.0 * self.wins / n, 2) if n else None

    @property
    def profit_factor(self) -> float | None:
        if self.gross_loss > 0:
            return round(self.gross_profit / self.gross_loss, 3)
        if self.gross_profit > 0:
            return None
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

    @property
    def avg_latency_ms(self) -> float | None:
        return (
            round(self.latency_ms_sum / self.latency_count, 2)
            if self.latency_count
            else None
        )


@dataclass
class StrategyStatsBook:
    _by_id: dict[str, StrategyProductionStats] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _path: Path | None = field(default=None, repr=False)

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
            self._path = base / "scalping_strategy_production_stats.json"
        self._load()

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            rows = raw.get("strategies", {}) if isinstance(raw, dict) else {}
            loaded: dict[str, StrategyProductionStats] = {}
            for sid, row in rows.items():
                if not isinstance(row, dict):
                    continue
                loaded[str(sid)] = StrategyProductionStats(
                    strategy_id=str(sid),
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
                    peak_equity_delta=float(row.get("peak_equity_delta") or 0),
                    trough_equity_delta=float(row.get("trough_equity_delta") or 0),
                    running_pnl=float(row.get("running_pnl") or 0),
                    max_drawdown=float(row.get("max_drawdown") or 0),
                    updated_at=str(row.get("updated_at") or ""),
                )
            with self._lock:
                self._by_id = loaded
        except Exception:
            logger.exception("strategy_production_stats_load_failed")

    def _persist(self) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                payload = {
                    "updated_at": datetime.now(UTC).isoformat(),
                    "strategies": {k: v.to_dict() for k, v in self._by_id.items()},
                }
            self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            logger.exception("strategy_production_stats_persist_failed")

    def _row(self, strategy_id: str) -> StrategyProductionStats:
        sid = str(strategy_id)
        row = self._by_id.get(sid)
        if row is None:
            row = StrategyProductionStats(strategy_id=sid)
            self._by_id[sid] = row
        return row

    def record_evaluation(self, strategy_id: str, *, passed: bool) -> None:
        with self._lock:
            row = self._row(strategy_id)
            row.scans += 1
            row.updated_at = datetime.now(UTC).isoformat()
            if passed:
                row.eligible += 1
            else:
                row.rejected += 1
        self._persist()

    def record_accepted(self, strategy_id: str, *, latency_ms: float | None = None) -> None:
        with self._lock:
            row = self._row(strategy_id)
            row.accepted += 1
            row.updated_at = datetime.now(UTC).isoformat()
            if latency_ms is not None:
                row.latency_ms_sum += float(latency_ms)
                row.latency_count += 1
        self._persist()

    def record_closed(
        self,
        strategy_id: str,
        *,
        win: bool,
        pnl: float,
        hold_minutes: float | None = None,
        r_multiple: float | None = None,
    ) -> None:
        with self._lock:
            row = self._row(strategy_id)
            row.updated_at = datetime.now(UTC).isoformat()
            pnl_f = float(pnl)
            row.running_pnl += pnl_f
            row.peak_equity_delta = max(row.peak_equity_delta, row.running_pnl)
            row.trough_equity_delta = min(row.trough_equity_delta, row.running_pnl)
            dd = row.peak_equity_delta - row.running_pnl
            row.max_drawdown = max(row.max_drawdown, dd)
            if win:
                row.wins += 1
                row.gross_profit += max(0.0, pnl_f)
            else:
                row.losses += 1
                row.gross_loss += abs(min(0.0, pnl_f))
            if hold_minutes is not None:
                row.hold_minutes_sum += float(hold_minutes)
                row.hold_count += 1
            if r_multiple is not None:
                row.rr_sum += float(r_multiple)
                row.rr_count += 1
        self._persist()

    def live_rank_boosts(self) -> dict[str, float]:
        """AI ranking boost from LIVE outcomes only (−20..+25)."""
        with self._lock:
            rows = list(self._by_id.values())
        out: dict[str, float] = {}
        for r in rows:
            score = 0.0
            if r.scans >= 10:
                elig_rate = r.eligible / max(1, r.scans)
                score += (elig_rate - 0.02) * 40.0
            closed = r.wins + r.losses
            if closed >= 2 and r.win_rate is not None:
                score += (r.win_rate - 50.0) * 0.35
            if r.profit_factor is not None:
                score += max(-12.0, min(18.0, (r.profit_factor - 1.0) * 10.0))
            elif r.gross_profit > 0 and r.gross_loss == 0 and closed >= 1:
                score += 12.0
            if r.max_drawdown > 0:
                score -= min(10.0, r.max_drawdown / 5.0)
            if r.accepted == 0 and r.scans >= 30 and r.eligible == 0:
                score -= 8.0
            out[r.strategy_id] = max(-20.0, min(25.0, score))
        return out

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            rows = [r.to_dict() for r in self._by_id.values()]
        boosts = self.live_rank_boosts()
        ranked = sorted(
            rows,
            key=lambda r: boosts.get(str(r.get("strategy_id")), 0.0),
            reverse=True,
        )
        return {
            "strategies": rows,
            "live_rank_boosts": boosts,
            "ranked": ranked,
        }


_BOOK: StrategyStatsBook | None = None
_LOCK = threading.Lock()


def get_strategy_stats_book() -> StrategyStatsBook:
    global _BOOK
    with _LOCK:
        if _BOOK is None:
            _BOOK = StrategyStatsBook()
        return _BOOK
