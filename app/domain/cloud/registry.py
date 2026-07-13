"""In-process gateway registry + security material — no DB schema change."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

from app.domain.cloud.types import GatewayRecord, GatewayStatus, utc_now


@dataclass
class FailureEvent:
    at: str
    gateway_id: str
    reason: str
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "at": self.at,
            "gateway_id": self.gateway_id,
            "reason": self.reason,
            "detail": self.detail,
        }


class GatewayRegistry:
    """Thread-safe registry of MT5 Windows gateways."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._gateways: dict[str, GatewayRecord] = {}
        self._token_hashes: dict[str, str] = {}
        self._nonces: dict[str, float] = {}
        self._failures: deque[FailureEvent] = deque(maxlen=200)
        self._rate: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=200))

    def all_gateways(self) -> list[GatewayRecord]:
        with self._lock:
            return list(self._gateways.values())

    def get(self, gateway_id: str) -> GatewayRecord | None:
        with self._lock:
            return self._gateways.get(gateway_id)

    def upsert(self, record: GatewayRecord, *, token_hash: str | None = None) -> None:
        with self._lock:
            self._gateways[record.gateway_id] = record
            if token_hash:
                self._token_hashes[record.gateway_id] = token_hash

    def remove(self, gateway_id: str) -> bool:
        with self._lock:
            existed = gateway_id in self._gateways
            self._gateways.pop(gateway_id, None)
            self._token_hashes.pop(gateway_id, None)
            return existed

    def set_token_hash(self, gateway_id: str, token_hash: str) -> None:
        with self._lock:
            self._token_hashes[gateway_id] = token_hash
            rec = self._gateways.get(gateway_id)
            if rec is not None:
                rec.token_fingerprint = token_hash[:12]
                rec.token_version += 1
                rec.updated_at = utc_now()

    def verify_token(self, gateway_id: str, token: str) -> bool:
        with self._lock:
            expected = self._token_hashes.get(gateway_id, "")
        if not expected or not token:
            return False
        actual = hash_token(token)
        return hmac.compare_digest(actual, expected)

    def record_failure(self, gateway_id: str, reason: str, detail: str = "") -> None:
        with self._lock:
            self._failures.append(
                FailureEvent(
                    at=utc_now(),
                    gateway_id=gateway_id,
                    reason=reason,
                    detail=detail,
                )
            )
            rec = self._gateways.get(gateway_id)
            if rec is not None:
                rec.failure_reason = reason
                if reason in {"heartbeat_timeout", "probe_failed", "unreachable"}:
                    rec.status = GatewayStatus.OFFLINE
                elif reason in {"degraded_latency", "partial_metrics"}:
                    rec.status = GatewayStatus.DEGRADED
                rec.updated_at = utc_now()

    def recent_failures(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = list(self._failures)[-limit:]
        return [f.to_dict() for f in reversed(rows)]

    def allow_nonce(self, nonce: str, *, ttl_seconds: float = 120.0) -> bool:
        """Replay protection — each nonce usable once within TTL window."""
        if not nonce or len(nonce) > 128:
            return False
        now = time.time()
        with self._lock:
            # purge expired
            expired = [k for k, exp in self._nonces.items() if exp < now]
            for k in expired:
                del self._nonces[k]
            if nonce in self._nonces:
                return False
            self._nonces[nonce] = now + ttl_seconds
            return True

    def rate_limit(
        self, key: str, *, limit: int = 60, window_seconds: float = 60.0
    ) -> bool:
        """Return True if allowed under simple sliding window."""
        now = time.time()
        with self._lock:
            q = self._rate[key]
            while q and q[0] < now - window_seconds:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True

    def ip_allowed(self, gateway_id: str, client_ip: str) -> bool:
        with self._lock:
            rec = self._gateways.get(gateway_id)
            if rec is None:
                return False
            if not rec.ip_allowlist:
                return True
            return client_ip in rec.ip_allowlist or client_ip == "127.0.0.1"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_gateway_token() -> str:
    return secrets.token_urlsafe(32)


@dataclass
class RouteDecision:
    gateway_id: str | None
    hostname: str | None
    broker: str
    region: str
    reason: str
    fallback_used: bool = False
    candidates: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gateway_id": self.gateway_id,
            "hostname": self.hostname,
            "broker": self.broker,
            "region": self.region,
            "reason": self.reason,
            "fallback_used": self.fallback_used,
            "candidates": list(self.candidates),
        }
