from enum import StrEnum
from typing import Dict


class ErrorCode(StrEnum):
    # General errors
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"

    # Validation errors (400)
    VALIDATION_FAILED = "VALIDATION_FAILED"
    INVALID_INPUT = "INVALID_INPUT"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    INVALID_FORMAT = "INVALID_FORMAT"

    # Authentication errors (401)
    AUTH_REQUIRED = "AUTH_REQUIRED"
    AUTH_INVALID_TOKEN = "AUTH_INVALID_TOKEN"
    AUTH_TOKEN_EXPIRED = "AUTH_TOKEN_EXPIRED"
    REFRESH_TOKEN_REUSE = "REFRESH_TOKEN_REUSE"
    SESSION_EXPIRED = "SESSION_EXPIRED"

    # Authorization errors (403)
    AUTH_PERMISSION_DENIED = "AUTH_PERMISSION_DENIED"
    AUTH_INSUFFICIENT_PRIVILEGES = "AUTH_INSUFFICIENT_PRIVILEGES"

    # Not found errors (404)
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    USER_NOT_FOUND = "USER_NOT_FOUND"
    ENTITY_NOT_FOUND = "ENTITY_NOT_FOUND"
    OAUTH_PROVIDER_UNKNOWN = "OAUTH_PROVIDER_UNKNOWN"

    # Database errors (500)
    DB_CONNECTION_ERROR = "DB_CONNECTION_ERROR"
    DB_QUERY_ERROR = "DB_QUERY_ERROR"
    DB_TRANSACTION_ERROR = "DB_TRANSACTION_ERROR"
    DB_CONSTRAINT_VIOLATION = "DB_CONSTRAINT_VIOLATION"
    DB_DUPLICATE_ENTRY = "DB_DUPLICATE_ENTRY"
    DB_INVALID_REFERENCE = "DB_INVALID_REFERENCE"
    DB_MISSING_REQUIRED = "DB_MISSING_REQUIRED"

    # Business logic errors
    BUSINESS_RULE_VIOLATION = "BUSINESS_RULE_VIOLATION"
    INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"
    OPERATION_NOT_ALLOWED = "OPERATION_NOT_ALLOWED"

    @classmethod
    def _missing_(cls, value):
        """Create new ErrorCode for unknown values."""
        if isinstance(value, str):
            # Create a pseudo member for custom values
            pseudo_member = str.__new__(cls, value)
            pseudo_member._name_ = value
            pseudo_member._value_ = value
            return pseudo_member
        return None


ERROR_HTTP_STATUS_MAP: Dict[ErrorCode, int] = {
    # 400 Bad Request
    ErrorCode.VALIDATION_FAILED: 400,
    ErrorCode.INVALID_INPUT: 400,
    ErrorCode.MISSING_REQUIRED_FIELD: 400,
    ErrorCode.INVALID_FORMAT: 400,
    # 401 Unauthorized
    ErrorCode.AUTH_REQUIRED: 401,
    ErrorCode.AUTH_INVALID_TOKEN: 401,
    ErrorCode.AUTH_TOKEN_EXPIRED: 401,
    ErrorCode.REFRESH_TOKEN_REUSE: 401,
    ErrorCode.SESSION_EXPIRED: 401,
    # 403 Forbidden
    ErrorCode.AUTH_PERMISSION_DENIED: 403,
    ErrorCode.AUTH_INSUFFICIENT_PRIVILEGES: 403,
    # 404 Not Found
    ErrorCode.RESOURCE_NOT_FOUND: 404,
    ErrorCode.USER_NOT_FOUND: 404,
    ErrorCode.ENTITY_NOT_FOUND: 404,
    ErrorCode.OAUTH_PROVIDER_UNKNOWN: 404,
    # 422 Unprocessable Entity
    ErrorCode.BUSINESS_RULE_VIOLATION: 422,
    ErrorCode.INSUFFICIENT_BALANCE: 422,
    ErrorCode.OPERATION_NOT_ALLOWED: 422,
    # 500 Internal Server Error
    ErrorCode.UNKNOWN_ERROR: 500,
    ErrorCode.INTERNAL_ERROR: 500,
    ErrorCode.DB_CONNECTION_ERROR: 500,
    ErrorCode.DB_QUERY_ERROR: 500,
    ErrorCode.DB_TRANSACTION_ERROR: 500,
    ErrorCode.DB_CONSTRAINT_VIOLATION: 409,  # Conflict
    ErrorCode.DB_DUPLICATE_ENTRY: 409,
    ErrorCode.DB_INVALID_REFERENCE: 422,
    ErrorCode.DB_MISSING_REQUIRED: 422,
}


def get_http_status(error_code: ErrorCode) -> int:
    """Get HTTP status code for an error code."""
    return ERROR_HTTP_STATUS_MAP.get(error_code, 500)
