"""Canonical public QuantForg Signals payload.

Presentation only. Never sizes lots, never calls MT5, never claims a fill.
Internal ticket / volume / execution evidence stay on classified notices and
bind_ticket — they must not appear in public Telegram or Jimvio text/metadata.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

PUBLIC_FOOTER = "QuantForg Signals"
PUBLIC_RULE = "━━━━━━━━━━━━━━"

SIGNAL_CONFIRMED = "SIGNAL_CONFIRMED"
TRADE_OPENED = "TRADE_OPENED"
BREAKEVEN_SET = "BREAKEVEN_SET"
SL_UPDATED = "SL_UPDATED"
TRAILING_STOP_UPDATED = "TRAILING_STOP_UPDATED"
PARTIAL_CLOSE = "PARTIAL_CLOSE"
TAKE_PROFIT = "TAKE_PROFIT"
STOP_LOSS = "STOP_LOSS"
TRADE_CLOSED = "TRADE_CLOSED"

_INTERNAL_FIELD_KEYS = frozenset(
    {
        "ticket",
        "mt5_ticket",
        "volume",
        "remaining_volume",
        "closed_volume",
        "deal_ticket",
        "order_ticket",
        "retcode",
        "deal_id",
        "order_id",
        "execution_ticket",
        "broker_ticket",
    }
)

PUBLIC_LEAK_MARKERS = (
    "MT5 Ticket",
    "Status: EXECUTED",
    "Volume:",
    "Automated Trading System",
    "deal_id",
    "order_id",
    "broker ticket",
    "execution ticket",
)

_FX = frozenset(
    {"USD", "EUR", "GBP", "JPY", "CHF", "AUD", "CAD", "NZD", "SGD", "HKD"}
)


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"none", "null", "n/a"}:
        return None
    return text


def _num(value: object) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    try:
        number = Decimal(text)
    except (InvalidOperation, ValueError):
        return text
    normalized = format(number.normalize(), "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized or "0"


def _pct(value: object) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    if text.endswith("%"):
        text = text[:-1].strip()
    number = _num(text)
    if number is None:
        return None
    return f"{number}%"


def _side(value: object) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    upper = text.upper()
    if upper in {"BUY", "LONG"}:
        return "BUY"
    if upper in {"SELL", "SHORT"}:
        return "SELL"
    return upper


def public_price_digits(symbol: object) -> int:
    u = "".join(ch for ch in str(symbol or "").upper() if ch.isalnum())
    if u.startswith("XAU") or "GOLD" in u:
        return 3
    if any(tag in u for tag in ("NAS", "US30", "AEX", "DAX", "SPX", "UK100", "US500")):
        return 2
    if len(u) >= 6:
        base, quote = u[:3], u[3:6]
        if base in _FX and quote in _FX:
            return 3 if "JPY" in (base, quote) else 5
    return 5


def format_public_price(value: object, *, symbol: object = None) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    try:
        number = Decimal(text)
    except (InvalidOperation, ValueError):
        return text
    if number == 0:
        return None
    digits = public_price_digits(symbol)
    quant = Decimal("1").scaleb(-digits)
    shown = number.quantize(quant, rounding=ROUND_HALF_UP)
    rendered = format(shown, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def format_public_rr(value: object) -> str | None:
    number = _num(value)
    if number is None:
        return None
    try:
        ratio = Decimal(number)
    except (InvalidOperation, ValueError):
        return f"1 : {number}"
    shown = format(ratio.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")
    if "." in shown:
        shown = shown.rstrip("0").rstrip(".")
    return f"1 : {shown}"


def format_public_regime(value: object) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    pretty = text.replace("_", " ").replace("-", " ").strip()
    if not pretty:
        return None
    return " ".join(part.capitalize() for part in pretty.split())


def public_fields_only(fields: dict[str, Any] | None) -> dict[str, Any]:
    extra = dict(fields or {})
    return {
        key: value
        for key, value in extra.items()
        if key not in _INTERNAL_FIELD_KEYS and value not in (None, "")
    }


def audit_public_message(text: str) -> list[str]:
    """Return leak reasons. Empty means the public text is clean."""
    blob = str(text or "")
    lower = blob.lower()
    found: list[str] = []
    for marker in PUBLIC_LEAK_MARKERS:
        if marker.lower() in lower:
            found.append(marker)
    if "automated trading system" in lower:
        found.append("Automated Trading System")
    return list(dict.fromkeys(found))


def audit_jimvio_payload(payload: dict[str, Any] | None) -> list[str]:
    """Public Jimvio JSON must not carry broker/execution infrastructure."""
    if not isinstance(payload, dict):
        return ["invalid_payload"]
    found = audit_public_message(str(payload.get("message") or ""))
    meta = payload.get("metadata")
    if isinstance(meta, dict):
        for key in (
            "mt5_ticket",
            "ticket",
            "volume",
            "deal_id",
            "order_id",
            "broker_ticket",
            "execution_ticket",
        ):
            if key in meta and meta.get(key) not in (None, ""):
                found.append(f"metadata.{key}")
    found.extend(audit_public_message(json.dumps(payload, default=str)))
    return list(dict.fromkeys(found))


def validate_canonical_signal(fields: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    symbol = fields.get("symbol")
    if not _clean(symbol):
        missing.append("symbol")
    if _side(fields.get("direction") or fields.get("side")) not in {"BUY", "SELL"}:
        missing.append("direction")
    if format_public_price(fields.get("entry"), symbol=symbol) is None:
        missing.append("entry")
    if format_public_price(fields.get("stop_loss"), symbol=symbol) is None:
        missing.append("stop_loss")
    if format_public_price(fields.get("take_profit"), symbol=symbol) is None:
        missing.append("take_profit")
    if _num(fields.get("opportunity")) is None:
        missing.append("opportunity")
    return missing


@dataclass(frozen=True, slots=True)
class CanonicalPublicSignal:
    kind: str
    symbol: str | None
    direction: str | None
    opportunity: str | None
    confidence: str | None
    entry: str | None
    stop_loss: str | None
    take_profit: str | None
    risk_reward: str | None
    regime: str | None
    headline: str
    intro: str | None = None
    extra_lines: tuple[str, ...] = ()

    def semantic_fields(self) -> dict[str, str]:
        out: dict[str, str] = {"kind": self.kind, "headline": self.headline}
        if self.symbol:
            out["symbol"] = self.symbol
        if self.direction:
            out["direction"] = self.direction
        if self.opportunity:
            out["opportunity"] = self.opportunity
        if self.confidence:
            out["confidence"] = self.confidence
        if self.entry:
            out["entry"] = self.entry
        if self.stop_loss:
            out["stop_loss"] = self.stop_loss
        if self.take_profit:
            out["take_profit"] = self.take_profit
        if self.risk_reward:
            out["risk_reward"] = self.risk_reward
        if self.regime:
            out["regime"] = self.regime
        return out


def _heading(direction: str | None) -> str:
    return "🔴" if direction == "SELL" else "🟢"


def _block(label: str, value: str | None) -> list[str]:
    if not value:
        return []
    return [label, value, ""]


def _join(lines: list[str | None]) -> str:
    return "\n".join(line for line in lines if line is not None).rstrip() + "\n"


def _footer() -> list[str]:
    return [PUBLIC_RULE, PUBLIC_FOOTER]


def build_canonical_signal(
    *,
    kind: str,
    fields: dict[str, Any],
    headline: str,
    intro: str | None = None,
    extra_lines: tuple[str, ...] = (),
) -> CanonicalPublicSignal:
    symbol = _clean(fields.get("symbol"))
    direction = _side(fields.get("direction") or fields.get("side"))
    return CanonicalPublicSignal(
        kind=kind,
        symbol=symbol.upper() if symbol else None,
        direction=direction,
        opportunity=_num(fields.get("opportunity")),
        confidence=_pct(fields.get("confidence")),
        entry=format_public_price(fields.get("entry"), symbol=symbol),
        stop_loss=format_public_price(fields.get("stop_loss"), symbol=symbol),
        take_profit=format_public_price(fields.get("take_profit"), symbol=symbol),
        risk_reward=format_public_rr(fields.get("risk_reward")),
        regime=format_public_regime(fields.get("regime")),
        headline=headline,
        intro=intro,
        extra_lines=extra_lines,
    )


def render_canonical(payload: CanonicalPublicSignal) -> str:
    pair = None
    if payload.symbol and payload.direction:
        pair = f"{payload.symbol} · {payload.direction}"
    elif payload.symbol:
        pair = payload.symbol
    lines: list[str | None] = [payload.headline, "", pair, ""]
    if payload.intro:
        lines.extend([payload.intro, ""])
    lines.extend(_block("Opportunity", payload.opportunity))
    lines.extend(_block("Confidence", payload.confidence))
    lines.extend(_block("Entry", payload.entry))
    lines.extend(_block("Stop Loss", payload.stop_loss))
    lines.extend(_block("Take Profit", payload.take_profit))
    lines.extend(_block("Risk / Reward", payload.risk_reward))
    lines.extend(_block("Market Regime", payload.regime))
    for extra in payload.extra_lines:
        lines.append(extra)
    if payload.extra_lines:
        lines.append("")
    lines.extend(_footer())
    text = _join(lines)
    leaks = audit_public_message(text)
    if leaks:
        raise ValueError(f"public_signal_leak:{','.join(leaks)}")
    return text.rstrip()


def render_public_signal(fields: dict[str, Any]) -> str:
    direction = _side(fields.get("direction") or fields.get("side"))
    payload = build_canonical_signal(
        kind="SIGNAL",
        fields=fields,
        headline=f"{_heading(direction)} QUANTFORG SIGNAL",
    )
    return render_canonical(payload)


def render_trade_active(fields: dict[str, Any]) -> str:
    payload = build_canonical_signal(
        kind="TRADE_ACTIVE",
        fields=fields,
        headline="🟢 TRADE ACTIVE",
        intro="The setup has been activated successfully.",
    )
    return render_canonical(payload)


def render_lifecycle_update(event: str, fields: dict[str, Any]) -> str:
    symbol = _clean(fields.get("symbol"))
    direction = _side(fields.get("direction") or fields.get("side"))
    pair = (
        f"{symbol.upper()} · {direction}"
        if symbol and direction
        else (symbol.upper() if symbol else None)
    )
    if event == BREAKEVEN_SET:
        headline = "🟠 TRADE UPDATE"
        intro = "Protective management is now active on this setup."
    elif event == TRAILING_STOP_UPDATED:
        headline = "🟠 TRADE UPDATE"
        intro = "The protective stop has been advanced with the market."
    elif event == SL_UPDATED:
        headline = "🟠 TRADE UPDATE"
        intro = "The stop has been adjusted according to the trade plan."
    elif event == PARTIAL_CLOSE:
        headline = "🟠 TRADE UPDATE"
        intro = "Part of the position has been realized according to the trade plan."
    elif event == TAKE_PROFIT:
        headline = "✅ TRADE COMPLETED"
        intro = (
            "The position has reached its planned objective.\n\n"
            "Another setup will only be considered when market conditions "
            "meet the required criteria."
        )
    elif event == STOP_LOSS:
        headline = "📊 TRADE COMPLETED"
        intro = (
            "The position has closed according to the trade plan.\n\n"
            "Risk remains controlled and QuantForg continues monitoring "
            "the market for the next qualified opportunity."
        )
    elif event == TRADE_CLOSED:
        headline = "📊 TRADE COMPLETED"
        intro = (
            "The position has closed according to the trade plan.\n\n"
            "QuantForg continues monitoring the market for the next "
            "qualified opportunity."
        )
    else:
        headline = "🟠 TRADE UPDATE"
        intro = "The setup remains under the original trade plan."
    lines: list[str | None] = [headline, "", pair, "", intro, ""]
    entry = format_public_price(fields.get("entry"), symbol=symbol)
    stop = format_public_price(
        fields.get("stop_loss") or fields.get("new_sl") or fields.get("new"),
        symbol=symbol,
    )
    target = format_public_price(fields.get("take_profit"), symbol=symbol)
    lines.extend(_block("Entry", entry))
    lines.extend(_block("Stop Loss", stop))
    lines.extend(_block("Take Profit", target))
    lines.extend(_footer())
    text = _join(lines)
    leaks = audit_public_message(text)
    if leaks:
        raise ValueError(f"public_signal_leak:{','.join(leaks)}")
    return text.rstrip()


def render_status_message(kind: str) -> str:
    copies = {
        "READY": (
            "🟢 MARKET WATCH",
            "QuantForg is ready.\n\n"
            "We are scanning the market for high-quality opportunities.\n\n"
            "Only setups that meet the required quality, risk and execution "
            "conditions will be considered.",
        ),
        "SCANNING": (
            "🔎 MARKET SCAN",
            "QuantForg is actively scanning the market.\n\n"
            "Watching multiple instruments for qualified opportunities.",
        ),
        "NO_SIGNAL": (
            "🔎 MARKET WATCH",
            "No qualified setup has met the required conditions yet.\n\n"
            "QuantForg remains active and continues monitoring the market.",
        ),
    }
    headline, body = copies.get(kind, copies["SCANNING"])
    text = _join([headline, "", body, "", *_footer()])
    leaks = audit_public_message(text)
    if leaks:
        raise ValueError(f"public_signal_leak:{','.join(leaks)}")
    return text.rstrip()


def render_contextual_reply(
    *,
    state: str | None,
    symbol: object = None,
    direction: object = None,
) -> str:
    pair = None
    sym = _clean(symbol)
    side = _side(direction)
    if sym and side:
        pair = f"{sym.upper()} · {side}"
    if state == "ACTIVE":
        lines = [
            "Yes — this setup is still active.",
            "",
            pair,
            "",
            "The position remains under the original trade plan.",
        ]
    elif state == "CLOSED":
        lines = [
            "This setup is no longer active.",
            "",
            "The position has already been closed according to its trade lifecycle.",
        ]
    elif state == "CONFIRMED":
        lines = [
            "This setup was confirmed but is not active yet.",
            "",
            "I'm unable to confirm a live position from the available state.",
        ]
    elif state == "NOT_EXECUTED":
        lines = [
            "This setup was not activated.",
            "",
            "The required execution conditions were not satisfied.",
        ]
    else:
        lines = [
            "I'm unable to confirm the current state of this setup yet.",
        ]
    return _join(lines).rstrip()


def canonical_parity(
    telegram_text: str, jimvio_message: str
) -> list[str]:
    if telegram_text.strip() != str(jimvio_message or "").strip():
        return ["telegram_jimvio_message_mismatch"]
    return audit_public_message(telegram_text) + audit_public_message(jimvio_message)


def public_kind_for_event(event: str) -> str:
    if event == SIGNAL_CONFIRMED:
        return "SIGNAL"
    if event == TRADE_OPENED:
        return "TRADE_ACTIVE"
    return "LIFECYCLE"
