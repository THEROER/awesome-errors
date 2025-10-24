"""
WebSocket exceptions extending awesome-errors for JSON-RPC 2.0 compatibility

This module provides WebSocket-specific error classes that integrate with
the existing awesome-errors system while adding JSON-RPC 2.0 support.
"""

from typing import Optional, Dict, Any
from awesome_errors.core.exceptions import AppError
from awesome_errors.core.error_codes import ErrorCode


class JSONRPCErrorCode:
    """Standard JSON-RPC 2.0 error codes"""

    # Standard codes defined by JSON-RPC 2.0 specification
    PARSE_ERROR = -32700  # Invalid JSON was received
    INVALID_REQUEST = -32600  # The JSON sent is not a valid Request object
    METHOD_NOT_FOUND = -32601  # The method does not exist / is not available
    INVALID_PARAMS = -32602  # Invalid method parameter(s)
    INTERNAL_ERROR = -32603  # Internal JSON-RPC error

    # Server error codes (reserved range: -32000 to -32099)
    # Custom codes for WebSocket-specific errors
    AUTH_REQUIRED = -32000  # Authentication required
    TOKEN_EXPIRED = -32001  # Authentication token expired
    RATE_LIMITED = -32002  # Rate limit exceeded
    SUBSCRIPTION_DENIED = -32003  # Subscription permission denied
    CONNECTION_LIMIT = -32004  # Too many connections


class WebSocketError(AppError):
    """
    WebSocket error extending AppError with JSON-RPC 2.0 compatibility

    This class bridges awesome-errors with WebSocket/JSON-RPC requirements,
    providing automatic error code mapping and connection management.
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        ws_error_code: Optional[int] = None,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        close_connection: bool = False,
    ):
        """
        Initialize WebSocket error

        Args:
            code: ErrorCode from awesome-errors
            message: Human-readable error message
            ws_error_code: JSON-RPC error code (auto-mapped if not provided)
            request_id: JSON-RPC request ID for correlation
            details: Additional error details
            close_connection: Whether to close WebSocket connection after error
        """
        super().__init__(code, message, details)

        # WebSocket specific fields
        self.ws_error_code = ws_error_code or self._map_to_jsonrpc_code(code)
        self.request_id = request_id
        self.close_connection = close_connection

    def _map_to_jsonrpc_code(self, error_code: ErrorCode) -> int:
        """
        Map ErrorCode to JSON-RPC error code

        Provides sensible defaults for mapping awesome-errors codes
        to JSON-RPC 2.0 standard codes.
        """
        mapping = {
            # Authentication errors
            ErrorCode.AUTH_REQUIRED: JSONRPCErrorCode.AUTH_REQUIRED,
            ErrorCode.AUTH_PERMISSION_DENIED: JSONRPCErrorCode.AUTH_REQUIRED,
            ErrorCode.AUTH_TOKEN_EXPIRED: JSONRPCErrorCode.TOKEN_EXPIRED,
            ErrorCode.AUTH_TOKEN_INVALID: JSONRPCErrorCode.AUTH_REQUIRED,
            # Validation errors
            ErrorCode.VALIDATION_FAILED: JSONRPCErrorCode.INVALID_PARAMS,
            ErrorCode.INVALID_INPUT: JSONRPCErrorCode.INVALID_PARAMS,
            ErrorCode.MISSING_REQUIRED_FIELD: JSONRPCErrorCode.INVALID_PARAMS,
            # Resource errors
            ErrorCode.RESOURCE_NOT_FOUND: JSONRPCErrorCode.METHOD_NOT_FOUND,
            ErrorCode.RESOURCE_ALREADY_EXISTS: JSONRPCErrorCode.INVALID_REQUEST,
            # Rate limiting
            ErrorCode.RATE_LIMIT_EXCEEDED: JSONRPCErrorCode.RATE_LIMITED,
            # Database errors (all map to internal error)
            ErrorCode.DB_CONNECTION_ERROR: JSONRPCErrorCode.INTERNAL_ERROR,
            ErrorCode.DB_QUERY_ERROR: JSONRPCErrorCode.INTERNAL_ERROR,
            ErrorCode.DB_CONSTRAINT_VIOLATION: JSONRPCErrorCode.INVALID_PARAMS,
            # Business logic
            ErrorCode.BUSINESS_RULE_VIOLATION: JSONRPCErrorCode.INVALID_REQUEST,
            # Generic errors
            ErrorCode.INTERNAL_ERROR: JSONRPCErrorCode.INTERNAL_ERROR,
            ErrorCode.SERVICE_UNAVAILABLE: JSONRPCErrorCode.INTERNAL_ERROR,
        }

        return mapping.get(error_code, JSONRPCErrorCode.INTERNAL_ERROR)

    def to_jsonrpc_error(self) -> Dict[str, Any]:
        """
        Convert to JSON-RPC 2.0 error format

        Returns a dictionary conforming to JSON-RPC 2.0 error object specification.
        """
        error_data = None

        # Build error data if we have details or metadata
        if self.details or self.request_id:
            error_data = {}

            if self.details:
                error_data["details"] = self.details

            # Include original error code for clients that understand it
            error_data["error_code"] = self.code.value

            # Include timestamp for debugging
            error_data["timestamp"] = self.timestamp.isoformat() + "Z"

            # Include request ID if available
            if self.request_id:
                error_data["request_id"] = self.request_id

        return {
            "jsonrpc": "2.0",
            "error": {
                "code": self.ws_error_code,
                "message": self.message,
                "data": error_data,
            },
            "id": self.request_id,
        }

    @classmethod
    def from_app_error(
        cls,
        error: AppError,
        request_id: Optional[str] = None,
        close_connection: bool = False,
    ) -> "WebSocketError":
        """
        Create WebSocketError from existing AppError

        This allows seamless conversion of any AppError to WebSocket format.
        """
        return cls(
            code=error.code,
            message=error.message,
            details=error.details,
            request_id=request_id,
            close_connection=close_connection,
        )


class WebSocketAuthError(WebSocketError):
    """Authentication error - always closes connection"""

    def __init__(
        self,
        message: str = "Authentication required",
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            code=ErrorCode.AUTH_REQUIRED,
            message=message,
            ws_error_code=JSONRPCErrorCode.AUTH_REQUIRED,
            request_id=request_id,
            details=details,
            close_connection=True,  # Always close on auth failure
        )


class WebSocketTokenExpiredError(WebSocketError):
    """Token expired error - requires re-authentication"""

    def __init__(
        self, request_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code=ErrorCode.AUTH_TOKEN_EXPIRED,
            message="Token expired",
            ws_error_code=JSONRPCErrorCode.TOKEN_EXPIRED,
            request_id=request_id,
            details=details,
            close_connection=True,  # Force reconnection with new token
        )


class WebSocketRateLimitError(WebSocketError):
    """Rate limit exceeded error"""

    def __init__(
        self,
        retry_after: int,
        request_id: Optional[str] = None,
        limit: Optional[int] = None,
        window: Optional[int] = None,
    ):
        details = {"retry_after": retry_after, "limit": limit, "window": window}

        super().__init__(
            code=ErrorCode.RATE_LIMIT_EXCEEDED,
            message=f"Rate limit exceeded. Retry after {retry_after} seconds",
            ws_error_code=JSONRPCErrorCode.RATE_LIMITED,
            details={k: v for k, v in details.items() if v is not None},
            request_id=request_id,
            close_connection=False,  # Don't close, client can retry
        )


class WebSocketValidationError(WebSocketError):
    """Validation error with field details"""

    def __init__(
        self,
        message: str,
        validation_errors: Optional[list] = None,
        request_id: Optional[str] = None,
    ):
        details = {}
        if validation_errors:
            details["validation_errors"] = validation_errors

        super().__init__(
            code=ErrorCode.VALIDATION_FAILED,
            message=message,
            ws_error_code=JSONRPCErrorCode.INVALID_PARAMS,
            details=details if details else None,
            request_id=request_id,
            close_connection=False,
        )


class WebSocketMethodNotFoundError(WebSocketError):
    """Method not found error"""

    def __init__(
        self,
        method: str,
        request_id: Optional[str] = None,
        available_methods: Optional[list] = None,
    ):
        details = {"method": method}
        if available_methods:
            details["available_methods"] = available_methods

        super().__init__(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message=f"Method not found: {method}",
            ws_error_code=JSONRPCErrorCode.METHOD_NOT_FOUND,
            details=details,
            request_id=request_id,
            close_connection=False,
        )


class WebSocketInternalError(WebSocketError):
    """Internal server error"""

    def __init__(
        self,
        message: str = "Internal server error",
        request_id: Optional[str] = None,
        original_error: Optional[str] = None,
    ):
        details = {}
        if original_error:
            details["original_error"] = str(original_error)

        super().__init__(
            code=ErrorCode.INTERNAL_ERROR,
            message=message,
            ws_error_code=JSONRPCErrorCode.INTERNAL_ERROR,
            details=details if details else None,
            request_id=request_id,
            close_connection=False,
        )
