"""Local Gateway execution authorization — independent of Railway EXECUTION_ENABLED.

Default is fail-closed. Token authentication alone must never authorize
broker-mutating calls (order_send / order_cancel).
"""

from __future__ import annotations

# Must stay aligned with app.domain.entities.execution_gateway.RETCODE_EXECUTION_DISABLED
RETCODE_EXECUTION_DISABLED = 90001

DISABLED_COMMENT = "gateway execution disabled"


class GatewayExecutionDisabled(RuntimeError):
    """Raised when MT5_GATEWAY_EXECUTION_ENABLED is false.

    Maps to HTTP 403 with retcode 90001 — never a fill.
    """

    retcode: int = RETCODE_EXECUTION_DISABLED

    def __init__(self, message: str = DISABLED_COMMENT) -> None:
        super().__init__(message)

    def as_detail(self) -> dict[str, object]:
        return {
            "ok": False,
            "retcode": self.retcode,
            "comment": DISABLED_COMMENT,
            "detail": "MT5_GATEWAY_EXECUTION_ENABLED=false",
            "order_ticket": 0,
            "deal_ticket": 0,
        }
