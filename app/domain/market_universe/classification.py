"""Auditable asset classification for the research universe.

Product taxonomy: FOREX / CRYPTO / METALS / INDICES / ENERGY / OTHER / UNKNOWN.

Prefers broker metadata when present. Does not change live gold gates.
Does not classify solely by string matching when an authoritative path,
category, or calc-mode is available.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.institutional_trading.ai_scalping.universe_discovery import (
    classify_broker_symbol,
)
from app.domain.market_universe.constants import (
    UNKNOWN,
    AssetClassName,
    ClassificationConfidence,
    ClassificationSource,
)
from app.domain.market_universe.identity import canonical_desk
from app.domain.market_universe.manual_overrides import MANUAL_CLASSIFICATION_OVERRIDES

_SCALP_TO_PRODUCT: dict[str, AssetClassName] = {
    "forex": "FOREX",
    "fx": "FOREX",
    "metals": "METALS",
    "gold": "METALS",
    "crypto": "CRYPTO",
    "indices": "INDICES",
    "index": "INDICES",
    "commodities": "COMMODITIES",
    "commodity": "COMMODITIES",
    "energy": "ENERGY",
    "stocks": "STOCKS",
    "stock": "STOCKS",
    "equity": "STOCKS",
    "equities": "STOCKS",
    "other": "UNKNOWN",
}

_PATH_TOKENS: tuple[tuple[str, AssetClassName], ...] = (
    ("forex", "FOREX"),
    ("fx", "FOREX"),
    ("currenc", "FOREX"),
    ("crypto", "CRYPTO"),
    ("bitcoin", "CRYPTO"),
    ("metal", "METALS"),
    ("gold", "METALS"),
    ("silver", "METALS"),
    ("indic", "INDICES"),
    ("index", "INDICES"),
    ("cfdindex", "INDICES"),
    ("energ", "ENERGY"),
    ("oil", "ENERGY"),
    ("brent", "ENERGY"),
    ("wti", "ENERGY"),
    ("gas", "ENERGY"),
    ("commodit", "COMMODITIES"),
    ("stock", "STOCKS"),
    ("share", "STOCKS"),
    ("equit", "STOCKS"),
    ("synthet", "OTHER"),
)

_ENERGY_DESKS: frozenset[str] = frozenset(
    {
        "XTIUSD",
        "XBRUSD",
        "XNGUSD",
        "USOIL",
        "UKOIL",
        "WTIUSD",
        "BRENT",
        "NATGAS",
    }
)
_METALS_DESKS: frozenset[str] = frozenset({"XAUUSD", "XAGUSD", "XPTUSD", "XPDUSD"})


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    asset_class: AssetClassName
    classification_source: ClassificationSource
    classification_reason: str
    classification_confidence: ClassificationConfidence = "UNKNOWN"
    broker_metadata_keys: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_class": self.asset_class,
            "classification_source": self.classification_source,
            "classification_reason": self.classification_reason,
            "classification_confidence": self.classification_confidence,
            "broker_metadata_keys": list(self.broker_metadata_keys),
        }


def _text(*parts: Any) -> str:
    return " ".join(str(p or "").strip().lower() for p in parts if p not in (None, ""))


def _from_broker_metadata(row: dict[str, Any]) -> ClassificationResult | None:
    path = str(row.get("path") or row.get("symbol_path") or "")
    category = str(
        row.get("category")
        or row.get("group")
        or row.get("sector")
        or row.get("asset_class")
        or ""
    )
    calc = str(
        row.get("margin_calc_mode")
        or row.get("trade_calc_mode")
        or row.get("calc_mode")
        or ""
    ).lower()
    blob = _text(path, category, calc)
    if not blob:
        return None
    keys = tuple(
        k
        for k in (
            "path",
            "symbol_path",
            "category",
            "group",
            "sector",
            "asset_class",
            "margin_calc_mode",
        )
        if row.get(k) not in (None, "")
    )
    for token, cls in _PATH_TOKENS:
        if token in blob:
            return ClassificationResult(
                asset_class=cls,
                classification_source="BROKER_METADATA",
                classification_reason=(
                    f"broker metadata matched {token!r} in {blob[:80]!r}"
                ),
                classification_confidence="HIGH",
                broker_metadata_keys=keys,
            )
    if calc in {"forex", "forex_no_leverage", "0", "5"}:
        return ClassificationResult(
            asset_class="FOREX",
            classification_source="BROKER_METADATA",
            classification_reason=f"margin_calc_mode={calc}",
            classification_confidence="HIGH",
            broker_metadata_keys=keys,
        )
    if calc in {"cfdindex", "3"}:
        return ClassificationResult(
            asset_class="INDICES",
            classification_source="BROKER_METADATA",
            classification_reason=f"margin_calc_mode={calc}",
            classification_confidence="HIGH",
            broker_metadata_keys=keys,
        )
    return None


def _from_symbol_rule(symbol: str, description: str = "") -> ClassificationResult:
    desk = canonical_desk(symbol)
    if desk in _ENERGY_DESKS or desk.startswith(("XTI", "XBR", "XNG")):
        return ClassificationResult(
            asset_class="ENERGY",
            classification_source="SYMBOL_RULE",
            classification_reason=f"energy desk token {desk}",
            classification_confidence="MEDIUM",
        )
    if desk in _METALS_DESKS or "XAU" in desk or "XAG" in desk:
        return ClassificationResult(
            asset_class="METALS",
            classification_source="SYMBOL_RULE",
            classification_reason=f"metals desk token {desk}",
            classification_confidence="MEDIUM",
        )
    scalp = classify_broker_symbol(symbol, description)
    mapped = _SCALP_TO_PRODUCT.get(scalp, "UNKNOWN")
    if mapped == "FOREX" and desk in _ENERGY_DESKS:
        mapped = "ENERGY"
    confidence: ClassificationConfidence = "LOW"
    if mapped == "UNKNOWN":
        confidence = "UNKNOWN"
    elif mapped == "OTHER":
        confidence = "LOW"
    elif mapped in {"FOREX", "CRYPTO", "METALS", "INDICES", "ENERGY"} and (
        desk in _ENERGY_DESKS or desk in _METALS_DESKS or mapped != "FOREX"
    ):
        confidence = "MEDIUM"
    return ClassificationResult(
        asset_class=mapped,
        classification_source="SYMBOL_RULE",
        classification_reason=f"symbol rule via scalp classifier {scalp!r} → {mapped}",
        classification_confidence=confidence,
    )


def classify_instrument(
    symbol: str,
    *,
    description: str = "",
    broker_row: dict[str, Any] | None = None,
    manual_overrides: dict[str, tuple[str, str]] | None = None,
) -> ClassificationResult:
    """Classify one instrument with an auditable source.

    Precedence: MANUAL_OVERRIDE > BROKER_METADATA > SYMBOL_RULE.
    """
    desk = canonical_desk(symbol)
    overrides = (
        MANUAL_CLASSIFICATION_OVERRIDES
        if manual_overrides is None
        else manual_overrides
    )
    if desk in overrides:
        cls, reason = overrides[desk]
        asset = str(cls or "OTHER").upper()
        allowed = {
            "FOREX",
            "CRYPTO",
            "METALS",
            "INDICES",
            "ENERGY",
            "STOCKS",
            "COMMODITIES",
            "OTHER",
            "UNKNOWN",
        }
        if asset not in allowed:
            asset = "UNKNOWN"
        return ClassificationResult(
            asset_class=asset,  # type: ignore[arg-type]
            classification_source="MANUAL_OVERRIDE",
            classification_reason=reason or "documented manual override",
            classification_confidence="HIGH",
        )
    row = broker_row if isinstance(broker_row, dict) else {}
    meta = _from_broker_metadata(row)
    if meta is not None:
        return meta
    return _from_symbol_rule(symbol, description or str(row.get("description") or ""))


def classify_or_unknown(symbol: str | None) -> AssetClassName:
    code = (symbol or "").strip()
    if not code:
        return "UNKNOWN"
    return classify_instrument(code).asset_class


def product_class_label(value: str | None) -> str:
    raw = str(value or "").strip().upper()
    if raw in {
        "FOREX",
        "CRYPTO",
        "METALS",
        "INDICES",
        "ENERGY",
        "STOCKS",
        "COMMODITIES",
        "OTHER",
        "UNKNOWN",
    }:
        return raw
    return _SCALP_TO_PRODUCT.get(raw.lower(), UNKNOWN if not raw else "OTHER")
