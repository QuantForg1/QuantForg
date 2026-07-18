"""Deterministic intelligence event engine.

Classifies *real* news/calendar payloads only. Never invents headlines or events.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from app.domain.intelligence.providers import (
    CalendarEvent,
    IntelligenceEvent,
    NewsArticle,
)

_CURRENCY_MAP: dict[str, tuple[str, ...]] = {
    "USD": ("USD", "DOLLAR", "FED", "FOMC", "CPI", "NFP", "PAYROLL"),
    "EUR": ("EUR", "EURO", "ECB", "EUROZONE"),
    "GBP": ("GBP", "STERLING", "BOE", "UK "),
    "JPY": ("JPY", "YEN", "BOJ"),
    "CHF": ("CHF", "SNB"),
    "AUD": ("AUD", "RBA"),
    "CAD": ("CAD", "BOC"),
    "NZD": ("NZD", "RBNZ"),
    "CNY": ("CNY", "PBOC", "CHINA"),
}

_ASSET_HINTS: dict[str, tuple[str, ...]] = {
    "EURUSD": ("EURUSD", "EUR/USD"),
    "GBPUSD": ("GBPUSD", "GBP/USD"),
    "USDJPY": ("USDJPY", "USD/JPY"),
    "XAUUSD": ("XAUUSD", "GOLD", "XAU"),
    "BTCUSDT": ("BTC", "BITCOIN"),
    "ETHUSDT": ("ETH", "ETHEREUM"),
}

_SECTOR_HINTS: dict[str, tuple[str, ...]] = {
    "rates": ("RATE", "YIELD", "TREASURY", "BOND", "FED", "ECB", "BOE"),
    "energy": ("OIL", "CRUDE", "ENERGY", "OPEC", "GAS"),
    "crypto": ("BITCOIN", "CRYPTO", "ETHEREUM", "BTC", "ETH"),
    "equities": ("STOCK", "EQUITY", "NASDAQ", "S&P", "EARNINGS"),
    "metals": ("GOLD", "SILVER", "COPPER", "XAU", "XAG"),
}

_HIGH = ("HIGH", "CRITICAL", "SEVERE", "EMERGENCY", "CRISIS")
_MED = ("MEDIUM", "MODERATE", "ELEVATED")


@dataclass(frozen=True, slots=True)
class IntelligenceEventEngine:
    """Parse → classify → score using only supplied provider content."""

    def from_news(
        self,
        articles: list[NewsArticle],
        *,
        portfolio_symbols: tuple[str, ...] = (),
    ) -> list[IntelligenceEvent]:
        return [
            self._build(
                title=a.title,
                summary=a.summary,
                provider=a.provider,
                source_url=a.url,
                published_at=a.published_at,
                hinted_assets=a.symbols,
                impact_hint="",
                portfolio_symbols=portfolio_symbols,
            )
            for a in articles
            if a.title.strip()
        ]

    def from_calendar(
        self,
        events: list[CalendarEvent],
        *,
        portfolio_symbols: tuple[str, ...] = (),
    ) -> list[IntelligenceEvent]:
        return [
            self._build(
                title=e.title,
                summary=f"{e.country} impact={e.impact} actual={e.actual} "
                f"forecast={e.forecast} previous={e.previous}".strip(),
                provider=e.provider,
                source_url="",
                published_at=e.scheduled_at,
                hinted_assets=(),
                impact_hint=e.impact,
                portfolio_symbols=portfolio_symbols,
                currency_hint=e.currency or e.country,
            )
            for e in events
            if e.title.strip()
        ]

    def _build(
        self,
        *,
        title: str,
        summary: str,
        provider: str,
        source_url: str,
        published_at: str,
        hinted_assets: tuple[str, ...],
        impact_hint: str,
        portfolio_symbols: tuple[str, ...],
        currency_hint: str = "",
    ) -> IntelligenceEvent:
        blob = f"{title} {summary} {currency_hint}".upper()
        currencies = self._match_map(_CURRENCY_MAP, blob)
        if currency_hint:
            code = currency_hint.strip().upper()[:3]
            if len(code) == 3 and code.isalpha() and code not in currencies:
                currencies = (*currencies, code)

        assets = tuple(
            dict.fromkeys(
                [
                    *(a.upper() for a in hinted_assets if a),
                    *self._match_map(_ASSET_HINTS, blob),
                ]
            )
        )
        sectors = self._match_map(_SECTOR_HINTS, blob)
        severity = self._severity(impact_hint, blob)
        classification = self._classify(sectors, currencies, assets)
        expected_vol = {
            "critical": "very_high",
            "high": "high",
            "medium": "elevated",
            "low": "normal",
        }.get(severity, "unknown")

        portfolio_hit = sorted(
            {
                s.upper()
                for s in portfolio_symbols
                if s
                and (s.upper() in assets or any(c in s.upper() for c in currencies))
            }
        )
        if portfolio_hit:
            portfolio_impact = "Potential relevance to open symbols: " + ", ".join(
                portfolio_hit
            )
            risk = {"critical": 0.9, "high": 0.75, "medium": 0.5, "low": 0.25}.get(
                severity, 0.4
            )
        elif assets or currencies:
            portfolio_impact = (
                "No direct overlap with supplied portfolio symbols; "
                "monitor correlated exposure."
            )
            risk = {"critical": 0.7, "high": 0.55, "medium": 0.35, "low": 0.15}.get(
                severity, 0.3
            )
        else:
            portfolio_impact = (
                "Insufficient symbol linkage in source text to assert portfolio impact."
            )
            risk = 0.1

        eid = hashlib.sha256(f"{provider}|{title}|{published_at}".encode()).hexdigest()[
            :24
        ]
        det = (
            f"[{severity}/{classification}] {title.strip()} — "
            f"currencies={','.join(currencies) or 'n/a'}; "
            f"assets={','.join(assets) or 'n/a'}; "
            f"vol={expected_vol}; provider={provider}."
        )
        return IntelligenceEvent(
            id=eid,
            title=title.strip()[:300],
            summary=(summary or "")[:1000],
            classification=classification,
            severity=severity,
            affected_currencies=currencies,
            affected_assets=assets,
            affected_sectors=sectors,
            expected_volatility=expected_vol,
            portfolio_impact=portfolio_impact,
            risk_score=round(risk, 3),
            provider=provider,
            source_url=source_url[:500],
            published_at=published_at[:64],
            deterministic_summary=det[:500],
        )

    @staticmethod
    def _match_map(mapping: dict[str, tuple[str, ...]], blob: str) -> tuple[str, ...]:
        hits: list[str] = []
        for key, needles in mapping.items():
            if any(re.search(rf"\b{re.escape(n)}\b", blob) for n in needles):
                hits.append(key)
        return tuple(hits)

    @staticmethod
    def _severity(impact_hint: str, blob: str) -> str:
        hint = (impact_hint or "").upper()
        if any(k in hint for k in _HIGH) or any(k in blob for k in _HIGH):
            return "high"
        if any(k in hint for k in _MED) or "VOLATIL" in blob:
            return "medium"
        if hint in {"1", "2", "LOW"} or "LOW" in hint:
            return "low"
        if hint in {"3", "HIGH"}:
            return "high"
        return "medium" if hint else "low"

    @staticmethod
    def _classify(
        sectors: tuple[str, ...],
        currencies: tuple[str, ...],
        assets: tuple[str, ...],
    ) -> str:
        if "rates" in sectors:
            return "macro_rates"
        if "crypto" in sectors:
            return "crypto"
        if "energy" in sectors:
            return "commodities_energy"
        if "metals" in sectors:
            return "commodities_metals"
        if "equities" in sectors:
            return "equities"
        if currencies or assets:
            return "fx_macro"
        return "general"
