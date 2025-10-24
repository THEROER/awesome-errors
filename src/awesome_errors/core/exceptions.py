from typing import Any, Dict, Optional, Union
from datetime import datetime, timezone
import uuid

from .error_codes import ErrorCode, get_http_status


class AppError(Exception):
    """
    Base application error class for server-side error handling.

    This is the core exception class used throughout the application.
    It provides standardized error structure with:
    - Error code (from ErrorCode enum or custom string)
    - Human-readable message
    - Additional details dictionary
    - Timestamp and request ID for tracing

    Usage:
        raise AppError(ErrorCode.USER_NOT_FOUND, "User not found", {"user_id": 123})
    """

    def __init__(
        self,
        code: Union[ErrorCode, str],
        message: str,
        details: Optional[Dict[str, Any]] = None,
        status_code: Optional[int] = None,
    ):
        super().__init__(message)
        self.code = code if isinstance(code, ErrorCode) else ErrorCode(code)
        self.message = message
        self.details = details or {}
        self.timestamp = datetime.now(timezone.utc)
        self.request_id = str(uuid.uuid4())

        # Use provided status code or get from mapping
        self.status_code = status_code or get_http_status(self.code)

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for JSON serialization."""
        return {
            "error": {
                "code": self.code.value,
                "message": self.message,
                "details": self.details,
                "timestamp": self.timestamp.isoformat() + "Z",
                "request_id": self.request_id,
            }
        }


class ValidationError(AppError):
    """
    Validation error (HTTP 400) for input validation failures.

    Used when user input fails validation rules.
    Can include field-specific information.

    Usage:
        raise ValidationError("Email is required", field="email")
    """

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Any = None,
        code: ErrorCode = ErrorCode.VALIDATION_FAILED,
    ):
        details = {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = value

        super().__init__(code, message, details, 400)


class AuthError(AppError):
    """
    Authentication/Authorization error (HTTP 401/403).

    Used for authentication and authorization failures.
    Can include required permission information.

    Usage:
        raise AuthError("Admin access required", required_permission="admin.users.read")
    """

    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.AUTH_REQUIRED,
        required_permission: Optional[str] = None,
    ):
        details = {}
        if required_permission:
            details["required_permission"] = required_permission

        super().__init__(code, message, details)


class NotFoundError(AppError):
    """
    Resource not found error (HTTP 404).

    Used when a requested resource doesn't exist.
    Includes resource type and ID information.

    Usage:
        raise NotFoundError("user", user_id=123)
    """

    def __init__(
        self,
        resource: str,
        resource_id: Optional[Union[str, int]] = None,
        code: ErrorCode = ErrorCode.RESOURCE_NOT_FOUND,
    ):
        details = {"resource": resource}
        if resource_id is not None:
            details["resource_id"] = resource_id

        message = f"{resource} not found"
        if resource_id:
            message += f" with id: {resource_id}"

        super().__init__(code, message, details, 404)


class DatabaseError(AppError):
    """
    Database error (HTTP 500/409/422).

    Used for database-related errors like constraint violations,
    connection issues, or query failures.

    Usage:
        raise DatabaseError("Duplicate email", table="users", sql_error="...")
    """

    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.DB_QUERY_ERROR,
        sql_error: Optional[str] = None,
        table: Optional[str] = None,
    ):
        details = {}
        if sql_error:
            details["sql_error"] = sql_error
        if table:
            details["table"] = table

        super().__init__(code, message, details)


class BusinessLogicError(AppError):
    """
    Business logic error (HTTP 422).

    Used for business rule violations and domain-specific errors.
    Can include rule name and context information.

    Usage:
        raise BusinessLogicError("Insufficient balance", rule="min_balance", context={"current": 50})
    """

    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.BUSINESS_RULE_VIOLATION,
        rule: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        details = {}
        if rule:
            details["rule"] = rule
        if context:
            details["context"] = context

        super().__init__(code, message, details, 422)
