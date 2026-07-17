"""Tests for frontend origin allowlisting (CORS + auth redirects)."""

from __future__ import annotations

import re

import pytest

from app.domain.exceptions.base import ValidationError
from app.presentation.security.redirects import sanitize_redirect_to
from core.config.environments import production_settings, testing_settings
from core.config.frontend_origins import (
    PRODUCTION_CORS_ORIGIN_REGEX,
    is_trusted_frontend_origin,
)


class TestFrontendOrigins:
    def test_production_hosts_trusted(self) -> None:
        assert is_trusted_frontend_origin("https://quantforg.com")
        assert is_trusted_frontend_origin("https://www.quantforg.com")
        assert is_trusted_frontend_origin("https://app.quantforg.com")
        assert is_trusted_frontend_origin(
            "https://quant-forg-ozdtue0ee-quantforg.vercel.app"
        )
        assert is_trusted_frontend_origin("http://localhost:3000")

    def test_untrusted_hosts_rejected(self) -> None:
        assert not is_trusted_frontend_origin("https://evil.example.com")
        assert not is_trusted_frontend_origin("http://quantforg.com")

    def test_cors_regex_matches_custom_domain_and_vercel(self) -> None:
        pattern = re.compile(PRODUCTION_CORS_ORIGIN_REGEX)
        assert pattern.fullmatch("https://www.quantforg.com")
        assert pattern.fullmatch("https://quantforg.com")
        assert pattern.fullmatch(
            "https://quant-forg-ozdtue0ee-quantforg.vercel.app"
        )
        assert pattern.fullmatch("https://foo.bar.vercel.app")
        assert not pattern.fullmatch("https://evil.example.com")
        assert not pattern.fullmatch("http://www.quantforg.com")


class TestSanitizeRedirect:
    def test_allows_www_even_when_default_is_preview(self) -> None:
        settings = production_settings(
            secret_key="a-real-production-secret-key-with-enough-entropy-here",
            postgres_password="a-real-production-password-here",
            railway_public_domain="quantforg-production.up.railway.app",
            auth_redirect_url="https://quant-forg-iota.vercel.app/auth/callback",
        )
        out = sanitize_redirect_to(
            "https://www.quantforg.com/reset-password",
            settings=settings,
        )
        assert out == "https://www.quantforg.com/reset-password"

    def test_rejects_foreign_origin(self) -> None:
        settings = testing_settings()
        with pytest.raises(ValidationError) as exc:
            sanitize_redirect_to("https://evil.example.com/phish", settings=settings)
        assert exc.value.code == "redirect_not_allowed"
