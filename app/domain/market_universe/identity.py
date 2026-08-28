"""Canonical instrument identity + broker-form aliases.

XAUUSD and XAUUSD_i are the same economic instrument. Broker suffixes
(_i, _I, .a) are mapping, not a wider product set.

Never invents a broker code the catalogue did not expose.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.institutional_trading.ai_scalping.asset_class import (
    BROKER_SYMBOL_CANDIDATES,
    desk_symbol_code,
)
from app.domain.institutional_trading.ai_scalping.universe_discovery import (
    scalp_desk_code,
)
from app.domain.market_universe.constants import UNKNOWN


def canonical_desk(symbol: str | None) -> str:
    """Canonical economic identity (EURUSD_I → EURUSD, XAUUSD_i → XAUUSD)."""
    code = (symbol or "").strip().upper()
    if not code:
        return ""
    if code.endswith("_I") and len(code) > 3:
        code = code[:-2]
    desk = desk_symbol_code(code) or scalp_desk_code(code)
    if desk in {"GOLD", "XAUUSDM"}:
        return "XAUUSD"
    if desk in {"SILVER"}:
        return "XAGUSD"
    return desk or code


def display_broker_form(symbol: str | None) -> str:
    """Operator-facing catalogue spelling (``XAUUSD_i``)."""
    raw = (symbol or "").strip()
    if not raw:
        return ""
    u = raw.upper()
    if u.endswith("_I") and len(u) > 2:
        return f"{u[:-2]}_i"
    return raw


def known_alias_forms(desk: str) -> tuple[str, ...]:
    """Documented aliases for a desk. Does not invent catalogue membership."""
    d = canonical_desk(desk)
    if not d:
        return ()
    ordered: list[str] = []
    seen: set[str] = set()

    def _add(name: str) -> None:
        n = (name or "").strip().upper()
        if not n or n in seen:
            return
        seen.add(n)
        ordered.append(n)

    _add(d)
    _add(f"{d}_I")
    for alias in BROKER_SYMBOL_CANDIDATES.get(d, ()):
        _add(alias)
    return tuple(ordered)


def same_economic_instrument(left: str | None, right: str | None) -> bool:
    a = canonical_desk(left)
    b = canonical_desk(right)
    return bool(a) and a == b


@dataclass(frozen=True, slots=True)
class CanonicalIdentity:
    canonical_symbol: str
    broker_symbol: str
    display_name: str
    broker_forms: tuple[str, ...]
    aliases: tuple[str, ...]
    broker: str = UNKNOWN
    exchange: str = UNKNOWN

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_symbol": self.canonical_symbol,
            "broker_symbol": self.broker_symbol,
            "display_name": self.display_name,
            "broker_forms": list(self.broker_forms),
            "aliases": list(self.aliases),
            "broker": self.broker,
            "exchange": self.exchange,
        }


def identity_from_broker_code(
    broker_symbol: str,
    *,
    display_name: str = "",
    catalogue_forms: tuple[str, ...] | list[str] | None = None,
    broker: str = UNKNOWN,
    exchange: str = UNKNOWN,
) -> CanonicalIdentity:
    raw = (broker_symbol or "").strip()
    desk = canonical_desk(raw)
    forms = tuple(
        sorted(
            {str(x).strip().upper() for x in (catalogue_forms or ()) if str(x).strip()}
            | {raw.upper()}
            if raw
            else set()
        )
    )
    aliases = known_alias_forms(desk)
    name = (display_name or "").strip() or desk or raw
    return CanonicalIdentity(
        canonical_symbol=desk,
        broker_symbol=raw,
        display_name=name,
        broker_forms=forms,
        aliases=aliases,
        broker=broker or UNKNOWN,
        exchange=exchange or UNKNOWN,
    )


def group_catalogue_by_desk(
    codes: tuple[str, ...] | list[str],
) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, list[str]] = {}
    for raw in codes:
        code = str(raw or "").strip()
        if not code:
            continue
        grouped.setdefault(canonical_desk(code), []).append(code)
    return {k: tuple(v) for k, v in grouped.items() if k}


@dataclass
class AliasIndex:
    """Maps any broker form onto one canonical desk."""

    by_form: dict[str, str] = field(default_factory=dict)

    def add(self, broker_symbol: str, canonical: str | None = None) -> None:
        form = (broker_symbol or "").strip().upper()
        desk = (canonical or canonical_desk(form)).upper()
        if form:
            self.by_form[form] = desk
        if desk:
            self.by_form.setdefault(desk, desk)

    def resolve(self, symbol: str | None) -> str:
        code = (symbol or "").strip().upper()
        if not code:
            return ""
        if code in self.by_form:
            return self.by_form[code]
        return canonical_desk(code)
