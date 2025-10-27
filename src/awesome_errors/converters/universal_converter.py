from typing import Optional, Any

try:  # pragma: no cover - optional dependency
    from pydantic import ValidationError as PydanticValidationError
except ImportError:  # pragma: no cover
    PydanticValidationError = None  # type: ignore[assignment]

from sqlalchemy.exc import SQLAlchemyError

from ..core.exceptions import AppError
from ..core.error_codes import ErrorCode
from .sql_converter import SQLErrorConverter
from .python_converter import PythonErrorConverter
try:  # pragma: no cover - optional dependency
    from .pydantic_converter import PydanticErrorConverter
except ImportError:  # pragma: no cover
    PydanticErrorConverter = None  # type: ignore[assignment]

from .generic import generic_error_handler


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
        if PydanticValidationError is not None and isinstance(
            error, PydanticValidationError
        ):
            if PydanticErrorConverter is None:
                raise ImportError(
                    "Install 'awesome-errors[pydantic]' to convert Pydantic validation errors."
                ) from None
            return PydanticErrorConverter.convert(error)

        # SQLAlchemy errors
        if isinstance(error, SQLAlchemyError):
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
        """Handle special error cases."""
        error_type = type(error).__name__
        error_str = str(error)

        # Handle HTTP-related errors
        if "HTTPError" in error_type:
            return AppError(
                code=ErrorCode.INTERNAL_ERROR,
                message="HTTP request failed",
                details={"error_type": error_type, "error": error_str},
            )

        # Handle JSON errors
        if "JSONDecodeError" in error_type:
            return AppError(
                code=ErrorCode.INVALID_FORMAT,
                message="Invalid JSON format",
                details={"error_type": error_type, "error": error_str},
            )

        # Handle import errors
        if isinstance(error, (ImportError, ModuleNotFoundError)):
            return AppError(
                code=ErrorCode.INTERNAL_ERROR,
                message="Missing required module",
                details={
                    "module": error.name if hasattr(error, "name") else "unknown",
                    "error": error_str,
                },
            )

        return None

    @staticmethod
    def _is_serializable(value: Any) -> bool:
        """Check if value can be safely serialized."""
        try:
            import json

            json.dumps(value)
            return True
        except Exception:
            return False
