"""Ticket-keyed strategy attribution — Signal → OMS → Fill → Close.

MT5 exit comments are overwritten with ``[sl]`` / ``[tp]`` and cannot be the
source of truth. Bind a *real* SOE five-pack ``strategy_id`` (never invented
``ite_primary``) to the broker ticket / position id at fill time, then resolve
on close — including partial closes.

Process memory + optional local JSON are a cache. Postgres is the durable
SoT when available so Railway restarts keep attribution. Unknown remains
unknown when no real strategy_id was bound.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

# Canonical five-pack IDs — used for confidence scoring, never invented at close.
FIVE_PACK_STRATEGY_IDS: frozenset[str] = frozenset(
    {
        "smc_scalping",
        "trend_continuation",
        "breakout_scalping",
        "range_mean_reversion",
        "momentum_scalping",
    }
)

_CREATE = """
CREATE TABLE IF NOT EXISTS public.strategy_attribution_binding (
    binding_key TEXT PRIMARY KEY,
    strategy_id TEXT NOT NULL,
    engine TEXT NOT NULL,
    strategy_name TEXT,
    symbol TEXT,
    ticket BIGINT,
    position_id BIGINT,
    broker_login BIGINT,
    remaining_volume NUMERIC,
    contributors JSONB NOT NULL DEFAULT '[]'::jsonb,
    meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'active',
    opened_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMPTZ
)
"""

_LOCKDOWN = """
DO $lock$
BEGIN
  EXECUTE 'ALTER TABLE public.strategy_attribution_binding ENABLE ROW LEVEL SECURITY';
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    EXECUTE 'REVOKE ALL ON TABLE public.strategy_attribution_binding FROM anon';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    EXECUTE
      'REVOKE ALL ON TABLE public.strategy_attribution_binding FROM authenticated';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
    EXECUTE 'GRANT ALL ON TABLE public.strategy_attribution_binding TO service_role';
  END IF;
END
$lock$;
"""

_UPSERT = """
INSERT INTO public.strategy_attribution_binding (
    binding_key, strategy_id, engine, strategy_name, symbol, ticket, position_id,
    broker_login, remaining_volume, contributors, meta, status, opened_at, updated_at
) VALUES (
    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, $11::jsonb, 'active', $12, NOW()
)
ON CONFLICT (binding_key) DO UPDATE SET
    strategy_id = EXCLUDED.strategy_id,
    engine = EXCLUDED.engine,
    strategy_name = EXCLUDED.strategy_name,
    symbol = COALESCE(EXCLUDED.symbol, public.strategy_attribution_binding.symbol),
    ticket = COALESCE(EXCLUDED.ticket, public.strategy_attribution_binding.ticket),
    position_id = COALESCE(
        EXCLUDED.position_id, public.strategy_attribution_binding.position_id
    ),
    broker_login = COALESCE(
        EXCLUDED.broker_login, public.strategy_attribution_binding.broker_login
    ),
    remaining_volume = EXCLUDED.remaining_volume,
    contributors = EXCLUDED.contributors,
    meta = EXCLUDED.meta,
    status = 'active',
    closed_at = NULL,
    updated_at = NOW()
"""

_SELECT_ACTIVE = """
SELECT binding_key, strategy_id, engine, strategy_name, symbol, ticket, position_id,
       broker_login, remaining_volume, contributors, meta, status, opened_at
FROM public.strategy_attribution_binding
WHERE status = 'active'
"""

_CLOSE = """
UPDATE public.strategy_attribution_binding
SET status = 'closed', closed_at = NOW(), updated_at = NOW(),
    remaining_volume = COALESCE($2, remaining_volume)
WHERE binding_key = ANY($1::text[]) AND status = 'active'
"""

_UPDATE_VOLUME = """
UPDATE public.strategy_attribution_binding
SET remaining_volume = $2, updated_at = NOW()
WHERE binding_key = ANY($1::text[]) AND status = 'active'
"""


@dataclass
class AttributionRecord:
    strategy_id: str
    engine: str  # soe | ite | m1 | unknown
    strategy_name: str | None = None
    symbol: str | None = None
    ticket: str | None = None
    position_id: str | None = None
    opened_at: str = ""
    remaining_volume: float | None = None
    broker_login: int | None = None
    contributors: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def attribution_confidence(self) -> str:
        sid = str(self.strategy_id or "").strip()
        if sid in FIVE_PACK_STRATEGY_IDS:
            return "bound_five_pack"
        if sid == "m1_micro":
            return "bound_m1"
        if sid:
            return "bound_other"
        return "unknown"


def is_five_pack_strategy_id(strategy_id: str | None) -> bool:
    return str(strategy_id or "").strip() in FIVE_PACK_STRATEGY_IDS


class StrategyAttributionStore:
    def __init__(self, path: Path | None = None) -> None:
        self._lock = threading.Lock()
        self._by_key: dict[str, AttributionRecord] = {}
        self._live_login: int | None = None
        if path is None:
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
            path = base / "strategy_attribution_bindings.json"
        self._path = path
        self._load()

    def set_live_login(self, login: int | None) -> None:
        with self._lock:
            self._live_login = int(login) if login else None

    def _testing(self) -> bool:
        return bool(os.environ.get("PYTEST_CURRENT_TEST"))

    def _use_postgres(self) -> bool:
        if self._testing():
            return False
        try:
            from app.infrastructure.persistence.direct_postgres import (
                direct_postgres_available,
            )

            return direct_postgres_available()
        except Exception:
            return False

    def _ensure_schema(self) -> None:
        from app.infrastructure.persistence.direct_postgres import execute

        execute(_CREATE)
        execute(_LOCKDOWN)

    def _load(self) -> None:
        if self._path.exists():
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                rows = raw.get("bindings", {}) if isinstance(raw, dict) else {}
                loaded: dict[str, AttributionRecord] = {}
                for key, row in rows.items():
                    if not isinstance(row, dict):
                        continue
                    rec = self._record_from_row(row)
                    if rec is None:
                        continue
                    loaded[str(key)] = rec
                with self._lock:
                    self._by_key = loaded
            except Exception:
                logger.exception("strategy_attribution_load_failed")
        if self._use_postgres():
            try:
                self.restore_from_postgres()
            except Exception:
                logger.exception("strategy_attribution_postgres_restore_failed")

    def _record_from_row(self, row: dict[str, Any]) -> AttributionRecord | None:
        sid = str(row.get("strategy_id") or "").strip()
        if not sid:
            return None
        contributors_raw = row.get("contributors") or []
        if isinstance(contributors_raw, str):
            try:
                contributors_raw = json.loads(contributors_raw)
            except Exception:
                contributors_raw = []
        contributors = [
            str(x).strip()
            for x in (contributors_raw if isinstance(contributors_raw, list) else [])
            if str(x).strip() and str(x).strip() != sid
        ]
        meta_raw = row.get("meta") or {}
        if isinstance(meta_raw, str):
            try:
                meta_raw = json.loads(meta_raw)
            except Exception:
                meta_raw = {}
        login = row.get("broker_login")
        return AttributionRecord(
            strategy_id=sid,
            engine=str(row.get("engine") or "unknown"),
            strategy_name=row.get("strategy_name"),
            symbol=row.get("symbol"),
            ticket=str(row["ticket"]) if row.get("ticket") not in (None, "") else None,
            position_id=(
                str(row["position_id"])
                if row.get("position_id") not in (None, "")
                else None
            ),
            opened_at=str(row.get("opened_at") or ""),
            remaining_volume=(
                float(row["remaining_volume"])
                if row.get("remaining_volume") is not None
                else None
            ),
            broker_login=int(login) if login not in (None, "") else None,
            contributors=contributors,
            meta=dict(meta_raw) if isinstance(meta_raw, dict) else {},
        )

    def _persist_file(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                payload = {
                    "updated_at": datetime.now(UTC).isoformat(),
                    "bindings": {k: v.to_dict() for k, v in self._by_key.items()},
                }
            self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            logger.exception("strategy_attribution_persist_failed")

    def restore_from_postgres(self) -> dict[str, Any]:
        """Reload active bindings from Postgres (startup / recovery)."""
        if not self._use_postgres():
            return {"trusted": False, "restored": 0, "reason": "postgres_unavailable"}
        self._ensure_schema()
        from app.infrastructure.persistence.direct_postgres import fetch

        rows = fetch(_SELECT_ACTIVE)
        loaded: dict[str, AttributionRecord] = {}
        for row in rows:
            rec = self._record_from_row(dict(row))
            if rec is None:
                continue
            key = str(row.get("binding_key") or "")
            if key:
                loaded[key] = rec
        with self._lock:
            # Postgres wins for durable keys; keep any local-only test keys.
            self._by_key.update(loaded)
            count = len(self._by_key)
        logger.warning(
            "strategy_attribution_restored",
            restored=len(loaded),
            total=count,
        )
        return {"trusted": True, "restored": len(loaded), "total": count}

    @staticmethod
    def _keys(ticket: Any = None, position_id: Any = None) -> list[str]:
        keys: list[str] = []
        for label, value in (("ticket", ticket), ("position", position_id)):
            text = str(value or "").strip()
            if text and text not in {"0", "None"}:
                keys.append(f"{label}:{text}")
        return keys

    def bind_fill(
        self,
        *,
        strategy_id: str,
        engine: str = "soe",
        strategy_name: str | None = None,
        symbol: str | None = None,
        ticket: Any = None,
        position_id: Any = None,
        volume: float | None = None,
        meta: dict[str, Any] | None = None,
        contributors: list[str] | None = None,
        broker_login: int | None = None,
    ) -> None:
        sid = str(strategy_id or "").strip()
        # Never invent fallback identities.
        if not sid or sid in {"ite_primary", "unknown", "none"}:
            return
        keys = self._keys(ticket=ticket, position_id=position_id)
        if not keys:
            return
        contrib = [
            str(c).strip()
            for c in (contributors or [])
            if str(c).strip() and str(c).strip() != sid
        ]
        login = int(broker_login) if broker_login else self._live_login
        opened = datetime.now(UTC).isoformat()
        record = AttributionRecord(
            strategy_id=sid,
            engine=str(engine or "unknown"),
            strategy_name=strategy_name,
            symbol=symbol,
            ticket=str(ticket) if ticket not in {None, ""} else None,
            position_id=str(position_id) if position_id not in {None, ""} else None,
            opened_at=opened,
            remaining_volume=float(volume) if volume is not None else None,
            broker_login=login,
            contributors=contrib,
            meta=dict(meta or {}),
        )
        with self._lock:
            for key in keys:
                self._by_key[key] = record
        self._persist_file()
        if self._use_postgres():
            try:
                self._ensure_schema()
                from app.infrastructure.persistence.direct_postgres import execute

                ticket_i = int(ticket) if str(ticket or "").isdigit() else None
                pos_i = int(position_id) if str(position_id or "").isdigit() else None
                for key in keys:
                    execute(
                        _UPSERT,
                        key,
                        sid,
                        record.engine,
                        record.strategy_name,
                        record.symbol,
                        ticket_i,
                        pos_i,
                        login,
                        record.remaining_volume,
                        json.dumps(contrib),
                        json.dumps(record.meta),
                        opened,
                    )
            except Exception:
                logger.exception("strategy_attribution_postgres_upsert_failed")

    def resolve(
        self, *, ticket: Any = None, position_id: Any = None
    ) -> AttributionRecord | None:
        with self._lock:
            for key in self._keys(ticket=ticket, position_id=position_id):
                hit = self._by_key.get(key)
                if hit is not None:
                    if (
                        self._live_login
                        and hit.broker_login
                        and hit.broker_login != self._live_login
                    ):
                        continue
                    return hit
        return None

    def note_partial_close(
        self,
        *,
        ticket: Any = None,
        position_id: Any = None,
        closed_volume: float | None = None,
        fully_closed: bool = False,
    ) -> AttributionRecord | None:
        """Keep binding across partial closes; drop only when fully flat."""
        record = self.resolve(ticket=ticket, position_id=position_id)
        if record is None:
            return None
        keys = self._keys(ticket=ticket, position_id=position_id)
        if fully_closed:
            self.clear(ticket=ticket, position_id=position_id)
            return record
        if closed_volume is not None and record.remaining_volume is not None:
            remaining = max(0.0, float(record.remaining_volume) - float(closed_volume))
            record.remaining_volume = remaining
            with self._lock:
                for key in keys:
                    if key in self._by_key:
                        self._by_key[key] = record
            self._persist_file()
            if self._use_postgres() and keys:
                try:
                    from app.infrastructure.persistence.direct_postgres import execute

                    execute(_UPDATE_VOLUME, keys, remaining)
                except Exception:
                    logger.exception("strategy_attribution_volume_update_failed")
            if remaining <= 0:
                self.clear(ticket=ticket, position_id=position_id)
        return record

    def clear(self, *, ticket: Any = None, position_id: Any = None) -> None:
        keys = self._keys(ticket=ticket, position_id=position_id)
        if not keys:
            return
        with self._lock:
            for key in keys:
                self._by_key.pop(key, None)
        self._persist_file()
        if self._use_postgres():
            try:
                from app.infrastructure.persistence.direct_postgres import execute

                execute(_CLOSE, keys, None)
            except Exception:
                logger.exception("strategy_attribution_postgres_close_failed")

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "count": len(self._by_key),
                "bindings": {k: v.to_dict() for k, v in self._by_key.items()},
                "live_login": self._live_login,
            }


_STORE: StrategyAttributionStore | None = None
_STORE_LOCK = threading.Lock()


def get_strategy_attribution_store() -> StrategyAttributionStore:
    global _STORE
    with _STORE_LOCK:
        if _STORE is None:
            _STORE = StrategyAttributionStore()
        return _STORE


def reset_strategy_attribution_store_for_tests(path: Path | None = None) -> None:
    global _STORE
    with _STORE_LOCK:
        target = path or Path("data") / "strategy_attribution_bindings.test.json"
        if target.exists():
            import contextlib

            with contextlib.suppress(OSError):
                target.unlink()
        _STORE = StrategyAttributionStore(path=target)


def recover_strategy_attribution_on_startup(
    adapter: Any | None = None,
) -> dict[str, Any]:
    """Restore durable bindings and pin the live broker login for isolation."""
    store = get_strategy_attribution_store()
    summary: dict[str, Any] = {"restored": 0, "trusted": False, "login": None}
    try:
        result = store.restore_from_postgres()
        summary.update(result)
    except Exception:
        logger.exception("strategy_attribution_startup_restore_failed")
    if adapter is not None:
        try:
            snap = adapter.account_snapshot()
            login = int(getattr(snap, "login", 0) or 0) or None
            store.set_live_login(login)
            summary["login"] = login
        except Exception:
            logger.exception("strategy_attribution_login_unavailable")
    logger.warning("strategy_attribution_startup_recover", **summary)
    return summary
