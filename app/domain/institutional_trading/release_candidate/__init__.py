"""Release Candidate RC1 — production readiness (validation only)."""

from __future__ import annotations

from app.domain.institutional_trading.release_candidate.capital_advisor import (
    advise_capital_scale,
)
from app.domain.institutional_trading.release_candidate.checklist import (
    run_production_checklist,
)
from app.domain.institutional_trading.release_candidate.config import (
    DEFAULT_RC1_CONFIG,
    ReleaseCandidateConfig,
)
from app.domain.institutional_trading.release_candidate.docs_gen import (
    guide_summaries,
    write_rc1_guides,
)
from app.domain.institutional_trading.release_candidate.go_live_score import (
    compute_go_live_score,
)
from app.domain.institutional_trading.release_candidate.live_stats import (
    build_live_statistics,
)
from app.domain.institutional_trading.release_candidate.reports import (
    get_rc1_reporting_store,
    report_to_csv,
    report_to_pdf_text,
)
from app.domain.institutional_trading.release_candidate.smoke import (
    get_smoke_store,
    run_production_smoke,
)
from app.domain.institutional_trading.release_candidate.validation import (
    build_rc_validation,
)
from app.domain.institutional_trading.release_candidate.venues import (
    get_venue_stats_store,
)

__all__ = [
    "DEFAULT_RC1_CONFIG",
    "ReleaseCandidateConfig",
    "advise_capital_scale",
    "build_live_statistics",
    "build_rc_validation",
    "compute_go_live_score",
    "get_rc1_reporting_store",
    "get_smoke_store",
    "get_venue_stats_store",
    "guide_summaries",
    "report_to_csv",
    "report_to_pdf_text",
    "run_production_checklist",
    "run_production_smoke",
    "write_rc1_guides",
]
