"""Bounded Gateway I/O — read-only retry/coalesce/lanes. Never retries mutations.

Errno 11 (EAGAIN / Resource temporarily unavailable) is a Linux client-side
socket-pressure failure on Railway→Gateway HTTP, not an MT5 trade retcode.
"""

from __future__ import annotations

import json
import random
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

LANE_TRADING = "trading"
LANE_UI = "ui"
LANE_OBS = "observability"

READ_ONLY_POST_PATHS = frozenset(
    {
        "/trade/order_calc_profit",
        "/trade/order_calc_margin",
        "/trade/order_check",
    }
)
MUTATION_POST_PATHS = frozenset(
    {
        "/trade/order_send",
        "/trade/order_cancel",
        "/session/connect",
        "/session/attach",
        "/session/disconnect",
    }
)

TRADING_READ_LIMIT = 6
UI_READ_LIMIT = 2
OBS_READ_LIMIT = 2
MUTATION_LIMIT = 1

READ_ONLY_POST_ATTEMPTS = 3
GET_ATTEMPTS = 2
GET_HEAVY_ATTEMPTS = 3
MUTATION_ATTEMPTS = 1

CALC_READ_TIMEOUT_SECONDS = 10.0

gateway_lane: ContextVar[str] = ContextVar(
    "quantforg_gateway_lane", default=LANE_TRADING
)


@contextmanager
def use_gateway_lane(lane: str) -> Iterator[None]:
    token = gateway_lane.set(str(lane or LANE_TRADING).strip().lower() or LANE_TRADING)
    try:
        yield
    finally:
        gateway_lane.reset(token)


def current_gateway_lane() -> str:
    lane = str(gateway_lane.get() or LANE_TRADING).strip().lower()
    if lane in {LANE_UI, LANE_OBS, LANE_TRADING}:
        return lane
    return LANE_TRADING


def is_read_only_post(path: str) -> bool:
    return str(path or "").split("?", 1)[0] in READ_ONLY_POST_PATHS


def is_mutation_path(method: str, path: str) -> bool:
    if str(method or "").upper() != "POST":
        return False
    return str(path or "").split("?", 1)[0] in MUTATION_POST_PATHS


def is_calc_path(path: str) -> bool:
    p = str(path or "").split("?", 1)[0]
    return p in {"/trade/order_calc_profit", "/trade/order_calc_margin"}


def request_attempts(method: str, path: str, *, light: bool = False) -> int:
    """Bounded attempts. Mutations always 1 — never retry order_send."""
    m = str(method or "").upper()
    if m == "GET":
        if light:
            return GET_ATTEMPTS
        # Candle windows are heavy; two attempts fail closed faster than a
        # 3x30s hang that burns the ITE cycle budget.
        if str(path or "").split("?", 1)[0].startswith("/candles/"):
            return GET_ATTEMPTS
        return GET_HEAVY_ATTEMPTS
    if is_read_only_post(path):
        return READ_ONLY_POST_ATTEMPTS
    return MUTATION_ATTEMPTS


def may_coalesce(method: str, path: str) -> bool:
    m = str(method or "").upper()
    if m == "GET":
        return True
    return is_read_only_post(path)


def coalesce_key(
    method: str,
    path: str,
    json_body: dict[str, Any] | None,
    params: dict[str, Any] | None,
) -> str | None:
    """In-flight only. None means do not share (mutations / non-identical)."""
    if not may_coalesce(method, path):
        return None
    payload = {
        "m": str(method or "").upper(),
        "p": str(path or "").split("?", 1)[0],
        "b": json_body or {},
        "q": params or {},
    }
    return json.dumps(payload, sort_keys=True, default=str)


def backoff_seconds(attempt_i: int) -> float:
    """Exponential backoff + jitter. Caps so retries cannot become a storm."""
    base = min(1.6, 0.2 * (2 ** max(0, int(attempt_i))))
    return base + random.uniform(0.0, 0.15)  # noqa: S311


def acquire_timeout_seconds(lane: str, *, mutation: bool) -> float:
    if mutation:
        return 30.0
    if lane == LANE_UI:
        return 2.0
    if lane == LANE_OBS:
        return 2.0
    return 10.0


def resource_pressure_state(
    *,
    errno11_count: int,
    retry_exhausted_count: int,
    timeout_count: int,
    active_requests: int,
    budget: int,
    calc_failures: int,
) -> str:
    cap = max(1, int(budget))
    if (
        int(errno11_count) >= 5
        or int(retry_exhausted_count) >= 3
        or int(active_requests) >= max(1, int(0.9 * cap))
    ):
        return "CRITICAL"
    if (
        int(errno11_count) >= 1
        or int(timeout_count) >= 3
        or int(calc_failures) >= 3
        or int(active_requests) >= max(1, int(0.6 * cap))
    ):
        return "ELEVATED"
    return "NORMAL"
