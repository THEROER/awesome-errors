"""Litestar integration helpers."""

from __future__ import annotations

import logging
import traceback
from typing import TYPE_CHECKING, Callable, Dict, Optional, Type

if TYPE_CHECKING:  # pragma: no cover - for type checkers only
    from litestar import Request
    from litestar.exceptions import HTTPException, ValidationException
    from litestar.response import Response
    from litestar.types import ExceptionHandler

from ..core.error_codes import ErrorCode
from ..core.exceptions import AppError, ValidationError as CoreValidationError
from ..core.renderers import ErrorResponseFormat, ErrorResponseRenderer, RenderResult
from ..converters.sql_converter import SQLErrorConverter
from ..i18n.translator import ErrorTranslator

logger = logging.getLogger(__name__)


def create_litestar_exception_handlers(
    *,
    translator: Optional[ErrorTranslator] = None,
    debug: bool = False,
    log_errors: bool = True,
    locales_dir: Optional[str] = None,
    default_locale: str = "en",
    response_format: ErrorResponseFormat = ErrorResponseFormat.RFC7807,
    problem_type_resolver: Optional[Callable[[AppError], str]] = None,
    problem_extension_builder: Optional[Callable[[AppError], Dict[str, object]]] = None,
    message_resolver: Optional[
        Callable[[AppError, Optional[str], Optional[ErrorTranslator]], str]
    ] = None,
) -> Dict[Type[Exception], "ExceptionHandler"]:
    """Return a mapping of exception handlers configured for Litestar."""

    if translator is None:
        from pathlib import Path

        locales_path = Path(locales_dir) if locales_dir else None
        translator = ErrorTranslator(
            locales_dir=locales_path, default_locale=default_locale
        )

    renderer = ErrorResponseRenderer(
        format=response_format,
        problem_type_resolver=problem_type_resolver,
        problem_extension_builder=problem_extension_builder,
    )

    from litestar.exceptions import HTTPException, ValidationException  # type: ignore
    from litestar.response import Response  # type: ignore

    def resolve_message(error: AppError, locale: Optional[str]) -> str:
        if message_resolver:
            return message_resolver(error, locale, translator)

        translated = translator.translate(
            error.code.value,
            locale=locale,
            params=error.details,
        )
        if translated == error.code.value:
            return error.message
        return translated

    def handle_app_error(request: "Request", exc: AppError) -> "Response":
        locale = request.headers.get("Accept-Language")
        if locale:
            locale = locale.split(",")[0].split("-")[0]

        if log_errors:
            logger.error(
                f"App error: {exc.code.value} - {exc.message}",
                extra={
                    "error_code": exc.code.value,
                    "details": exc.details,
                    "request_id": exc.request_id,
                },
            )

        if exc.status_code >= 500:
            _print_stacktrace(
                "500 ERROR",
                Error_Code=exc.code.value,
                Message=exc.message,
                Request_ID=exc.request_id,
                Details=exc.details,
            )

        rendered: RenderResult = renderer.render(
            exc, message=resolve_message(exc, locale), request=request
        )

        return Response(
            content=rendered.payload,
            status_code=exc.status_code,
            media_type=rendered.media_type,
            headers={"X-Request-ID": exc.request_id},
        )

    def handle_validation_error(
        request: "Request", exc: "ValidationException"
    ) -> "Response":
        error = CoreValidationError(
            message="Request validation failed",
            code=ErrorCode.VALIDATION_FAILED,
        )
        error.details = {
            "errors": exc.extra or [],
            "path": exc.path,
        }
        return handle_app_error(request, error)

    def handle_http_exception(request: "Request", exc: "HTTPException") -> "Response":
        status_to_code = {
            400: ErrorCode.INVALID_INPUT,
            401: ErrorCode.AUTH_REQUIRED,
            403: ErrorCode.AUTH_PERMISSION_DENIED,
            404: ErrorCode.RESOURCE_NOT_FOUND,
            422: ErrorCode.VALIDATION_FAILED,
        }

        error_code = status_to_code.get(exc.status_code, ErrorCode.UNKNOWN_ERROR)
        error = AppError(
            code=error_code,
            message=str(exc.detail or exc.extra or exc.__class__.__name__),
            status_code=exc.status_code,
            details={
                "detail": exc.detail,
                "extra": exc.extra,
            },
        )

        if exc.status_code >= 500:
            _print_stacktrace(
                "500 HTTP ERROR",
                HTTP_Status=exc.status_code,
                Error_Code=error_code.value,
                Message=exc.detail,
            )

        return handle_app_error(request, error)

    def handle_sqlalchemy_error(request: "Request", exc: Exception) -> "Response":
        error = SQLErrorConverter.convert(exc)
        return handle_app_error(request, error)

    def handle_generic_error(request: "Request", exc: Exception) -> "Response":
        if log_errors:
            logger.exception("Unhandled exception")

        _print_stacktrace(
            "UNHANDLED ERROR",
            Exception_Type=type(exc).__name__,
            Exception_Message=str(exc),
        )

        error = AppError(
            code=ErrorCode.INTERNAL_ERROR,
            message="An internal error occurred" if not debug else str(exc),
            status_code=500,
        )

        if debug:
            error.details["traceback"] = traceback.format_exc()

        return handle_app_error(request, error)

    handlers: Dict[Type[Exception], "ExceptionHandler"] = {
        AppError: handle_app_error,
        ValidationException: handle_validation_error,
        HTTPException: handle_http_exception,
        Exception: handle_generic_error,
    }

    try:
        from sqlalchemy.exc import SQLAlchemyError  # type: ignore

        handlers[SQLAlchemyError] = handle_sqlalchemy_error  # type: ignore
    except Exception:  # pragma: no cover - SQLAlchemy already a dependency
        pass

    return handlers


def _print_stacktrace(error_type: str, **kwargs: object) -> None:
    logger.error(f"\n=== {error_type} STACKTRACE ===")
    for key, value in kwargs.items():
        logger.error(f"{key}: {value}")
    logger.error("Stacktrace:")
    traceback.print_exc(limit=30)
    logger.error(f"=== END {error_type} STACKTRACE ===\n")
