"""Portfolio allocation explainability — permanent why-share records."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.domain.institutional_trading.portfolio_intelligence.config import (
    DEFAULT_PI_CONFIG,
)
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AllocationExplanation:
    id: str
    at: str
    symbol: str
    share_pct: float
    why: str
    skipped: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PortfolioExplainStore:
    _rows: list[AllocationExplanation] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _path: Path | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._path is None:
            try:
                from core.config.settings import get_settings

                base = Path(getattr(get_settings(), "data_dir", None) or "data")
            except Exception:
                base = Path("data")
            self._path = base / "portfolio_allocation_explanations.json"

    def record_allocation(
        self,
        allocation: dict[str, Any],
        *,
        skipped_reasons: dict[str, str] | None = None,
    ) -> list[AllocationExplanation]:
        out: list[AllocationExplanation] = []
        for a in allocation.get("allocations") or []:
            expl = AllocationExplanation(
                id=str(uuid4()),
                at=datetime.now(UTC).isoformat(),
                symbol=str(a.get("symbol") or ""),
                share_pct=float(a.get("share_pct") or 0),
                why=f"Why {a.get('symbol')} received {a.get('share_pct')}%: {a.get('reason')}",
                skipped=False,
            )
            out.append(expl)
        for sym in allocation.get("skipped_symbols") or []:
            reason = (skipped_reasons or {}).get(sym, "ranked below deployable slots / correlation")
            out.append(
                AllocationExplanation(
                    id=str(uuid4()),
                    at=datetime.now(UTC).isoformat(),
                    symbol=str(sym),
                    share_pct=0.0,
                    why=f"Why {sym} received 0% / skipped: {reason}",
                    skipped=True,
                )
            )
        with self._lock:
            self._rows.extend(out)
            if len(self._rows) > DEFAULT_PI_CONFIG.max_explanations:
                self._rows = self._rows[-DEFAULT_PI_CONFIG.max_explanations :]
        self._persist()
        return out

    def _persist(self) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                payload = {
                    "updated_at": datetime.now(UTC).isoformat(),
                    "records": [r.to_dict() for r in self._rows[-DEFAULT_PI_CONFIG.max_explanations :]],
                }
            self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            logger.exception("portfolio_explain_persist_failed")

    def recent(self, *, limit: int = 40) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._rows[-max(1, limit) :]
        return [r.to_dict() for r in reversed(rows)]


_STORE: PortfolioExplainStore | None = None
_LOCK = threading.Lock()


def get_portfolio_explain_store() -> PortfolioExplainStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = PortfolioExplainStore()
        return _STORE
