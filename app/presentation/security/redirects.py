"""Safe redirect URL validation for OAuth and password-reset flows."""

from __future__ import annotations

from urllib.parse import urlparse

from app.domain.exceptions.base import ValidationError
from core.config.frontend_origins import is_trusted_frontend_origin
from core.config.settings import Settings


def sanitize_redirect_to(
    redirect_to: str | None,
    *,
    settings: Settings,
) -> str | None:
    """Return an allowlisted redirect URL or raise ValidationError.

    Production never forwards arbitrary client redirects to the IdP.
    """
    if redirect_to is None or not redirect_to.strip():
        return None
    candidate = redirect_to.strip()
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValidationError(
            "redirect_to must be an absolute http(s) URL",
            code="invalid_redirect",
        )

    allowed: set[str] = set()
    default = (settings.auth_redirect_url or "").strip()
    if default:
        allowed.add(default.rstrip("/"))
        default_parsed = urlparse(default)
        if default_parsed.scheme and default_parsed.netloc:
            allowed.add(f"{default_parsed.scheme}://{default_parsed.netloc}")

    for origin in settings.cors_origins or []:
        origin = origin.strip().rstrip("/")
        if origin and origin != "*":
            allowed.add(origin)

    railway = (settings.railway_public_domain or "").strip()
    if railway:
        allowed.add(f"https://{railway}")

    # Exact match or same-origin + path under an allowed origin.
    normalized = candidate.rstrip("/")
    for base in allowed:
        if normalized == base or candidate.startswith(base + "/"):
            return candidate

    # Trust canonical product hosts (custom domain + Vercel + local) even when
    # AUTH_REDIRECT_URL still points at a legacy preview URL.
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if is_trusted_frontend_origin(origin):
        return candidate

    raise ValidationError(
        "redirect_to is not an allowed application origin",
        code="redirect_not_allowed",
        details={"redirect_to": candidate},
    )
