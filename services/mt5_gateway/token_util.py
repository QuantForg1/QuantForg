"""Gateway shared secret helpers — normalize, mask, compare."""

from __future__ import annotations

import hmac
import re
import unicodedata


# BOM / zero-width / NBSP plus other invisible format controls that survive .strip().
_INVISIBLE = re.compile(
    r"[\u0000-\u001f\u007f-\u009f\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff\u00a0\u00ad]"
)


def normalize_gateway_token(raw: str | None) -> str:
    """Strip BOM, CR, quotes, invisible controls, and surrounding whitespace.

    Windows ``.env`` / NSSM values often include trailing ``\\r``, UTF-8 BOM,
    accidental surrounding quotes, or invisible Unicode — any of which break
    exact Bearer match while still producing identical first/last-6 masks.
    """
    if raw is None:
        return ""
    text = str(raw)
    # UTF-8 BOM or Windows UTF-16 LE BOM residue when mis-decoded.
    text = text.lstrip("\ufeff").replace("\r", "").replace("\n", "")
    text = unicodedata.normalize("NFKC", text)
    text = _INVISIBLE.sub("", text)
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        text = text[1:-1].strip()
        text = _INVISIBLE.sub("", text).strip()
    # Unwrap a mistaken "Bearer <secret>" stored as the env value itself.
    if text.lower().startswith("bearer ") or text.lower().startswith("bearer\t"):
        text = text[7:].strip()
    return text


def mask_gateway_token(token: str) -> str:
    """Safe fingerprint: first 6 + ****** + last 6 (or shorter form)."""
    token = normalize_gateway_token(token)
    if not token:
        return "<empty>"
    if len(token) <= 12:
        return f"{token[:2]}******{token[-2:]}" if len(token) > 4 else "******"
    return f"{token[:6]}******{token[-6:]}"


def tokens_equal(left: str | None, right: str | None) -> bool:
    """Constant-time compare after normalization (never raises on length mismatch)."""
    a = normalize_gateway_token(left)
    b = normalize_gateway_token(right)
    if not a or not b:
        return False
    a_b = a.encode("utf-8")
    b_b = b.encode("utf-8")
    if len(a_b) != len(b_b):
        return False
    return hmac.compare_digest(a_b, b_b)


def parse_authorization_bearer(authorization: str | None) -> str:
    """Parse ``Authorization: Bearer <token>`` without depending solely on HTTPBearer."""
    if not authorization:
        return ""
    # Strip BOM before scheme detection — ``\\ufeffBearer …`` must still parse.
    raw = str(authorization).lstrip("\ufeff").strip().replace("\r", "")
    lower = raw.lower()
    if lower.startswith("bearer ") or lower.startswith("bearer\t"):
        return normalize_gateway_token(raw[7:])
    return ""
