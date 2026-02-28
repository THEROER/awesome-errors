from typing import Any, Dict, List, Mapping, Sequence
from pydantic import ValidationError as PydanticValidationError

from ..core.error_codes import ErrorCode
from ..core.exceptions import ValidationError


class PydanticErrorConverter:
    """Convert Pydantic validation errors to application errors."""

    @classmethod
    def convert(cls, error: PydanticValidationError) -> ValidationError:
        """
        Convert Pydantic ValidationError to application ValidationError.

        Args:
            error: Pydantic validation error

        Returns:
            Application ValidationError with detailed field information
        """
        errors = error.errors()

        # Extract first error for main message
        first_error: Mapping[str, Any] | None = errors[0] if errors else None
        main_field = cls._get_field_path(first_error.get("loc", [])) if first_error else ""
        main_message = first_error.get("msg", "Validation failed") if first_error else "Validation failed"

        # Build detailed error information
        field_errors = cls._build_field_errors(errors)

        # Create validation error with detailed field information
        validation_error = ValidationError(
            message=f"Validation failed for field '{main_field}': {main_message}"
            if main_field
            else main_message,
            code=ErrorCode.VALIDATION_FAILED,
        )

        # Add detailed field errors
        validation_error.details = {
            "field_errors": field_errors,
            "error_count": len(errors),
        }

        return validation_error

    @classmethod
    def _build_field_errors(
        cls, errors: Sequence[Mapping[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Build detailed field error information."""
        field_errors = []

        for error in errors:
            field_path = cls._get_field_path(error.get("loc", []))
            field_error = {
                "field": field_path,
                "message": error.get("msg", "Invalid value"),
                "type": error.get("type", "unknown"),
                "context": error.get("ctx", {}),
            }

            # Add input value if available
            if "input" in error:
                field_error["input"] = error["input"]

            field_errors.append(field_error)

        return field_errors

    @classmethod
    def _get_field_path(cls, loc: Sequence[Any]) -> str:
        """Convert location list to field path string."""
        return ".".join(str(part) for part in loc) if loc else ""
