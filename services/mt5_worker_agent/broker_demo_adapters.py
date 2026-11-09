"""Exness / HFM / Weltrade demo credential adapters for Windows MT5 workers.

Never invents server names. Never logs passwords. Demo and live env vars are
separated. A successful login must return a server matching the broker pattern.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Literal

BrokerSlug = Literal["exness", "hfm", "weltrade"]

_SUPPORTED: tuple[BrokerSlug, ...] = ("exness", "hfm", "weltrade")

# Pattern checks after MT5 returns account_info.server — not UI server lists.
_SERVER_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "exness": (re.compile(r"exness", re.I),),
    "hfm": (
        re.compile(r"hfmarkets", re.I),
        re.compile(r"\bhfm\b", re.I),
        re.compile(r"hotforex", re.I),
    ),
    "weltrade": (re.compile(r"weltrade", re.I),),
}


@dataclass(frozen=True, slots=True)
class DemoCredentialBundle:
    broker_slug: BrokerSlug
    environment: Literal["demo", "live"]
    login: str
    password: str
    server: str

    def public_dict(self) -> dict[str, str]:
        return {
            "broker_slug": self.broker_slug,
            "environment": self.environment,
            "login": self.login,
            "server": self.server,
            "password_included": "false",
        }


def supported_brokers() -> tuple[str, ...]:
    return tuple(_SUPPORTED)


def normalize_broker_slug(raw: str | None) -> BrokerSlug | None:
    code = (raw or "").strip().lower().replace("_", "-")
    if code in {"hf-markets", "hfmarkets", "hotforex"}:
        code = "hfm"
    if code in _SUPPORTED:
        return code  # type: ignore[return-value]
    return None


def _env(*keys: str) -> str:
    for key in keys:
        value = os.environ.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def resolve_demo_credentials(broker_slug: str) -> DemoCredentialBundle | None:
    """Resolve broker-specific demo credentials from env. Password never logged."""
    slug = normalize_broker_slug(broker_slug)
    if slug is None:
        return None
    prefix = {
        "exness": "QF_DEMO_EXNESS",
        "hfm": "QF_DEMO_HFM",
        "weltrade": "QF_DEMO_WELTRADE",
    }[slug]
    login = _env(f"{prefix}_LOGIN", "QF_DEMO_LOGIN")
    password = _env(f"{prefix}_PASSWORD", "QF_DEMO_PASSWORD")
    server = _env(f"{prefix}_SERVER", "QF_DEMO_SERVER")
    env_raw = _env(f"{prefix}_ENV", "QF_DEMO_ENV") or "demo"
    environment: Literal["demo", "live"] = (
        "live" if env_raw.lower() == "live" else "demo"
    )
    if not login or not password or not server:
        return None
    return DemoCredentialBundle(
        broker_slug=slug,
        environment=environment,
        login=login,
        password=password,
        server=server,
    )


def missing_credential_keys(broker_slug: str) -> list[str]:
    slug = normalize_broker_slug(broker_slug) or "exness"
    prefix = {
        "exness": "QF_DEMO_EXNESS",
        "hfm": "QF_DEMO_HFM",
        "weltrade": "QF_DEMO_WELTRADE",
    }.get(slug, "QF_DEMO")
    keys = [f"{prefix}_LOGIN", f"{prefix}_PASSWORD", f"{prefix}_SERVER"]
    # Also accept generic fallbacks — report generic if broker-specific absent.
    missing: list[str] = []
    for key in keys:
        generic = key.replace(prefix, "QF_DEMO")
        if not _env(key, generic):
            missing.append(f"{key} (or {generic})")
    return missing


def server_matches_broker(*, broker_slug: str, server: str) -> bool:
    slug = normalize_broker_slug(broker_slug)
    if slug is None:
        return False
    name = (server or "").strip()
    if not name:
        return False
    return any(pat.search(name) for pat in _SERVER_PATTERNS[slug])


def classify_environment(server: str) -> Literal["demo", "live"]:
    low = (server or "").lower()
    if any(tok in low for tok in ("demo", "trial")):
        return "demo"
    return "live"
