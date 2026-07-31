"""Institutional Learning Engine (AI v8) — append-only structured observations.

Never overwrites historical evidence. Never changes production behaviour.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

_LOCK = threading.Lock()
_STORE: InstitutionalLearningEngine | None = None


def _iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass
class LearningObservation:
    """Structured post-trade observation — append-only evidence."""

    observed_at: str
    ticket: str | None
    symbol: str
    direction: str
    entry_reason: str | None
    exit_reason: str | None
    duration_minutes: float | None
    management_phase: str | None
    pnl: float | None
    win: bool | None
    execution_quality: str | None
    market_regime: str | None
    session: str | None
    volatility: str | None
    atr_pct: float | None
    spread: float | None
    liquidity: float | None
    quality: int | None
    confidence: int | None
    mtf: int | None
    correlation_group: str | None
    r_multiple: float | None
    mae_r: float | None
    mfe_r: float | None
    slippage: float | None
    extras: dict[str, Any] = field(default_factory=dict)
    fabricated: bool = False
    source: str = "real_completed_trade"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class InstitutionalLearningEngine:
    """Append-only observation journal (file-backed)."""

    max_records: int = 8000
    _records: list[dict[str, Any]] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _path: Path | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._path is None:
            try:
                from core.config.settings import get_settings

                base = Path(getattr(get_settings(), "data_dir", None) or "data")
            except Exception:
                base = Path("data")
            self._path = base / "institutional_learning_observations_v8.json"
        self._load()

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            rows = raw.get("observations", []) if isinstance(raw, dict) else []
            with self._lock:
                # Never overwrite — load then keep; truncate only by max window
                self._records = [r for r in rows if isinstance(r, dict)][
                    -self.max_records :
                ]
        except Exception:
            logger.exception("institutional_learning_load_failed")

    def _persist(self) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                payload = {
                    "updated_at": _iso(),
                    "version": "ai-v8-learning",
                    "observations": list(self._records[-self.max_records :]),
                    "overwrite_forbidden": True,
                }
            self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            logger.exception("institutional_learning_persist_failed")

    def observe(self, observation: LearningObservation) -> dict[str, Any]:
        row = observation.to_dict()
        row["fabricated"] = False
        with self._lock:
            self._records.append(row)
            if len(self._records) > self.max_records:
                # Drop oldest only — never rewrite prior rows in place
                self._records = self._records[-self.max_records :]
        self._persist()
        return row

    def snapshot(self, *, limit: int = 50) -> dict[str, Any]:
        with self._lock:
            rows = list(self._records)
        return {
            "count": len(rows),
            "recent": list(reversed(rows[-limit:])),
            "overwrite_forbidden": True,
            "auto_applies_to_strategy": False,
            "fabricated": False,
            "observe_only": True,
            "version": "ai-v8-learning",
        }


def get_institutional_learning_engine() -> InstitutionalLearningEngine:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = InstitutionalLearningEngine()
        return _STORE


def _f(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def observe_from_learning_trade(
    trade: Any,
    *,
    management_phase: str | None = None,
    liquidity: float | None = None,
    mtf: int | None = None,
    execution_quality: str | None = None,
    correlation_group: str | None = None,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build observation from LearningTradeRecord (or duck-typed equivalent)."""
    indicators = getattr(trade, "indicators", None)
    if not isinstance(indicators, dict):
        indicators = {}
    corr = correlation_group
    if corr is None:
        try:
            from app.domain.institutional_trading.ai_scalping.correlation_book import (
                correlation_group_name,
            )

            corr = correlation_group_name(str(getattr(trade, "symbol", "") or ""))
        except Exception:
            corr = None

    obs = LearningObservation(
        observed_at=_iso(),
        ticket=getattr(trade, "ticket", None),
        symbol=str(getattr(trade, "symbol", "") or "").upper(),
        direction=str(getattr(trade, "direction", "") or ""),
        entry_reason=getattr(trade, "entry_reason", None),
        exit_reason=getattr(trade, "exit_reason", None),
        duration_minutes=_f(getattr(trade, "holding_time_minutes", None)),
        management_phase=management_phase
        or str(indicators.get("management_reason") or "")
        or None,
        pnl=_f(getattr(trade, "pnl", None)),
        win=bool(getattr(trade, "win", False)),
        execution_quality=execution_quality,
        market_regime=getattr(trade, "regime", None),
        session=getattr(trade, "session", None),
        volatility=getattr(trade, "regime", None),
        atr_pct=_f(getattr(trade, "atr_pct", None)),
        spread=_f(getattr(trade, "spread", None)),
        liquidity=liquidity,
        quality=int(getattr(trade, "quality", 0) or 0) or None,
        confidence=int(getattr(trade, "confidence", 0) or 0) or None,
        mtf=(
            mtf
            if mtf is not None
            else (
                int(_f(indicators.get("mtf")) or 0) or None
                if indicators.get("mtf") is not None
                else None
            )
        ),
        correlation_group=corr,
        r_multiple=_f(getattr(trade, "r_multiple", None)),
        mae_r=_f(getattr(trade, "mae_r", None)),
        mfe_r=_f(getattr(trade, "mfe_r", None)),
        slippage=_f(getattr(trade, "slippage", None)),
        extras=dict(extras or {}),
    )
    return get_institutional_learning_engine().observe(obs)
