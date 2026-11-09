"""MT5 broker credential adapters for Windows workers (six-broker + Weltrade).

Supports Exness, HFM, IC Markets, Pepperstone, FP Markets, XM, Weltrade.
Demo and Live env vars are separated. Passwords are never logged.
Server names are never invented — login must return a matching broker pattern.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Literal

BrokerSlug = Literal[
    "exness",
    "hfm",
    "ic-markets",
    "pepperstone",
    "fp-markets",
    "xm",
    "weltrade",
]

_SUPPORTED: tuple[BrokerSlug, ...] = (
    "exness",
    "hfm",
    "ic-markets",
    "pepperstone",
    "fp-markets",
    "xm",
    "weltrade",
)

_ENV_PREFIX: dict[str, str] = {
    "exness": "EXNESS",
    "hfm": "HFM",
    "ic-markets": "IC_MARKETS",
    "pepperstone": "PEPPERSTONE",
    "fp-markets": "FP_MARKETS",
    "xm": "XM",
    "weltrade": "WELTRADE",
}

# Pattern checks after MT5 returns account_info.server — not UI server lists.
_SERVER_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "exness": (re.compile(r"exness", re.I),),
    "hfm": (
        re.compile(r"hfmarkets", re.I),
        re.compile(r"\bhfm\b", re.I),
        re.compile(r"hotforex", re.I),
    ),
    "ic-markets": (
        re.compile(r"icmarkets", re.I),
        re.compile(r"icmarketssc", re.I),
        re.compile(r"icmarketseu", re.I),
    ),
    "pepperstone": (re.compile(r"pepperstone", re.I),),
    "fp-markets": (
        re.compile(r"fpmarkets", re.I),
        re.compile(r"firstprudential", re.I),
    ),
    "xm": (
        re.compile(r"xmglobal", re.I),
        re.compile(r"xm\.com", re.I),
        re.compile(r"xmtrading", re.I),
        re.compile(r"xmau", re.I),
        re.compile(r"xm-", re.I),
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
    aliases = {
        "hf-markets": "hfm",
        "hfmarkets": "hfm",
        "hotforex": "hfm",
        "icmarkets": "ic-markets",
        "ic": "ic-markets",
        "fpmarkets": "fp-markets",
        "fp": "fp-markets",
    }
    code = aliases.get(code, code)
    for slug in _SUPPORTED:
        if code == slug:
            return slug
    return None


def _env(*keys: str) -> str:
    for key in keys:
        value = os.environ.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _prefix_keys(
    slug: BrokerSlug, environment: Literal["demo", "live"]
) -> tuple[str, ...]:
    mid = _ENV_PREFIX[slug]
    env_tag = "DEMO" if environment == "demo" else "LIVE"
    # Prefer env-specific, then DEMO_* legacy for demo, then generic QF_DEMO_*.
    specific = f"QF_{env_tag}_{mid}"
    keys = [specific]
    if environment == "demo":
        keys.append(f"QF_DEMO_{mid}")
    return tuple(keys)


def resolve_credentials(
    broker_slug: str,
    *,
    environment: Literal["demo", "live"] = "demo",
) -> DemoCredentialBundle | None:
    """Resolve broker-specific credentials from env. Password never logged."""
    slug = normalize_broker_slug(broker_slug)
    if slug is None:
        return None
    prefixes = _prefix_keys(slug, environment)
    login = _env(*(f"{p}_LOGIN" for p in prefixes), "QF_DEMO_LOGIN")
    password = _env(*(f"{p}_PASSWORD" for p in prefixes), "QF_DEMO_PASSWORD")
    server = _env(*(f"{p}_SERVER" for p in prefixes), "QF_DEMO_SERVER")
    env_raw = _env(*(f"{p}_ENV" for p in prefixes), "QF_DEMO_ENV") or environment
    resolved_env: Literal["demo", "live"] = (
        "live" if env_raw.lower() == "live" else "demo"
    )
    if environment == "live" and resolved_env != "live":
        # Explicit live request must use live material when only demo is set.
        live_only = _prefix_keys(slug, "live")
        login = _env(*(f"{p}_LOGIN" for p in live_only)) or login
        password = _env(*(f"{p}_PASSWORD" for p in live_only)) or password
        server = _env(*(f"{p}_SERVER" for p in live_only)) or server
        if not _env(*(f"{p}_LOGIN" for p in live_only)):
            return None
        resolved_env = "live"
    if not login or not password or not server:
        return None
    return DemoCredentialBundle(
        broker_slug=slug,
        environment=resolved_env,
        login=login,
        password=password,
        server=server,
    )


def resolve_demo_credentials(broker_slug: str) -> DemoCredentialBundle | None:
    """Backward-compatible demo resolver."""
    return resolve_credentials(broker_slug, environment="demo")


def missing_credential_keys(
    broker_slug: str,
    *,
    environment: Literal["demo", "live"] = "demo",
) -> list[str]:
    slug = normalize_broker_slug(broker_slug) or "exness"
    mid = _ENV_PREFIX.get(slug, "DEMO")
    env_tag = "DEMO" if environment == "demo" else "LIVE"
    primary = f"QF_{env_tag}_{mid}"
    keys = [f"{primary}_LOGIN", f"{primary}_PASSWORD", f"{primary}_SERVER"]
    missing: list[str] = []
    for key in keys:
        alts = [key]
        if environment == "demo":
            alts.append(key.replace(f"QF_DEMO_{mid}", f"QF_DEMO_{mid}"))
            alts.append(key.replace(primary, "QF_DEMO"))
        if not _env(*alts):
            missing.append(f"{key} (or broker-specific / QF_DEMO_* fallback)")
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
