import json
from typing import TYPE_CHECKING, Optional, cast

if TYPE_CHECKING:
    from pydantic import ValidationError as PydanticValidationError

from ..core.error_codes import ErrorCode
from ..core.exceptions import AppError
from .generic import generic_error_handler
from .python_converter import PythonErrorConverter
from .sql_converter import SQLErrorConverter

SQLAlchemyErrorType: type[Exception] | None = None
try:  # pragma: no cover - optional dependency
    from sqlalchemy.exc import SQLAlchemyError as _LoadedSQLAlchemyError
except ImportError:  # pragma: no cover
    pass
else:  # pragma: no cover
    SQLAlchemyErrorType = _LoadedSQLAlchemyError

PydanticValidationErrorType: type[Exception] | None = None
try:  # pragma: no cover - optional dependency
    from pydantic import ValidationError as _LoadedPydanticValidationError
except ImportError:  # pragma: no cover
    pass
else:  # pragma: no cover
    PydanticValidationErrorType = _LoadedPydanticValidationError


class UniversalErrorConverter:
    """Universal error converter that handles any type of exception."""

    @classmethod
    def convert(cls, error: Exception, debug: bool = False) -> AppError:
        """
        Convert any exception to AppError.

        Args:
            error: Any exception
            debug: Include debug information

        Returns:
            AppError instance with appropriate details
        """
        # Check if it's already an AppError
        if isinstance(error, AppError):
            return error

        # Pydantic validation errors
        if PydanticValidationErrorType is not None and isinstance(
            error, PydanticValidationErrorType
        ):
            from .pydantic_converter import PydanticErrorConverter

            return PydanticErrorConverter.convert(
                cast("PydanticValidationError", error)
            )

        # SQLAlchemy errors
        if SQLAlchemyErrorType is not None and isinstance(error, SQLAlchemyErrorType):
            return SQLErrorConverter.convert(error)

        # Standard Python exceptions
        if type(error) in PythonErrorConverter.EXCEPTION_MAP:
            return PythonErrorConverter.convert(error)

        # Handle other specific error types
        app_error = cls._handle_special_cases(error)
        if app_error:
            return app_error

        # Default handling for unknown errors
        return generic_error_handler(error, debug)

    @classmethod
    def _handle_special_cases(cls, error: Exception) -> Optional[AppError]:
        """Handle special error cases from the standard library and popular
        third-party packages that are not covered by the dedicated converters."""
        error_type = type(error).__name__
        error_str = str(error)

        # JSON decode errors (subclass of ValueError; check before generic HTTP)
        if isinstance(error, json.JSONDecodeError):
            return AppError(
                code=ErrorCode.INVALID_FORMAT,
                message="Invalid JSON format",
                details={"error_type": error_type, "error": error_str},
            )

        # HTTP client errors (requests/httpx/urllib) are matched by name so we
        # don't have to import those optional packages just to identify them.
        if "HTTPError" in error_type:
            return AppError(
                code=ErrorCode.INTERNAL_ERROR,
                message="HTTP request failed",
                details={"error_type": error_type, "error": error_str},
            )

        # Missing modules
        if isinstance(error, (ImportError, ModuleNotFoundError)):
            return AppError(
                code=ErrorCode.INTERNAL_ERROR,
                message="Missing required module",
                details={
                    "module": getattr(error, "name", None) or "unknown",
                    "error": error_str,
                },
            )

        return None
