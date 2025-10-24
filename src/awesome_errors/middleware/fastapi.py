from typing import Optional, Dict
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError, HTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import SQLAlchemyError
import logging
import traceback

from awesome_serialization.fastapi import AwesomeResponse

from ..core.exceptions import AppError, ValidationError
from ..core.error_codes import ErrorCode
from ..core.error_response import ErrorResponse, ErrorDetail
from ..converters.sql_converter import SQLErrorConverter
from ..i18n.translator import ErrorTranslator


logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware:
    """FastAPI middleware for handling errors."""

    def __init__(
        self,
        app: FastAPI,
        translator: Optional[ErrorTranslator] = None,
        debug: bool = False,
        log_errors: bool = True,
        locales_dir: Optional[str] = None,
        default_locale: str = "en",
    ):
        """
        Initialize error handler middleware.

        Args:
            app: FastAPI application instance
            translator: Error translator instance
            debug: Debug mode (include stack traces)
            log_errors: Whether to log errors
            locales_dir: Custom directory for locales
            default_locale: Default locale to use
        """
        self.app = app

        # Create translator with custom settings
        if translator is None:
            from pathlib import Path

            locales_path = Path(locales_dir) if locales_dir else None
            self.translator = ErrorTranslator(
                locales_dir=locales_path, default_locale=default_locale
            )
        else:
            self.translator = translator

        self.debug = debug
        self.log_errors = log_errors

        # Register exception handlers
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register exception handlers."""
        # App errors
        self.app.add_exception_handler(AppError, self._handle_app_error)

        # FastAPI validation errors
        self.app.add_exception_handler(
            RequestValidationError, self._handle_validation_error
        )

        # HTTP exceptions
        self.app.add_exception_handler(HTTPException, self._handle_http_exception)
        self.app.add_exception_handler(
            StarletteHTTPException, self._handle_http_exception
        )

        # SQLAlchemy errors
        self.app.add_exception_handler(SQLAlchemyError, self._handle_sqlalchemy_error)

        # Generic errors
        self.app.add_exception_handler(Exception, self._handle_generic_error)

    def _print_stacktrace(self, error_type: str, **kwargs):
        """Print stacktrace to console for 500+ errors."""
        logger.error(f"\n=== {error_type} STACKTRACE ===")
        for key, value in kwargs.items():
            logger.error(f"{key}: {value}")
        logger.error("Stacktrace:")
        traceback.print_exc(limit=30)
        logger.error(f"=== END {error_type} STACKTRACE ===\n")

    async def _handle_app_error(
        self, request: Request, exc: AppError
    ) -> AwesomeResponse:
        """Handle application errors."""
        locale = self._get_locale(request)

        # Translate message
        translated_message = self.translator.translate(
            exc.code.value, locale=locale, params=exc.details
        )

        # Log error if needed
        if self.log_errors:
            logger.error(
                f"App error: {exc.code.value} - {exc.message}",
                extra={
                    "error_code": exc.code.value,
                    "details": exc.details,
                    "request_id": exc.request_id,
                },
            )

        # Print stacktrace to console for 500 errors
        if exc.status_code >= 500:
            self._print_stacktrace(
                "500 ERROR",
                Error_Code=exc.code.value,
                Message=exc.message,
                Request_ID=exc.request_id,
                Details=exc.details,
            )

        # Create response
        error_detail = ErrorDetail(
            code=exc.code.value,
            message=translated_message,
            details=exc.details,
            timestamp=exc.timestamp,
            request_id=exc.request_id,
        )

        response = ErrorResponse(error=error_detail)

        return AwesomeResponse(
            content=response.model_dump(),
            status_code=exc.status_code,
            headers={"X-Request-ID": exc.request_id},
        )

    async def _handle_validation_error(
        self, request: Request, exc: RequestValidationError
    ) -> AwesomeResponse:
        """Handle FastAPI validation errors."""
        # Convert to our validation error
        details = {"errors": exc.errors()}

        error = ValidationError(
            message="Request validation failed",
            code=ErrorCode.VALIDATION_FAILED,
        )
        error.details = details

        return await self._handle_app_error(request, error)

    async def _handle_http_exception(
        self, request: Request, exc: HTTPException
    ) -> AwesomeResponse:
        """Handle HTTP exceptions."""
        # Map status codes to error codes
        status_to_code = {
            400: ErrorCode.INVALID_INPUT,
            401: ErrorCode.AUTH_REQUIRED,
            403: ErrorCode.AUTH_PERMISSION_DENIED,
            404: ErrorCode.RESOURCE_NOT_FOUND,
            422: ErrorCode.VALIDATION_FAILED,
        }

        error_code = status_to_code.get(exc.status_code, ErrorCode.UNKNOWN_ERROR)

        # Create details with HTTPException.detail
        details = {"http_detail": exc.detail}

        error = AppError(
            code=error_code,
            message=str(exc.detail),
            status_code=exc.status_code,
            details=details,
        )

        # Print stacktrace to console for 500 errors
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
    ) -> AwesomeResponse:
        """Handle SQLAlchemy errors."""
        error = SQLErrorConverter.convert(exc)
        return await self._handle_app_error(request, error)

    async def _handle_generic_error(
        self, request: Request, exc: Exception
    ) -> AwesomeResponse:
        """Handle generic errors."""
        # Log full error
        if self.log_errors:
            logger.exception("Unhandled exception")

        # Print stacktrace to console for all unhandled errors
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
        """Get locale from request."""
        # Check Accept-Language header
        accept_language = request.headers.get("Accept-Language", "")
        if accept_language:
            # Simple parsing - take first language
            locale = accept_language.split(",")[0].split("-")[0]
            return locale

        return None


def setup_error_handling(
    app: FastAPI,
    translator: Optional[ErrorTranslator] = None,
    debug: bool = False,
    log_errors: bool = True,
    locales_dir: Optional[str] = None,
    default_locale: str = "en",
    custom_translations: Optional[Dict[str, Dict[str, str]]] = None,
) -> ErrorHandlerMiddleware:
    """
    Setup error handling for FastAPI app.

    Args:
        app: FastAPI application
        translator: Error translator
        debug: Debug mode
        log_errors: Whether to log errors
        locales_dir: Custom directory for locales
        default_locale: Default locale to use
        custom_translations: Custom translations dict {locale: {code: message}}

    Returns:
        ErrorHandlerMiddleware instance
    """
    middleware = ErrorHandlerMiddleware(
        app=app,
        translator=translator,
        debug=debug,
        log_errors=log_errors,
        locales_dir=locales_dir,
        default_locale=default_locale,
    )

    # Add custom translations if provided
    if custom_translations:
        for locale, translations in custom_translations.items():
            middleware.translator.add_translations(locale, translations)

    return middleware
