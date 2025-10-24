from typing import Optional, Dict, Any
from ..core.error_response import ErrorDetail


class BackendError(Exception):
    """
    Client-side exception for handling backend API errors.

    This exception is raised when the client receives an error response
    from the backend API. It wraps the error details from the server
    and provides convenient properties for error handling.

    Unlike core exceptions (AppError, ValidationError, etc.), this is used
    on the client side to handle errors received from the server.

    Usage:
        try:
            response = api_client.get_user(123)
        except BackendError as e:
            if e.is_not_found_error():
                print("User not found")
            elif e.is_validation_error():
                print("Invalid input")
    """

    def __init__(
        self,
        error: ErrorDetail,
        status_code: int,
        response_headers: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize backend error.

        Args:
            error: Error detail model from server response
            status_code: HTTP status code from response
            response_headers: Response headers for additional context
        """
        self.error = error
        self.status_code = status_code
        self.response_headers = response_headers or {}

        super().__init__(error.message)

    @property
    def code(self) -> str:
        """Get error code from server response."""
        return self.error.code

    @property
    def message(self) -> str:
        """Get error message from server response."""
        return self.error.message

    @property
    def details(self) -> Dict[str, Any]:
        """Get error details from server response."""
        return self.error.details

    @property
    def request_id(self) -> str:
        """Get request ID for tracing."""
        return self.error.request_id

    @property
    def timestamp(self):
        """Get error timestamp from server."""
        return self.error.timestamp

    def is_validation_error(self) -> bool:
        """Check if this is a validation error from server."""
        return self.code in [
            "VALIDATION_FAILED",
            "INVALID_INPUT",
            "MISSING_REQUIRED_FIELD",
        ]

    def is_auth_error(self) -> bool:
        """Check if this is an authentication/authorization error from server."""
        return self.code.startswith("AUTH_")

    def is_not_found_error(self) -> bool:
        """Check if this is a not found error from server."""
        return self.code.endswith("_NOT_FOUND")

    def is_database_error(self) -> bool:
        """Check if this is a database error from server."""
        return self.code.startswith("DB_")

    def is_business_error(self) -> bool:
        """Check if this is a business logic error from server."""
        return self.code in [
            "BUSINESS_RULE_VIOLATION",
            "INSUFFICIENT_BALANCE",
            "OPERATION_NOT_ALLOWED",
        ]
