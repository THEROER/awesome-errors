"""FastAPI integration for awesome-errors."""

from __future__ import annotations

import logging
import traceback
from typing import Callable, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..core.error_codes import ErrorCode
from ..core.exceptions import AppError, ValidationError
from ..core.renderers import ErrorResponseFormat, ErrorResponseRenderer, RenderResult
from ..converters.sql_converter import SQLErrorConverter
from ..i18n.translator import ErrorTranslator

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware:
    """FastAPI middleware that converts exceptions into structured responses."""

    def __init__(
        self,
        app: FastAPI,
        translator: Optional[ErrorTranslator] = None,
        debug: bool = False,
        log_errors: bool = True,
        locales_dir: Optional[str] = None,
        default_locale: str = "en",
        response_format: ErrorResponseFormat = ErrorResponseFormat.LEGACY,
        problem_type_resolver: Optional[Callable[[AppError], str]] = None,
        problem_extension_builder: Optional[
            Callable[[AppError], Dict[str, object]]
        ] = None,
        message_resolver: Optional[
            Callable[[AppError, Optional[str], Optional[ErrorTranslator]], str]
        ] = None,
    ) -> None:
        self.app = app

        if translator is None:
            from pathlib import Path

            locales_path = Path(locales_dir) if locales_dir else None
            self.translator = ErrorTranslator(
                locales_dir=locales_path, default_locale=default_locale
            )
        else:
            self.translator = translator

        self.message_resolver = message_resolver
        self.debug = debug
        self.log_errors = log_errors
        self.renderer = ErrorResponseRenderer(
            format=response_format,
            problem_type_resolver=problem_type_resolver,
            problem_extension_builder=problem_extension_builder,
        )

        self._register_handlers()

    def _register_handlers(self) -> None:
        self.app.add_exception_handler(AppError, self._handle_app_error)
        self.app.add_exception_handler(
            RequestValidationError, self._handle_validation_error
        )
        self.app.add_exception_handler(HTTPException, self._handle_http_exception)
        self.app.add_exception_handler(
            StarletteHTTPException, self._handle_http_exception
        )
        self.app.add_exception_handler(SQLAlchemyError, self._handle_sqlalchemy_error)
        self.app.add_exception_handler(Exception, self._handle_generic_error)

    async def _handle_app_error(self, request: Request, exc: AppError) -> JSONResponse:
        locale = self._get_locale(request)
        translated_message = self._resolve_message(exc, locale)

        if self.log_errors:
            logger.error(
                f"App error: {exc.code.value} - {exc.message}",
                extra={
                    "error_code": exc.code.value,
                    "details": exc.details,
                    "request_id": exc.request_id,
                },
            )

        if exc.status_code >= 500:
            self._print_stacktrace(
                "500 ERROR",
                Error_Code=exc.code.value,
                Message=exc.message,
                Request_ID=exc.request_id,
                Details=exc.details,
            )

        rendered: RenderResult = self.renderer.render(
            exc, message=translated_message, request=request
        )

        return JSONResponse(
            content=rendered.payload,
            status_code=exc.status_code,
            media_type=rendered.media_type,
            headers={"X-Request-ID": exc.request_id},
        )

    async def _handle_validation_error(
        self, request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = {"errors": exc.errors()}

        error = ValidationError(
            message="Request validation failed",
            code=ErrorCode.VALIDATION_FAILED,
        )
        error.details = details

        return await self._handle_app_error(request, error)

    async def _handle_http_exception(
        self, request: Request, exc: HTTPException
    ) -> JSONResponse:
        status_to_code = {
            400: ErrorCode.INVALID_INPUT,
            401: ErrorCode.AUTH_REQUIRED,
            403: ErrorCode.AUTH_PERMISSION_DENIED,
            404: ErrorCode.RESOURCE_NOT_FOUND,
            422: ErrorCode.VALIDATION_FAILED,
        }

        error_code = status_to_code.get(exc.status_code, ErrorCode.UNKNOWN_ERROR)
        details = {"http_detail": exc.detail}

        error = AppError(
            code=error_code,
            message=str(exc.detail),
            status_code=exc.status_code,
            details=details,
        )

        if exc.status_code >= 500:
            self._print_stacktrace(
                "500 HTTP ERROR",
                HTTP_Status=exc.status_code,
                Error_Code=error_code.value,
                Message=exc.detail,
                Details=details,
            )

        return await self._handle_app_error(request, error)

    async def _handle_sqlalchemy_error(
        self, request: Request, exc: SQLAlchemyError
    ) -> JSONResponse:
        error = SQLErrorConverter.convert(exc)
        return await self._handle_app_error(request, error)

    async def _handle_generic_error(
        self, request: Request, exc: Exception
    ) -> JSONResponse:
        if self.log_errors:
            logger.exception("Unhandled exception")

        self._print_stacktrace(
            "UNHANDLED ERROR",
            Exception_Type=type(exc).__name__,
            Exception_Message=str(exc),
        )

        error = AppError(
            code=ErrorCode.INTERNAL_ERROR,
            message="An internal error occurred" if not self.debug else str(exc),
            status_code=500,
        )

        if self.debug:
            error.details["traceback"] = traceback.format_exc()

        return await self._handle_app_error(request, error)

    def _get_locale(self, request: Request) -> Optional[str]:
        accept_language = request.headers.get("Accept-Language", "")
        if accept_language:
            return accept_language.split(",")[0].split("-")[0]
        return None

    def _resolve_message(self, error: AppError, locale: Optional[str]) -> str:
        if self.message_resolver:
            return self.message_resolver(error, locale, self.translator)

        translated = self.translator.translate(
            error.code.value,
            locale=locale,
            params=error.details,
        )
        if translated == error.code.value:
            return error.message
        return translated

    def _print_stacktrace(self, error_type: str, **kwargs: object) -> None:
        logger.error(f"\n=== {error_type} STACKTRACE ===")
        for key, value in kwargs.items():
            logger.error(f"{key}: {value}")
        logger.error("Stacktrace:")
        traceback.print_exc(limit=30)
        logger.error(f"=== END {error_type} STACKTRACE ===\n")


def setup_error_handling(
    app: FastAPI,
    translator: Optional[ErrorTranslator] = None,
    debug: bool = False,
    log_errors: bool = True,
    locales_dir: Optional[str] = None,
    default_locale: str = "en",
    custom_translations: Optional[Dict[str, Dict[str, str]]] = None,
    response_format: ErrorResponseFormat = ErrorResponseFormat.LEGACY,
    problem_type_resolver: Optional[Callable[[AppError], str]] = None,
    problem_extension_builder: Optional[Callable[[AppError], Dict[str, object]]] = None,
    message_resolver: Optional[
        Callable[[AppError, Optional[str], Optional[ErrorTranslator]], str]
    ] = None,
) -> ErrorHandlerMiddleware:
    middleware = ErrorHandlerMiddleware(
        app=app,
        translator=translator,
        debug=debug,
        log_errors=log_errors,
        locales_dir=locales_dir,
        default_locale=default_locale,
        response_format=response_format,
        problem_type_resolver=problem_type_resolver,
        problem_extension_builder=problem_extension_builder,
        message_resolver=message_resolver,
    )

    if custom_translations:
        for locale, translations in custom_translations.items():
            middleware.translator.add_translations(locale, translations, persist=False)

    return middleware
