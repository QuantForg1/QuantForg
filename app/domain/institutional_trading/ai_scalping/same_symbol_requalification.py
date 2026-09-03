"""Same-symbol re-entry requires fresh structure — not a timer.

After a close, a new entry on the same desk must prove a changed setup.
Does not force trades, widen SL, raise size, or bypass P>70 / Sniper / Risk.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.institutional_trading.ai_scalping.direction import (
    iter_scalp_structures,
)
from core.logging import get_logger

logger = get_logger(__name__)

# Same material-delta used by focused-pair hysteresis. Score-only drift
# below this is not "new evidence".
MATERIAL_SCORE_DELTA = 12

REQUALIFY_REJECT = "SAME_SYMBOL_REQUIRES_FRESH_STRUCTURE"


@dataclass(frozen=True, slots=True)
class SetupFingerprint:
    direction: str | None
    setup_family: str | None
    opportunity_score: int | None
    structure_sig: str | None
    regime: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "direction": self.direction,
            "setup_family": self.setup_family,
            "opportunity_score": self.opportunity_score,
            "structure_sig": self.structure_sig,
            "regime": self.regime,
        }

    def comparable(self) -> bool:
        return any(
            v not in (None, "", 0)
            for v in (
                self.direction,
                self.setup_family,
                self.opportunity_score,
                self.structure_sig,
                self.regime,
            )
        )


def _norm_dir(value: Any) -> str | None:
    raw = str(value or "").strip().upper()
    return raw if raw in {"BUY", "SELL"} else None


def _latest_event_sig(items: Any, *, price_attr: str, time_attr: str) -> str | None:
    seq = list(items) if isinstance(items, (list, tuple)) else []
    if not seq:
        return None
    ev = seq[-1]
    price = getattr(ev, price_attr, None)
    when = getattr(ev, time_attr, None)
    tf = getattr(getattr(ev, "timeframe", None), "value", None) or getattr(
        ev, "timeframe", None
    )
    if price is None and when is None:
        return None
    return f"{tf}:{price}:{when}"


def structure_signature(snapshot: Any) -> str | None:
    """Identity of live structure events — never uses as_of / input_hash / UUID."""
    if snapshot is None:
        return None
    parts: list[str] = []
    try:
        bos_sig: str | None = None
        choch_sig: str | None = None
        for struct in iter_scalp_structures(snapshot):
            bos_sig = _latest_event_sig(
                getattr(struct, "breaks_of_structure", None),
                price_attr="break_price",
                time_attr="broken_at",
            ) or bos_sig
            choch_sig = _latest_event_sig(
                getattr(struct, "changes_of_character", None),
                price_attr="break_price",
                time_attr="broken_at",
            ) or choch_sig
        if bos_sig:
            parts.append(f"bos={bos_sig}")
        if choch_sig:
            parts.append(f"choch={choch_sig}")
    except Exception:
        logger.debug("structure_signature_unavailable", exc_info=True)
    liq = getattr(snapshot, "liquidity", None)
    sweeps = getattr(liq, "sweeps", None) if liq is not None else None
    if isinstance(sweeps, (list, tuple)):
        parts.append(f"sweeps={len(sweeps)}")
        last_sw = _latest_event_sig(sweeps, price_attr="price", time_attr="swept_at")
        if last_sw is None:
            last_sw = _latest_event_sig(
                sweeps, price_attr="level", time_attr="timestamp"
            )
        if last_sw:
            parts.append(f"sweep={last_sw}")
    fvg = getattr(snapshot, "fair_value_gaps", None)
    gaps = getattr(fvg, "gaps", None) if fvg is not None else None
    if not isinstance(gaps, (list, tuple)):
        gaps = getattr(fvg, "fair_value_gaps", None) if fvg is not None else None
    if isinstance(gaps, (list, tuple)) and gaps:
        g = gaps[-1]
        parts.append(
            "fvg="
            f"{getattr(g, 'high', None)}:{getattr(g, 'low', None)}:"
            f"{getattr(g, 'created_at', None)}"
        )
    ob = getattr(snapshot, "order_blocks", None)
    blocks = getattr(ob, "blocks", None) if ob is not None else None
    if not isinstance(blocks, (list, tuple)):
        blocks = getattr(ob, "order_blocks", None) if ob is not None else None
    if isinstance(blocks, (list, tuple)) and blocks:
        b = blocks[-1]
        parts.append(
            "ob="
            f"{getattr(b, 'high', None)}:{getattr(b, 'low', None)}:"
            f"{getattr(b, 'created_at', None)}"
        )
    if not parts:
        return None
    return "|".join(parts)


def fingerprint_from_snapshot(
    snapshot: Any,
    *,
    direction: str | None = None,
    setup_family: str | None = None,
    opportunity_score: int | None = None,
    regime: str | None = None,
) -> SetupFingerprint:
    fam = str(setup_family or "").strip() or None
    score = None
    if opportunity_score is not None:
        try:
            score = int(opportunity_score)
        except (TypeError, ValueError):
            score = None
    reg = str(regime or "").strip() or None
    return SetupFingerprint(
        direction=_norm_dir(direction),
        setup_family=fam,
        opportunity_score=score,
        structure_sig=structure_signature(snapshot),
        regime=reg,
    )


def fresh_setup_evidence(
    previous: SetupFingerprint | None,
    current: SetupFingerprint,
) -> tuple[bool, str]:
    """True when current is a new setup vs the closed trade.

    Unknown fields are never invented. If nothing comparable is known on
    the new scan, fail-closed (not proven fresh).
    """
    if previous is None:
        return True, "no_prior_close"
    if not current.comparable():
        return False, "current_setup_unknown"
    reasons: list[str] = []
    if (
        previous.direction
        and current.direction
        and previous.direction != current.direction
    ):
        reasons.append("direction_changed")
    if (
        previous.setup_family
        and current.setup_family
        and previous.setup_family != current.setup_family
    ):
        reasons.append("setup_family_changed")
    if (
        previous.structure_sig
        and current.structure_sig
        and previous.structure_sig != current.structure_sig
    ):
        reasons.append("structure_changed")
    if (
        previous.regime
        and current.regime
        and previous.regime != current.regime
    ):
        reasons.append("regime_changed")
    if (
        previous.opportunity_score is not None
        and current.opportunity_score is not None
        and abs(current.opportunity_score - previous.opportunity_score)
        >= MATERIAL_SCORE_DELTA
    ):
        reasons.append("opportunity_score_material_change")
    if reasons:
        return True, ",".join(reasons)
    return False, "same_setup_as_closed_trade"
