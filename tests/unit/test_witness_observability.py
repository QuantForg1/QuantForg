"""Witness observability — auth vs execution health separation."""

from __future__ import annotations

import pytest

from app.application.services.witness_observability import (
    AUTH_LABEL,
    classify_witness_fault,
    dashboard_payload,
    is_auth_failure,
    parse_http_status,
)
from app.domain.institutional_trading.reliability.platform import (
    reset_reliability_platform_for_tests,
)


@pytest.mark.unit
class TestWitnessAuthClassification:
    def test_401_is_auth_not_execution(self) -> None:
        err = "HTTP Error 401: Unauthorized"
        assert is_auth_failure(err, 401) is True
        assert classify_witness_fault(err, 401) == "auth"
        assert AUTH_LABEL == "Witness Authentication Failed"

    def test_parse_http_status(self) -> None:
        assert parse_http_status("HTTP Error 401: Unauthorized") == 401

    def test_dns_is_network(self) -> None:
        err = "<urlopen error [Errno 11001] getaddrinfo failed>"
        assert classify_witness_fault(err) == "network"
        assert is_auth_failure(err) is False

    def test_dashboard_isolates_acceptance(self) -> None:
        reset_reliability_platform_for_tests()
        payload = dashboard_payload()
        assert (
            payload["acceptance_isolation"][
                "witness_auth_affects_production_acceptance"
            ]
            is False
        )
        # Must not invent PRODUCTION ACCEPTED from witness auth state
        assert "PRODUCTION ACCEPTED" not in str(payload.get("authentication"))
