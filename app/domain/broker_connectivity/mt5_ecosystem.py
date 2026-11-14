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
                "Open /broker and submit your LIVE MT5 login, master password, "
                "and the exact server string from the broker portal. Demo remains "
                "optional. Never paste credentials into docs or chat."
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


# Canonical product order (priority 1-8). Do not sort alphabetically.
MT5_ECOSYSTEM: tuple[MT5BrokerProfile, ...] = (
    MT5BrokerProfile(
        slug="weltrade",
        name="Weltrade",
        website="https://www.weltrade.com",
        regions=("Global",),
        account_types=("standard", "pro", "demo"),
        order_types=("market", "limit", "stop", "stop_limit"),
        server_match_patterns=("weltrade",),
        # Weltrade-Real / Weltrade-Demo observed in native MT5 Open Account dialog.
        server_hints=("Weltrade-Real", "Weltrade-Demo", "Weltrade-MT5"),
        onboarding=_mt5_onboarding(
            brand="Weltrade",
            website="https://www.weltrade.com",
            search_terms="Weltrade, Weltrade-Real, Weltrade-Demo",
            server_note=(
                "Use Weltrade-Real (LIVE) or Weltrade-Demo from the MT5 Open "
                "Account server list — copy verbatim."
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
        # Numbered XMGlobal-MT5 N rows observed in native MT5 Open Account for
        # XM Global Limited. Environment is confirmed from MT5 account metadata
        # after login (e.g. "XMGlobal-MT5 2" may be DEMO; "XMGlobal-MT5 20" LIVE).
        server_hints=(
            "XMGlobal-MT5 2",
            "XMGlobal-MT5 4",
            "XMGlobal-MT5 5",
            "XMGlobal-MT5 6",
            "XMGlobal-MT5 7",
            "XMGlobal-MT5 8",
            "XMGlobal-MT5 9",
            "XMGlobal-MT5 10",
            "XMGlobal-MT5 11",
            "XMGlobal-MT5 12",
            "XMGlobal-MT5 13",
            "XMGlobal-MT5 14",
            "XMGlobal-MT5 15",
            "XMGlobal-MT5 16",
            "XMGlobal-MT5 17",
            "XMGlobal-MT5 18",
            "XMGlobal-MT5 19",
            "XMGlobal-MT5 20",
            "XMGlobal-MT5 21",
            "XMGlobal-MT5 22",
            "XMGlobal-MT5",
            "XMGlobal-Real",
            "XM.COM-Real",
            "XMTrading-Real",
        ),
        onboarding=_mt5_onboarding(
            brand="XM",
            website="https://www.xm.com",
            search_terms="XMGlobal-MT5, XM.COM, XMTrading",
            server_note=(
                "Pick the exact XMGlobal-MT5 N from the MT5 Open Account list "
                "or Personal Area. Do not assume LIVE from the number alone."
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
        # Exact Real/Trial names observed in native MT5 Open Account discovery
        # for Exness Technologies Ltd (screenshot evidence 2026-11-13). Still
        # CANDIDATE until authenticated verify; never invent unverified shards.
        server_hints=(
            "Exness-MT5Real10",
            "Exness-MT5Real",
            "Exness-MT5Real2",
            "Exness-MT5Real3",
            "Exness-MT5Real6",
            "Exness-MT5Real7",
            "Exness-MT5Real8",
            "Exness-MT5Real15",
            "Exness-MT5Real16",
            "Exness-MT5Real17",
            "Exness-MT5Real18",
            "Exness-MT5Real20",
            "Exness-MT5Real21",
            "Exness-MT5Real24",
            "Exness-MT5Real28",
            "Exness-MT5Real29",
            "Exness-MT5Real30",
            "Exness-MT5Real31",
            "Exness-MT5Real32",
            "Exness-MT5Real33",
            "Exness-MT5Real34",
            "Exness-MT5Real36",
            "Exness-MT5Real37",
            "Exness-MT5Real38",
            "Exness-MT5Real39",
            "Exness-MT5Real40",
            "Exness-MT5Real41",
            "Exness-MT5Real42",
            "Exness-MT5Real43",
            "Exness-MT5Real44",
            "Exness-MT5Real46",
            "Exness-MT5Real48",
            "Exness-MT5Real50",
            "Exness-MT5Real51",
            "Exness-MT5Trial2",
            "Exness-MT5Trial3",
            "Exness-MT5Trial4",
            "Exness-MT5Trial5",
            "Exness-MT5Trial7",
            "Exness-MT5Trial8",
            "Exness-MT5Trial10",
            "Exness-MT5Trial14",
            "Exness-MT5Trial15",
            "Exness-MT5Trial17",
            "ExnessSC-MT5Trial",
            "ExnessSC-MT5Real",
        ),
        onboarding=_mt5_onboarding(
            brand="Exness",
            website="https://www.exness.com",
            search_terms="Exness-MT5Real, Exness-MT5Trial",
            server_note=(
                "Select the exact Exness-MT5RealN / Exness-MT5TrialN from the "
                "MT5 Open Account list or Personal Area. Demo = Trial; LIVE = Real."
            ),
        ),
        notes="Priority MT5 retail brand — high leverage accounts still MT5-gated.",
        priority=3,
    ),
    MT5BrokerProfile(
        slug="hfm",
        name="HFM",
        website="https://www.hfm.com",
        regions=("Global", "EU", "SA", "KE", "UK"),
        account_types=("premium", "pro", "cent", "demo"),
        order_types=("market", "limit", "stop", "stop_limit"),
        server_match_patterns=("hfm", "hfmarkets", "hotforex"),
        # Official HFM connect guide names (documented search hints only).
        server_hints=(
            "HFMarketsGlobal-Live20",
            "HFMarketsGlobal-Demo",
            "HFMarketsGlobal-Demo3",
            "HFMarketsGlobal-Demo4",
            "HFMarketsGlobal-Live1",
            "HFMarketsGlobal-Live3",
            "HFMarkets-Demo",
            "HFMarkets-Live1",
        ),
        onboarding=_mt5_onboarding(
            brand="HFM",
            website="https://www.hfm.com",
            search_terms="HFMarketsGlobal, HFMarkets, HFM",
            server_note=(
                "Use the exact server from the HFM welcome email / myHF area "
                "(e.g. HFMarketsGlobal-Demo). Live and Demo clusters differ."
            ),
        ),
        notes="HFM (HF Markets) MT5 — connectable only after Windows demo verify.",
        priority=4,
    ),
    MT5BrokerProfile(
        slug="justmarkets",
        name="JustMarkets",
        website="https://justmarkets.com",
        regions=("Global", "CY", "SC", "SG"),
        account_types=("standard", "pro", "raw_spread", "cent", "demo"),
        order_types=("market", "limit", "stop", "stop_limit"),
        server_match_patterns=("justmarkets", "justmarketscy"),
        # Documented MetaQuotes / WebTerminal candidates only — copy exact PA server.
        server_hints=(
            "JustMarkets-Live7",
            "JustMarkets-Demo",
            "JustMarkets-Demo2",
            "JustMarkets-Live",
            "JustMarkets-Live2",
            "JustMarkets-Live3",
            "JustMarketsCY-Demo",
            "JustMarketsCY-Live",
        ),
        onboarding=_mt5_onboarding(
            brand="JustMarkets",
            website="https://justmarkets.com",
            search_terms=(
                "JustMarkets, JustMarketsCY, JustMarkets-Live, JustMarkets-Demo"
            ),
            server_note=(
                "Copy the exact server from the JustMarkets Personal Area / "
                "welcome email (e.g. JustMarkets-Live2). Live and Demo clusters "
                "differ; do not guess the suffix."
            ),
        ),
        notes="JustMarkets MT5 — connectable only after Windows verify.",
        priority=5,
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
            "ICMarketsSC-MT5-3",
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
        priority=6,
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
            "PepperstoneKE-MT5-Live01",
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
        priority=7,
    ),
    MT5BrokerProfile(
        slug="fp-markets",
        name="FP Markets",
        website="https://www.fpmarkets.com",
        regions=("Global", "AU", "SC", "KE"),
        account_types=("raw", "standard", "demo"),
        order_types=("market", "limit", "stop", "stop_limit"),
        server_match_patterns=("fpmarkets", "firstprudential"),
        # Documented search hints only — copy exact portal/email server.
        server_hints=(
            "FPMarkets-Demo",
            "FPMarkets-Live",
            "FPMarketsSC-Demo",
            "FPMarketsSC-Live",
            "FPMarketsKE-Demo",
            "FPMarketsKE-Live",
        ),
        onboarding=_mt5_onboarding(
            brand="FP Markets",
            website="https://www.fpmarkets.com",
            search_terms="FPMarkets, FPMarketsSC, FPMarketsKE",
            server_note=(
                "Use the exact server from the FP Markets registration email / "
                "Client Portal. Demo and Live names differ by entity."
            ),
        ),
        notes="FP Markets MT5 — connectable only after Windows verify.",
        priority=8,
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
