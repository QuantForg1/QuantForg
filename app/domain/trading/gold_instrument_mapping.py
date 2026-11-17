"""Gold First — broker-aware canonical XAUUSD instrument mapping.

A broker symbol is mapped to canonical ``XAUUSD`` only after its live MT5
metadata validates as spot gold quoted in US dollars. The symbol *name* is
used only to pick candidates cheaply; it never proves anything.

Evidence (17 Nov 2026, Weltrade-Real 12439799): the broker's gold symbol is
``XAUUSD`` (not ``XAUUSD_i``) and MT5 reports ``currency_base="USD"``, so a
single-field rule such as ``currency_base == "XAU"`` would reject real gold.
Validation therefore combines independent checks:

1. quoted in USD (``currency_profit``);
2. identifies as gold in broker metadata (``currency_base`` XAU *or* the
   broker-provided description names gold / XAU);
3. a gold-like price (spot bid inside a broad sanity band);
4. ounce-contract geometry: when the account currency is USD,
   ``tick_value ~= contract_size * tick_size`` (100 oz * 0.001 = 0.1);
5. tradable spec: trade mode not disabled/close-only, symbol selectable,
   positive contract size, tick size/value and sane volume rules.

Zero validated candidates → MISSING; more than one → AMBIGUOUS (unless the
owner pinned one for that broker); any stale / incomplete metadata → INVALID.
Execution must fail closed on anything other than VALIDATED.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

CANONICAL_GOLD = "XAUUSD"

GoldMappingStatus = Literal["VALIDATED", "MISSING", "AMBIGUOUS", "INVALID"]

# Spot gold, USD per ounce. Deliberately broad: a sanity bound, not a price
# model. A symbol outside it is not ounce gold in USD (e.g. gram gold, gold
# index, a mislabelled FX pair).
GOLD_PRICE_MIN = Decimal("500")
GOLD_PRICE_MAX = Decimal("20000")
_GEOMETRY_TOLERANCE = Decimal("0.02")
_UNTRADABLE_MODES = {"disabled", "closeonly", "close_only", "0", "3"}

# Discovery hints only — never treat these as VALIDATED without live metadata.
# Order is probe priority for catalogue lookup. Fixtures / common published
# spellings; each broker still needs A14 DEMO observation before §3 COMPLETE.
BROKER_GOLD_DISCOVERY_HINTS: dict[str, tuple[str, ...]] = {
    "weltrade": ("XAUUSD", "XAUUSD_i", "GOLD"),
    "xm": ("GOLD", "XAUUSD", "GOLD.", "XAUUSDm"),
    "exness": ("XAUUSDm", "XAUUSD", "GOLD"),
    "hfm": ("XAUUSD", "GOLD", "XAUUSD."),
    "icmarkets": ("XAUUSD", "XAUUSD.a", "GOLD"),
    "pepperstone": ("XAUUSD", "XAUUSD.a", "GOLD"),
    "fpmarkets": ("XAUUSD", "XAUUSD.", "GOLD"),
    "justmarkets": ("XAUUSD.m", "XAUUSD", "GOLD"),
}

_GENERIC_GOLD_HINTS: tuple[str, ...] = (
    "XAUUSD",
    "GOLD",
    "XAUUSDm",
    "XAUUSD_i",
    "XAUUSD.m",
    "XAUUSD.a",
    "XAUUSD.",
)


def _dec(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        out = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return out


def _get(spec: Any, name: str) -> Any:
    if isinstance(spec, dict):
        return spec.get(name)
    return getattr(spec, name, None)


def is_gold_candidate(code: str, description: str = "") -> bool:
    """Cheap pre-filter for which catalogue rows to inspect. Not validation."""
    text = f"{code} {description}".upper()
    return "XAU" in text or "GOLD" in text


def normalize_broker_key(broker: str | None) -> str:
    """Map MT5 company / server text to a discovery-hint key (hints only)."""
    text = (broker or "").strip().lower()
    if not text:
        return ""
    aliases = (
        ("weltrade", ("weltrade",)),
        ("xm", ("xm ", "xm-", "xmglobal", "xm trading", "xm.com")),
        ("exness", ("exness",)),
        ("hfm", ("hfm", "hotforex", "hf markets")),
        ("icmarkets", ("ic markets", "icmarkets", "raw trading")),
        ("pepperstone", ("pepperstone",)),
        ("fpmarkets", ("fp markets", "fpmarkets")),
        ("justmarkets", ("justmarkets", "just markets")),
    )
    for key, needles in aliases:
        if any(n in text for n in needles) or text == key or text.startswith(key):
            return key
    # server names often look like Weltrade-Real / Exness-MT5Trial…
    compact = text.replace(" ", "").replace("_", "").replace("-", "")
    for key, _ in aliases:
        if compact.startswith(key):
            return key
    return compact


def discovery_hint_codes(broker: str | None = None) -> tuple[str, ...]:
    """Ordered catalogue probe codes. Never implies VALIDATED."""
    key = normalize_broker_key(broker)
    specific = BROKER_GOLD_DISCOVERY_HINTS.get(key, ())
    merged: list[str] = []
    for code in (*specific, *_GENERIC_GOLD_HINTS):
        if code not in merged:
            merged.append(code)
    return tuple(merged)


def order_specs_for_discovery(
    specs: list[Any], *, broker: str | None = None
) -> list[Any]:
    """Stable-sort specs so broker hint codes are inspected first.

    Does not drop non-hint candidates and does not validate anything.
    """
    hints = {c.upper(): i for i, c in enumerate(discovery_hint_codes(broker))}

    def _key(spec: Any) -> tuple[int, str]:
        code = str(_get(spec, "code") or "").strip()
        rank = hints.get(code.upper(), 10_000)
        return (rank, code.upper())

    return sorted(specs, key=_key)


@dataclass(frozen=True, slots=True)
class GoldSpecCheck:
    code: str
    ok: bool
    reasons: tuple[str, ...]
    evidence: dict[str, Any] = field(default_factory=dict)


def validate_gold_spec(
    spec: Any, *, account_currency: str | None = None, require_quote: bool = True
) -> GoldSpecCheck:
    """Validate one symbol's live MT5 metadata as spot gold in USD."""
    code = str(_get(spec, "code") or "").strip()
    reasons: list[str] = []
    base = str(_get(spec, "currency_base") or "").strip().upper()
    profit = str(_get(spec, "currency_profit") or "").strip().upper()
    description = str(_get(spec, "description") or "")
    contract = _dec(_get(spec, "contract_size"))
    tick_size = _dec(_get(spec, "tick_size"))
    tick_value = _dec(_get(spec, "tick_value"))
    bid = _dec(_get(spec, "bid"))
    ask = _dec(_get(spec, "ask"))
    vmin = _dec(_get(spec, "volume_min"))
    vstep = _dec(_get(spec, "volume_step"))
    vmax = _dec(_get(spec, "volume_max"))
    digits = _get(spec, "digits")
    trade_mode = str(_get(spec, "trade_mode") or "").strip().lower()
    selected = _get(spec, "selected")
    visible = _get(spec, "visible")
    trade_allowed = _get(spec, "trade_allowed")

    if profit != "USD":
        reasons.append(f"not_quoted_in_usd:{profit or 'missing'}")
    desc_u = description.upper()
    if not (base == "XAU" or "GOLD" in desc_u or "XAU" in desc_u):
        reasons.append("metadata_does_not_identify_gold")
    if bid is None or ask is None or bid <= 0 or ask <= 0:
        if require_quote:
            reasons.append("no_live_quote")
    else:
        if ask < bid:
            reasons.append("crossed_quote")
        if not (GOLD_PRICE_MIN <= bid <= GOLD_PRICE_MAX):
            reasons.append(f"price_outside_gold_band:{bid}")
    if contract is None or contract <= 0:
        reasons.append("contract_size_missing")
    if tick_size is None or tick_size <= 0:
        reasons.append("tick_size_missing")
    if tick_value is None or tick_value <= 0:
        reasons.append("tick_value_missing")
    geometry_checked = False
    if (
        (account_currency or "").strip().upper() == "USD"
        and contract
        and tick_size
        and tick_value
        and contract > 0
        and tick_size > 0
    ):
        geometry_checked = True
        expected = contract * tick_size
        if abs(tick_value - expected) > expected * _GEOMETRY_TOLERANCE:
            reasons.append(
                f"tick_geometry_mismatch:tick_value={tick_value},expected={expected}"
            )
    if vmin is None or vmin <= 0:
        reasons.append("volume_min_missing")
    if vstep is None or vstep <= 0:
        reasons.append("volume_step_missing")
    if vmax is not None and vmin is not None and vmax < vmin:
        reasons.append("volume_max_below_min")
    try:
        if digits is None or int(digits) < 1:
            reasons.append("digits_missing")
    except (TypeError, ValueError):
        reasons.append("digits_missing")
    if trade_mode in _UNTRADABLE_MODES:
        reasons.append(f"trade_mode_{trade_mode}")
    if trade_allowed is False:
        reasons.append("trade_not_allowed")
    if selected is False and visible is False:
        reasons.append("not_selectable")

    evidence = {
        "currency_base": base or None,
        "currency_profit": profit or None,
        "description": description or None,
        "contract_size": str(contract) if contract is not None else None,
        "digits": digits,
        "tick_size": str(tick_size) if tick_size is not None else None,
        "tick_value": str(tick_value) if tick_value is not None else None,
        "volume_min": str(vmin) if vmin is not None else None,
        "volume_max": str(vmax) if vmax is not None else None,
        "volume_step": str(vstep) if vstep is not None else None,
        "stops_level": _get(spec, "stops_level"),
        "freeze_level": _get(spec, "freeze_level"),
        "execution_mode": _get(spec, "execution_mode"),
        "trade_mode": trade_mode or None,
        "bid": str(bid) if bid is not None else None,
        "ask": str(ask) if ask is not None else None,
        "geometry_checked": geometry_checked,
    }
    return GoldSpecCheck(
        code=code, ok=not reasons, reasons=tuple(reasons), evidence=evidence
    )


@dataclass(frozen=True, slots=True)
class GoldInstrumentMapping:
    canonical: str
    status: GoldMappingStatus
    broker: str
    server: str | None
    login_masked: str | None
    broker_symbol: str | None
    discovery_source: str
    validated_at: str
    candidates: tuple[GoldSpecCheck, ...]
    detail: str = ""

    @property
    def tradable(self) -> bool:
        return self.status == "VALIDATED" and bool(self.broker_symbol)

    def as_dict(self) -> dict[str, Any]:
        chosen = next(
            (c for c in self.candidates if c.code == self.broker_symbol), None
        )
        return {
            "canonical": self.canonical,
            "status": self.status,
            "broker": self.broker,
            "server": self.server,
            "login": self.login_masked,
            "broker_symbol": self.broker_symbol,
            "discovery_source": self.discovery_source,
            "validated_at": self.validated_at,
            "detail": self.detail,
            "spec": dict(chosen.evidence) if chosen else None,
            "candidates": [
                {"code": c.code, "ok": c.ok, "reasons": list(c.reasons)}
                for c in self.candidates
            ],
        }


def _mask_login(login: Any) -> str | None:
    s = str(login or "").strip()
    if not s:
        return None
    return s if len(s) <= 4 else f"{s[:2]}•••{s[-2:]}"


def resolve_gold_mapping(
    specs: list[Any],
    *,
    broker: str,
    server: str | None = None,
    login: Any = None,
    account_currency: str | None = None,
    pinned_symbol: str | None = None,
    discovery_source: str = "mt5_symbol_info",
    now: datetime | None = None,
) -> GoldInstrumentMapping:
    """Map canonical XAUUSD to exactly one validated broker symbol."""
    ordered = order_specs_for_discovery(specs, broker=broker)
    checks = tuple(
        validate_gold_spec(s, account_currency=account_currency) for s in ordered
    )
    valid = [c for c in checks if c.ok]
    stamp = (now or datetime.now(UTC)).isoformat()

    def _make(
        status: GoldMappingStatus, symbol: str | None, detail: str
    ) -> GoldInstrumentMapping:
        return GoldInstrumentMapping(
            canonical=CANONICAL_GOLD,
            status=status,
            broker=broker,
            server=server,
            login_masked=_mask_login(login),
            broker_symbol=symbol,
            discovery_source=discovery_source,
            validated_at=stamp,
            candidates=checks,
            detail=detail,
        )

    if not checks:
        return _make("MISSING", None, "no_gold_candidates")
    if not valid:
        return _make("INVALID", None, "no_candidate_passed_metadata_validation")
    if len(valid) > 1:
        pin = (pinned_symbol or "").strip().upper()
        pinned = [c for c in valid if c.code.upper() == pin] if pin else []
        if len(pinned) == 1:
            return _make(
                "VALIDATED", pinned[0].code, "owner_pinned_among_multiple_valid"
            )
        return _make(
            "AMBIGUOUS",
            None,
            "multiple_valid_gold_symbols:" + ",".join(c.code for c in valid),
        )
    return _make("VALIDATED", valid[0].code, "")
