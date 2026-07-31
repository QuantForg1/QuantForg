"""RC1 Production Validation Pipeline — paper / shadow / live evidence framework.

Does not modify strategy, Quality/Confidence floors (80/80), weights, or risk.
"""

from app.domain.institutional_trading.rc1_production_validation.acceptance import (
    evaluate_acceptance_gates,
)
from app.domain.institutional_trading.rc1_production_validation.config import (
    CONFIDENCE_FLOOR,
    QUALITY_FLOOR,
    ValidationExecutionMode,
    clear_validation_runtime_override_for_tests,
    resolve_validation_runtime,
    set_validation_runtime_for_tests,
)
from app.domain.institutional_trading.rc1_production_validation.dashboard import (
    build_validation_dashboard,
)
from app.domain.institutional_trading.rc1_production_validation.hooks import (
    handle_validation_execution,
    record_decision_outcome,
)
from app.domain.institutional_trading.rc1_production_validation.paper_engine import (
    get_paper_engine,
    reset_paper_engine_for_tests,
)
from app.domain.institutional_trading.rc1_production_validation.pipeline import (
    run_rc1_validation_pipeline,
)
from app.domain.institutional_trading.rc1_production_validation.replay import (
    build_synthetic_replay_dataset,
    run_replay_verification,
)
from app.domain.institutional_trading.rc1_production_validation.report import (
    render_rc1_validation_report,
    write_rc1_validation_report,
)
from app.domain.institutional_trading.rc1_production_validation.shadow_engine import (
    get_shadow_journal,
    reset_shadow_journal_for_tests,
)
from app.domain.institutional_trading.rc1_production_validation.trade_recorder import (
    get_trade_recorder,
    reset_trade_recorder_for_tests,
)

__all__ = [
    "CONFIDENCE_FLOOR",
    "QUALITY_FLOOR",
    "ValidationExecutionMode",
    "build_synthetic_replay_dataset",
    "build_validation_dashboard",
    "clear_validation_runtime_override_for_tests",
    "evaluate_acceptance_gates",
    "get_paper_engine",
    "get_shadow_journal",
    "get_trade_recorder",
    "handle_validation_execution",
    "record_decision_outcome",
    "render_rc1_validation_report",
    "reset_paper_engine_for_tests",
    "reset_shadow_journal_for_tests",
    "reset_trade_recorder_for_tests",
    "resolve_validation_runtime",
    "run_rc1_validation_pipeline",
    "run_replay_verification",
    "set_validation_runtime_for_tests",
    "write_rc1_validation_report",
]
