from __future__ import annotations

import json
from typing import Any, Dict, Optional, Union

from .exceptions import BackendError
from ..core.error_response import ErrorDetail, error_detail_from_mapping


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
            data = (
                json.loads(response_body)
                if isinstance(response_body, (str, bytes))
                else response_body
            )

            if not isinstance(data, dict):
                raise ValueError("Response body is not a JSON object")

            detail_payload: Optional[Dict[str, Any]] = None
            if cls.is_error_response(data):
                error_block = data.get("error", {})
                if isinstance(error_block, dict):
                    detail_payload = dict(error_block)
            elif cls.is_problem_response(data):
                detail_payload = cls._problem_detail_to_error_payload(data)

            if detail_payload is None:
                raise ValueError("Unsupported error response shape")

            request_id = detail_payload.get("request_id")
            if not request_id:
                request_id = headers.get("X-Request-ID") if headers else None
                detail_payload["request_id"] = request_id or "unknown"

            error_detail = error_detail_from_mapping(detail_payload)

            return BackendError(
                error=error_detail,
                status_code=status_code,
                response_headers=headers,
            )

        except (json.JSONDecodeError, ValueError, TypeError) as e:
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

    @classmethod
    def is_problem_response(cls, response_data: Dict[str, Any]) -> bool:
        """Check whether the payload follows RFC 7807 conventions."""

        required = {"type", "title", "status", "code"}
        return required.issubset(response_data.keys())

    @staticmethod
    def _problem_detail_to_error_payload(data: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "code": str(data.get("code", "UNKNOWN_ERROR")),
            "message": data.get("title") or data.get("detail") or "Unknown error",
            "request_id": data.get("request_id", ""),
            "timestamp": data.get("timestamp"),
            "details": dict(data.get("details") or {}),
        }

        # Carry over common meta fields into details for debugging purposes
        details = payload["details"]
        if "detail" in data and "explanation" not in details:
            details.setdefault("detail", data.get("detail"))
        if "instance" in data:
            details.setdefault("instance", data.get("instance"))
        return payload
