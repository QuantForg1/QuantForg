"""Global exception handlers.

Maps domain exceptions and unexpected errors to consistent JSON error
bodies. Never leaks internal stack traces to clients in production.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.exceptions.auth import AuthenticationError, AuthorizationError
from app.domain.exceptions.base import (
    ConflictError,
    DomainError,
    NotFoundError,
    ValidationError,
)
from core.logging import get_logger

logger = get_logger(__name__)


def _error_body(
    *,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        }
    }
    if request_id:
        body["request_id"] = request_id
    return body


def _request_id_from(request: Request) -> str | None:
    state_id = getattr(request.state, "request_id", None)
    if isinstance(state_id, str) and state_id:
        return state_id
    from contextlib import suppress

    with suppress(Exception):
        import structlog

        ctx = structlog.contextvars.get_contextvars()
        ctx_id = ctx.get("request_id")
        if isinstance(ctx_id, str) and ctx_id:
            return ctx_id
    return request.headers.get("X-Request-ID")


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all global exception handlers to the FastAPI application."""

    @app.exception_handler(AuthenticationError)
    async def authentication_handler(
        request: Request, exc: AuthenticationError
    ) -> JSONResponse:
        # Map provider-specific auth codes to accurate HTTP statuses.
        # Never echo raw IdP exception text for auth failures.
        public_messages = {
            "invalid_credentials": "Invalid login credentials",
            "email_already_registered": "An account with this email already exists",
            "auth_rate_limited": "Too many authentication attempts. Try again later.",
            "email_not_verified": "Email address has not been verified",
            "missing_token": "Missing bearer access token",
        }
        message = public_messages.get(exc.code, "Authentication failed")
        if exc.code == "email_already_registered":
            http_status = status.HTTP_409_CONFLICT
            headers: dict[str, str] | None = None
        elif exc.code == "auth_rate_limited":
            http_status = status.HTTP_429_TOO_MANY_REQUESTS
            headers = {"Retry-After": "60"}
        elif exc.code == "email_not_verified":
            http_status = status.HTTP_403_FORBIDDEN
            headers = None
        else:
            http_status = status.HTTP_401_UNAUTHORIZED
            headers = {"WWW-Authenticate": "Bearer"}
        return JSONResponse(
            status_code=http_status,
            content=_error_body(
                code=exc.code,
                message=message,
                details=exc.details if exc.code == "missing_token" else {},
                request_id=_request_id_from(request),
            ),
            headers=headers,
        )

    @app.exception_handler(AuthorizationError)
    async def authorization_handler(
        request: Request, exc: AuthorizationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=_error_body(
                code=exc.code,
                message=exc.message,
                details=exc.details,
                request_id=_request_id_from(request),
            ),
        )

    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=_error_body(
                code=exc.code,
                message=exc.message,
                details=exc.details,
                request_id=_request_id_from(request),
            ),
        )

    @app.exception_handler(ValidationError)
    async def validation_handler(
        request: Request, exc: ValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_body(
                code=exc.code,
                message=exc.message,
                details=exc.details,
                request_id=_request_id_from(request),
            ),
        )

    @app.exception_handler(ConflictError)
    async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_error_body(
                code=exc.code,
                message=exc.message,
                details=exc.details,
                request_id=_request_id_from(request),
            ),
        )

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_error_body(
                code=exc.code,
                message=exc.message,
                details=exc.details,
                request_id=_request_id_from(request),
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_body(
                code="request_validation_error",
                message="Request validation failed",
                details={"errors": exc.errors()},
                request_id=_request_id_from(request),
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(
                code="http_error",
                message=str(exc.detail),
                request_id=_request_id_from(request),
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception(
            "unhandled_exception",
            path=str(request.url.path),
            method=request.method,
            error_type=type(exc).__name__,
        )
        # Never echo exception text to clients — paths, credentials, and
        # infrastructure details must stay in server logs only.
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body(
                code="internal_error",
                message="An unexpected error occurred",
                request_id=_request_id_from(request),
            ),
        )
