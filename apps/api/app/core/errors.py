"""Consistent API error envelope: {"error": {"code", "message", "details"}}."""

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("fogroom.errors")


class AppError(Exception):
    """Domain error rendered with the standard error envelope."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def not_found(code: str, message: str) -> AppError:
    return AppError(code, message, status.HTTP_404_NOT_FOUND)


def forbidden(
    message: str = "You do not have access to this resource.", code: str = "FORBIDDEN"
) -> AppError:
    return AppError(code, message, status.HTTP_403_FORBIDDEN)


def conflict(code: str, message: str, details: dict[str, Any] | None = None) -> AppError:
    return AppError(code, message, status.HTTP_409_CONFLICT, details)


def unauthorized(message: str = "Authentication required.", code: str = "UNAUTHORIZED") -> AppError:
    return AppError(code, message, status.HTTP_401_UNAUTHORIZED)


def _envelope(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return JSONResponse(
            _envelope(exc.code, exc.message, exc.details),
            status_code=exc.status_code,
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"loc": list(e.get("loc", [])), "msg": e.get("msg", ""), "type": e.get("type", "")}
            for e in exc.errors()
        ]
        return JSONResponse(
            _envelope("VALIDATION_ERROR", "Request validation failed.", {"errors": errors}),
            status_code=422,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
        }.get(exc.status_code, f"HTTP_{exc.status_code}")
        return JSONResponse(_envelope(code, str(exc.detail)), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            _envelope("INTERNAL_ERROR", "An unexpected error occurred."),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
