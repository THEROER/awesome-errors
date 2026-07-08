"""FastAPI integration for awesome-errors."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional, cast

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..core.error_codes import ErrorCode
from ..core.exceptions import AppError, ValidationError
from ..core.renderers import ErrorResponseFormat, ErrorResponseRenderer, RenderResult
from ..converters.sql_converter import SQLErrorConverter
from ..i18n.translator import ErrorTranslator
from . import _base

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
        message_resolver: Optional[_base.MessageResolver] = None,
    ) -> None:
        self.app = app
        self.translator = _base.resolve_translator(
            translator, locales_dir=locales_dir, default_locale=default_locale
        )
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
        self.app.add_exception_handler(AppError, cast(Any, self._handle_app_error))
        self.app.add_exception_handler(
            RequestValidationError, cast(Any, self._handle_validation_error)
        )
        self.app.add_exception_handler(
            HTTPException, cast(Any, self._handle_http_exception)
        )
        self.app.add_exception_handler(
            StarletteHTTPException, cast(Any, self._handle_http_exception)
        )

        sqlalchemy_error = _base.load_sqlalchemy_base_error()
        if sqlalchemy_error is not None:
            self.app.add_exception_handler(
                sqlalchemy_error, cast(Any, self._handle_sqlalchemy_error)
            )

        self.app.add_exception_handler(Exception, cast(Any, self._handle_generic_error))

    async def _handle_app_error(self, request: Request, exc: AppError) -> JSONResponse:
        locale = _base.locale_from_accept_language(
            request.headers.get("Accept-Language")
        )
        message = _base.resolve_message(
            exc, locale, self.translator, self.message_resolver
        )

        if self.log_errors:
            logger.error(
                "App error: %s - %s",
                exc.code.value,
                exc.message,
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

        rendered: RenderResult = self.renderer.render(
            exc, message=message, request=request
        )

        return JSONResponse(
            content=rendered.payload,
            status_code=exc.status_code,
            media_type=rendered.media_type,
            headers={"X-Request-ID": exc.request_id or "unknown"},
        )

    async def _handle_validation_error(
        self, request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        error = ValidationError(
            message="Request validation failed",
            code=ErrorCode.VALIDATION_FAILED,
        )
        error.details = {"errors": exc.errors()}
        return await self._handle_app_error(request, error)

    async def _handle_http_exception(
        self, request: Request, exc: HTTPException
    ) -> JSONResponse:
        error = AppError(
            code=_base.error_code_for_status(exc.status_code),
            message=str(exc.detail),
            status_code=exc.status_code,
            details={"http_detail": exc.detail},
        )
        return await self._handle_app_error(request, error)

    async def _handle_sqlalchemy_error(
        self, request: Request, exc: Exception
    ) -> JSONResponse:
        error = SQLErrorConverter.convert(exc)
        return await self._handle_app_error(request, error)

    async def _handle_generic_error(
        self, request: Request, exc: Exception
    ) -> JSONResponse:
        if self.log_errors:
            logger.exception("Unhandled exception")
        _base.log_stacktrace(
            logger,
            "UNHANDLED ERROR",
            Exception_Type=type(exc).__name__,
            Exception_Message=str(exc),
        )
        error = _base.build_generic_error(exc, debug=self.debug)
        return await self._handle_app_error(request, error)


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
    message_resolver: Optional[_base.MessageResolver] = None,
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
