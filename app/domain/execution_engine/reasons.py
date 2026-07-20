"""Human-readable pre-trade and execution reject reasons."""

from __future__ import annotations

from collections.abc import Iterable

_REASON_MAP: dict[str, str] = {
    "broker connection not active": (
        "Broker is not connected — open Broker Workspace and attach a live session."
    ),
    "symbol not tradable": "Symbol is not tradable on this broker account.",
    "market closed": "Market is closed.",
    "market is closed": "Market is closed.",
    "execution disabled": (
        "Live execution is disabled (EXECUTION_ENABLED=false) — "
        "no broker order was sent."
    ),
    "outside configured trading hours": (
        "Outside configured trading hours for this desk policy."
    ),
    "not enough money": "Insufficient free margin.",
    "insufficient free margin": "Insufficient free margin.",
    "no money": "Insufficient free margin.",
    "invalid volume": "Lot size is invalid for this symbol (min/max/step).",
    "volume must align": "Lot size must match the broker volume step.",
    "lot size must be": "Lot size must use broker volume_step increments.",
    "lot size below": "Lot size is below the broker minimum.",
    "lot size above": "Lot size is above the broker maximum.",
    "invalid stops": "Stop loss / take profit violate broker distance rules.",
    "stop loss too close": "Stop loss is too close to price (broker stop level).",
    "take profit too close": "Take profit is too close to price (broker stop level).",
    "invalid price": "Order price is invalid for the selected order type.",
    "trade disabled": "Trading is disabled on this account by the broker.",
    "trading is disabled": "Trading is disabled for this symbol.",
    "request rejected": "Broker rejected the order request.",
    "unsupported filling": "Unsupported filling mode.",
    "filling mode": "Unsupported filling mode for this symbol.",
    "autotrading": "AutoTrading is disabled in MetaTrader 5 — enable it and retry.",
    "close only": "Symbol is close-only — new entries are blocked.",
    "close-only": "Symbol is close-only — new entries are blocked.",
    "freeze level": "Price is inside the broker freeze level.",
    "stop loss inside freeze level": (
        "Stop loss is inside the broker freeze level — move it farther from price."
    ),
    "take profit inside freeze level": (
        "Take profit is inside the broker freeze level — move it farther from price."
    ),
    "requote": "Broker requoted — retry the order.",
    "off quotes": "No quotes available — market may be closed.",
    "timeout": "Broker request timed out — retry.",
}


def humanize_reason(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return "Unknown rejection — no reason supplied."
    lower = text.lower()
    for needle, readable in _REASON_MAP.items():
        if needle in lower:
            return readable
    # Prefer shorter soft templates for known prefixes
    if lower.startswith("spread ") and "exceeds" in lower:
        return f"Spread too wide for desk policy ({text})."
    if lower.startswith("volume ") and "exceeds" in lower:
        return f"Volume above maximum lot ({text})."
    if lower.startswith("volume ") and "below" in lower:
        return f"Volume below minimum lot ({text})."
    if lower.startswith("symbol ") and "whitelist" in lower:
        return f"Symbol not allowed by execution policy ({text})."
    if lower.startswith("account ") and "whitelist" in lower:
        return f"Account not allowed by execution policy ({text})."
    if "leverage" in lower and "exceeds" in lower:
        return f"Account leverage exceeds desk policy ({text})."
    if "duplicate" in lower:
        return f"Duplicate / rapid submit blocked ({text})."
    if "rapid repeated" in lower:
        return f"Too many rapid submissions ({text})."
    if "session" in lower and ("bound" in lower or "not" in lower):
        return f"Trading session is not bound ({text})."
    return text


def humanize_reasons(reasons: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for r in reasons:
        h = humanize_reason(str(r))
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out
