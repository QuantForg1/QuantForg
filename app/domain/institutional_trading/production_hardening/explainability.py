"""AI trade explainability — permanent why-* records for every execution."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.domain.institutional_trading.production_hardening.config import (
    DEFAULT_HARDENING_CONFIG,
)
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TradeExplanation:
    id: str
    created_at: str
    symbol: str
    direction: str
    ticket: str | None
    why_entered: str
    why_risk_pct: str
    why_lot_size: str
    why_tp: str
    why_sl: str
    why_confidence: str
    why_symbol: str
    why_session: str
    why_regime: str
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TradeExplainabilityStore:
    max_records: int = DEFAULT_HARDENING_CONFIG.explainability_max_records
    _rows: list[TradeExplanation] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _path: Path | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._path is None:
            try:
                from core.config.settings import get_settings

                base = Path(getattr(get_settings(), "data_dir", None) or "data")
            except Exception:
                base = Path("data")
            self._path = base / "trade_explanations.json"
        self._load()

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            rows = raw.get("records", []) if isinstance(raw, dict) else []
            loaded: list[TradeExplanation] = []
            for row in rows[-self.max_records :]:
                if not isinstance(row, dict):
                    continue
                loaded.append(
                    TradeExplanation(
                        id=str(row.get("id") or uuid4()),
                        created_at=str(row.get("created_at") or ""),
                        symbol=str(row.get("symbol") or ""),
                        direction=str(row.get("direction") or ""),
                        ticket=row.get("ticket"),
                        why_entered=str(row.get("why_entered") or ""),
                        why_risk_pct=str(row.get("why_risk_pct") or ""),
                        why_lot_size=str(row.get("why_lot_size") or ""),
                        why_tp=str(row.get("why_tp") or ""),
                        why_sl=str(row.get("why_sl") or ""),
                        why_confidence=str(row.get("why_confidence") or ""),
                        why_symbol=str(row.get("why_symbol") or ""),
                        why_session=str(row.get("why_session") or ""),
                        why_regime=str(row.get("why_regime") or ""),
                        extras=dict(row.get("extras") or {}),
                    )
                )
            with self._lock:
                self._rows = loaded
        except Exception:
            logger.exception("trade_explainability_load_failed")

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
            logger.exception("trade_explainability_persist_failed")

    def record(self, explanation: TradeExplanation) -> TradeExplanation:
        with self._lock:
            self._rows.append(explanation)
            if len(self._rows) > self.max_records:
                self._rows = self._rows[-self.max_records :]
        self._persist()
        logger.info(
            "trade_explanation_stored",
            id=explanation.id,
            symbol=explanation.symbol,
            ticket=explanation.ticket,
        )
        return explanation

    def recent(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._rows[-max(1, limit) :]
        return [r.to_dict() for r in reversed(rows)]


_STORE: TradeExplainabilityStore | None = None
_LOCK = threading.Lock()


def get_explainability_store() -> TradeExplainabilityStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = TradeExplainabilityStore()
        return _STORE


def build_explanation(
    *,
    symbol: str,
    direction: str,
    ticket: str | None = None,
    why_entered: str,
    why_risk_pct: str,
    why_lot_size: str,
    why_tp: str,
    why_sl: str,
    why_confidence: str,
    why_symbol: str,
    why_session: str,
    why_regime: str,
    extras: dict[str, Any] | None = None,
) -> TradeExplanation:
    return TradeExplanation(
        id=str(uuid4()),
        created_at=datetime.now(UTC).isoformat(),
        symbol=symbol,
        direction=direction,
        ticket=ticket,
        why_entered=why_entered,
        why_risk_pct=why_risk_pct,
        why_lot_size=why_lot_size,
        why_tp=why_tp,
        why_sl=why_sl,
        why_confidence=why_confidence,
        why_symbol=why_symbol,
        why_session=why_session,
        why_regime=why_regime,
        extras=dict(extras or {}),
    )
