"""Research Workspace — isolated strategy variants (never affect live trading)."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ResearchVariant:
    id: str
    name: str
    author: str
    created_at: str
    scoring_weights: dict[str, float] = field(default_factory=dict)
    indicators: list[str] = field(default_factory=list)
    filters: dict[str, Any] = field(default_factory=dict)
    ai_model_ref: str | None = None
    notes: str = ""
    isolated: bool = True
    affects_production: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["affects_production"] = False
        d["isolated"] = True
        return d


@dataclass
class ResearchWorkspaceStore:
    _variants: list[ResearchVariant] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _path: Path | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._path is None:
            try:
                from core.config.settings import get_settings

                base = Path(getattr(get_settings(), "data_dir", None) or "data")
            except Exception:
                base = Path("data")
            self._path = base / "research_workspace_v10.json"
        self._load()

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            rows = []
            for row in raw.get("variants", []):
                if isinstance(row, dict):
                    rows.append(
                        ResearchVariant(
                            id=str(row.get("id") or uuid4()),
                            name=str(row.get("name") or ""),
                            author=str(row.get("author") or ""),
                            created_at=str(row.get("created_at") or ""),
                            scoring_weights=dict(row.get("scoring_weights") or {}),
                            indicators=list(row.get("indicators") or []),
                            filters=dict(row.get("filters") or {}),
                            ai_model_ref=row.get("ai_model_ref"),
                            notes=str(row.get("notes") or ""),
                            isolated=True,
                            affects_production=False,
                        )
                    )
            with self._lock:
                self._variants = rows
        except Exception:
            logger.exception("research_workspace_load_failed")

    def _persist(self) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                payload = {
                    "updated_at": datetime.now(UTC).isoformat(),
                    "variants": [v.to_dict() for v in self._variants],
                }
            self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            logger.exception("research_workspace_persist_failed")

    def add_variant(
        self,
        *,
        name: str,
        author: str,
        scoring_weights: dict[str, float] | None = None,
        indicators: list[str] | None = None,
        filters: dict[str, Any] | None = None,
        ai_model_ref: str | None = None,
        notes: str = "",
    ) -> ResearchVariant:
        v = ResearchVariant(
            id=str(uuid4()),
            name=name,
            author=author,
            created_at=datetime.now(UTC).isoformat(),
            scoring_weights=dict(scoring_weights or {}),
            indicators=list(indicators or []),
            filters=dict(filters or {}),
            ai_model_ref=ai_model_ref,
            notes=notes,
            isolated=True,
            affects_production=False,
        )
        with self._lock:
            self._variants.append(v)
        self._persist()
        logger.info("research_variant_created", id=v.id, affects_production=False)
        return v

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return [v.to_dict() for v in reversed(self._variants)]


_STORE: ResearchWorkspaceStore | None = None
_LOCK = threading.Lock()


def get_research_workspace() -> ResearchWorkspaceStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = ResearchWorkspaceStore()
        return _STORE
