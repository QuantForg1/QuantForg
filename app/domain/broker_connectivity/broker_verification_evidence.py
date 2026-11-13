"""Broker MT5 verification evidence — no passwords, no invented servers.

A broker becomes ``connectable`` only when a Windows worker records a
successful authenticated demo (or live) verification for that slug.
Weltrade remains production-verified independently of this store.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()

# Password-like keys are stripped from any inbound evidence payload.
_FORBIDDEN_KEYS = frozenset(
    {
        "password",
        "master_password",
        "investor_password",
        "secret",
        "token",
        "credential",
        "credentials",
    }
)


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def default_evidence_path() -> Path:
    raw = (os.environ.get("QF_BROKER_VERIFICATION_EVIDENCE_PATH") or "").strip()
    if raw:
        return Path(raw)
    return Path("var") / "mt5_broker_verification.json"


def _strip_secrets(payload: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in payload.items():
        k = str(key).lower()
        if k in _FORBIDDEN_KEYS or any(
            tok in k for tok in ("password", "secret", "token")
        ):
            continue
        if isinstance(value, dict):
            clean[key] = _strip_secrets(value)
        else:
            clean[key] = value
    return clean


def mask_login(login: str | int | None) -> str:
    text = str(login or "").strip()
    if not text:
        return ""
    if len(text) <= 4:
        return "***"
    return f"***{text[-4:]}"


def load_evidence(path: Path | None = None) -> dict[str, Any]:
    target = path or default_evidence_path()
    if not target.is_file():
        return {"brokers": {}, "updated_at": None, "version": 1}
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {"brokers": {}, "updated_at": None, "version": 1}
        brokers = raw.get("brokers")
        if not isinstance(brokers, dict):
            brokers = {}
        return {
            "brokers": brokers,
            "updated_at": raw.get("updated_at"),
            "version": int(raw.get("version") or 1),
        }
    except Exception:
        logger.exception("broker_verification_evidence_load_failed path=%s", target)
        return {"brokers": {}, "updated_at": None, "version": 1}


def save_evidence(store: dict[str, Any], path: Path | None = None) -> Path:
    target = path or default_evidence_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": int(store.get("version") or 1),
        "updated_at": _now_iso(),
        "brokers": store.get("brokers") or {},
    }
    tmp = target.with_suffix(target.suffix + ".tmp")
    with _LOCK:
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(target)
    return target


def record_verification_success(
    *,
    broker_slug: str,
    server: str,
    environment: str,
    login: str | int | None,
    trade_allowed: bool,
    market_data_ok: bool,
    balance: float | None = None,
    equity: float | None = None,
    currency: str = "",
    host_code: str = "",
    slot_id: str = "",
    worker_id: str = "",
    source: str = "windows_mt5_demo_verify",
    path: Path | None = None,
) -> dict[str, Any]:
    """Persist a successful verify. Never stores passwords."""
    slug = broker_slug.strip().lower()
    server_name = server.strip()
    if not slug or not server_name:
        raise ValueError("broker_slug and server are required")
    if not trade_allowed:
        raise ValueError("trade_allowed must be true for connectable evidence")

    env = environment.strip().lower()
    if env not in {"demo", "live"}:
        low = server_name.lower()
        if any(tok in low for tok in ("demo", "trial")):
            env = "demo"
        elif any(tok in low for tok in ("real", "live")):
            env = "live"
        else:
            raise ValueError(
                "environment must be demo or live — will not invent from server name"
            )

    store = load_evidence(path)
    brokers = dict(store.get("brokers") or {})
    entry = dict(brokers.get(slug) or {})
    servers = list(entry.get("servers") or [])
    # Replace same server name if re-verified.
    servers = [
        s for s in servers if str(s.get("name") or "").lower() != server_name.lower()
    ]
    servers.append(
        {
            "name": server_name,
            "environment": env,
            "source": source,
            "verified_at": _now_iso(),
            "login_masked": mask_login(login),
            "trade_allowed": True,
            "market_data_ok": bool(market_data_ok),
            "balance_observed": balance is not None,
            "equity_observed": equity is not None,
            "currency": currency,
            "host_code": host_code,
            "slot_id": slot_id,
            "worker_id": worker_id,
        }
    )
    entry.update(
        {
            "broker_slug": slug,
            "connectable": True,
            "connection_status": (
                "demo_verified" if env == "demo" else "live_verified"
            ),
            "servers": servers,
            "last_success_at": _now_iso(),
            "last_error": "",
        }
    )
    brokers[slug] = entry
    store["brokers"] = brokers
    save_evidence(store, path)
    return entry


def record_verification_failure(
    *,
    broker_slug: str,
    error: str,
    server: str = "",
    host_code: str = "",
    slot_id: str = "",
    path: Path | None = None,
) -> dict[str, Any]:
    """Record a failed attempt without inventing connectable=true."""
    slug = broker_slug.strip().lower()
    store = load_evidence(path)
    brokers = dict(store.get("brokers") or {})
    entry = dict(brokers.get(slug) or {})
    history = list(entry.get("failure_history") or [])
    history.append(
        {
            "at": _now_iso(),
            "error": (error or "unknown")[:200],
            "server": server.strip()[:128],
            "host_code": host_code,
            "slot_id": slot_id,
        }
    )
    entry.update(
        {
            "broker_slug": slug,
            "connectable": bool(entry.get("connectable")),
            "connection_status": entry.get("connection_status") or "not_verified",
            "servers": list(entry.get("servers") or []),
            "last_error": (error or "unknown")[:200],
            "last_failure_at": _now_iso(),
            "failure_history": history[-20:],
        }
    )
    brokers[slug] = entry
    store["brokers"] = brokers
    save_evidence(store, path)
    return entry


def evidence_for_broker(slug: str, path: Path | None = None) -> dict[str, Any] | None:
    store = load_evidence(path)
    row = (store.get("brokers") or {}).get(slug.strip().lower())
    return dict(row) if isinstance(row, dict) else None


def discovered_servers_from_evidence(
    path: Path | None = None,
) -> dict[str, list[str]]:
    store = load_evidence(path)
    out: dict[str, list[str]] = {}
    for slug, entry in (store.get("brokers") or {}).items():
        if not isinstance(entry, dict):
            continue
        names: list[str] = []
        for server in entry.get("servers") or []:
            if not isinstance(server, dict):
                continue
            name = str(server.get("name") or "").strip()
            if name:
                names.append(name)
        if names:
            out[str(slug)] = names
    return out


def connectable_slugs_from_evidence(path: Path | None = None) -> set[str]:
    store = load_evidence(path)
    out: set[str] = set()
    for slug, entry in (store.get("brokers") or {}).items():
        if isinstance(entry, dict) and entry.get("connectable") is True:
            out.add(str(slug).lower())
    return out


def ingest_worker_report(
    payload: dict[str, Any], path: Path | None = None
) -> dict[str, Any]:
    """Accept a redacted worker verification report."""
    clean = _strip_secrets(dict(payload or {}))
    slug = str(clean.get("broker_slug") or "").strip().lower()
    ok = bool(clean.get("ok"))
    if not slug:
        raise ValueError("broker_slug is required")
    if ok:
        return record_verification_success(
            broker_slug=slug,
            server=str(clean.get("server") or ""),
            environment=str(clean.get("environment") or "demo"),
            login=clean.get("login") or clean.get("login_masked"),
            trade_allowed=bool(clean.get("trade_allowed")),
            market_data_ok=bool(clean.get("market_data_ok")),
            balance=(
                clean.get("balance")
                if isinstance(clean.get("balance"), (int, float))
                else None
            ),
            equity=(
                clean.get("equity")
                if isinstance(clean.get("equity"), (int, float))
                else None
            ),
            currency=str(clean.get("currency") or ""),
            host_code=str(clean.get("host_code") or ""),
            slot_id=str(clean.get("slot_id") or ""),
            worker_id=str(clean.get("worker_id") or ""),
            source=str(clean.get("source") or "windows_mt5_demo_verify"),
            path=path,
        )
    return record_verification_failure(
        broker_slug=slug,
        error=str(clean.get("error") or "verification_failed"),
        server=str(clean.get("server") or ""),
        host_code=str(clean.get("host_code") or ""),
        slot_id=str(clean.get("slot_id") or ""),
        path=path,
    )


def ops_snapshot(path: Path | None = None) -> dict[str, Any]:
    store = load_evidence(path)
    brokers = store.get("brokers") or {}
    return {
        "updated_at": store.get("updated_at"),
        "brokers": brokers,
        "connectable_slugs": sorted(connectable_slugs_from_evidence(path)),
        "credentials_exposed": False,
        "note": (
            "Evidence is written only after a real Windows MT5 authenticate+verify. "
            "Passwords are never stored."
        ),
    }
