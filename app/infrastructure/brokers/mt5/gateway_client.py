"""HTTP MT5 client — Railway → Windows MT5 Gateway (no local MetaTrader5).

Broker passwords are forwarded once to ``POST /session/connect`` and never
retained on this process. Prefer ``attach()`` when the terminal is already
logged in. Does not invent market data.

Cloudflare Quick Tunnel compatibility:
- ``follow_redirects=True`` (301/302/307/308)
- HTTP/2 when available
- Absolute HTTPS base URLs via ``normalize_gateway_base_url``
"""

from __future__ import annotations

import contextlib
import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse
from uuid import uuid4

import httpx

from app.domain.entities.mt5 import MT5AccountInfo, MT5Server, MT5Terminal
from app.domain.entities.mt5_market import MT5Rate, MT5SymbolInfo, MT5Tick
from app.domain.entities.mt5_order import TradeRequest
from app.domain.entities.mt5_portfolio import (
    AccountSnapshot,
    MT5Deal,
    MT5HistoryOrder,
    MT5PendingOrder,
    MT5Position,
)
from app.domain.interfaces.broker_adapter import BrokerSymbolInfo
from app.domain.interfaces.mt5_client import MT5HealthSnapshot, MT5LoginRequest
from app.domain.interfaces.mt5_order import (
    RETCODE_INVALID,
    MT5MarginResult,
    MT5OrderCheckResult,
    MT5OrderSendResult,
    MT5ProfitResult,
)
from app.domain.market_data.timeframe import Timeframe
from app.infrastructure.brokers.mt5.metrics import gateway_metrics
from core.logging import get_logger

logger = get_logger(__name__)

_BODY_PREVIEW_LIMIT = 200
_CLOUDFLARE_HOST_MARKERS = (
    "trycloudflare.com",
    "cloudflare.com",
    "cfargotunnel.com",
)


def _dec(value: Any, default: str = "0") -> Decimal:
    if value is None or value == "":
        return Decimal(default)
    return Decimal(str(value))


def _mt5_retcode(payload: dict[str, Any], *, default: int = RETCODE_INVALID) -> int:
    """Parse broker retcode without collapsing success ``0`` via falsy ``or``."""
    if "retcode" not in payload or payload.get("retcode") is None:
        return int(default)
    return int(payload["retcode"])


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def is_cloudflare_tunnel_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(marker in host for marker in _CLOUDFLARE_HOST_MARKERS)


def normalize_gateway_base_url(raw: str) -> str:
    """Normalize Railway ``MT5_GATEWAY_BASE_URL`` for Cloudflare HTTPS tunnels.

    - Trims whitespace and trailing slashes
    - Requires an absolute URL with scheme
    - Rejects accidental path-only values
    """
    text = (raw or "").strip()
    if not text:
        return ""
    parsed = urlparse(text)
    if not parsed.scheme or not parsed.netloc:
        msg = (
            f"MT5_GATEWAY_BASE_URL must be an absolute URL with scheme "
            f"(got {text!r}). Example: https://xxxx.trycloudflare.com"
        )
        raise ValueError(msg)
    path = parsed.path.rstrip("/")
    cleaned = urlunparse((parsed.scheme.lower(), parsed.netloc, path, "", "", ""))
    return cleaned.rstrip("/")


def join_gateway_url(base_url: str, path: str) -> str:
    """Join base + path without duplicating or dropping slashes."""
    base = normalize_gateway_base_url(base_url)
    suffix = path if path.startswith("/") else f"/{path}"
    return urljoin(base + "/", suffix.lstrip("/"))


def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in headers.items():
        low = key.lower()
        if low in {"authorization", "x-gateway-token"}:
            out[key] = "***" if value else ""
        else:
            out[key] = value
    return out


def _clip(text: str, limit: int = _BODY_PREVIEW_LIMIT) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "…(truncated)"


def classify_gateway_failure(
    *,
    error: str | None = None,
    status_code: int | None = None,
    error_type: str | None = None,
    body_preview: str | None = None,
    cloudflare: bool = False,
) -> str:
    """Map transport failures to short UI diagnostics (never generic Offline)."""
    err = (error or "").lower()
    et = (error_type or "").lower()
    body = (body_preview or "").lower()

    if status_code == 401 or "invalid or missing gateway token" in err + body:
        return "Invalid Gateway Token"
    if status_code == 403:
        return "403 Forbidden"
    if status_code == 404:
        return "404 Endpoint"
    if status_code == 429:
        return "Cloudflare rate limited"
    if status_code is not None and status_code >= 500:
        return (
            "Cloudflare upstream error" if cloudflare else f"Gateway HTTP {status_code}"
        )

    if "too many redirects" in err or "redirect loop" in err:
        return "Redirect loop"
    if "non-json" in err or "jsondecode" in et:
        return "JSON parse error"
    if "timeout" in err or "timeout" in et:
        return "Cloudflare timeout" if cloudflare else "Gateway timeout"
    if "ssl" in err or "tls" in err or "certificate" in err:
        return "TLS failure"
    if "connection refused" in err or "connecterror" in et:
        return "Gateway refused connection"
    if "name or service not known" in err or "nodename" in err:
        return "DNS failure"
    if cloudflare and ("523" in err or "524" in err or "522" in err):
        return "Cloudflare timeout"
    if error:
        return _clip(error, 120)
    if status_code is not None:
        return f"Gateway HTTP {status_code}"
    return "Gateway unreachable"


@dataclass
class GatewayMT5Client:
    """Sync httpx client implementing ``MT5ClientPort`` against gateway REST."""

    base_url: str
    token: str
    timeout_seconds: float = 30.0
    stores_credentials_remotely: bool = field(default=True, init=False)
    _initialized: bool = field(default=False, init=False)
    _connected: bool = field(default=False, init=False)
    _login: int = field(default=0, init=False)
    _server: str = field(default="", init=False)
    _path: str = field(default="", init=False)
    _session_token: str = field(default="", init=False)
    _last_heartbeat: datetime | None = field(default=None, init=False)
    _session_mode: str = field(default="none", init=False)
    _last_gateway_health: dict[str, Any] = field(default_factory=dict, init=False)
    _last_upstream: dict[str, Any] = field(default_factory=dict, init=False)
    _catalogue_cache: list[BrokerSymbolInfo] = field(default_factory=list, init=False)
    _catalogue_cached_at: float = field(default=0.0, init=False)
    _catalogue_ttl_seconds: float = field(default=60.0, init=False)
    _account_cache: MT5AccountInfo | None = field(default=None, init=False)
    _account_cache_at: float = field(default=0.0, init=False)
    _positions_cache: list[MT5Position] | None = field(default=None, init=False)
    _positions_cache_at: float = field(default=0.0, init=False)
    _snapshot_ttl_seconds: float = field(default=0.75, init=False)

    def __post_init__(self) -> None:
        self.base_url = normalize_gateway_base_url(self.base_url)
        self.token = (self.token or "").strip()

    @property
    def session_token(self) -> str:
        return self._session_token

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def session_mode(self) -> str:
        return self._session_mode

    @property
    def is_cloudflare(self) -> bool:
        return is_cloudflare_tunnel_url(self.base_url)

    def last_upstream(self) -> dict[str, Any]:
        return dict(self._last_upstream)

    def _headers(self, *, auth: bool) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
            "User-Agent": "QuantForg-Railway-GatewayClient/1.1",
        }
        if auth and self.token:
            # Gateway accepts either header; send both for tunnel proxies that
            # strip one of them.
            headers["Authorization"] = f"Bearer {self.token}"
            headers["X-Gateway-Token"] = self.token
        return headers

    def _timeout(self) -> httpx.Timeout:
        # Cloudflare Quick Tunnels can be slow on first connect.
        connect = min(15.0, float(self.timeout_seconds))
        return httpx.Timeout(
            self.timeout_seconds,
            connect=connect,
            read=float(self.timeout_seconds),
            write=float(self.timeout_seconds),
            pool=connect,
        )

    def _record_upstream(self, payload: dict[str, Any]) -> None:
        self._last_upstream = payload

    def _build_http_client(self) -> httpx.Client:
        """Prefer HTTP/2; fall back to 1.1 if the runtime lacks ``h2``."""
        common: dict[str, Any] = {
            "timeout": self._timeout(),
            "follow_redirects": True,
            "trust_env": True,
        }
        try:
            return httpx.Client(http2=True, **common)
        except Exception as exc:
            logger.warning(
                "gateway_http2_unavailable",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return httpx.Client(http2=False, **common)

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        auth: bool = True,
    ) -> dict[str, Any]:
        if not self.base_url:
            raise RuntimeError(
                "MT5_GATEWAY_BASE_URL is empty — "
                "Railway cannot reach the Windows gateway"
            )
        if auth and not self.token and path != "/health":
            raise RuntimeError(
                "MT5_GATEWAY_CALLER_TOKEN is not configured on the API "
                "(must match Windows MT5_GATEWAY_TOKEN)"
            )

        url = join_gateway_url(self.base_url, path)
        headers = self._headers(auth=auth)
        safe_headers = _redact_headers(headers)
        started = datetime.now(UTC).isoformat()
        t0 = time.perf_counter()
        cloudflare = is_cloudflare_tunnel_url(url) or self.is_cloudflare

        logger.info(
            "gateway_http_request",
            method=method,
            gateway_url=self.base_url,
            resolved_url=url,
            path=path,
            auth=auth,
            token_configured=bool(self.token),
            headers=safe_headers,
            timeout_seconds=self.timeout_seconds,
            cloudflare=cloudflare,
            follow_redirects=True,
            http2=True,
            has_json_body=json_body is not None,
            # Never log password even if present in body keys.
            json_keys=sorted(k for k in (json_body or {}) if k.lower() != "password"),
        )

        try:
            with self._build_http_client() as client:
                # Safe retries: GET + connect failures only. Never retry order_send
                # after the request may have reached the broker (duplicate risk).
                attempts = 2 if method.upper() == "GET" else 1
                last_exc: Exception | None = None
                response = None
                for attempt_i in range(attempts):
                    try:
                        response = client.request(
                            method,
                            url,
                            headers=headers,
                            json=json_body,
                            params=params,
                        )
                        last_exc = None
                        break
                    except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                        last_exc = exc
                        if attempt_i + 1 >= attempts:
                            raise
                        time.sleep(0.15 * (attempt_i + 1))
                if response is None and last_exc is not None:
                    raise last_exc
                assert response is not None
        except httpx.TooManyRedirects as exc:
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            gateway_metrics.record_request(latency_ms=latency_ms, error=True)
            detail = f"Redirect loop calling {method} {url}: {exc}"
            label = classify_gateway_failure(
                error=detail,
                error_type=type(exc).__name__,
                cloudflare=cloudflare,
            )
            self._record_upstream(
                {
                    "ok": False,
                    "method": method,
                    "url": url,
                    "requested_url": url,
                    "path": path,
                    "error": detail,
                    "error_type": type(exc).__name__,
                    "diagnostic": label,
                    "latency_ms": latency_ms,
                    "redirects_followed": None,
                    "cloudflare": cloudflare,
                    "started_at": started,
                }
            )
            logger.warning(
                "gateway_http_redirect_loop",
                method=method,
                resolved_url=url,
                error=str(exc),
                latency_ms=latency_ms,
                diagnostic=label,
            )
            raise RuntimeError(f"{label}: {detail}") from exc
        except httpx.TimeoutException as exc:
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            gateway_metrics.record_request(latency_ms=latency_ms, error=True)
            detail = (
                f"Gateway timeout calling {method} {url} "
                f"(timeout={self.timeout_seconds}s): {exc}"
            )
            label = classify_gateway_failure(
                error=detail,
                error_type=type(exc).__name__,
                cloudflare=cloudflare,
            )
            self._record_upstream(
                {
                    "ok": False,
                    "method": method,
                    "url": url,
                    "requested_url": url,
                    "path": path,
                    "error": detail,
                    "error_type": type(exc).__name__,
                    "diagnostic": label,
                    "latency_ms": latency_ms,
                    "cloudflare": cloudflare,
                    "started_at": started,
                }
            )
            logger.warning(
                "gateway_http_timeout",
                method=method,
                resolved_url=url,
                error=str(exc),
                timeout_seconds=self.timeout_seconds,
                latency_ms=latency_ms,
                diagnostic=label,
                cloudflare=cloudflare,
            )
            raise RuntimeError(f"{label}: {detail}") from exc
        except httpx.HTTPError as exc:
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            gateway_metrics.record_request(latency_ms=latency_ms, error=True)
            detail = f"Gateway unreachable calling {method} {url}: {exc}"
            label = classify_gateway_failure(
                error=detail,
                error_type=type(exc).__name__,
                cloudflare=cloudflare,
            )
            self._record_upstream(
                {
                    "ok": False,
                    "method": method,
                    "url": url,
                    "requested_url": url,
                    "path": path,
                    "error": detail,
                    "error_type": type(exc).__name__,
                    "diagnostic": label,
                    "latency_ms": latency_ms,
                    "cloudflare": cloudflare,
                    "started_at": started,
                }
            )
            logger.warning(
                "gateway_http_error",
                method=method,
                resolved_url=url,
                error=str(exc),
                error_type=type(exc).__name__,
                latency_ms=latency_ms,
                diagnostic=label,
                cloudflare=cloudflare,
            )
            raise RuntimeError(f"{label}: {detail}") from exc

        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        body_text = response.text or ""
        history = list(response.history)
        redirects_followed = len(history)
        cf_ray = response.headers.get("cf-ray", "")
        cf_cache = response.headers.get("cf-cache-status", "")
        http_version = getattr(response, "http_version", "") or ""
        gateway_metrics.record_request(
            latency_ms=latency_ms,
            error=response.status_code >= 400,
        )

        upstream = {
            "ok": response.is_success,
            "method": method,
            "url": str(response.url),
            "requested_url": url,
            "path": path,
            "status_code": response.status_code,
            "redirected": redirects_followed > 0 or str(response.url) != url,
            "redirects_followed": redirects_followed,
            "latency_ms": latency_ms,
            "http_version": http_version,
            "cloudflare": cloudflare or bool(cf_ray),
            "cloudflare_ray": cf_ray or None,
            "cloudflare_cache": cf_cache or None,
            "headers": {
                "content-type": response.headers.get("content-type", ""),
                "content-encoding": response.headers.get("content-encoding", ""),
                "server": response.headers.get("server", ""),
            },
            "body_preview": _clip(body_text),
            "token_sent": bool(auth and self.token),
            "started_at": started,
        }
        self._record_upstream(upstream)

        logger.info(
            "gateway_http_response",
            method=method,
            gateway_url=self.base_url,
            resolved_url=str(response.url),
            requested_url=url,
            path=path,
            status_code=response.status_code,
            redirects_followed=redirects_followed,
            latency_ms=latency_ms,
            http_version=http_version,
            cloudflare=upstream["cloudflare"],
            cloudflare_ray=cf_ray or None,
            content_type=response.headers.get("content-type", ""),
            content_encoding=response.headers.get("content-encoding", ""),
            body_preview=_clip(body_text),
            token_sent=bool(auth and self.token),
        )

        if response.status_code >= 400:
            upstream_detail: Any
            try:
                payload = response.json()
                upstream_detail = (
                    payload.get("detail", payload)
                    if isinstance(payload, dict)
                    else payload
                )
            except Exception:
                upstream_detail = _clip(body_text or response.reason_phrase)
            label = classify_gateway_failure(
                error=str(upstream_detail),
                status_code=response.status_code,
                body_preview=body_text,
                cloudflare=bool(upstream["cloudflare"]),
            )
            msg = (
                f"{label}: Gateway {path} failed upstream "
                f"HTTP {response.status_code} at {response.url}: "
                f"{upstream_detail}"
            )
            upstream["error"] = msg
            upstream["diagnostic"] = label
            raise RuntimeError(msg)

        if not body_text.strip():
            return {}

        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            label = "JSON parse error"
            msg = (
                f"{label}: Gateway {path} returned non-JSON body "
                f"(HTTP {response.status_code}) at {response.url}: "
                f"{_clip(body_text)}"
            )
            upstream["error"] = msg
            upstream["diagnostic"] = label
            logger.warning(
                "gateway_http_json_error",
                method=method,
                resolved_url=str(response.url),
                status_code=response.status_code,
                error=str(exc),
                body_preview=_clip(body_text),
                diagnostic=label,
            )
            raise RuntimeError(msg) from exc

        if isinstance(data, dict):
            return data
        return {"data": data}

    def gateway_health(self) -> dict[str, Any]:
        data = self._request("GET", "/health", auth=False)
        self._last_gateway_health = data
        return data

    def diagnostics_probe(self) -> dict[str, Any]:
        """Return transport diagnostics for Weltrade health/UI."""
        upstream = self.last_upstream()
        return {
            "base_url": self.base_url,
            "gateway_url": self.base_url,
            "token_configured": bool(self.token),
            "timeout_seconds": self.timeout_seconds,
            "cloudflare": self.is_cloudflare or bool(upstream.get("cloudflare")),
            "follow_redirects": True,
            "http2": True,
            "last_upstream": upstream,
            "last_gateway_health": dict(self._last_gateway_health),
            "session_mode": self._session_mode,
            "connected": self._connected,
            "redirects_followed": upstream.get("redirects_followed"),
            "latency_ms": upstream.get("latency_ms"),
            "gateway_metrics": gateway_metrics.snapshot(),
            "last_http_status": upstream.get("status_code"),
            "last_body_preview": upstream.get("body_preview"),
            "last_upstream_error": upstream.get("error"),
            "diagnostic": upstream.get("diagnostic"),
        }

    def initialize(self, *, path: str = "") -> bool:
        if not self.base_url:
            return False
        try:
            health = self.gateway_health()
        except RuntimeError as exc:
            logger.warning("gateway_initialize_failed", error=str(exc))
            return False
        if health.get("status") != "ok":
            logger.warning(
                "gateway_initialize_unhealthy",
                health_status=health.get("status"),
                health=health,
            )
            return False
        if health.get("bridge_available") is False:
            logger.warning("gateway_bridge_unavailable", health=health)
            return False
        self._path = path.strip()
        self._initialized = True
        return True

    def login(self, request: MT5LoginRequest) -> bool:
        if not self._initialized and not self.initialize(path=request.path):
            return False
        # Never re-login over a live attached gateway session.
        if self.adopt_existing_session():
            logger.info(
                "gateway_login_skipped_existing_session",
                login=self._login,
                session_mode=self._session_mode,
            )
            return True
        body = {
            "login": int(request.login),
            "password": request.password,
            "server": request.server.strip(),
            "path": (request.path or self._path or "").strip(),
        }
        try:
            data = self._request("POST", "/session/connect", json_body=body)
        except RuntimeError as exc:
            logger.exception(
                "gateway_login_failed",
                error=str(exc),
                login=request.login,
                last_upstream=self.last_upstream(),
            )
            return False
        if not data.get("connected"):
            logger.warning(
                "gateway_login_not_connected",
                login=request.login,
                response=data,
                last_upstream=self.last_upstream(),
            )
            return False
        self._apply_session(
            login=int(data.get("login") or request.login),
            server=str(data.get("server") or request.server),
            mode=str(data.get("session_mode") or "connected"),
        )
        return True

    def adopt_existing_session(self) -> bool:
        """Adopt a live gateway MT5 session via GET /session/status (no re-login).

        Always probe status before POST /session/attach or POST /session/connect.
        When ``connected=true`` OR ``session_mode`` is ``attached``/``connected``,
        bind to that session and skip another login.
        """
        if not self.base_url:
            return False
        if not self._initialized and not self.initialize():
            return False
        try:
            status = self._request("GET", "/session/status")
        except RuntimeError as exc:
            logger.warning("gateway_adopt_status_failed", error=str(exc))
            return False
        mode = str(status.get("session_mode") or "").strip().lower()
        live = bool(status.get("connected")) or mode in {"attached", "connected"}
        if not live:
            return False
        self._apply_session(
            login=int(status.get("login") or 0),
            server=str(status.get("server") or ""),
            mode=mode or "attached",
        )
        self._initialized = True
        logger.info(
            "gateway_session_adopted",
            login=self._login,
            server=self._server,
            session_mode=self._session_mode,
        )
        return True

    def attach(self, *, path: str = "") -> bool:
        """Reuse an already logged-in terminal — no broker password on Railway."""
        term_path = (path or self._path or "").strip()
        if not self._initialized and not self.initialize(path=term_path):
            return False
        # Already attached on Windows: adopt via status — do not re-init/login.
        if self.adopt_existing_session():
            return True
        try:
            data = self._request(
                "POST",
                "/session/attach",
                json_body={"path": term_path},
            )
        except RuntimeError as exc:
            logger.exception("gateway_attach_failed", error=str(exc))
            return False
        if not data.get("connected"):
            return False
        self._apply_session(
            login=int(data.get("login") or 0),
            server=str(data.get("server") or ""),
            mode=str(data.get("session_mode") or "attached"),
        )
        return True

    def _apply_session(self, *, login: int, server: str, mode: str) -> None:
        self._login = login
        self._server = server
        self._connected = True
        self._session_mode = mode
        self._session_token = f"gw-mt5-{uuid4().hex[:12]}"
        self._last_heartbeat = datetime.now(UTC)
        self._clear_data_caches()

    def _clear_data_caches(self) -> None:
        self._catalogue_cache = []
        self._catalogue_cached_at = 0.0
        self._account_cache = None
        self._account_cache_at = 0.0
        self._positions_cache = None
        self._positions_cache_at = 0.0

    def shutdown(self) -> None:
        if self._initialized and self.token:
            with contextlib.suppress(RuntimeError):
                self._request("POST", "/session/disconnect", json_body={})
        self._connected = False
        self._initialized = False
        self._session_token = ""
        self._login = 0
        self._server = ""
        self._session_mode = "none"
        self._clear_data_caches()

    def reconnect(self, request: MT5LoginRequest) -> bool:
        if request.password:
            self.shutdown()
            if not self.initialize(path=request.path or self._path):
                return False
            return self.login(request)
        try:
            status = self._request("GET", "/session/status")
            if status.get("connected"):
                health = _as_dict(status.get("health"))
                self._apply_session(
                    login=int(status.get("login") or self._login or 0),
                    server=str(status.get("server") or self._server or ""),
                    mode=str(status.get("session_mode") or "attached"),
                )
                if health.get("latency_ms") is not None:
                    self._last_heartbeat = datetime.now(UTC)
                return True
        except RuntimeError as exc:
            logger.warning("gateway_reconnect_status_failed", error=str(exc))
        return self.attach(path=request.path or self._path)

    def ping(self) -> float:
        self._require_connected()
        data = self._request("GET", "/heartbeat")
        self._last_heartbeat = datetime.now(UTC)
        return float(data.get("ping_ms") or 0.0)

    def terminal_info(self) -> MT5Terminal:
        health = self.health()
        return MT5Terminal(
            build=int(health.terminal_build or 0),
            name="MetaTrader 5 (Gateway)",
            path=self._path,
            company="Weltrade via QuantForg Gateway",
            language="en",
            connected=self._connected,
        )

    def version(self) -> tuple[int, int, int]:
        raw = ""
        try:
            snap = self.health()
            raw = snap.version or ""
        except Exception:
            raw = ""
        parts = [*raw.split("."), "0", "0", "0"][:3]
        # Strip " (28 Apr 2026)" style suffixes from gateway version strings.
        clean: list[str] = []
        for part in parts:
            clean.append(part.split()[0].split("(")[0] or "0")
        try:
            return int(clean[0] or 0), int(clean[1] or 0), int(clean[2] or 0)
        except ValueError:
            return (0, 0, 0)

    def account_info(self) -> MT5AccountInfo:
        self._require_connected()
        now = time.monotonic()
        if (
            self._account_cache is not None
            and now - self._account_cache_at <= self._snapshot_ttl_seconds
        ):
            gateway_metrics.record_cache(hit=True)
            return self._account_cache
        gateway_metrics.record_cache(hit=False)
        data = self._request("GET", "/account")
        info = MT5AccountInfo(
            login=int(data.get("login") or self._login),
            name=str(data.get("name") or f"Account {data.get('login', '')}"),
            server=str(data.get("server") or self._server),
            currency=str(data.get("currency") or "USD"),
            leverage=int(data.get("leverage") or 1),
            balance=_dec(data.get("balance")),
            equity=_dec(data.get("equity")),
            margin=_dec(data.get("margin")),
            free_margin=_dec(data.get("free_margin")),
            margin_level=_dec(data.get("margin_level")),
            profit=_dec(data.get("profit")),
            company="Weltrade",
            trade_mode="demo",
        )
        self._account_cache = info
        self._account_cache_at = now
        return info

    def server_info(self) -> MT5Server:
        return MT5Server(
            name=self._server or "Weltrade",
            company="Weltrade",
            trade_mode="demo",
        )

    def symbols(self) -> list[BrokerSymbolInfo]:
        self._require_connected()
        cached = self._catalogue_cached()
        if cached is not None:
            gateway_metrics.record_cache(hit=True)
            return list(cached)
        gateway_metrics.record_cache(hit=False)
        data = self._request("GET", "/symbols")
        items = data.get("items") or []
        out = [
            BrokerSymbolInfo(
                code=str(row.get("code") or ""),
                description=str(row.get("description") or ""),
                digits=int(row.get("digits") or 0),
                contract_size=Decimal("100000"),
            )
            for row in items
            if row.get("code")
        ]
        self._catalogue_cache = out
        self._catalogue_cached_at = time.monotonic()
        return list(out)

    def _catalogue_cached(self) -> list[BrokerSymbolInfo] | None:
        if not self._catalogue_cache:
            return None
        if time.monotonic() - self._catalogue_cached_at > self._catalogue_ttl_seconds:
            return None
        return self._catalogue_cache

    def health(self) -> MT5HealthSnapshot:
        latency: float | None = None
        terminal_build: int | None = None
        version = ""
        login_status = "logged_out"
        server = self._server
        connected = self._connected
        try:
            if self.token:
                status = self._request("GET", "/session/status")
                connected = bool(status.get("connected"))
                self._connected = connected
                server = str(status.get("server") or server)
                if status.get("login") is not None:
                    self._login = int(status["login"])
                mode = status.get("session_mode")
                if mode:
                    self._session_mode = str(mode)
                h = _as_dict(status.get("health"))
                latency = (
                    float(h["latency_ms"]) if h.get("latency_ms") is not None else None
                )
                terminal_build = (
                    int(h["terminal_build"])
                    if h.get("terminal_build") is not None
                    else None
                )
                version = str(h.get("version") or "")
                login_status = str(
                    h.get("login_status")
                    or ("logged_in" if connected else "logged_out")
                )
                # Treat gateway "connected" / "ok" as healthy login.
                if login_status in {"ok", "connected"}:
                    login_status = "connected"
                if h.get("last_heartbeat_at"):
                    self._last_heartbeat = datetime.now(UTC)
            else:
                gw = self.gateway_health()
                mt5 = _as_dict(gw.get("mt5"))
                connected = bool(mt5.get("connected"))
                latency = (
                    float(mt5["latency_ms"])
                    if mt5.get("latency_ms") is not None
                    else None
                )
        except RuntimeError as exc:
            login_status = "error"
            connected = False
            self._connected = False
            logger.warning("gateway_health_probe_failed", error=str(exc))
        return MT5HealthSnapshot(
            connected=connected,
            latency_ms=latency,
            terminal_build=terminal_build,
            server=server,
            login_status=login_status,
            last_heartbeat_at=(
                self._last_heartbeat.isoformat() if self._last_heartbeat else None
            ),
            version=version,
        )

    def list_symbols(
        self,
        *,
        include_quotes: bool = False,
        codes: list[str] | None = None,
    ) -> list[MT5SymbolInfo]:
        """Return catalogue symbols without N+1 quote fan-out by default."""
        catalogue = self.symbols()
        wanted: set[str] | None = None
        if codes:
            wanted = {c.strip().upper() for c in codes if c and c.strip()}
        rows = [
            s
            for s in catalogue
            if s.code and (wanted is None or s.code.upper() in wanted)
        ]
        out: list[MT5SymbolInfo] = []
        for meta in rows:
            code = meta.code.upper()
            bid = Decimal("0")
            ask = Decimal("0")
            if include_quotes:
                try:
                    tick = self._request("GET", f"/quotes/{code}")
                    bid = _dec(tick.get("bid"))
                    ask = _dec(tick.get("ask"))
                except RuntimeError:
                    pass
            out.append(
                MT5SymbolInfo(
                    code=code,
                    description=meta.description or code,
                    digits=meta.digits or 5,
                    point=Decimal("0.00001"),
                    contract_size=meta.contract_size or Decimal("100000"),
                    selected=True,
                    trade_mode="full",
                    currency_base="",
                    currency_profit="",
                    bid=bid,
                    ask=ask,
                )
            )
        return out

    def symbol_info(self, symbol: str) -> MT5SymbolInfo:
        self._require_connected()
        code = symbol.strip().upper()
        # Prefer dedicated live specs endpoint (volume_step, stops, filling, …)
        try:
            specs = self._request("GET", f"/symbols/{code}")
        except RuntimeError:
            specs = {}
            try:
                tick_payload = self._request("GET", f"/quotes/{code}")
                specs = dict(tick_payload.get("specs") or {})
                if not specs:
                    # Fall back to quote + catalogue digits only
                    catalogue = self.symbols()
                    meta = next((s for s in catalogue if s.code.upper() == code), None)
                    return MT5SymbolInfo(
                        code=code,
                        description=meta.description if meta else code,
                        digits=meta.digits if meta else 5,
                        point=_dec(tick_payload.get("point"), "0.00001"),
                        contract_size=(
                            meta.contract_size if meta else Decimal("100000")
                        ),
                        selected=True,
                        trade_mode="full",
                        bid=_dec(tick_payload.get("bid")),
                        ask=_dec(tick_payload.get("ask")),
                    )
            except RuntimeError as exc:
                raise RuntimeError(
                    f"symbol_info unavailable for {code}: {exc}"
                ) from exc

        trade_mode = str(specs.get("trade_mode") or "full")
        trade_allowed = bool(specs.get("trade_allowed", trade_mode != "disabled"))
        market_open = bool(specs.get("market_open", True))
        return MT5SymbolInfo(
            code=code,
            description=str(specs.get("description") or code),
            digits=int(specs.get("digits") or 5),
            point=_dec(specs.get("point"), "0.00001"),
            contract_size=_dec(specs.get("contract_size"), "100000"),
            selected=bool(specs.get("selected", True)),
            trade_mode=trade_mode,
            currency_base=str(specs.get("currency_base") or ""),
            currency_profit=str(specs.get("currency_profit") or ""),
            bid=_dec(specs.get("bid")) if specs.get("bid") is not None else None,
            ask=_dec(specs.get("ask")) if specs.get("ask") is not None else None,
            volume_min=_dec(specs.get("volume_min"), "0.01"),
            volume_max=_dec(specs.get("volume_max"), "100"),
            volume_step=_dec(specs.get("volume_step"), "0.01"),
            stops_level=int(specs.get("stops_level") or 0),
            freeze_level=int(specs.get("freeze_level") or 0),
            filling_mode=int(specs.get("filling_mode") or 0),
            execution_mode=str(specs.get("execution_mode") or "market"),
            margin_calc_mode=str(specs.get("margin_calc_mode") or ""),
            visible=bool(specs.get("visible", True)),
            market_open=market_open,
            trade_allowed=trade_allowed,
        )

    def symbol_select(self, symbol: str, *, enable: bool = True) -> bool:
        _ = enable
        self._require_connected()
        try:
            self._request("GET", f"/quotes/{symbol.strip().upper()}")
            return True
        except RuntimeError:
            return False

    def latest_tick(self, symbol: str) -> MT5Tick:
        self._require_connected()
        data = self._request("GET", f"/quotes/{symbol.strip().upper()}")
        ts = data.get("time")
        timestamp = datetime.fromtimestamp(int(ts), tz=UTC) if ts else datetime.now(UTC)
        return MT5Tick(
            symbol=str(data.get("symbol") or symbol).upper(),
            bid=_dec(data.get("bid")),
            ask=_dec(data.get("ask")),
            timestamp=timestamp,
            volume=Decimal("0"),
        )

    def copy_rates_from(
        self,
        symbol: str,
        timeframe: Timeframe,
        date_from: datetime,
        count: int,
    ) -> list[MT5Rate]:
        """Fetch recent candles and keep those at/after ``date_from``.

        Gateway HTTP API only exposes ``count`` (no absolute from-time). We
        over-fetch then filter so callers never get bars silently outside the
        requested window.
        """
        if count < 1:
            return []
        start = date_from if date_from.tzinfo else date_from.replace(tzinfo=UTC)
        fetch = min(5000, max(count, count * 4))
        rates = self.copy_rates_from_pos(symbol, timeframe, 0, fetch)
        filtered = [r for r in rates if r.open_time >= start]
        if not filtered:
            return []
        return filtered[-count:]

    def copy_rates_range(
        self,
        symbol: str,
        timeframe: Timeframe,
        date_from: datetime,
        date_to: datetime,
    ) -> list[MT5Rate]:
        """Fetch then filter to ``[date_from, date_to]`` (fail-closed empty)."""
        start = date_from if date_from.tzinfo else date_from.replace(tzinfo=UTC)
        end = date_to if date_to.tzinfo else date_to.replace(tzinfo=UTC)
        if end < start:
            return []
        rates = self.copy_rates_from_pos(symbol, timeframe, 0, 5000)
        return [r for r in rates if start <= r.open_time <= end]

    def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: Timeframe,
        start_pos: int,
        count: int,
    ) -> list[MT5Rate]:
        self._require_connected()
        if count < 1:
            return []
        # Gateway returns newest-first window of ``count``; ``start_pos`` is
        # applied client-side by requesting an extended window then slicing.
        pos = max(0, int(start_pos))
        fetch = min(5000, pos + count)
        data = self._request(
            "GET",
            f"/candles/{symbol.strip().upper()}",
            params={"timeframe": timeframe.value, "count": fetch},
        )
        items = data.get("items") or []
        rates: list[MT5Rate] = []
        for row in items:
            rates.append(
                MT5Rate(
                    symbol=symbol.strip().upper(),
                    timeframe=timeframe,
                    open_time=datetime.fromtimestamp(int(row["time"]), tz=UTC),
                    open=_dec(row.get("open")),
                    high=_dec(row.get("high")),
                    low=_dec(row.get("low")),
                    close=_dec(row.get("close")),
                    tick_volume=0,
                    spread_points=0,
                    real_volume=Decimal("0"),
                )
            )
        # Assume gateway returns chronological ascending; oldest at index 0.
        if pos:
            rates = rates[pos:] if pos < len(rates) else []
        return rates[:count]

    def order_check(self, request: TradeRequest) -> MT5OrderCheckResult:
        self._require_connected()
        data = self._request(
            "POST",
            "/trade/order_check",
            json_body={
                "symbol": request.symbol,
                "action": request.action,
                "volume": float(request.volume),
                "price": float(request.price),
                "sl": float(request.stop_loss),
                "tp": float(request.take_profit),
                "deviation": int(request.deviation),
                "magic": int(request.magic),
                "comment": request.comment or "quantforg",
                "position": int(request.position or 0),
                "order_ticket": int(request.order_ticket or 0),
                "oms_kind": request.oms_kind or "",
            },
        )
        return MT5OrderCheckResult(
            retcode=_mt5_retcode(data),
            comment=str(data.get("comment") or ""),
            request=request,
            balance=_dec(data.get("balance")),
            equity=_dec(data.get("equity")),
            margin=_dec(data.get("margin")),
            margin_free=_dec(data.get("margin_free")),
            profit=_dec(data.get("profit")),
        )

    def order_calc_margin(self, request: TradeRequest) -> MT5MarginResult:
        self._require_connected()
        data = self._request(
            "POST",
            "/trade/order_calc_margin",
            json_body={
                "symbol": request.symbol,
                "action": request.action,
                "volume": float(request.volume),
                "price": float(request.price),
            },
        )
        return MT5MarginResult(
            margin=_dec(data.get("margin")),
            retcode=_mt5_retcode(data),
            comment=str(data.get("comment") or ""),
        )

    def order_calc_profit(
        self,
        request: TradeRequest,
        *,
        close_price: Decimal | None = None,
    ) -> MT5ProfitResult:
        self._require_connected()
        body: dict[str, Any] = {
            "symbol": request.symbol,
            "action": request.action,
            "volume": float(request.volume),
            "price": float(request.price),
        }
        if close_price is not None:
            body["close_price"] = float(close_price)
        data = self._request("POST", "/trade/order_calc_profit", json_body=body)
        return MT5ProfitResult(
            profit=_dec(data.get("profit")),
            retcode=_mt5_retcode(data),
            comment=str(data.get("comment") or ""),
        )

    def order_send(self, request: TradeRequest) -> MT5OrderSendResult:
        """POST /trade/order_send → MetaTrader5.order_send — never invents fills."""
        self._require_connected()
        data = self._request(
            "POST",
            "/trade/order_send",
            json_body={
                "symbol": request.symbol,
                "action": request.action,
                "volume": float(request.volume),
                "price": float(request.price),
                "sl": float(request.stop_loss),
                "tp": float(request.take_profit),
                "deviation": int(request.deviation),
                "magic": int(request.magic),
                "comment": request.comment or "quantforg",
                "position": int(request.position or 0),
                "order_ticket": int(request.order_ticket or 0),
                "oms_kind": request.oms_kind or "",
            },
        )
        self._positions_cache = None
        self._positions_cache_at = 0.0
        self._account_cache = None
        self._account_cache_at = 0.0
        return MT5OrderSendResult(
            retcode=_mt5_retcode(data),
            comment=str(data.get("comment") or ""),
            order_ticket=int(data.get("order_ticket") or 0),
            deal_ticket=int(data.get("deal_ticket") or 0),
            volume=_dec(data.get("volume"), str(request.volume)),
            price=_dec(data.get("price"), str(request.price)),
            request=request,
        )

    def order_cancel(self, ticket: int) -> MT5OrderSendResult:
        self._require_connected()
        data = self._request(
            "POST",
            "/trade/order_cancel",
            json_body={"ticket": int(ticket)},
        )
        self._positions_cache = None
        self._positions_cache_at = 0.0
        self._account_cache = None
        self._account_cache_at = 0.0
        return MT5OrderSendResult(
            retcode=_mt5_retcode(data),
            comment=str(data.get("comment") or ""),
            order_ticket=int(data.get("order_ticket") or ticket),
            deal_ticket=int(data.get("deal_ticket") or 0),
            volume=_dec(data.get("volume")),
            price=_dec(data.get("price")),
        )

    def list_positions(self) -> list[MT5Position]:
        self._require_connected()
        now = time.monotonic()
        if (
            self._positions_cache is not None
            and now - self._positions_cache_at <= self._snapshot_ttl_seconds
        ):
            gateway_metrics.record_cache(hit=True)
            return list(self._positions_cache)
        gateway_metrics.record_cache(hit=False)
        data = self._request("GET", "/positions")
        out: list[MT5Position] = []
        for row in data.get("items") or []:
            typ = int(row.get("type") or 0)
            opened_raw = row.get("time") or row.get("time_msc")
            opened_at = datetime.now(UTC)
            if opened_raw:
                try:
                    ts = int(opened_raw)
                    if ts > 10_000_000_000:
                        ts = ts // 1000
                    opened_at = datetime.fromtimestamp(ts, tz=UTC)
                except (TypeError, ValueError, OSError):
                    opened_at = datetime.now(UTC)
            out.append(
                MT5Position(
                    ticket=int(row["ticket"]),
                    symbol=str(row.get("symbol") or ""),
                    side="buy" if typ == 0 else "sell",
                    volume=_dec(row.get("volume"), "0.01"),
                    open_price=_dec(row.get("price_open")),
                    current_price=_dec(row.get("price_current")),
                    stop_loss=_dec(row.get("sl") or row.get("stop_loss")),
                    take_profit=_dec(row.get("tp") or row.get("take_profit")),
                    profit=_dec(row.get("profit")),
                    swap=_dec(row.get("swap")),
                    magic=int(row.get("magic") or 0),
                    comment=str(row.get("comment") or ""),
                    opened_at=opened_at,
                )
            )
        self._positions_cache = out
        self._positions_cache_at = now
        return list(out)

    def position_by_ticket(self, ticket: int) -> MT5Position | None:
        for pos in self.list_positions():
            if pos.ticket == ticket:
                return pos
        return None

    def position_by_symbol(self, symbol: str) -> list[MT5Position]:
        code = symbol.strip().upper()
        return [p for p in self.list_positions() if p.symbol == code]

    def list_orders(self) -> list[MT5PendingOrder]:
        self._require_connected()
        data = self._request("GET", "/orders")
        out: list[MT5PendingOrder] = []
        for row in data.get("items") or []:
            typ = int(row.get("type") or 0)
            out.append(
                MT5PendingOrder(
                    ticket=int(row["ticket"]),
                    symbol=str(row.get("symbol") or ""),
                    side="buy" if typ % 2 == 0 else "sell",
                    order_type="limit",
                    volume=_dec(row.get("volume_current"), "0.01"),
                    price=_dec(row.get("price_open")),
                    stop_loss=_dec(row.get("sl") or row.get("stop_loss")),
                    take_profit=_dec(row.get("tp") or row.get("take_profit")),
                )
            )
        return out

    def order_by_ticket(self, ticket: int) -> MT5PendingOrder | None:
        for order in self.list_orders():
            if order.ticket == ticket:
                return order
        return None

    def history_orders(
        self,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[MT5HistoryOrder]:
        self._require_connected()
        now = datetime.now(UTC)
        start = date_from
        end = date_to
        if start is not None and start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        if end is not None and end.tzinfo is None:
            end = end.replace(tzinfo=UTC)

        if start is not None:
            span_end = end if end is not None else now
            days = max(
                1, min(365, int((span_end - start).total_seconds() // 86400) or 1)
            )
        elif end is not None:
            days = 365
        else:
            days = 30

        data = self._request("GET", "/history/orders", params={"days": days})
        out: list[MT5HistoryOrder] = []
        for row in data.get("items") or []:
            symbol = str(row.get("symbol") or "").strip()
            ticket = int(row.get("ticket") or 0)
            if ticket <= 0 or not symbol:
                continue
            raw_t = row.get("time_setup") or row.get("time_done") or row.get("time")
            if raw_t is not None and (start is not None or end is not None):
                try:
                    ts = int(raw_t)
                    if ts > 10_000_000_000:
                        ts = ts // 1000
                    order_time = datetime.fromtimestamp(ts, tz=UTC)
                    if start is not None and order_time < start:
                        continue
                    if end is not None and order_time > end:
                        continue
                except (TypeError, ValueError, OSError):
                    continue
            elif raw_t is None and (start is not None or end is not None):
                # Cannot honor window without broker timestamp — fail closed.
                continue
            out.append(
                MT5HistoryOrder(
                    ticket=ticket,
                    symbol=symbol,
                    side="buy",
                    order_type="market",
                    volume=Decimal("0"),
                    price=Decimal("0"),
                    state="filled",
                )
            )
        return out

    def history_deals(
        self,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[MT5Deal]:
        self._require_connected()
        now = datetime.now(UTC)
        start = date_from
        end = date_to
        if start is not None and start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        if end is not None and end.tzinfo is None:
            end = end.replace(tzinfo=UTC)

        if start is not None:
            span_end = end if end is not None else now
            days = max(
                1, min(365, int((span_end - start).total_seconds() // 86400) or 1)
            )
        elif end is not None:
            days = 365
        else:
            days = 30

        data = self._request("GET", "/history/deals", params={"days": days})
        out: list[MT5Deal] = []
        for row in data.get("items") or []:
            symbol = str(row.get("symbol") or "").strip()
            ticket = int(row.get("ticket") or 0)
            if ticket <= 0 or not symbol:
                continue
            vol = _dec(row.get("volume"), "0")
            if vol <= 0:
                continue
            typ = int(row.get("type") or 0)
            # MT5 DEAL_TYPE_BUY=0, DEAL_TYPE_SELL=1
            side = "buy" if typ % 2 == 0 else "sell"
            entry = int(row.get("entry") or 0)
            deal_type = (
                "entry_in" if entry == 0 else "entry_out" if entry == 1 else "deal"
            )
            deal_time: datetime | None = None
            raw_t = row.get("time")
            if raw_t:
                try:
                    ts = int(raw_t)
                    if ts > 10_000_000_000:
                        ts = ts // 1000
                    deal_time = datetime.fromtimestamp(ts, tz=UTC)
                except (TypeError, ValueError, OSError):
                    deal_time = None
            if deal_time is None:
                if start is not None or end is not None:
                    continue
                deal_time = now
            else:
                if start is not None and deal_time < start:
                    continue
                if end is not None and deal_time > end:
                    continue
            out.append(
                MT5Deal(
                    ticket=ticket,
                    order_ticket=int(row.get("order") or ticket),
                    symbol=symbol,
                    side=side,
                    volume=vol,
                    price=_dec(row.get("price")),
                    profit=_dec(row.get("profit")),
                    commission=_dec(row.get("commission")),
                    swap=_dec(row.get("swap")),
                    deal_type=deal_type,
                    time=deal_time,
                    magic=int(row.get("magic") or 0),
                    comment=str(row.get("comment") or ""),
                    position_id=int(row.get("position_id") or 0),
                )
            )
        return out

    def account_snapshot(self) -> AccountSnapshot:
        info = self.account_info()
        return AccountSnapshot(
            login=info.login,
            balance=info.balance,
            equity=info.equity,
            margin=info.margin,
            free_margin=info.free_margin,
            margin_level=info.margin_level,
            profit=info.profit,
            leverage=info.leverage,
            currency=info.currency,
            server=info.server,
        )

    def diagnostics(self) -> dict[str, Any]:
        if not self.token:
            return {"error": "caller token not configured"}
        return self._request("GET", "/diagnostics")

    def _require_connected(self) -> None:
        if not self._connected:
            raise RuntimeError("MT5 gateway session not connected")
