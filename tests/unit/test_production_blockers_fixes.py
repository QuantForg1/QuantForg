"""Regression tests for verified production blockers (no mocks of broker tickets)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx
import pytest

from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG
from app.domain.institutional_trading.models import (
    TradeQualityFactor,
    TradeQualityScore,
)
from app.domain.institutional_trading.quality_components import quality_components
from app.domain.institutional_trading.session_filter import (
    SessionFilter,
    classify_session_utc,
)
from app.domain.market_context.enums import MarketSession
from app.infrastructure.brokers.mt5.gateway_client import (
    GatewayMT5Client,
    classify_gateway_failure,
)


@pytest.mark.unit
class TestGatewayTransientRetries:
    def test_classify_errno_11(self) -> None:
        assert (
            classify_gateway_failure(
                error="Gateway unreachable: [Errno 11] Resource temporarily unavailable"
            )
            == "Gateway transient socket pressure"
        )

    def test_get_retries_on_errno_11_then_succeeds(self) -> None:
        attempts = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise httpx.ConnectError(
                    "[Errno 11] Resource temporarily unavailable",
                    request=request,
                )
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "service": "mt5-gateway",
                    "bridge_available": True,
                },
            )

        transport = httpx.MockTransport(handler)
        client = GatewayMT5Client(
            base_url="https://tunnel.example",
            token="tok",
            timeout_seconds=5.0,
        )
        import app.infrastructure.brokers.mt5.gateway_client as mod

        original = mod.httpx.Client

        class PatchedClient(original):  # type: ignore[valid-type,misc]
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                kwargs["transport"] = transport
                super().__init__(*args, **kwargs)

        mod.httpx.Client = PatchedClient  # type: ignore[misc]
        try:
            data = client._request("GET", "/account")
        finally:
            mod.httpx.Client = original  # type: ignore[misc]

        assert data["status"] == "ok"
        assert attempts["n"] == 3


@pytest.mark.unit
class TestAccountModeTruth:
    def test_account_info_does_not_hardcode_demo(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "login": 16785006,
                    "balance": "181.53",
                    "equity": "181.53",
                    "margin": "0",
                    "free_margin": "181.53",
                    "margin_level": "0",
                    "profit": "0",
                    "leverage": 1000,
                    "currency": "USD",
                    "server": "Weltrade-Real",
                    "name": "Prod",
                    "account_mode": "real",
                    "trade_mode": "real",
                    "trade_mode_raw": 2,
                    "trade_allowed": True,
                },
            )

        transport = httpx.MockTransport(handler)
        client = GatewayMT5Client(
            base_url="https://tunnel.example", token="tok", timeout_seconds=5.0
        )
        client._connected = True
        client._login = 16785006
        client._server = "Weltrade-Real"
        import app.infrastructure.brokers.mt5.gateway_client as mod

        original = mod.httpx.Client

        class PatchedClient(original):  # type: ignore[valid-type,misc]
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                kwargs["transport"] = transport
                super().__init__(*args, **kwargs)

        mod.httpx.Client = PatchedClient  # type: ignore[misc]
        try:
            info = client.account_info()
        finally:
            mod.httpx.Client = original  # type: ignore[misc]

        assert info.server == "Weltrade-Real"
        assert info.trade_mode == "real"
        assert info.trade_allowed is True


@pytest.mark.unit
class TestQualityComponents:
    def test_components_from_real_factors_not_missing_attr(self) -> None:
        score = TradeQualityScore(
            total=72,
            passed=False,
            band="reject",
            factors=(
                TradeQualityFactor(code="trend", weight=20, score=78, detail="aligned"),
                TradeQualityFactor(
                    code="liquidity", weight=15, score=70, detail="sweeps"
                ),
                TradeQualityFactor(
                    code="market_structure", weight=15, score=80, detail="bos"
                ),
            ),
        )
        comps = quality_components(score)
        assert comps["trend"] == 78
        assert comps["momentum"] == 78  # alias from trend
        assert comps["volume"] == 70  # alias from liquidity
        assert score.components["momentum"] == 78

    def test_momentum_not_silent_55_default(self) -> None:
        comps = quality_components(
            TradeQualityScore(
                total=66,
                passed=False,
                band="reject",
                factors=(
                    TradeQualityFactor(code="trend", weight=20, score=45, detail=""),
                ),
            )
        )
        assert comps["momentum"] == 45


@pytest.mark.unit
class TestSessionAutoResume:
    def test_classifier_covers_all_named_sessions(self) -> None:
        cases = {
            datetime(2026, 7, 31, 2, 0, tzinfo=UTC): MarketSession.TOKYO,
            datetime(2026, 7, 31, 8, 0, tzinfo=UTC): MarketSession.LONDON,
            datetime(2026, 7, 31, 14, 0, tzinfo=UTC): MarketSession.LONDON_NY_OVERLAP,
            datetime(2026, 7, 31, 18, 0, tzinfo=UTC): MarketSession.NEW_YORK,
            datetime(2026, 7, 31, 22, 0, tzinfo=UTC): MarketSession.SYDNEY,
            datetime(
                2026, 8, 1, 12, 0, tzinfo=UTC
            ): MarketSession.OFF_HOURS,  # Saturday
        }
        for when, expected in cases.items():
            assert classify_session_utc(when) is expected

    def test_engine_allows_again_when_session_opens_without_restart(self) -> None:
        filt = SessionFilter(config=DEFAULT_ITE_CONFIG)
        tokyo = filt.evaluate(as_of=datetime(2026, 7, 31, 2, 0, tzinfo=UTC))
        london = filt.evaluate(as_of=datetime(2026, 7, 31, 8, 30, tzinfo=UTC))
        assert tokyo.allowed is True
        assert tokyo.session is MarketSession.TOKYO
        assert tokyo.quality_score < london.quality_score
        assert london.allowed is True
        assert london.session is MarketSession.LONDON

    def test_sydney_and_overlap_allowed(self) -> None:
        filt = SessionFilter(config=DEFAULT_ITE_CONFIG)
        sydney = filt.evaluate(as_of=datetime(2026, 7, 31, 22, 0, tzinfo=UTC))
        overlap = filt.evaluate(as_of=datetime(2026, 7, 31, 14, 0, tzinfo=UTC))
        assert sydney.allowed is True
        assert sydney.session is MarketSession.SYDNEY
        assert overlap.allowed is True
        assert overlap.session is MarketSession.LONDON_NY_OVERLAP


@pytest.mark.unit
class TestLotSizingLiveSpecs:
    def test_below_min_lot_is_zero_not_upsize(self) -> None:
        from app.domain.institutional_trading.ai_scalping.sizing import (
            calculate_scalping_lots,
        )

        sized = calculate_scalping_lots(
            equity=Decimal("181.53"),
            stop_distance=Decimal("7.26"),
            risk_pct=Decimal("1.0"),
            contract_size=Decimal("100"),
            min_lot=Decimal("0.01"),
            lot_step=Decimal("0.01"),
        )
        assert sized.valid is False
        assert sized.lots == Decimal("0")
        assert sized.method == "below_min_lot"

    def test_finer_step_produces_tradable_lots(self) -> None:
        from app.domain.institutional_trading.ai_scalping.sizing import (
            calculate_scalping_lots,
        )

        sized = calculate_scalping_lots(
            equity=Decimal("181.53"),
            stop_distance=Decimal("7.26"),
            risk_pct=Decimal("1.0"),
            contract_size=Decimal("100"),
            min_lot=Decimal("0.001"),
            lot_step=Decimal("0.001"),
        )
        assert sized.valid is True
        assert sized.lots >= Decimal("0.001")
        assert sized.lots < Decimal("0.01")
