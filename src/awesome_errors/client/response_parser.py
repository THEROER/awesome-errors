from typing import Dict, Any, Union, Optional
import json
from .exceptions import BackendError
from ..core.error_response import ErrorResponse, ErrorDetail


class ErrorDetailMixin:
    @property
    def field(self):
        return self.details.get("field")

    @property
    def field_errors(self):
        return self.details.get("field_errors")

    @property
    def table(self):
        return self.details.get("table")

    @property
    def constraint(self):
        return self.details.get("constraint")

    @property
    def duplicate_value(self):
        return self.details.get("duplicate_value")


class ErrorResponseParser:
    """Parser for backend error responses."""

    @classmethod
    def parse_response(
        cls,
        response_body: Union[str, bytes, Dict[str, Any]],
        status_code: int,
        headers: Optional[Dict[str, str]] = None,
    ) -> BackendError:
        """
        Parse error response from backend.

        Args:
            response_body: Response body (JSON string, bytes, or dict)
            status_code: HTTP status code
            headers: Response headers

        Returns:
            BackendError instance

        Raises:
            ValueError: If response cannot be parsed
        """
        try:
            # Parse response body
            if isinstance(response_body, (str, bytes)):
                data = json.loads(response_body)
            else:
                data = response_body

            # Validate and parse error response
            error_response = ErrorResponse(**data)

            # Create BackendError
            return BackendError(
                error=error_response.error,
                status_code=status_code,
                response_headers=headers,
            )

        except (json.JSONDecodeError, ValueError) as e:
            # Fallback for non-standard error responses
            return cls._create_fallback_error(response_body, status_code, headers, e)

    @classmethod
    def _create_fallback_error(
        cls,
        response_body: Any,
        status_code: int,
        headers: Optional[Dict[str, str]],
        parse_error: Exception,
    ) -> BackendError:
        """Create fallback error when parsing fails."""
        # Try to extract message from response
        message = "Unknown error"
        details = {
            "parse_error": str(parse_error),
            "response_type": type(response_body).__name__,
        }

        if isinstance(response_body, dict):
            # Try common error fields
            message = (
                response_body.get("message")
                or response_body.get("error")
                or response_body.get("detail")
                or str(response_body)
            )
            details["raw_response"] = response_body
        elif isinstance(response_body, (str, bytes)):
            message = str(response_body)[:200]  # Limit length
            details["raw_response"] = message

        # Create error detail
        error_detail = ErrorDetail(
            code="UNKNOWN_ERROR",
            message=message,
            details=details,
            timestamp=None,  # Will use default
            request_id=headers.get("X-Request-ID", "unknown") if headers else "unknown",
        )

        return BackendError(
            error=error_detail, status_code=status_code, response_headers=headers
        )

    @classmethod
    def is_error_response(cls, response_data: Dict[str, Any]) -> bool:
        """
        Check if response data is an error response.

        Args:
            response_data: Response data as dictionary

        Returns:
            True if this is an error response
        """
        return "error" in response_data and isinstance(response_data.get("error"), dict)
