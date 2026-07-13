"""MT5 Broker Ecosystem v1.1 — retail brand profiles (documented, not live venues).

These are MT5 *broker brands* that connect through the existing MT5 adapter.
They are not separate connectivity platforms and never invent market data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

COMPATIBILITY_CHECKS: tuple[str, ...] = (
    "login",
    "account_sync",
    "balances",
    "equity",
    "positions",
    "pending_orders",
    "history",
    "symbols",
    "quotes",
    "candles",
    "paper_trading",
    "execution_checks",
)


@dataclass(frozen=True, slots=True)
class OnboardingStep:
    title: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"title": self.title, "detail": self.detail}


@dataclass(frozen=True, slots=True)
class MT5BrokerProfile:
    """Documented MT5 retail brand — compatibility via live MT5 session only."""

    slug: str
    name: str
    website: str
    platform: str = "mt5"
    regions: tuple[str, ...] = ()
    account_types: tuple[str, ...] = ()
    order_types: tuple[str, ...] = ()
    margin: bool = True
    leverage: bool = True
    netting: bool = True
    hedging: bool = True
    market_data: bool = True
    history: bool = True
    streaming: bool = False
    server_match_patterns: tuple[str, ...] = ()
    server_hints: tuple[str, ...] = ()
    onboarding: tuple[OnboardingStep, ...] = ()
    notes: str = ""
    priority: int = 100

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "name": self.name,
            "website": self.website,
            "platform": self.platform,
            "regions": list(self.regions),
            "account_types": list(self.account_types),
            "order_types": list(self.order_types),
            "margin": self.margin,
            "leverage": self.leverage,
            "netting": self.netting,
            "hedging": self.hedging,
            "market_data": self.market_data,
            "history": self.history,
            "streaming": self.streaming,
            "server_match_patterns": list(self.server_match_patterns),
            "server_hints": list(self.server_hints),
            "onboarding": [s.to_dict() for s in self.onboarding],
            "notes": self.notes,
            "priority": self.priority,
            "data_status": "documented_only",
            "connectivity": (
                "Uses live MetaTrader 5 adapter — no brand-specific socket. "
                "Operator must connect with credentials from the broker portal."
            ),
        }


def _mt5_onboarding(
    *,
    brand: str,
    website: str,
    search_terms: str,
    server_note: str,
) -> tuple[OnboardingStep, ...]:
    return (
        OnboardingStep(
            title="Open / verify account",
            detail=(
                f"Create or verify your {brand} trading account at {website}. "
                "Complete KYC per the broker's requirements."
            ),
        ),
        OnboardingStep(
            title="Install MetaTrader 5",
            detail=(
                "Install the official MetaTrader 5 terminal (desktop). "
                "QuantForg talks to the local MT5 terminal — not a fake feed."
            ),
        ),
        OnboardingStep(
            title="Locate the assigned MT5 server",
            detail=(
                f"Use the exact server name from your {brand} welcome email "
                f"or client portal. Search hints: {search_terms}. {server_note}"
            ),
        ),
        OnboardingStep(
            title="Connect in QuantForg",
            detail=(
                "Open /mt5 and submit login, password, and the exact server "
                "string. Prefer demo first. Never paste credentials into docs."
            ),
        ),
        OnboardingStep(
            title="Validate compatibility",
            detail=(
                "Open /broker-compatibility and run live checks after connect. "
                "Unavailable means no live session — not a fabricated pass."
            ),
        ),
        OnboardingStep(
            title="Paper then gated execution",
            detail=(
                "Use /paper for simulated fills inside QuantForg. Live "
                "execution stays behind EXECUTION_ENABLED and /execution/check."
            ),
        ),
    )


MT5_ECOSYSTEM: tuple[MT5BrokerProfile, ...] = (
    MT5BrokerProfile(
        slug="weltrade",
        name="Weltrade",
        website="https://www.weltrade.com",
        regions=("Global",),
        account_types=("standard", "pro", "demo"),
        order_types=("market", "limit", "stop", "stop_limit"),
        server_match_patterns=("weltrade",),
        server_hints=("Weltrade-MT5", "Weltrade-Demo"),
        onboarding=_mt5_onboarding(
            brand="Weltrade",
            website="https://www.weltrade.com",
            search_terms="Weltrade, Weltrade MT5",
            server_note=(
                "Server strings vary by entity/demo; copy the assigned value "
                "verbatim — do not invent a server name."
            ),
        ),
        notes="Priority MT5 retail brand — connectivity via MetaTrader 5 only.",
        priority=1,
    ),
    MT5BrokerProfile(
        slug="xm",
        name="XM",
        website="https://www.xm.com",
        regions=("Global", "EU", "AU", "JP"),
        account_types=("standard", "micro", "ultra_low", "demo"),
        order_types=("market", "limit", "stop", "stop_limit"),
        server_match_patterns=("xmglobal", "xm.com", "xmtrading", "xmau", "xm-"),
        server_hints=(
            "XMGlobal-MT5",
            "XMGlobal-Real",
            "XM.COM-Real",
            "XMTrading-Real",
        ),
        onboarding=_mt5_onboarding(
            brand="XM",
            website="https://www.xm.com",
            search_terms="XMGlobal, XM.COM, XMTrading, XMAU",
            server_note=(
                "Match brand prefix + Real/Demo + MT5. Wrong cluster rejects "
                "login even with correct password."
            ),
        ),
        notes="Priority MT5 retail brand — entity prefixes differ by region.",
        priority=2,
    ),
    MT5BrokerProfile(
        slug="exness",
        name="Exness",
        website="https://www.exness.com",
        regions=("Global",),
        account_types=("standard", "raw_spread", "zero", "pro", "demo"),
        order_types=("market", "limit", "stop", "stop_limit"),
        server_match_patterns=("exness",),
        server_hints=("Exness-MT5", "Exness-MT5Real", "Exness-Trial"),
        onboarding=_mt5_onboarding(
            brand="Exness",
            website="https://www.exness.com",
            search_terms="Exness, Exness MT5",
            server_note=(
                "Use the Personal Area server assignment. Demo and live "
                "clusters are distinct."
            ),
        ),
        notes="Priority MT5 retail brand — high leverage accounts still MT5-gated.",
        priority=3,
    ),
    MT5BrokerProfile(
        slug="ic-markets",
        name="IC Markets",
        website="https://www.icmarkets.com",
        regions=("Global", "EU", "SC"),
        account_types=("raw_spread", "standard", "cfd", "demo"),
        order_types=("market", "limit", "stop", "stop_limit"),
        server_match_patterns=("icmarkets", "icmarketssc", "icmarketseu"),
        server_hints=(
            "ICMarketsSC-MT5",
            "ICMarketsSC-MT5-2",
            "ICMarketsEU-MT5",
            "ICMarkets-Demo",
        ),
        onboarding=_mt5_onboarding(
            brand="IC Markets",
            website="https://www.icmarkets.com",
            search_terms="ICMarketsSC, ICMarketsEU, ICMarkets",
            server_note=(
                "MT5-2 / MT5-4 suffixes are load clusters, not better pricing. "
                "Use the cluster assigned to your login."
            ),
        ),
        notes="Priority MT5 ECN-style retail brand — MT5 path only in v1.1.",
        priority=4,
    ),
    MT5BrokerProfile(
        slug="pepperstone",
        name="Pepperstone",
        website="https://pepperstone.com",
        regions=("Global", "EU", "AU", "UK"),
        account_types=("razor", "standard", "demo"),
        order_types=("market", "limit", "stop", "stop_limit"),
        server_match_patterns=("pepperstone",),
        server_hints=(
            "Pepperstone-MT5-Live",
            "Pepperstone-MT5-Demo",
            "PepperstoneLtd-Live",
        ),
        onboarding=_mt5_onboarding(
            brand="Pepperstone",
            website="https://pepperstone.com",
            search_terms="Pepperstone, PepperstoneLtd",
            server_note=(
                "Entity (Ltd vs Global) and Live vs Demo must match the "
                "portal assignment."
            ),
        ),
        notes="Priority MT5 retail brand — Razor/Standard map to MT5 accounts.",
        priority=5,
    ),
)


def ecosystem_profiles() -> list[MT5BrokerProfile]:
    return sorted(MT5_ECOSYSTEM, key=lambda p: (p.priority, p.slug))


def ecosystem_as_dicts() -> list[dict[str, Any]]:
    return [p.to_dict() for p in ecosystem_profiles()]


def profile_by_slug(slug: str) -> MT5BrokerProfile | None:
    code = slug.strip().lower()
    for p in MT5_ECOSYSTEM:
        if p.slug == code:
            return p
    return None


def match_broker_for_server(server: str) -> MT5BrokerProfile | None:
    """Best-effort brand match from live MT5 server string — never invents."""
    hay = server.strip().lower().replace(" ", "")
    if not hay:
        return None
    hits: list[MT5BrokerProfile] = []
    for profile in MT5_ECOSYSTEM:
        for pattern in profile.server_match_patterns:
            needle = pattern.lower().replace(" ", "")
            if needle and needle in hay:
                hits.append(profile)
                break
    if not hits:
        return None
    return sorted(hits, key=lambda p: p.priority)[0]
