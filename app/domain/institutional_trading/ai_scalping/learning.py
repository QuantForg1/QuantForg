"""Self-learning store — record closed trades to improve future scoring."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from core.config.settings import get_settings
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class LearningTradeRecord:
    closed_at: str
    symbol: str
    direction: str
    session: str
    win: bool
    pnl: str
    confidence: int
    quality: int
    confluence: int
    spread: str | None
    atr_pct: str | None
    regime: str | None
    execution_ms: float | None
    ticket: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScalpingLearningStore:
    """In-process + optional JSON persistence for post-trade learning."""

    max_records: int = 5000
    _records: list[LearningTradeRecord] = field(default_factory=list)
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
            self._path = base / "ai_scalping_learning.json"
        self._load()

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            rows = raw.get("records", []) if isinstance(raw, dict) else raw
            loaded: list[LearningTradeRecord] = []
            for row in rows[-self.max_records :]:
                if not isinstance(row, dict):
                    continue
                loaded.append(
                    LearningTradeRecord(
                        closed_at=str(row.get("closed_at") or ""),
                        symbol=str(row.get("symbol") or "XAUUSD"),
                        direction=str(row.get("direction") or ""),
                        session=str(row.get("session") or ""),
                        win=bool(row.get("win")),
                        pnl=str(row.get("pnl") or "0"),
                        confidence=int(row.get("confidence") or 0),
                        quality=int(row.get("quality") or 0),
                        confluence=int(row.get("confluence") or 0),
                        spread=row.get("spread"),
                        atr_pct=row.get("atr_pct"),
                        regime=row.get("regime"),
                        execution_ms=(
                            float(row["execution_ms"])
                            if row.get("execution_ms") is not None
                            else None
                        ),
                        ticket=row.get("ticket"),
                    )
                )
            with self._lock:
                self._records = loaded
        except Exception:
            logger.exception("ai_scalping_learning_load_failed")

    def _persist(self) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                payload = {
                    "updated_at": datetime.now(UTC).isoformat(),
                    "records": [r.to_dict() for r in self._records[-self.max_records :]],
                }
            self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            logger.exception("ai_scalping_learning_persist_failed")

    def record(self, trade: LearningTradeRecord) -> None:
        with self._lock:
            self._records.append(trade)
            if len(self._records) > self.max_records:
                self._records = self._records[-self.max_records :]
        self._persist()
        logger.info(
            "ai_scalping_learning_recorded",
            win=trade.win,
            session=trade.session,
            confidence=trade.confidence,
        )

    def historical_similarity_bonus(
        self,
        *,
        session: str,
        confidence: int,
        regime: str | None,
        spread: Decimal | None = None,
    ) -> int:
        """Return 0–100 similarity prior from past outcomes (wins weighted up)."""
        with self._lock:
            rows = list(self._records)
        if not rows:
            return 55
        session_l = (session or "").lower()
        scored: list[float] = []
        for r in rows[-200:]:
            score = 0.0
            if r.session.lower() == session_l:
                score += 2.0
            if regime and r.regime == regime:
                score += 2.0
            if abs(r.confidence - confidence) <= 8:
                score += 1.5
            if spread is not None and r.spread:
                try:
                    if abs(Decimal(str(r.spread)) - spread) <= Decimal("0.25"):
                        score += 1.0
                except Exception:
                    pass
            if score <= 0:
                continue
            scored.append(score * (1.4 if r.win else 0.6))
        if not scored:
            return 55
        # Map average match strength → 40–90 band
        avg = sum(scored) / len(scored)
        return max(40, min(90, int(50 + avg * 6)))

    def summary(self) -> dict[str, Any]:
        with self._lock:
            rows = list(self._records)
        if not rows:
            return {
                "trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": None,
                "by_session": {},
            }
        wins = sum(1 for r in rows if r.win)
        by_session: dict[str, dict[str, int]] = {}
        for r in rows:
            bucket = by_session.setdefault(r.session or "unknown", {"wins": 0, "n": 0})
            bucket["n"] += 1
            if r.win:
                bucket["wins"] += 1
        return {
            "trades": len(rows),
            "wins": wins,
            "losses": len(rows) - wins,
            "win_rate": round(100.0 * wins / len(rows), 2),
            "by_session": by_session,
        }


_STORE: ScalpingLearningStore | None = None
_STORE_LOCK = threading.Lock()


def get_scalping_learning_store() -> ScalpingLearningStore:
    global _STORE
    with _STORE_LOCK:
        if _STORE is None:
            _STORE = ScalpingLearningStore()
        return _STORE
