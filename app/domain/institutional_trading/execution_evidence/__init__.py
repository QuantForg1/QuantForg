"""Production Execution Evidence Collector — observe-only.

Captures real BUY/SELL executions from PVM + journals.
Never fabricates trades, tickets, or fills.
Never modifies trading, AI, risk, OMS, MT5, or Gateway.
"""

from app.domain.institutional_trading.execution_evidence.collector import (
    build_evidence_from_attempt,
    collect_after_finalize,
    is_eligible_execution,
)
from app.domain.institutional_trading.execution_evidence.export import (
    CERTIFICATE_PATH,
    EXECUTION_DIR,
    export_evidence_package,
    export_waiting_state,
)
from app.domain.institutional_trading.execution_evidence.models import (
    EXECUTION_TIMELINE,
    ExecutionEvidencePackage,
)

__all__ = [
    "CERTIFICATE_PATH",
    "EXECUTION_DIR",
    "EXECUTION_TIMELINE",
    "ExecutionEvidencePackage",
    "build_evidence_from_attempt",
    "collect_after_finalize",
    "export_evidence_package",
    "export_waiting_state",
    "is_eligible_execution",
]
