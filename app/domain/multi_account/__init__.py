"""Multi-user MT5 registry foundation (Phase 1a).

Product rule: one QuantForg user → at most one active MT5 account → at most
one active worker *assignment*.

This package provides registry, ownership, effective-risk, and dispatch
*models* only. It does **not** provision isolated MT5 terminals, does **not**
wire the LIVE ITE path, and does **not** enable concurrent LIVE execution.

Feature flags ``MULTI_ACCOUNT_DISPATCH_ENABLED`` and
``MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED`` default to false.
"""

from __future__ import annotations

from app.domain.multi_account.effective_risk import (
    USER_EDITABLE_RISK_KEYS,
    EffectiveRiskProfile,
    RiskSettingProposal,
    resolve_effective_risk,
)
from app.domain.multi_account.execution_worker_registry import (
    ExecutionWorkerAssignment,
    InMemoryExecutionWorkerRegistry,
)
from app.domain.multi_account.feature_gates import (
    multi_account_dispatch_allowed,
    multi_account_live_submit_allowed,
)
from app.domain.multi_account.ownership_claim import (
    AccountOwnershipRecord,
    InMemoryOwnershipClaimRegistry,
)
from app.domain.multi_account.signal_dispatch import (
    AccountExecutionIntent,
    AccountExecutionState,
    CentralSignalIntent,
)

REGISTRY_CAPABILITY_STATEMENT = (
    "QuantForg Phase 1a supports multi-user registration of one active MT5 "
    "account per user, with global login uniqueness and worker assignment "
    "metadata. It does not yet support simultaneous multi-user MT5 LIVE "
    "execution or provisioned isolated terminals."
)

__all__ = [
    "REGISTRY_CAPABILITY_STATEMENT",
    "USER_EDITABLE_RISK_KEYS",
    "AccountExecutionIntent",
    "AccountExecutionState",
    "AccountOwnershipRecord",
    "CentralSignalIntent",
    "EffectiveRiskProfile",
    "ExecutionWorkerAssignment",
    "InMemoryExecutionWorkerRegistry",
    "InMemoryOwnershipClaimRegistry",
    "RiskSettingProposal",
    "multi_account_dispatch_allowed",
    "multi_account_live_submit_allowed",
    "resolve_effective_risk",
]
