"""Read-only Trust Engine.

Turns broker deal records into a performance report with a source, a
timestamp, an account scope, a calculation method, and a verification
status on every figure. Missing money stays missing.
"""

from app.domain.trust_engine.report import TrustBuildInput, build_trust_report

__all__ = ["TrustBuildInput", "build_trust_report"]
