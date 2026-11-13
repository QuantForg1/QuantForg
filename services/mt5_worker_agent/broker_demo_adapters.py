"""MT5 broker credential adapters for Windows workers (eight-broker).

Canonical order: Weltrade, XM, Exness, HFM, JustMarkets, IC Markets,
Pepperstone, FP Markets.
Demo and Live env vars are separated. Passwords are never logged.
Server names are never invented — login must return a matching broker pattern.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Literal

BrokerSlug = Literal[
    "weltrade",
    "xm",
    "exness",
    "hfm",
    "justmarkets",
    "ic-markets",
    "pepperstone",
    "fp-markets",
]

# Stable product order — not alphabetical.
_SUPPORTED: tuple[BrokerSlug, ...] = (
    "weltrade",
    "xm",
    "exness",
    "hfm",
    "justmarkets",
    "ic-markets",
    "pepperstone",
    "fp-markets",
)

_ENV_PREFIX: dict[str, str] = {
    "weltrade": "WELTRADE",
    "xm": "XM",
    "exness": "EXNESS",
    "hfm": "HFM",
    "justmarkets": "JUSTMARKETS",
    "ic-markets": "IC_MARKETS",
    "pepperstone": "PEPPERSTONE",
    "fp-markets": "FP_MARKETS",
}

# Pattern checks after MT5 returns account_info.server — not UI server lists.
_SERVER_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "weltrade": (re.compile(r"weltrade", re.I),),
    "xm": (
        re.compile(r"xmglobal", re.I),
        re.compile(r"xm\.com", re.I),
        re.compile(r"xmtrading", re.I),
        re.compile(r"xmau", re.I),
        re.compile(r"xm-", re.I),
    ),
    "exness": (re.compile(r"exness", re.I),),
    "hfm": (
        re.compile(r"hfmarkets", re.I),
        re.compile(r"\bhfm\b", re.I),
        re.compile(r"hotforex", re.I),
    ),
    "justmarkets": (
        re.compile(r"justmarkets", re.I),
        re.compile(r"justmarketscy", re.I),
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
}


@dataclass(frozen=True, slots=True)
class DemoCredentialBundle:
    broker_slug: BrokerSlug
    environment: Literal["demo", "live"]
    login: str
    password: str
    server: str

    def public_dict(self) -> dict[str, str]:
        # Never include secret values or key names containing "password".
        return {
            "broker_slug": self.broker_slug,
            "environment": self.environment,
            "login": self.login,
            "server": self.server,
            "auth_material_present": "true" if self.password.strip() else "false",
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
        "justmarket": "justmarkets",
        "just-markets": "justmarkets",
        "justmarkets-cy": "justmarkets",
        "justmarketscy": "justmarkets",
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
    # Prefer env-specific, then DEMO_* legacy for demo only.
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
    """Resolve broker-specific credentials from env. Password never logged.

    Broker-specific requests never fall back to generic ``QF_DEMO_*`` so one
    broker's credentials cannot silently authenticate another broker.
    LIVE never falls back to DEMO material.
    """
    slug = normalize_broker_slug(broker_slug)
    if slug is None:
        return None
    prefixes = _prefix_keys(slug, environment)
    login = _env(*(f"{p}_LOGIN" for p in prefixes))
    password = _env(*(f"{p}_PASSWORD" for p in prefixes))
    server = _env(*(f"{p}_SERVER" for p in prefixes))
    resolved_env: Literal["demo", "live"] = "live" if environment == "live" else "demo"
    if environment == "live":
        live_only = _prefix_keys(slug, "live")
        login = _env(*(f"{p}_LOGIN" for p in live_only))
        password = _env(*(f"{p}_PASSWORD" for p in live_only))
        server = _env(*(f"{p}_SERVER" for p in live_only))
        if not login or not password or not server:
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
        if environment == "live":
            # LIVE never falls back to DEMO material.
            if not _env(key):
                missing.append(key)
            continue
        alts = [key, key.replace(primary, "QF_DEMO")]
        if not _env(*alts):
            missing.append(f"{key} (or QF_DEMO_* generic fallback)")
    return missing


def server_matches_broker(*, broker_slug: str, server: str) -> bool:
    slug = normalize_broker_slug(broker_slug)
    if slug is None:
        return False
    name = (server or "").strip()
    if not name:
        return False
    return any(pat.search(name) for pat in _SERVER_PATTERNS[slug])


def classify_environment_from_server(
    server: str,
) -> Literal["demo", "live", "unknown"]:
    """Heuristic only — never sole proof of account type."""
    low = (server or "").lower()
    if any(tok in low for tok in ("demo", "trial")):
        return "demo"
    if any(tok in low for tok in ("real", "live")):
        return "live"
    return "unknown"


def classify_environment(server: str) -> Literal["demo", "live"]:
    """Backward-compatible server-name heuristic.

    Ambiguous names (e.g. ``XMGlobal-MT5``) used to default to ``live``.
    Prefer :func:`resolve_account_environment` for verification evidence.
    """
    hint = classify_environment_from_server(server)
    if hint == "demo":
        return "demo"
    if hint == "live":
        return "live"
    # Ambiguous: do not invent live — caller must supply request/trade_mode.
    return "demo"


def resolve_account_environment(
    *,
    requested: Literal["demo", "live"],
    credential_environment: Literal["demo", "live"],
    server: str,
    trade_mode: int | None = None,
) -> tuple[Literal["demo", "live"], str]:
    """Classify account environment for evidence (never silent demo→live flip).

    Priority:
    1. MT5 ``account_info.trade_mode`` (0=demo, 1=contest, 2=real)
    2. Credential / request namespace (``QF_DEMO_*`` vs ``QF_LIVE_*``)
    3. Explicit server-name tokens (demo/trial/real/live)
    """
    if trade_mode is not None:
        mode = int(trade_mode)
        if mode == 0:
            return "demo", "mt5_account_trade_mode"
        if mode == 1:
            return "demo", "mt5_account_trade_mode_contest"
        if mode == 2:
            return "live", "mt5_account_trade_mode"

    # Explicit demo credentials / request must not become live from bare server.
    if requested == "demo" or credential_environment == "demo":
        hint = classify_environment_from_server(server)
        if hint == "demo":
            return "demo", "server_name_and_demo_request"
        return "demo", "demo_credential_namespace"

    hint = classify_environment_from_server(server)
    if hint == "demo":
        return "demo", "server_name_demo_token"
    if hint == "live":
        return "live", "server_name_and_live_request"
    return "live", "live_credential_namespace"


def account_type_mismatch(
    *,
    requested: Literal["demo", "live"],
    resolved: Literal["demo", "live"],
    trade_mode: int | None,
) -> str | None:
    """Fail closed when DEMO request authenticates a REAL MT5 account."""
    if trade_mode is not None and int(trade_mode) == 2 and requested == "demo":
        return "demo_request_authenticated_live_account"
    if requested == "demo" and resolved == "live":
        return "demo_request_resolved_as_live"
    if requested == "live" and resolved == "demo" and trade_mode == 0:
        return "live_request_authenticated_demo_account"
    return None
