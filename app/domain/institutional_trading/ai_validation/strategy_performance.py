"""Strategy performance tracking — scalping / intraday / swing."""

from __future__ import annotations

import json
import math
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.domain.institutional_trading.ai_validation.config import STRATEGIES
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ClosedTradeSample:
    strategy: str
    pnl: float
    rr: float
    holding_seconds: float
    win: bool
    at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "pnl": self.pnl,
            "rr": self.rr,
            "holding_seconds": self.holding_seconds,
            "win": self.win,
            "at": self.at,
        }


def _normalize_strategy(raw: str | None) -> str:
    s = (raw or "swing").strip().lower()
    if s in {"scalp", "scalping", "ai_scalping"}:
        return "scalping"
    if s in {"intraday", "day", "daytrade"}:
        return "intraday"
    if s in {"alpha", "swing"}:
        return "swing" if s == "swing" else "swing"
    if s not in STRATEGIES:
        return "swing"
    return s


def _metrics(samples: list[ClosedTradeSample]) -> dict[str, Any]:
    if not samples:
        return {
            "trades": 0,
            "win_rate": None,
            "avg_rr": None,
            "avg_profit": None,
            "avg_loss": None,
            "profit_factor": None,
            "sharpe": None,
            "avg_holding_seconds": None,
        }
    wins = [s for s in samples if s.win]
    losses = [s for s in samples if not s.win]
    pnls = [s.pnl for s in samples]
    avg_win = sum(s.pnl for s in wins) / len(wins) if wins else None
    avg_loss = sum(s.pnl for s in losses) / len(losses) if losses else None
    gross_profit = sum(s.pnl for s in wins) if wins else 0.0
    gross_loss = abs(sum(s.pnl for s in losses)) if losses else 0.0
    pf = round(gross_profit / gross_loss, 3) if gross_loss > 0 else None
    mean = sum(pnls) / len(pnls)
    var = sum((p - mean) ** 2 for p in pnls) / len(pnls)
    std = math.sqrt(var) if var > 0 else 0.0
    sharpe = round(mean / std, 3) if std > 0 else None
    return {
        "trades": len(samples),
        "win_rate": round(100.0 * len(wins) / len(samples), 2),
        "avg_rr": round(sum(s.rr for s in samples) / len(samples), 3),
        "avg_profit": round(avg_win, 2) if avg_win is not None else None,
        "avg_loss": round(avg_loss, 2) if avg_loss is not None else None,
        "profit_factor": pf,
        "sharpe": sharpe,
        "avg_holding_seconds": round(
            sum(s.holding_seconds for s in samples) / len(samples), 1
        ),
    }


@dataclass
class StrategyPerformanceStore:
    _samples: list[ClosedTradeSample] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _path: Path | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._path is None:
            try:
                from core.config.settings import get_settings

                base = Path(getattr(get_settings(), "data_dir", None) or "data")
            except Exception:
                base = Path("data")
            self._path = base / "strategy_performance_v7.json"
        self._load()

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            rows = []
            for row in raw.get("samples", []):
                if not isinstance(row, dict):
                    continue
                rows.append(
                    ClosedTradeSample(
                        strategy=_normalize_strategy(str(row.get("strategy"))),
                        pnl=float(row.get("pnl") or 0),
                        rr=float(row.get("rr") or 0),
                        holding_seconds=float(row.get("holding_seconds") or 0),
                        win=bool(row.get("win")),
                        at=str(row.get("at") or ""),
                    )
                )
            with self._lock:
                self._samples = rows[-5_000:]
        except Exception:
            logger.exception("strategy_performance_load_failed")

    def _persist(self) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                payload = {
                    "updated_at": datetime.now(UTC).isoformat(),
                    "samples": [s.to_dict() for s in self._samples[-5_000:]],
                }
            self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            logger.exception("strategy_performance_persist_failed")

    def record_closed(
        self,
        *,
        strategy: str,
        pnl: float,
        rr: float = 0.0,
        holding_seconds: float = 0.0,
    ) -> None:
        sample = ClosedTradeSample(
            strategy=_normalize_strategy(strategy),
            pnl=float(pnl),
            rr=float(rr),
            holding_seconds=float(holding_seconds),
            win=pnl > 0,
            at=datetime.now(UTC).isoformat(),
        )
        with self._lock:
            self._samples.append(sample)
            if len(self._samples) > 5_000:
                self._samples = self._samples[-5_000:]
        self._persist()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            by: dict[str, list[ClosedTradeSample]] = {s: [] for s in STRATEGIES}
            for sample in self._samples:
                by.setdefault(sample.strategy, []).append(sample)
            per_strategy = {k: _metrics(v) for k, v in by.items()}
            all_m = _metrics(list(self._samples))
        return {
            "by_strategy": per_strategy,
            "combined": all_m,
            "strategies": list(STRATEGIES),
        }


_STORE: StrategyPerformanceStore | None = None
_LOCK = threading.Lock()


def get_strategy_performance_store() -> StrategyPerformanceStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = StrategyPerformanceStore()
        return _STORE
