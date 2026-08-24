"""Post-AI execution-chain labels — observability only.

Does not submit, retry, or invent a second OMS path. A blocked cycle must
never inherit a prior ticket / retcode / PASS.
"""

from __future__ import annotations

from typing import Any

NOT_ATTEMPTED = "NOT_ATTEMPTED"
CHAIN_PASS = "PASS"  # noqa: S105 — log label, not a secret
CHAIN_FAIL = "FAIL"


def classify_post_ai_execution_chain(
    *,
    forwarded_to_oms: bool,
    may_submit_oms: bool | None = None,
    blocking_stage: str | None = None,
    ticket: Any = None,
    retcode: Any = None,
    this_cycle_forwarded: bool | None = None,
) -> dict[str, Any]:
    """Labels for OMS / Gateway / MT5 after AI Decision.

    If this cycle did not reach OMS, tickets from a prior fill are dropped.
    """
    forwarded = bool(forwarded_to_oms)
    if this_cycle_forwarded is False:
        forwarded = False
    stage = str(blocking_stage or "").strip().upper()
    blocked = (
        not forwarded
        or may_submit_oms is False
        or stage == "RISK"
    )
    if blocked:
        return {
            "oms_submit": NOT_ATTEMPTED,
            "submitting_order": False,
            "mt5_gateway": NOT_ATTEMPTED,
            "broker": NOT_ATTEMPTED,
            "mt5_accepted": False,
            "ticket": None,
            "retcode": None,
            "forwarded_to_oms": False,
        }
    ticket_ok = ticket is not None and str(ticket).strip() not in {"", "None", "0"}
    return {
        "oms_submit": CHAIN_PASS,
        "submitting_order": True,
        "mt5_gateway": CHAIN_PASS,
        "broker": CHAIN_PASS if ticket_ok else CHAIN_FAIL,
        "mt5_accepted": ticket_ok,
        "ticket": ticket if ticket_ok else None,
        "retcode": retcode,
        "forwarded_to_oms": True,
    }
