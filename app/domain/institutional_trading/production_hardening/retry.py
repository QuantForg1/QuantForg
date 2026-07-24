"""Classify MT5/OMS outcomes — retry only transient failures."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any

from app.domain.institutional_trading.production_hardening.config import (
    DEFAULT_HARDENING_CONFIG,
    ProductionHardeningConfig,
)
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RetryDecision:
    retryable: bool
    reason: str
    attempt: int
    backoff_ms: int

    def to_dict(self) -> dict[str, object]:
        return {
            "retryable": self.retryable,
            "reason": self.reason,
            "attempt": self.attempt,
            "backoff_ms": self.backoff_ms,
        }


def is_permanent_reject(
    *,
    retcode: int | None,
    message: str | None = None,
    config: ProductionHardeningConfig | None = None,
) -> bool:
    cfg = config or DEFAULT_HARDENING_CONFIG
    if retcode is not None and int(retcode) in cfg.permanent_retcodes:
        return True
    text = (message or "").strip().lower()
    permanent_tokens = (
        "invalid volume",
        "invalid stop",
        "invalid stops",
        "insufficient margin",
        "no money",
        "not enough money",
        "market closed",
        "trade is disabled",
        "trade disabled",
    )
    return any(t in text for t in permanent_tokens)


def is_transient_reject(
    *,
    retcode: int | None,
    message: str | None = None,
    config: ProductionHardeningConfig | None = None,
) -> bool:
    cfg = config or DEFAULT_HARDENING_CONFIG
    if is_permanent_reject(retcode=retcode, message=message, config=cfg):
        return False
    if retcode is not None and int(retcode) in cfg.retryable_retcodes:
        return True
    text = (message or "").strip().lower()
    return any(t in text for t in cfg.retryable_message_tokens)


def backoff_ms_for_attempt(
    attempt: int,
    *,
    config: ProductionHardeningConfig | None = None,
) -> int:
    cfg = config or DEFAULT_HARDENING_CONFIG
    base = max(1, int(cfg.retry_base_backoff_ms))
    raw = min(cfg.retry_max_backoff_ms, base * (2 ** max(0, attempt - 1)))
    jitter = raw * cfg.retry_jitter_ratio
    return int(max(1, raw + random.uniform(-jitter, jitter)))


def decide_retry(
    *,
    attempt: int,
    retcode: int | None,
    message: str | None,
    outcome: str | None = None,
    config: ProductionHardeningConfig | None = None,
) -> RetryDecision:
    cfg = config or DEFAULT_HARDENING_CONFIG
    if not cfg.retry_enabled:
        return RetryDecision(False, "retry disabled", attempt, 0)
    if attempt >= cfg.retry_max_attempts:
        return RetryDecision(False, "max retry attempts reached", attempt, 0)
    out = (outcome or "").lower()
    if out in {"success", "filled", "done"}:
        return RetryDecision(False, "already succeeded", attempt, 0)
    if is_permanent_reject(retcode=retcode, message=message, config=cfg):
        return RetryDecision(
            False,
            f"permanent reject retcode={retcode} msg={message or ''}",
            attempt,
            0,
        )
    if is_transient_reject(retcode=retcode, message=message, config=cfg):
        wait = backoff_ms_for_attempt(attempt + 1, config=cfg)
        return RetryDecision(
            True,
            f"transient reject retcode={retcode} — backoff {wait}ms",
            attempt,
            wait,
        )
    return RetryDecision(
        False,
        f"non-retryable outcome={outcome} retcode={retcode}",
        attempt,
        0,
    )


def sleep_backoff(ms: int) -> None:
    if ms > 0:
        time.sleep(ms / 1000.0)


class RetryingOmsSubmitPort:
    """Wraps an OmsSubmitPort with configurable exponential backoff retries."""

    def __init__(
        self,
        inner: Any,
        *,
        config: ProductionHardeningConfig | None = None,
        on_retry: Any | None = None,
    ) -> None:
        self.inner = inner
        self.config = config or DEFAULT_HARDENING_CONFIG
        self.on_retry = on_retry
        self.retry_count = 0

    def submit_market(self, **kwargs: Any) -> Any:
        attempt = 0
        last = None
        while True:
            attempt += 1
            last = self.inner.submit_market(**kwargs)
            outcome = str(getattr(last, "outcome", "") or "")
            retcode = getattr(last, "retcode", None)
            message = str(getattr(last, "message", "") or "")
            if outcome.lower() in {"success", "filled", "done"}:
                return last
            decision = decide_retry(
                attempt=attempt,
                retcode=int(retcode) if retcode is not None else None,
                message=message,
                outcome=outcome,
                config=self.config,
            )
            logger.warning(
                "oms_submit_retry_decision",
                attempt=attempt,
                retryable=decision.retryable,
                reason=decision.reason,
                retcode=retcode,
                # Never log secrets — message is broker text only
                message=message[:240],
            )
            if self.on_retry is not None:
                try:
                    self.on_retry(attempt, decision, last)
                except Exception:
                    logger.exception("oms_retry_hook_failed")
            if not decision.retryable:
                return last
            self.retry_count += 1
            # Distinct request_id suffix so OMS idempotency does not collapse retries
            rid = str(kwargs.get("request_id") or "")
            if rid and f":r{attempt}" not in rid:
                kwargs = {**kwargs, "request_id": f"{rid}:r{attempt}"}
            sleep_backoff(decision.backoff_ms)
