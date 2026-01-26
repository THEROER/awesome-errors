from typing import Any, ClassVar, Dict, Optional, Union
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


class APIError(AppError):
    """Base HTTP-facing error with OpenAPI metadata."""

    code: ClassVar[Union[ErrorCode, str]] = ErrorCode.UNKNOWN_ERROR
    status_code: ClassVar[int | None] = None
    title: ClassVar[str] = "Internal error"
    description: ClassVar[str] = "An internal error occurred"
    response_media_type: ClassVar[str] = "application/problem+json"

    def __init__(
        self,
        code: Union[ErrorCode, str] | None = None,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        status_code: Optional[int] = None,
    ):
        effective_code = code or self.code
        effective_status = (
            status_code if status_code is not None else self.status_code
        )
        super().__init__(
            effective_code,
            message or self.title,
            details,
            effective_status,
        )

    @classmethod
    def get_status_code(cls) -> int:
        if cls.status_code is not None:
            return cls.status_code
        error_code = cls.code if isinstance(cls.code, ErrorCode) else ErrorCode(cls.code)
        return get_http_status(error_code)

    @classmethod
    def openapi_response(cls) -> "ResponseSpec":  # type: ignore[name-defined]
        try:
            from litestar.openapi.spec import ResponseSpec  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            msg = "Litestar is required to build OpenAPI response specs"
            raise RuntimeError(msg) from exc

        return ResponseSpec(
            description=cls.description,
            media_type=cls.response_media_type,
        )


class ValidationError(APIError):
    """
    Validation error (HTTP 400) for input validation failures.

    Used when user input fails validation rules.
    Can include field-specific information.

    Usage:
        raise ValidationError("Email is required", field="email")
    """

    code: ClassVar[ErrorCode] = ErrorCode.VALIDATION_FAILED
    status_code: ClassVar[int] = 400
    title: ClassVar[str] = "Request validation failed"
    description: ClassVar[str] = "Request validation failed"

    def __init__(
        self,
        message: Optional[str] = None,
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


class InvalidInputError(ValidationError):
    """Invalid input error (HTTP 400)."""

    code: ClassVar[ErrorCode] = ErrorCode.INVALID_INPUT
    title: ClassVar[str] = "Invalid input"
    description: ClassVar[str] = "Invalid input"

    def __init__(self, message: Optional[str] = None, field: Optional[str] = None):
        super().__init__(message or self.title, field=field, code=self.code)


class MissingRequiredFieldError(ValidationError):
    """Missing required field error (HTTP 400)."""

    code: ClassVar[ErrorCode] = ErrorCode.MISSING_REQUIRED_FIELD
    title: ClassVar[str] = "Missing required field"
    description: ClassVar[str] = "Missing required field"

    def __init__(self, message: Optional[str] = None, field: Optional[str] = None):
        super().__init__(message or self.title, field=field, code=self.code)


class InvalidFormatError(ValidationError):
    """Invalid format error (HTTP 400)."""

    code: ClassVar[ErrorCode] = ErrorCode.INVALID_FORMAT
    title: ClassVar[str] = "Invalid format"
    description: ClassVar[str] = "Invalid format"

    def __init__(self, message: Optional[str] = None, field: Optional[str] = None):
        super().__init__(message or self.title, field=field, code=self.code)


class AuthError(APIError):
    """
    Authentication/Authorization error (HTTP 401/403).

    Used for authentication and authorization failures.
    Can include required permission information.

    Usage:
        raise AuthError("Admin access required", required_permission="admin.users.read")
    """

    code: ClassVar[ErrorCode] = ErrorCode.AUTH_REQUIRED
    status_code: ClassVar[int] = 401
    title: ClassVar[str] = "Authentication required"
    description: ClassVar[str] = "Authentication required"

    def __init__(
        self,
        message: Optional[str] = None,
        code: ErrorCode = ErrorCode.AUTH_REQUIRED,
        required_permission: Optional[str] = None,
        status_code: Optional[int] = None,
    ):
        details = {}
        if required_permission:
            details["required_permission"] = required_permission

        super().__init__(code, message, details, status_code)


class AuthRequiredError(AuthError):
    """Authentication required error (HTTP 401)."""

    code: ClassVar[ErrorCode] = ErrorCode.AUTH_REQUIRED
    title: ClassVar[str] = "Authentication required"
    description: ClassVar[str] = "Authentication required"

    def __init__(
        self, message: Optional[str] = None, required_permission: Optional[str] = None
    ):
        super().__init__(message, code=self.code, required_permission=required_permission)


class AuthInvalidTokenError(AuthError):
    """Invalid token error (HTTP 401)."""

    code: ClassVar[ErrorCode] = ErrorCode.AUTH_INVALID_TOKEN
    title: ClassVar[str] = "Invalid token"
    description: ClassVar[str] = "Invalid token"

    def __init__(self, message: Optional[str] = None):
        super().__init__(message, code=self.code)


class AuthTokenExpiredError(AuthError):
    """Token expired error (HTTP 401)."""

    code: ClassVar[ErrorCode] = ErrorCode.AUTH_TOKEN_EXPIRED
    title: ClassVar[str] = "Token expired"
    description: ClassVar[str] = "Token expired"

    def __init__(self, message: Optional[str] = None):
        super().__init__(message, code=self.code)


class AuthPermissionDeniedError(AuthError):
    """Permission denied error (HTTP 403)."""

    code: ClassVar[ErrorCode] = ErrorCode.AUTH_PERMISSION_DENIED
    status_code: ClassVar[int] = 403
    title: ClassVar[str] = "Access denied"
    description: ClassVar[str] = "Access denied"

    def __init__(
        self, message: Optional[str] = None, required_permission: Optional[str] = None
    ):
        super().__init__(
            message,
            code=self.code,
            required_permission=required_permission,
            status_code=self.status_code,
        )


class AuthInsufficientPrivilegesError(AuthError):
    """Insufficient privileges error (HTTP 403)."""

    code: ClassVar[ErrorCode] = ErrorCode.AUTH_INSUFFICIENT_PRIVILEGES
    status_code: ClassVar[int] = 403
    title: ClassVar[str] = "Insufficient privileges"
    description: ClassVar[str] = "Insufficient privileges"

    def __init__(
        self, message: Optional[str] = None, required_permission: Optional[str] = None
    ):
        super().__init__(
            message,
            code=self.code,
            required_permission=required_permission,
            status_code=self.status_code,
        )


class SessionExpiredError(AuthError):
    """Session expired error (HTTP 401)."""

    code: ClassVar[ErrorCode] = ErrorCode.SESSION_EXPIRED
    title: ClassVar[str] = "Session has expired"
    description: ClassVar[str] = "Session has expired"

    def __init__(self, message: Optional[str] = None):
        super().__init__(message or self.title, code=self.code)


class RefreshTokenReuseDetectedError(AuthError):
    """Refresh token reuse detected (HTTP 401)."""

    code: ClassVar[ErrorCode] = ErrorCode.REFRESH_TOKEN_REUSE
    title: ClassVar[str] = "Refresh token reuse detected"
    description: ClassVar[str] = "Refresh token reuse detected"

    def __init__(self, message: Optional[str] = None):
        super().__init__(message or self.title, code=self.code)


class NotFoundError(APIError):
    """
    Resource not found error (HTTP 404).

    Used when a requested resource doesn't exist.
    Includes resource type and ID information.

    Usage:
        raise NotFoundError("user", user_id=123)
    """

    code: ClassVar[ErrorCode] = ErrorCode.RESOURCE_NOT_FOUND
    status_code: ClassVar[int] = 404
    title: ClassVar[str] = "Resource not found"
    description: ClassVar[str] = "Resource not found"

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


class ResourceNotFoundError(NotFoundError):
    """Resource not found error (HTTP 404)."""

    code: ClassVar[ErrorCode] = ErrorCode.RESOURCE_NOT_FOUND
    title: ClassVar[str] = "Resource not found"
    description: ClassVar[str] = "Resource not found"

    def __init__(self, resource: str, resource_id: Optional[Union[str, int]] = None):
        super().__init__(resource, resource_id=resource_id, code=self.code)


class UserNotFoundError(NotFoundError):
    """User not found error (HTTP 404)."""

    code: ClassVar[ErrorCode] = ErrorCode.USER_NOT_FOUND
    title: ClassVar[str] = "User not found"
    description: ClassVar[str] = "User not found"

    def __init__(self, user_id: Optional[Union[str, int]] = None):
        super().__init__("user", resource_id=user_id, code=self.code)


class EntityNotFoundError(NotFoundError):
    """Entity not found error (HTTP 404)."""

    code: ClassVar[ErrorCode] = ErrorCode.ENTITY_NOT_FOUND
    title: ClassVar[str] = "Entity not found"
    description: ClassVar[str] = "Entity not found"

    def __init__(self, entity: str, entity_id: Optional[Union[str, int]] = None):
        super().__init__(entity, resource_id=entity_id, code=self.code)


class OAuthProviderUnknownError(NotFoundError):
    """OAuth provider not found error (HTTP 404)."""

    code: ClassVar[ErrorCode] = ErrorCode.OAUTH_PROVIDER_UNKNOWN
    title: ClassVar[str] = "OAuth provider not found"
    description: ClassVar[str] = "OAuth provider not found"

    def __init__(self, provider: str):
        super().__init__("oauth_provider", resource_id=provider, code=self.code)


class DatabaseError(APIError):
    """
    Database error (HTTP 500/409/422).

    Used for database-related errors like constraint violations,
    connection issues, or query failures.

    Usage:
        raise DatabaseError("Duplicate email", table="users", sql_error="...")
    """

    code: ClassVar[ErrorCode] = ErrorCode.DB_QUERY_ERROR
    title: ClassVar[str] = "Database query error"
    description: ClassVar[str] = "Database query error"

    def __init__(
        self,
        message: Optional[str] = None,
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


class DatabaseConnectionError(DatabaseError):
    """Database connection error (HTTP 500)."""

    code: ClassVar[ErrorCode] = ErrorCode.DB_CONNECTION_ERROR
    title: ClassVar[str] = "Database connection error"
    description: ClassVar[str] = "Database connection error"

    def __init__(self, message: Optional[str] = None, sql_error: Optional[str] = None):
        super().__init__(message or self.title, code=self.code, sql_error=sql_error)


class DatabaseQueryError(DatabaseError):
    """Database query error (HTTP 500)."""

    code: ClassVar[ErrorCode] = ErrorCode.DB_QUERY_ERROR
    title: ClassVar[str] = "Database query error"
    description: ClassVar[str] = "Database query error"

    def __init__(self, message: Optional[str] = None, sql_error: Optional[str] = None):
        super().__init__(message or self.title, code=self.code, sql_error=sql_error)


class DatabaseTransactionError(DatabaseError):
    """Database transaction error (HTTP 500)."""

    code: ClassVar[ErrorCode] = ErrorCode.DB_TRANSACTION_ERROR
    title: ClassVar[str] = "Database transaction error"
    description: ClassVar[str] = "Database transaction error"

    def __init__(self, message: Optional[str] = None, sql_error: Optional[str] = None):
        super().__init__(message or self.title, code=self.code, sql_error=sql_error)


class DatabaseConstraintViolationError(DatabaseError):
    """Database constraint violation (HTTP 409)."""

    code: ClassVar[ErrorCode] = ErrorCode.DB_CONSTRAINT_VIOLATION
    title: ClassVar[str] = "Database constraint violation"
    description: ClassVar[str] = "Database constraint violation"

    def __init__(
        self,
        message: Optional[str] = None,
        sql_error: Optional[str] = None,
        table: Optional[str] = None,
    ):
        super().__init__(
            message or self.title,
            code=self.code,
            sql_error=sql_error,
            table=table,
        )


class DatabaseDuplicateEntryError(DatabaseError):
    """Database duplicate entry (HTTP 409)."""

    code: ClassVar[ErrorCode] = ErrorCode.DB_DUPLICATE_ENTRY
    title: ClassVar[str] = "Database duplicate entry"
    description: ClassVar[str] = "Database duplicate entry"

    def __init__(
        self,
        message: Optional[str] = None,
        sql_error: Optional[str] = None,
        table: Optional[str] = None,
    ):
        super().__init__(
            message or self.title,
            code=self.code,
            sql_error=sql_error,
            table=table,
        )


class DatabaseInvalidReferenceError(DatabaseError):
    """Database invalid reference (HTTP 422)."""

    code: ClassVar[ErrorCode] = ErrorCode.DB_INVALID_REFERENCE
    title: ClassVar[str] = "Database invalid reference"
    description: ClassVar[str] = "Database invalid reference"

    def __init__(
        self,
        message: Optional[str] = None,
        sql_error: Optional[str] = None,
        table: Optional[str] = None,
    ):
        super().__init__(
            message or self.title,
            code=self.code,
            sql_error=sql_error,
            table=table,
        )


class DatabaseMissingRequiredError(DatabaseError):
    """Database missing required field (HTTP 422)."""

    code: ClassVar[ErrorCode] = ErrorCode.DB_MISSING_REQUIRED
    title: ClassVar[str] = "Database missing required field"
    description: ClassVar[str] = "Database missing required field"

    def __init__(
        self,
        message: Optional[str] = None,
        sql_error: Optional[str] = None,
        table: Optional[str] = None,
    ):
        super().__init__(
            message or self.title,
            code=self.code,
            sql_error=sql_error,
            table=table,
        )


class BusinessLogicError(APIError):
    """
    Business logic error (HTTP 422).

    Used for business rule violations and domain-specific errors.
    Can include rule name and context information.

    Usage:
        raise BusinessLogicError("Insufficient balance", rule="min_balance", context={"current": 50})
    """

    code: ClassVar[ErrorCode] = ErrorCode.BUSINESS_RULE_VIOLATION
    status_code: ClassVar[int] = 422
    title: ClassVar[str] = "Business rule violation"
    description: ClassVar[str] = "Business rule violation"

    def __init__(
        self,
        message: Optional[str] = None,
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


class InsufficientBalanceError(BusinessLogicError):
    """Insufficient balance error (HTTP 422)."""

    code: ClassVar[ErrorCode] = ErrorCode.INSUFFICIENT_BALANCE
    title: ClassVar[str] = "Insufficient balance"
    description: ClassVar[str] = "Insufficient balance"

    def __init__(self, message: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        super().__init__(message or self.title, code=self.code, context=context)


class OperationNotAllowedError(BusinessLogicError):
    """Operation not allowed error (HTTP 422)."""

    code: ClassVar[ErrorCode] = ErrorCode.OPERATION_NOT_ALLOWED
    title: ClassVar[str] = "Operation not allowed"
    description: ClassVar[str] = "Operation not allowed"

    def __init__(self, message: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        super().__init__(message or self.title, code=self.code, context=context)
