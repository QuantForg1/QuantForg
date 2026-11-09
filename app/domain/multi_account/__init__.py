"""Multi-user MT5 foundation (Phase 1a registry + Phase 1B worker infra).

Product rule: one QuantForg user → at most one active MT5 account → at most
one active isolated worker runtime.

Phase 1B adds provisioner / capacity / supervisor / agent protocol. It does
**not** claim real Windows MT5 terminals are running unless operators deploy
the Windows agent on approved hosts. LIVE submit flags remain false.
"""

from __future__ import annotations

from app.domain.multi_account.capacity import (
    InMemoryCapacityManager,
    WorkerHostCapacity,
)
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
from app.domain.multi_account.worker_lifecycle import WorkerLifecycleState
from app.domain.multi_account.worker_provisioner import InMemoryWorkerProvisioner
from app.domain.multi_account.worker_runtime import WorkerRuntime

REGISTRY_CAPABILITY_STATEMENT = (
    "QuantForg Phase 1a/1B supports multi-user registration of one active MT5 "
    "account per user, worker assignment/provisioning control-plane logic, and "
    "a Windows agent interface. It does not yet prove simultaneous real MT5 "
    "LIVE sessions or provisioned cloud Windows hosts."
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
    "InMemoryCapacityManager",
    "InMemoryExecutionWorkerRegistry",
    "InMemoryOwnershipClaimRegistry",
    "InMemoryWorkerProvisioner",
    "RiskSettingProposal",
    "WorkerHostCapacity",
    "WorkerLifecycleState",
    "WorkerRuntime",
    "multi_account_dispatch_allowed",
    "multi_account_live_submit_allowed",
    "resolve_effective_risk",
]
