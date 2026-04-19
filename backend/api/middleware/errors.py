"""Global exception handlers for FastAPI."""

import logging
from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class ErrorResponse:
    """Standardized error response format."""

    def __init__(self, detail: str, code: str, status_code: int = 500) -> None:
        """Initialize error response.

        Args:
            detail: Human-readable error message
            code: Error code identifier (e.g., 'validation_error', 'not_found')
            status_code: HTTP status code
        """
        self.detail = detail
        self.code = code
        self.status_code = status_code

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {"detail": self.detail, "code": self.code}

    def to_response(self) -> JSONResponse:
        """Convert to FastAPI JSONResponse."""
        return JSONResponse(
            status_code=self.status_code,
            content=self.to_dict(),
        )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors (422).

    Args:
        request: FastAPI request
        exc: Validation exception

    Returns:
        JSONResponse with standardized error format
    """
    # Extract first validation error for user-friendly message
    errors = exc.errors()
    first_error = errors[0] if errors else {}

    field = " -> ".join(str(loc) for loc in first_error.get("loc", []))
    msg = first_error.get("msg", "Validation error")

    detail = f"Validation error in {field}: {msg}" if field else msg

    logger.warning(
        f"Validation error on {request.method} {request.url.path}: {detail}",
        extra={"errors": errors},
    )

    error = ErrorResponse(
        detail=detail, code="validation_error", status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
    )
    return error.to_response()


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle HTTP exceptions (404, 403, etc.).

    Args:
        request: FastAPI request
        exc: HTTP exception

    Returns:
        JSONResponse with standardized error format
    """
    # Map HTTP status codes to error codes
    code_mapping = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        405: "method_not_allowed",
        409: "conflict",
        429: "rate_limit_exceeded",
    }

    code = code_mapping.get(exc.status_code, "http_error")

    logger.info(
        f"HTTP {exc.status_code} on {request.method} {request.url.path}: {exc.detail}",
        extra={"status_code": exc.status_code, "detail": exc.detail},
    )

    error = ErrorResponse(detail=str(exc.detail), code=code, status_code=exc.status_code)
    return error.to_response()


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions (500).

    Args:
        request: FastAPI request
        exc: Unhandled exception

    Returns:
        JSONResponse with standardized error format
    """
    logger.exception(
        f"Unhandled exception on {request.method} {request.url.path}: {exc}",
        exc_info=exc,
    )

    # Don't expose internal error details to clients
    error = ErrorResponse(
        detail="An internal server error occurred. Please try again later.",
        code="internal_server_error",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
    return error.to_response()
