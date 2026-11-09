"""Broker-specific symbol / contract validation for OMS pre-trade checks.

Does not invent contract specs. Without a verified MT5 session payload the
validator fails closed for non-Weltrade brokers. Never enables LIVE submit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SymbolValidationResult:
    ok: bool
    broker_slug: str
    symbol: str
    reason: str
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "broker_slug": self.broker_slug,
            "symbol": self.symbol,
            "reason": self.reason,
            "details": self.details,
            "live_submit_enabled": False,
        }


def validate_broker_symbol(
    *,
    broker_slug: str,
    symbol: str,
    session_symbols: list[dict[str, Any]] | None = None,
    volume: float | None = None,
) -> SymbolValidationResult:
    """Validate symbol against broker session facts when available.

    ``session_symbols`` must come from a real MT5 ``symbols_get`` / info probe —
    never fabricate rows.
    """
    slug = (broker_slug or "").strip().lower()
    sym = (symbol or "").strip()
    if not slug or not sym:
        return SymbolValidationResult(
            ok=False,
            broker_slug=slug,
            symbol=sym,
            reason="broker_or_symbol_required",
            details={},
        )
    if slug == "weltrade":
        # Existing Weltrade path retains current OMS validation elsewhere.
        return SymbolValidationResult(
            ok=True,
            broker_slug=slug,
            symbol=sym,
            reason="weltrade_delegated_to_existing_oms",
            details={},
        )
    if not session_symbols:
        return SymbolValidationResult(
            ok=False,
            broker_slug=slug,
            symbol=sym,
            reason="broker_session_symbols_unavailable",
            details={
                "note": (
                    "Non-Weltrade brokers require a verified MT5 session symbol "
                    "catalogue before Robot order validation can pass."
                )
            },
        )

    matched: dict[str, Any] | None = None
    for row in session_symbols:
        name = str(row.get("name") or row.get("symbol") or "").strip()
        if name == sym or name.upper() == sym.upper():
            matched = row
            break
    if matched is None:
        return SymbolValidationResult(
            ok=False,
            broker_slug=slug,
            symbol=sym,
            reason="symbol_not_listed_on_broker_session",
            details={
                "candidates_sample": [
                    str(r.get("name") or "") for r in session_symbols[:8]
                ]
            },
        )

    volume_min = matched.get("volume_min")
    volume_step = matched.get("volume_step")
    trade_mode = matched.get("trade_mode")
    if volume is not None and volume_min is not None:
        try:
            if float(volume) < float(volume_min):
                return SymbolValidationResult(
                    ok=False,
                    broker_slug=slug,
                    symbol=sym,
                    reason="below_broker_volume_min",
                    details={"volume": volume, "volume_min": volume_min},
                )
        except (TypeError, ValueError):
            return SymbolValidationResult(
                ok=False,
                broker_slug=slug,
                symbol=sym,
                reason="invalid_volume",
                details={"volume": volume},
            )
    if volume is not None and volume_step not in (None, 0, 0.0):
        try:
            step = float(volume_step)
            vol = float(volume)
            # Allow floating tolerance for broker steps.
            units = round(vol / step)
            if abs(units * step - vol) > 1e-8:
                return SymbolValidationResult(
                    ok=False,
                    broker_slug=slug,
                    symbol=sym,
                    reason="volume_not_aligned_to_broker_step",
                    details={"volume": volume, "volume_step": volume_step},
                )
        except (TypeError, ValueError):
            pass

    return SymbolValidationResult(
        ok=True,
        broker_slug=slug,
        symbol=sym,
        reason="broker_session_symbol_ok",
        details={
            "volume_min": volume_min,
            "volume_step": volume_step,
            "trade_mode": trade_mode,
            "digits": matched.get("digits"),
            "point": matched.get("point"),
            "stops_level": matched.get("trade_stops_level"),
        },
    )
