import functools
from typing import Any, Callable, Dict, List, Optional, Set, cast
from ..analysis.error_analyzer import ErrorAnalyzer
from ..core.error_codes import ErrorCode, ERROR_HTTP_STATUS_MAP


def analyze_errors(include_dependencies: bool = True):
    """
    Decorator to analyze all possible errors in a function.

    Args:
        include_dependencies: Whether to analyze called functions too

    Returns:
        Decorated function with error analysis attached
    """

    def decorator(func: Callable) -> Callable:
        # Perform analysis
        analyzer = ErrorAnalyzer(func)
        analysis = analyzer.analyze()

        # Attach analysis to function
        setattr(func, "_error_analysis", analysis)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        # Copy analysis to wrapper
        setattr(wrapper, "_error_analysis", analysis)

        return wrapper

    return decorator


def openapi_errors(
    additional_errors: Optional[List[str]] = None,
    exclude_errors: Optional[List[str]] = None,
    custom_descriptions: Optional[Dict[str, str]] = None,
):
    """
    Decorator to generate OpenAPI error responses for a function.

    Args:
        additional_errors: Additional error codes to include
        exclude_errors: Error codes to exclude from analysis
        custom_descriptions: Custom descriptions for error codes

    Returns:
        Decorated function with OpenAPI responses attached
    """

    def decorator(func: Callable) -> Callable:
        # Analyze function for errors
        analyzer = ErrorAnalyzer(func)
        analysis = analyzer.analyze()

        # Get all error codes
        error_codes = set(analysis["error_codes"])

        # Add additional errors
        if additional_errors:
            error_codes.update(additional_errors)

        # Remove excluded errors
        if exclude_errors:
            error_codes -= set(exclude_errors)

        # Generate OpenAPI responses
        openapi_responses = _generate_openapi_responses(
            error_codes, custom_descriptions or {}
        )

        # Attach to function
        setattr(func, "_openapi_error_responses", openapi_responses)
        setattr(func, "_error_analysis", analysis)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        # Copy to wrapper
        setattr(wrapper, "_openapi_error_responses", openapi_responses)
        setattr(wrapper, "_error_analysis", analysis)

        return wrapper

    return decorator


def _generate_openapi_responses(
    error_codes: Set[str], custom_descriptions: Dict[str, str]
) -> Dict[str, Dict[str, Any]]:
    """Generate OpenAPI response schemas for error codes."""
    responses = {}

    # Group errors by HTTP status code
    status_groups: Dict[int, List[str]] = {}

    for error_code in error_codes:
        try:
            error_enum = ErrorCode(error_code)
            status_code = ERROR_HTTP_STATUS_MAP.get(error_enum, 500)
        except ValueError:
            # Unknown error code
            status_code = 500

        if status_code not in status_groups:
            status_groups[status_code] = []
        status_groups[status_code].append(error_code)

    # Generate response for each status code
    for status_code, codes in status_groups.items():
        response_schema = {
            "description": _get_status_description(status_code, codes),
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "error": {
                                "type": "object",
                                "properties": {
                                    "code": {
                                        "type": "string",
                                        "enum": codes,
                                        "description": "Error code",
                                    },
                                    "message": {
                                        "type": "string",
                                        "description": "Error message",
                                    },
                                    "details": {
                                        "type": "object",
                                        "description": "Additional error details",
                                    },
                                    "timestamp": {
                                        "type": "string",
                                        "format": "date-time",
                                        "description": "Error timestamp",
                                    },
                                    "request_id": {
                                        "type": "string",
                                        "description": "Request ID for tracing",
                                    },
                                },
                                "required": [
                                    "code",
                                    "message",
                                    "timestamp",
                                    "request_id",
                                ],
                            }
                        },
                        "required": ["error"],
                    },
                    "examples": _generate_examples(codes, custom_descriptions),
                }
            },
        }

        responses[str(status_code)] = response_schema

    return responses


def _get_status_description(status_code: int, error_codes: List[str]) -> str:
    """Get description for HTTP status code."""
    status_descriptions = {
        400: "Bad Request - Validation or input errors",
        401: "Unauthorized - Authentication required",
        403: "Forbidden - Insufficient permissions",
        404: "Not Found - Resource not found",
        409: "Conflict - Resource conflict (e.g., duplicate entry)",
        422: "Unprocessable Entity - Business logic errors",
        500: "Internal Server Error - Server errors",
    }

    base_desc = status_descriptions.get(status_code, f"HTTP {status_code}")
    codes_str = ", ".join(error_codes)

    return f"{base_desc}. Possible error codes: {codes_str}"


def _generate_examples(
    error_codes: List[str], custom_descriptions: Dict[str, str]
) -> Dict[str, Dict[str, Any]]:
    """Generate example responses for error codes."""
    examples = {}

    for error_code in error_codes:
        example_name = error_code.lower().replace("_", "-")
        description = custom_descriptions.get(
            error_code, _get_default_error_description(error_code)
        )

        examples[example_name] = {
            "summary": f"{error_code} example",
            "description": description,
            "value": {
                "error": {
                    "code": error_code,
                    "message": description,
                    "details": _get_example_details(error_code),
                    "timestamp": "2024-01-08T12:00:00Z",
                    "request_id": "req_abc123",
                }
            },
        }

    return examples


def _get_default_error_description(error_code: str) -> str:
    """Get default description for error code."""
    descriptions = {
        "VALIDATION_FAILED": "Request validation failed",
        "USER_NOT_FOUND": "User not found",
        "AUTH_REQUIRED": "Authentication required",
        "AUTH_PERMISSION_DENIED": "Permission denied",
        "DB_DUPLICATE_ENTRY": "Duplicate entry in database",
        "BUSINESS_RULE_VIOLATION": "Business rule violated",
    }

    return descriptions.get(error_code, f"Error: {error_code}")


def _get_example_details(error_code: str) -> Dict[str, Any]:
    """Get example details for error code."""
    example_details = {
        "VALIDATION_FAILED": {
            "field_errors": [
                {
                    "field": "email",
                    "message": "invalid email format",
                    "input": "not-an-email",
                }
            ]
        },
        "USER_NOT_FOUND": {"resource": "user", "resource_id": 123},
        "DB_DUPLICATE_ENTRY": {
            "table": "users",
            "field": "email",
            "duplicate_value": "user@example.com",
        },
        "AUTH_PERMISSION_DENIED": {"required_permission": "admin.users.delete"},
    }

    return cast(Dict[str, Any], example_details.get(error_code, {}))
