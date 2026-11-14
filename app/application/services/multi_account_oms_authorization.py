"""Multi-account OMS authorization preview (non-executing).

Validates that a claimed / planned intent would satisfy OMS hard gates
without calling order_send, PME mutate, or the MT5 gateway.

Used to prove the LIVE_SUBMIT-authorized path can reach OMS checks while
keeping actual broker submit unwired until worker+OMS fan-out is complete.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.domain.multi_account.feature_gates import (
    multi_account_dispatch_allowed,
    multi_account_live_submit_allowed,
)


@dataclass(frozen=True, slots=True)
class OmsAuthorizationPreview:
    authorized: bool
    dispatch_allowed: bool
    live_submit_flag: bool
    order_send: bool
    reasons: tuple[str, ...]
    user_id: str | None = None
    broker_account_id: str | None = None
    symbol: str | None = None
    side: str | None = None

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "authorized": self.authorized,
            "dispatch_allowed": self.dispatch_allowed,
            "live_submit_flag": self.live_submit_flag,
            "order_send": False,
            "oms_touched": True,
            "reasons": list(self.reasons),
            "user_id": self.user_id,
            "broker_account_id": self.broker_account_id,
            "symbol": self.symbol,
            "side": self.side,
        }


def preview_oms_authorization(
    *,
    user_id: UUID | str | None,
    broker_account_id: UUID | str | None,
    symbol: str | None,
    side: str | None,
    volume: Decimal | float | str | None,
    stop_loss: Decimal | float | str | None,
    worker_dispatch_ready: bool,
    ownership_verified: bool,
    account_environment: str | None = None,
    settings: Any | None = None,
) -> OmsAuthorizationPreview:
    """Fail-closed OMS preview — never submits."""
    reasons: list[str] = []
    dispatch_ok = multi_account_dispatch_allowed(settings)
    live_flag = multi_account_live_submit_allowed(settings)

    if not dispatch_ok:
        reasons.append("dispatch_disabled")
    if not ownership_verified:
        reasons.append("ownership_unverified")
    if not worker_dispatch_ready:
        reasons.append("worker_not_dispatch_ready")
    if not user_id:
        reasons.append("user_missing")
    if not broker_account_id:
        reasons.append("broker_account_missing")

    sym = str(symbol or "").strip().upper()
    if not sym or sym in {"UNKNOWN", "NONE", "NULL"}:
        reasons.append("symbol_invalid")

    sd = str(side or "").strip().upper()
    if sd not in {"BUY", "SELL"}:
        reasons.append("side_invalid")

    try:
        vol = Decimal(str(volume)) if volume is not None else Decimal("0")
    except Exception:
        vol = Decimal("0")
        reasons.append("volume_invalid")
    if vol <= 0:
        reasons.append("volume_non_positive")

    try:
        sl = Decimal(str(stop_loss)) if stop_loss is not None else None
    except Exception:
        sl = None
    if sl is None:
        reasons.append("mandatory_stop_loss_missing")

    env = str(account_environment or "").strip().lower()
    if env and env not in {"demo", "live"}:
        reasons.append("account_environment_invalid")

    # Preview never authorizes order_send — even when LIVE_SUBMIT is true.
    authorized = not reasons
    return OmsAuthorizationPreview(
        authorized=authorized,
        dispatch_allowed=dispatch_ok,
        live_submit_flag=live_flag,
        order_send=False,
        reasons=tuple(reasons),
        user_id=str(user_id) if user_id else None,
        broker_account_id=str(broker_account_id) if broker_account_id else None,
        symbol=sym or None,
        side=sd or None,
    )
