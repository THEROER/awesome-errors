"""Litestar integration helpers."""

from __future__ import annotations

import logging
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
from . import _base

logger = logging.getLogger(__name__)


def create_litestar_exception_handlers(
    *,
    translator: Optional[ErrorTranslator] = None,
    debug: bool = False,
    log_errors: bool = True,
    log_level_resolver: Optional[Callable[[AppError], Optional[int]]] = None,
    suppress_error_codes: Optional[Tuple[ErrorCode | str, ...]] = None,
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

    translator = _base.resolve_translator(
        translator, locales_dir=locales_dir, default_locale=default_locale
    )

    renderer = ErrorResponseRenderer(
        format=response_format,
        problem_type_resolver=problem_type_resolver,
        problem_extension_builder=problem_extension_builder,
    )

    from litestar.exceptions import HTTPException, ValidationException  # type: ignore
    from litestar.response import Response  # type: ignore

    suppressed_codes = {
        code.value if isinstance(code, ErrorCode) else str(code)
        for code in (suppress_error_codes or ())
    }

    def handle_app_error(request: "Request", exc: AppError) -> "Response":
        locale = _base.locale_from_accept_language(
            request.headers.get("Accept-Language")
        )

        if log_errors:
            if exc.code.value not in suppressed_codes:
                level = log_level_resolver(exc) if log_level_resolver else logging.ERROR
                if level is not None:
                    logger.log(
                        level,
                        f"App error: {exc.code.value} - {exc.message}",
                        extra={
                            "error_code": exc.code.value,
                            "details": exc.details,
                            "request_id": exc.request_id,
                        },
                    )

        if exc.status_code >= 500:
            _base.log_stacktrace(
                logger,
                "500 ERROR",
                Error_Code=exc.code.value,
                Message=exc.message,
                Request_ID=exc.request_id,
                Details=exc.details,
            )

        rendered: RenderResult = renderer.render(
            exc,
            message=_base.resolve_message(exc, locale, translator, message_resolver),
            request=request,
        )

        return Response(
            content=rendered.payload,
            status_code=exc.status_code,
            media_type=rendered.media_type,
            headers={"X-Request-ID": exc.request_id or "unknown"},
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
        error_code = _base.error_code_for_status(exc.status_code)
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
            _base.log_stacktrace(
                logger,
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

        _base.log_stacktrace(
            logger,
            "UNHANDLED ERROR",
            Exception_Type=type(exc).__name__,
            Exception_Message=str(exc),
        )

        error = _base.build_generic_error(exc, debug=debug)
        return handle_app_error(request, error)

    handlers: Dict[Type[Exception], "ExceptionHandler"] = {
        AppError: handle_app_error,
        ValidationException: handle_validation_error,
        HTTPException: handle_http_exception,
        Exception: handle_generic_error,
    }

    sqlalchemy_error = _base.load_sqlalchemy_base_error()
    if sqlalchemy_error is not None:
        handlers[sqlalchemy_error] = handle_sqlalchemy_error

    return handlers


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
    try:  # pragma: no cover - optional dependency
        from litestar.openapi.spec.enums import OpenAPIFormat, OpenAPIType
        from litestar.openapi.spec.media_type import OpenAPIMediaType
        from litestar.openapi.spec.schema import Schema
    except ImportError as exc:  # pragma: no cover
        raise ImportError("litestar must be installed to use this helper") from exc

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
            "type": Schema(type=OpenAPIType.STRING, format=OpenAPIFormat.URI),
            "title": Schema(type=OpenAPIType.STRING),
            "status": Schema(type=OpenAPIType.INTEGER),
            "detail": Schema(type=OpenAPIType.STRING),
            "instance": Schema(type=OpenAPIType.STRING, format=OpenAPIFormat.URI),
            "code": Schema(type=OpenAPIType.STRING),
            "timestamp": Schema(type=OpenAPIType.STRING, format=OpenAPIFormat.DATE_TIME),
            "request_id": Schema(type=OpenAPIType.STRING),
            "service": Schema(type=OpenAPIType.STRING),
            "details": Schema(type=OpenAPIType.OBJECT, additional_properties=True),
        },
        additional_properties=True,
        description="RFC 7807 compatible error payload produced by awesome-errors.",
    )

    operations = ("delete", "get", "head", "options", "patch", "post", "put", "trace")

    for path_item in (schema.paths or {}).values():
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
