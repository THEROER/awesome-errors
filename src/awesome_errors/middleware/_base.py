"""Framework-agnostic building blocks shared by the framework integrations.

FastAPI and Litestar integrations differ only in the request/response types
they speak. Everything else — locale negotiation, message translation,
mapping raw exceptions to :class:`AppError`, stacktrace logging — lives here so
neither integration duplicates it.
"""

from __future__ import annotations

import logging
import traceback
from typing import Callable, Dict, Optional

from ..core.error_codes import ErrorCode
from ..core.exceptions import AppError
from ..i18n.translator import ErrorTranslator

MessageResolver = Callable[[AppError, Optional[str], Optional[ErrorTranslator]], str]

# HTTP status code -> ErrorCode used when translating framework HTTPExceptions
# that were not raised as AppError instances.
STATUS_TO_ERROR_CODE: Dict[int, ErrorCode] = {
    400: ErrorCode.INVALID_INPUT,
    401: ErrorCode.AUTH_REQUIRED,
    403: ErrorCode.AUTH_PERMISSION_DENIED,
    404: ErrorCode.RESOURCE_NOT_FOUND,
    422: ErrorCode.VALIDATION_FAILED,
}


def error_code_for_status(status_code: int) -> ErrorCode:
    """Return the :class:`ErrorCode` best matching an HTTP status code."""
    return STATUS_TO_ERROR_CODE.get(status_code, ErrorCode.UNKNOWN_ERROR)


def locale_from_accept_language(header_value: Optional[str]) -> Optional[str]:
    """Extract the primary language tag from an ``Accept-Language`` header."""
    if not header_value:
        return None
    return header_value.split(",")[0].split("-")[0] or None


def resolve_translator(
    translator: Optional[ErrorTranslator],
    *,
    locales_dir: Optional[str],
    default_locale: str,
) -> ErrorTranslator:
    """Return the provided translator or build a default one."""
    if translator is not None:
        return translator

    from pathlib import Path

    locales_path = Path(locales_dir) if locales_dir else None
    return ErrorTranslator(locales_dir=locales_path, default_locale=default_locale)


def resolve_message(
    error: AppError,
    locale: Optional[str],
    translator: ErrorTranslator,
    message_resolver: Optional[MessageResolver] = None,
) -> str:
    """Translate an error's message, falling back to the raw message."""
    if message_resolver is not None:
        return message_resolver(error, locale, translator)

    translated = translator.translate(
        error.code.value,
        locale=locale,
        params=error.details,
    )
    if translated == error.code.value:
        return error.message
    return translated


def build_generic_error(exc: Exception, *, debug: bool) -> AppError:
    """Build an :class:`AppError` for an otherwise-unhandled exception."""
    error = AppError(
        code=ErrorCode.INTERNAL_ERROR,
        message=str(exc) if debug else "An internal error occurred",
        status_code=500,
    )
    if debug:
        error.details["traceback"] = traceback.format_exc()
    return error


def log_stacktrace(logger: logging.Logger, error_type: str, **context: object) -> None:
    """Emit a labelled stacktrace block for a server-side (5xx) error."""
    logger.error("\n=== %s STACKTRACE ===", error_type)
    for key, value in context.items():
        logger.error("%s: %s", key, value)
    logger.error("Stacktrace:")
    traceback.print_exc(limit=30)
    logger.error("=== END %s STACKTRACE ===\n", error_type)


def load_sqlalchemy_base_error() -> Optional[type]:
    """Return SQLAlchemy's base error class, or ``None`` if not installed."""
    try:
        from sqlalchemy.exc import SQLAlchemyError
    except ImportError:  # pragma: no cover - optional dependency
        return None
    return SQLAlchemyError
