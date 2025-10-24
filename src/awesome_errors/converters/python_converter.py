from typing import Dict, Type, Tuple

from ..core.error_codes import ErrorCode
from ..core.exceptions import AppError, ValidationError, AuthError, NotFoundError
from .generic import generic_error_handler


class PythonErrorConverter:
    """Convert standard Python exceptions to application errors."""

    # Mapping of Python exceptions to (ErrorCode, message) tuples
    EXCEPTION_MAP: Dict[Type[Exception], Tuple[ErrorCode, str]] = {
        # Value errors
        ValueError: (ErrorCode.INVALID_INPUT, "Invalid value provided"),
        TypeError: (ErrorCode.INVALID_INPUT, "Invalid type provided"),
        AttributeError: (ErrorCode.INVALID_INPUT, "Invalid attribute access"),
        # Key/Index errors
        KeyError: (ErrorCode.RESOURCE_NOT_FOUND, "Key not found"),
        IndexError: (ErrorCode.RESOURCE_NOT_FOUND, "Index out of range"),
        # Permission errors
        PermissionError: (ErrorCode.AUTH_PERMISSION_DENIED, "Permission denied"),
        # File errors
        FileNotFoundError: (ErrorCode.RESOURCE_NOT_FOUND, "File not found"),
        # Arithmetic errors
        ZeroDivisionError: (ErrorCode.INVALID_INPUT, "Division by zero"),
        ArithmeticError: (ErrorCode.INVALID_INPUT, "Arithmetic error"),
        # System errors
        MemoryError: (ErrorCode.INTERNAL_ERROR, "Memory error"),
        RecursionError: (ErrorCode.INTERNAL_ERROR, "Maximum recursion depth exceeded"),
        # Connection errors
        ConnectionError: (ErrorCode.DB_CONNECTION_ERROR, "Connection error"),
        TimeoutError: (ErrorCode.DB_CONNECTION_ERROR, "Operation timed out"),
    }

    @classmethod
    def convert(cls, error: Exception) -> AppError:
        """
        Convert Python exception to AppError.

        Args:
            error: Python exception

        Returns:
            AppError instance
        """
        error_type = type(error)

        # Check if we have a specific mapping
        for exc_type, (code, default_message) in cls.EXCEPTION_MAP.items():
            if issubclass(error_type, exc_type):
                return cls._create_app_error(error, code, default_message)

        # Default to internal error
        return generic_error_handler(error)

    @classmethod
    def _create_app_error(
        cls, error: Exception, code: ErrorCode, default_message: str
    ) -> AppError:
        """Create appropriate AppError subclass."""
        message = str(error) or default_message
        details = {"exception_type": type(error).__name__}

        # Add specific details based on exception type
        if isinstance(error, KeyError):
            details["key"] = str(error).strip("'\"")
            return NotFoundError(resource="key", resource_id=details["key"], code=code)

        elif isinstance(error, FileNotFoundError):
            details["filename"] = error.filename
            return NotFoundError(resource="file", resource_id=error.filename, code=code)

        elif isinstance(error, (ValueError, TypeError, AttributeError)):
            return ValidationError(message=message, code=code)

        elif isinstance(error, PermissionError):
            return AuthError(message=message, code=code)

        # Default to AppError
        return AppError(code=code, message=message, details=details)
