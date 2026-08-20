"""Classify conditions that may halt a new entry vs advisory noise.

Product-owner split (does not change Safety / Risk / OMS thresholds):

Advisory — must not immediately halt a trade:
  UI/telemetry stale, duplicate health probe, optional enrichment miss,
  non-authoritative analytics unavailable.

Hard block — fail closed:
  MT5 disconnected, Gateway unavailable, stale quote, invalid symbol,
  risk limit exceeded, Safety failure, min-lot risk violation,
  reconciliation unknown.
"""

from __future__ import annotations

from enum import StrEnum


class HaltClass(StrEnum):
    ADVISORY = "advisory"
    HARD_BLOCK = "hard_block"
    UNCLASSIFIED = "unclassified"


def _norm(text: str) -> str:
    raw = str(text or "").lower()
    for ch in ("_", "-", ":", "/", ".", ",", "(", ")", "[", "]"):
        raw = raw.replace(ch, " ")
    return " ".join(raw.split())


# Specific needles — order is not used for scoring; hard is always checked first.
_HARD_NEEDLES: tuple[str, ...] = (
    "mt5 disconnected",
    "mt5 unavailable",
    "broker unavailable",
    "gateway unavailable",
    "gateway disconnected",
    "stale quote",
    "stale market data",
    "market data stale",
    "quote missing",
    "quote malformed",
    "invalid symbol",
    "symbol identity invalid",
    "symbol not tradable",
    "risk limit exceeded",
    "portfolio risk exceeded",
    "portfolio risk limit",
    "daily loss exceeded",
    "safety failure",
    "safety blocked",
    "safety block",
    "below min lot",
    "min lot constraint",
    "minimum lot causes risk",
    "min lot risk",
    "reconciliation required",
    "reconciliation unknown",
    "unknown order reconciliation",
    "stale heartbeat gateway",
    "stale heartbeat mt5",
    "stale heartbeat oms",
    "no market context",
    "market data load failed",
    "cloudflare origin unreachable",
    "symbol catalogue resolution failed",
    "http 530",
    "account leverage exceeds desk policy",
    "exceeds max leverage",
)

_ADVISORY_NEEDLES: tuple[str, ...] = (
    "ui telemetry stale",
    "telemetry stale",
    "ops telemetry",
    "ops telemetry delayed",
    "duplicate health probe",
    "duplicate health",
    "optional enrichment",
    "enrichment unavailable",
    "non authoritative analytics",
    "analytics unavailable",
    "execution quality analytics",
    "platform probe",
    "railway self probe",
    "stale heartbeat execution",
    "stale heartbeat decision",
    "stale heartbeat pme",
    "connected cached",
)


def classify_halt_condition(reason: str) -> HaltClass:
    """Label a condition. Unclassified strings are not treated as advisory."""
    needle_hay = _norm(reason)
    if not needle_hay:
        return HaltClass.UNCLASSIFIED
    for needle in _HARD_NEEDLES:
        if needle in needle_hay:
            return HaltClass.HARD_BLOCK
    for needle in _ADVISORY_NEEDLES:
        if needle in needle_hay:
            return HaltClass.ADVISORY
    return HaltClass.UNCLASSIFIED


def does_not_halt_new_entry(reason: str) -> bool:
    """True only for explicit advisory (soft) conditions."""
    return classify_halt_condition(reason) is HaltClass.ADVISORY


def halts_new_entry(reason: str) -> bool:
    """True only for explicit hard-block conditions."""
    return classify_halt_condition(reason) is HaltClass.HARD_BLOCK
