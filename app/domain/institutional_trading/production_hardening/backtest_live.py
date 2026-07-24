"""Backtest vs live performance comparison — highlight material deviations."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class StrategyPerfSnapshot:
    strategy_id: str
    backtest_win_rate: float | None = None
    live_win_rate: float | None = None
    backtest_avg_rr: float | None = None
    live_avg_rr: float | None = None
    backtest_expectancy: float | None = None
    live_expectancy: float | None = None
    updated_at: str = ""

    def deviations(self) -> dict[str, Any]:
        def _dev(a: float | None, b: float | None) -> float | None:
            if a is None or b is None:
                return None
            return round(b - a, 4)

        wr = _dev(self.backtest_win_rate, self.live_win_rate)
        rr = _dev(self.backtest_avg_rr, self.live_avg_rr)
        exp = _dev(self.backtest_expectancy, self.live_expectancy)
        material = False
        flags: list[str] = []
        if wr is not None and abs(wr) >= 10:
            material = True
            flags.append(f"win_rate Δ {wr}%")
        if rr is not None and abs(rr) >= 0.35:
            material = True
            flags.append(f"avg_rr Δ {rr}")
        if exp is not None and abs(exp) >= 0.2:
            material = True
            flags.append(f"expectancy Δ {exp}")
        return {
            "win_rate_delta": wr,
            "avg_rr_delta": rr,
            "expectancy_delta": exp,
            "material_deviation": material,
            "flags": flags,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "backtest_win_rate": self.backtest_win_rate,
            "live_win_rate": self.live_win_rate,
            "backtest_avg_rr": self.backtest_avg_rr,
            "live_avg_rr": self.live_avg_rr,
            "backtest_expectancy": self.backtest_expectancy,
            "live_expectancy": self.live_expectancy,
            "updated_at": self.updated_at,
            "deviations": self.deviations(),
        }


@dataclass
class BacktestLiveCompareStore:
    _rows: dict[str, StrategyPerfSnapshot] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _path: Path | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._path is None:
            try:
                from core.config.settings import get_settings

                base = Path(getattr(get_settings(), "data_dir", None) or "data")
            except Exception:
                base = Path("data")
            self._path = base / "backtest_live_compare.json"
        self._load()

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            for row in raw.get("strategies", []):
                if not isinstance(row, dict):
                    continue
                sid = str(row.get("strategy_id") or "production")
                self._rows[sid] = StrategyPerfSnapshot(
                    strategy_id=sid,
                    backtest_win_rate=row.get("backtest_win_rate"),
                    live_win_rate=row.get("live_win_rate"),
                    backtest_avg_rr=row.get("backtest_avg_rr"),
                    live_avg_rr=row.get("live_avg_rr"),
                    backtest_expectancy=row.get("backtest_expectancy"),
                    live_expectancy=row.get("live_expectancy"),
                    updated_at=str(row.get("updated_at") or ""),
                )
        except Exception:
            logger.exception("backtest_live_load_failed")

    def _persist(self) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                payload = {
                    "updated_at": datetime.now(UTC).isoformat(),
                    "strategies": [r.to_dict() for r in self._rows.values()],
                }
            self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            logger.exception("backtest_live_persist_failed")

    def upsert(
        self,
        strategy_id: str = "production",
        *,
        backtest_win_rate: float | None = None,
        live_win_rate: float | None = None,
        backtest_avg_rr: float | None = None,
        live_avg_rr: float | None = None,
        backtest_expectancy: float | None = None,
        live_expectancy: float | None = None,
    ) -> StrategyPerfSnapshot:
        with self._lock:
            cur = self._rows.get(strategy_id) or StrategyPerfSnapshot(strategy_id=strategy_id)
            snap = StrategyPerfSnapshot(
                strategy_id=strategy_id,
                backtest_win_rate=(
                    backtest_win_rate
                    if backtest_win_rate is not None
                    else cur.backtest_win_rate
                ),
                live_win_rate=(
                    live_win_rate if live_win_rate is not None else cur.live_win_rate
                ),
                backtest_avg_rr=(
                    backtest_avg_rr if backtest_avg_rr is not None else cur.backtest_avg_rr
                ),
                live_avg_rr=live_avg_rr if live_avg_rr is not None else cur.live_avg_rr,
                backtest_expectancy=(
                    backtest_expectancy
                    if backtest_expectancy is not None
                    else cur.backtest_expectancy
                ),
                live_expectancy=(
                    live_expectancy
                    if live_expectancy is not None
                    else cur.live_expectancy
                ),
                updated_at=datetime.now(UTC).isoformat(),
            )
            self._rows[strategy_id] = snap
        self._persist()
        return snap

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            rows = [r.to_dict() for r in self._rows.values()]
        material = [r for r in rows if r.get("deviations", {}).get("material_deviation")]
        return {
            "strategies": rows,
            "material_deviations": material,
            "count": len(rows),
        }


_STORE: BacktestLiveCompareStore | None = None
_LOCK = threading.Lock()


def get_backtest_live_store() -> BacktestLiveCompareStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = BacktestLiveCompareStore()
        return _STORE
