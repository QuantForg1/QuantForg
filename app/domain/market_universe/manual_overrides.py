"""Explicit, documented classification overrides.

Empty by default. Add an entry only with a product-owner reason.
Never use this file to silently retune live gold execution.
"""

from __future__ import annotations

# canonical_desk -> (ASSET_CLASS, reason)
# Example (commented — not active):
# "XAUUSD": ("METALS", "Product-owner: gold is metals, not energy")
MANUAL_CLASSIFICATION_OVERRIDES: dict[str, tuple[str, str]] = {}
