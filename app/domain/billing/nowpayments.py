"""NOWPayments LIVE API client and IPN signature verification.

Production host only: https://api.nowpayments.io/v1
Never falls back to the sandbox host.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.logging import get_logger

logger = get_logger(__name__)

NOWPAYMENTS_LIVE_BASE = "https://api.nowpayments.io/v1"

# Provider statuses that must NOT activate paid entitlements.
PENDING_STATUSES = frozenset(
    {
        "waiting",
        "confirming",
        "confirmed",
        "sending",
        "partially_paid",
    }
)
FINISHED_STATUS = "finished"
FAILED_STATUSES = frozenset({"failed", "expired", "refunded"})


def sort_object(value: Any) -> Any:
    """Alphabetically sort dict keys recursively (NOWPayments IPN contract)."""
    if isinstance(value, dict):
        return {k: sort_object(value[k]) for k in sorted(value.keys())}
    if isinstance(value, list):
        return [sort_object(item) for item in value]
    return value


def verify_ipn_signature(
    *,
    payload: dict[str, Any],
    signature: str,
    ipn_secret: str,
) -> bool:
    """Verify ``x-nowpayments-sig`` with HMAC-SHA512 over sorted JSON."""
    if not signature or not ipn_secret:
        return False
    sorted_payload = sort_object(payload)
    # Match documented PHP/Node samples: JSON without unnecessary escaping.
    encoded = json.dumps(sorted_payload, separators=(",", ":"), ensure_ascii=False)
    # Official Node sample uses JSON.stringify which may include spaces after `: `;
    # PHP uses JSON_UNESCAPED_SLASHES without pretty print. Try both encodings.
    candidates = [
        encoded,
        json.dumps(sorted_payload, ensure_ascii=False),
        json.dumps(sorted_payload, separators=(",", ":"), ensure_ascii=False).replace(
            "/", "\\/"
        ),
    ]
    # Prefer the compact form first (common in PHP plugins).
    digest = hmac.new(
        ipn_secret.encode("utf-8"),
        encoded.encode("utf-8"),
        hashlib.sha512,
    ).hexdigest()
    if hmac.compare_digest(digest, signature.strip()):
        return True
    for candidate in candidates[1:]:
        alt = hmac.new(
            ipn_secret.encode("utf-8"),
            candidate.encode("utf-8"),
            hashlib.sha512,
        ).hexdigest()
        if hmac.compare_digest(alt, signature.strip()):
            return True
    # Final attempt: Node-style JSON.stringify(sortObject(obj)) with default spacing.
    node_style = json.dumps(sorted_payload, ensure_ascii=False, separators=(", ", ": "))
    node_digest = hmac.new(
        ipn_secret.encode("utf-8"),
        node_style.encode("utf-8"),
        hashlib.sha512,
    ).hexdigest()
    return hmac.compare_digest(node_digest, signature.strip())


class NowPaymentsLiveClient:
    """Authenticated LIVE NOWPayments HTTP client (server-side only)."""

    def __init__(self, *, api_key: str, base_url: str = NOWPAYMENTS_LIVE_BASE) -> None:
        key = (api_key or "").strip()
        if not key:
            msg = "NOWPAYMENTS_API_KEY is required for LIVE checkout"
            raise ValueError(msg)
        base = (base_url or NOWPAYMENTS_LIVE_BASE).rstrip("/")
        if "sandbox" in base.lower():
            msg = (
                "Sandbox NOWPayments host is forbidden; "
                "use LIVE api.nowpayments.io only"
            )
            raise ValueError(msg)
        self._api_key = key
        self._base = base

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        timeout: float = 25.0,
    ) -> dict[str, Any]:
        url = f"{self._base}{path}"
        data = None
        headers = {
            "x-api-key": self._api_key,
            "Accept": "application/json",
        }
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if not url.startswith("https://"):
            msg = "NOWPayments client only allows HTTPS LIVE endpoints"
            raise ValueError(msg)
        req = Request(url, data=data, headers=headers, method=method.upper())  # noqa: S310
        try:
            with urlopen(req, timeout=timeout) as resp:  # noqa: S310
                raw = resp.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            logger.warning(
                "nowpayments_http_error",
                status=exc.code,
                path=path,
                detail=detail,
            )
            raise RuntimeError(f"NOWPayments HTTP {exc.code}") from exc
        except URLError as exc:
            logger.warning("nowpayments_network_error", path=path, error=str(exc))
            raise RuntimeError("NOWPayments network error") from exc
        if not raw:
            return {}
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return {"data": parsed}
        return parsed

    def status(self) -> dict[str, Any]:
        return self._request("GET", "/status")

    def currencies(self) -> list[str]:
        payload = self._request("GET", "/currencies")
        items = payload.get("currencies")
        if isinstance(items, list):
            return [str(c).lower() for c in items if c]
        return []

    def create_invoice(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/invoice", body=body)

    def get_payment(self, payment_id: str) -> dict[str, Any]:
        return self._request("GET", f"/payment/{payment_id}")
