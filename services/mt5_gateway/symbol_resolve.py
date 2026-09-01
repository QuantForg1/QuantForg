"""Catalogue-only MT5 symbol spelling.

Weltrade (and similar) expose gold as ``XAUUSD`` on some books and
``XAUUSD_i`` on others. Callers often uppercase the display form to
``XAUUSD_I``, which ``symbol_select`` rejects with Terminal: Call failed
even though the instrument is already quoting under another catalogue name.

Resolution never invents a name that is absent from ``symbols_get``.
"""

from __future__ import annotations

_GOLD_IDENTITY: tuple[str, ...] = ("XAUUSD", "XAUUSD_I", "GOLD", "XAUUSDM")
_SILVER_IDENTITY: tuple[str, ...] = ("XAGUSD", "XAGUSD_I", "SILVER")


def desk_code(symbol: str) -> str:
    """Strip a trailing institutional ``_I`` suffix (any case)."""
    key = (symbol or "").strip().upper()
    if key.endswith("_I") and len(key) > 3:
        return key[:-2]
    return key


def identity_alias_keys(symbol: str) -> tuple[str, ...]:
    """Ordered UPPER keys that share the same instrument identity."""
    key = (symbol or "").strip().upper()
    if not key:
        return ()
    desk = desk_code(key)
    ordered: list[str] = []
    seen: set[str] = set()

    def _add(name: str) -> None:
        n = (name or "").strip().upper()
        if not n or n in seen:
            return
        seen.add(n)
        ordered.append(n)

    _add(key)
    _add(desk)
    if desk:
        _add(f"{desk}_I")
    if desk in {"XAUUSD", "GOLD", "XAUUSDM"} or "XAU" in desk:
        for alias in _GOLD_IDENTITY:
            _add(alias)
    if desk in {"XAGUSD", "SILVER"} or "XAG" in desk:
        for alias in _SILVER_IDENTITY:
            _add(alias)
    return tuple(ordered)


def resolve_catalogue_symbol(
    requested: str, name_by_upper: dict[str, str]
) -> str | None:
    """Exact catalogue spelling for ``requested``, or None if unknown.

    Prefers an exact UPPER hit, then identity aliases that exist in the
    catalogue, then any catalogue name with the same desk code.
    """
    raw = (requested or "").strip()
    if not raw or not name_by_upper:
        return None
    key = raw.upper()
    hit = name_by_upper.get(key)
    if hit:
        return hit
    for alias in identity_alias_keys(key):
        hit = name_by_upper.get(alias)
        if hit:
            return hit
    desk = desk_code(key)
    if not desk:
        return None
    for cat_upper, exact in name_by_upper.items():
        if desk_code(cat_upper) == desk:
            return exact
    return None


def catalogue_exact_names(
    requested: str, name_by_upper: dict[str, str]
) -> tuple[str, ...]:
    """All catalogue-exact names that could satisfy ``requested`` (no duplicates)."""
    primary = resolve_catalogue_symbol(requested, name_by_upper)
    ordered: list[str] = []
    seen: set[str] = set()

    def _add(name: str | None) -> None:
        n = (name or "").strip()
        if not n or n in seen:
            return
        seen.add(n)
        ordered.append(n)

    _add(primary)
    for alias in identity_alias_keys(requested):
        _add(name_by_upper.get(alias))
    desk = desk_code(requested)
    if desk:
        for cat_upper, exact in name_by_upper.items():
            if desk_code(cat_upper) == desk:
                _add(exact)
    return tuple(ordered)
