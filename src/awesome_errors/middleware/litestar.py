"""Litestar integration helpers."""

from __future__ import annotations

import logging
import traceback
from typing import TYPE_CHECKING, Callable, Dict, Mapping, Optional, Tuple, Type

if TYPE_CHECKING:
    from litestar import Request
    from litestar import Litestar
    from litestar.exceptions import HTTPException, ValidationException
    from litestar.response import Response
    from litestar.types import ExceptionHandler

from ..core.error_codes import ErrorCode
from ..core.exceptions import AppError, ValidationError as CoreValidationError
from ..core.renderers import ErrorResponseFormat, ErrorResponseRenderer, RenderResult
from ..converters.sql_converter import SQLErrorConverter
from ..i18n.translator import ErrorTranslator

try:  # pragma: no cover - optional import guard
    from litestar.openapi.spec.enums import OpenAPIType
    from litestar.openapi.spec.media_type import OpenAPIMediaType
    from litestar.openapi.spec.schema import Schema
except ImportError:  # pragma: no cover
    OpenAPIType = None  # type: ignore[assignment]
    OpenAPIMediaType = None  # type: ignore[assignment]
    Schema = None  # type: ignore[assignment]

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
        errors = exc.extra or []
        first_error = next(
            (err for err in errors if isinstance(err, dict) and "path" in err),
            None,
        )
        path = first_error.get("path") if first_error else None
        if path is None:
            path = getattr(exc, "path", None)
        error.details = {
            "errors": errors,
            "path": path,
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


_DEFAULT_PROBLEM_DETAILS: Dict[int, Tuple[str, str, str]] = {
    400: ("VALIDATION_FAILED", "Request validation failed", "Bad Request"),
    401: ("AUTH_REQUIRED", "Authentication required", "Unauthorized"),
    403: ("AUTH_PERMISSION_DENIED", "Access denied", "Forbidden"),
    404: ("RESOURCE_NOT_FOUND", "Resource not found", "Not Found"),
    409: ("DB_DUPLICATE_ENTRY", "Resource conflict", "Conflict"),
    422: ("VALIDATION_FAILED", "Unprocessable entity", "Unprocessable Entity"),
    429: ("RATE_LIMIT_EXCEEDED", "Too many requests", "Too Many Requests"),
    500: ("INTERNAL_ERROR", "Internal server error", "Internal Server Error"),
}


def apply_litestar_openapi_problem_details(
    app: "Litestar",
    *,
    service_name: str,
    status_defaults: Optional[Mapping[int, Tuple[str, str, str]]] = None,
    example_instance: str = "/docs/openapi.json",
) -> None:
    """Ensure generated OpenAPI documentation reflects RFC 7807 error payloads."""

    if OpenAPIType is None or OpenAPIMediaType is None or Schema is None:  # pragma: no cover
        raise ImportError("litestar must be installed to use this helper")

    try:
        schema = app.openapi_schema
    except Exception:  # pragma: no cover - OpenAPI disabled or misconfigured
        return

    if not schema or not getattr(schema, "paths", None):
        return

    defaults = dict(_DEFAULT_PROBLEM_DETAILS)
    if status_defaults:
        defaults.update(status_defaults)

    problem_schema = Schema(
        type=OpenAPIType.OBJECT,
        required=[
            "type",
            "title",
            "status",
            "detail",
            "instance",
            "code",
            "timestamp",
            "request_id",
        ],
        properties={
            "type": Schema(type=OpenAPIType.STRING, format="uri"),
            "title": Schema(type=OpenAPIType.STRING),
            "status": Schema(type=OpenAPIType.INTEGER),
            "detail": Schema(type=OpenAPIType.STRING),
            "instance": Schema(type=OpenAPIType.STRING, format="uri"),
            "code": Schema(type=OpenAPIType.STRING),
            "timestamp": Schema(type=OpenAPIType.STRING, format="date-time"),
            "request_id": Schema(type=OpenAPIType.STRING),
            "service": Schema(type=OpenAPIType.STRING),
            "details": Schema(type=OpenAPIType.OBJECT, additional_properties=True),
        },
        additional_properties=True,
        description="RFC 7807 compatible error payload produced by awesome-errors.",
    )

    operations = ("delete", "get", "head", "options", "patch", "post", "put", "trace")

    for path_item in schema.paths.values():
        for operation_name in operations:
            operation = getattr(path_item, operation_name, None)
            if not operation or not getattr(operation, "responses", None):
                continue

            for status, response in operation.responses.items():
                try:
                    status_code = int(status)
                except (TypeError, ValueError):
                    continue

                if status_code < 400:
                    continue

                error_code, detail, title = defaults.get(
                    status_code,
                    ("UNKNOWN_ERROR", "An unexpected error occurred", "Error"),
                )

                example_payload = {
                    "type": f"urn:{service_name}:error:{error_code.lower()}",
                    "title": title,
                    "status": status_code,
                    "detail": detail,
                    "instance": example_instance,
                    "code": error_code,
                    "timestamp": "2024-01-08T12:00:00Z",
                    "request_id": "req_example123",
                    "service": service_name,
                    "details": {"info": "Example payload"},
                }

                existing = getattr(response, "content", None) or {}
                media_type = existing.get("application/problem+json")
                if media_type:
                    media_type.schema = problem_schema
                    media_type.example = example_payload
                    continue

                response.content = {
                    "application/problem+json": OpenAPIMediaType(
                        schema=problem_schema,
                        example=example_payload,
                    )
                }
