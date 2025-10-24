import pytest
from datetime import datetime
from awesome_errors import (
    AppError,
    ValidationError,
    AuthError,
    NotFoundError,
    DatabaseError,
    BusinessLogicError,
    ErrorCode,
)


class TestCoreExceptions:
    """Test core exception classes."""

    def test_app_error_creation(self):
        """Test basic AppError creation."""
        error = AppError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Test error",
            details={"key": "value"},
        )

        assert error.code == ErrorCode.INTERNAL_ERROR
        assert error.message == "Test error"
        assert error.details["key"] == "value"
        assert isinstance(error.timestamp, datetime)
        assert error.request_id is not None
        assert error.status_code == 500

    def test_app_error_string_code(self):
        """Test AppError with string error code."""
        error = AppError(code="CUSTOM_ERROR", message="Custom error message")

        assert error.code == ErrorCode("CUSTOM_ERROR")
        assert error.message == "Custom error message"

    def test_app_error_to_dict(self):
        """Test AppError to_dict conversion."""
        error = AppError(
            code=ErrorCode.VALIDATION_FAILED,
            message="Validation error",
            details={"field": "email"},
        )

        error_dict = error.to_dict()

        assert "error" in error_dict
        error_data = error_dict["error"]

        assert error_data["code"] == "VALIDATION_FAILED"
        assert error_data["message"] == "Validation error"
        assert error_data["details"]["field"] == "email"
        assert "timestamp" in error_data
        assert "request_id" in error_data

    def test_validation_error_creation(self):
        """Test ValidationError creation."""
        error = ValidationError(
            message="Invalid email",
            field="email",
            value="invalid-email",
            code=ErrorCode.INVALID_FORMAT,
        )

        assert error.code == ErrorCode.INVALID_FORMAT
        assert error.message == "Invalid email"
        assert error.details["field"] == "email"
        assert error.details["value"] == "invalid-email"
        assert error.status_code == 400

    def test_validation_error_defaults(self):
        """Test ValidationError with defaults."""
        error = ValidationError("Test validation error")

        assert error.code == ErrorCode.VALIDATION_FAILED
        assert error.status_code == 400

    def test_auth_error_creation(self):
        """Test AuthError creation."""
        error = AuthError(
            message="Permission denied",
            code=ErrorCode.AUTH_PERMISSION_DENIED,
            required_permission="admin.users.delete",
        )

        assert error.code == ErrorCode.AUTH_PERMISSION_DENIED
        assert error.message == "Permission denied"
        assert error.details["required_permission"] == "admin.users.delete"

    def test_auth_error_defaults(self):
        """Test AuthError with defaults."""
        error = AuthError("Authentication required")

        assert error.code == ErrorCode.AUTH_REQUIRED

    def test_auth_error_custom_status(self):
        """AuthError allows custom codes and status codes."""

        error = AuthError(
            message="Session expired",
            code=ErrorCode("SESSION_EXPIRED"),
            status_code=401,
        )

        assert error.code == ErrorCode("SESSION_EXPIRED")
        assert error.status_code == 401

    def test_not_found_error_creation(self):
        """Test NotFoundError creation."""
        error = NotFoundError(
            resource="user", resource_id=123, code=ErrorCode.USER_NOT_FOUND
        )

        assert error.code == ErrorCode.USER_NOT_FOUND
        assert "user not found with id: 123" in error.message.lower()
        assert error.details["resource"] == "user"
        assert error.details["resource_id"] == 123
        assert error.status_code == 404

    def test_not_found_error_without_id(self):
        """Test NotFoundError without resource ID."""
        error = NotFoundError("user")

        assert error.details["resource"] == "user"
        assert "resource_id" not in error.details
        assert "user not found" in error.message.lower()

    def test_database_error_creation(self):
        """Test DatabaseError creation."""
        error = DatabaseError(
            message="Query failed",
            code=ErrorCode.DB_QUERY_ERROR,
            sql_error="SELECT * FROM invalid_table",
            table="users",
        )

        assert error.code == ErrorCode.DB_QUERY_ERROR
        assert error.message == "Query failed"
        assert error.details["sql_error"] == "SELECT * FROM invalid_table"
        assert error.details["table"] == "users"

    def test_database_error_defaults(self):
        """Test DatabaseError with defaults."""
        error = DatabaseError("Database error")

        assert error.code == ErrorCode.DB_QUERY_ERROR

    def test_business_logic_error_creation(self):
        """Test BusinessLogicError creation."""
        error = BusinessLogicError(
            message="Insufficient balance",
            code=ErrorCode.INSUFFICIENT_BALANCE,
            rule="minimum_balance",
            context={"current": 100, "required": 500},
        )

        assert error.code == ErrorCode.INSUFFICIENT_BALANCE
        assert error.message == "Insufficient balance"
        assert error.details["rule"] == "minimum_balance"
        assert error.details["context"]["current"] == 100
        assert error.status_code == 422

    def test_business_logic_error_defaults(self):
        """Test BusinessLogicError with defaults."""
        error = BusinessLogicError("Business rule violated")

        assert error.code == ErrorCode.BUSINESS_RULE_VIOLATION
        assert error.status_code == 422

    def test_custom_status_code(self):
        """Test AppError with custom status code."""
        error = AppError(
            code=ErrorCode.VALIDATION_FAILED,
            message="Custom error",
            status_code=418,  # I'm a teapot
        )

        assert error.status_code == 418

    def test_error_inheritance(self):
        """Test that all errors inherit from AppError."""
        validation_error = ValidationError("Test")
        auth_error = AuthError("Test")
        not_found_error = NotFoundError("test")
        database_error = DatabaseError("Test")
        business_error = BusinessLogicError("Test")

        assert isinstance(validation_error, AppError)
        assert isinstance(auth_error, AppError)
        assert isinstance(not_found_error, AppError)
        assert isinstance(database_error, AppError)
        assert isinstance(business_error, AppError)

    def test_error_str_representation(self):
        """Test string representation of errors."""
        error = AppError(code=ErrorCode.VALIDATION_FAILED, message="Test error message")

        assert str(error) == "Test error message"

    def test_timestamp_format_in_dict(self):
        """Test timestamp format in to_dict output."""
        error = AppError(code=ErrorCode.INTERNAL_ERROR, message="Test")

        error_dict = error.to_dict()
        timestamp_str = error_dict["error"]["timestamp"]

        # Should be ISO format with Z suffix
        assert timestamp_str.endswith("Z")
        assert "T" in timestamp_str

    def test_unique_request_ids(self):
        """Test that request IDs are unique."""
        error1 = AppError(ErrorCode.INTERNAL_ERROR, "Error 1")
        error2 = AppError(ErrorCode.INTERNAL_ERROR, "Error 2")

        assert error1.request_id != error2.request_id

    def test_error_details_immutability(self):
        """Test that error details can be safely modified."""
        error = AppError(
            code=ErrorCode.VALIDATION_FAILED,
            message="Test",
            details={"original": "value"},
        )

        # Modifying details after creation should work
        error.details["new_key"] = "new_value"

        assert error.details["original"] == "value"
        assert error.details["new_key"] == "new_value"

    def test_empty_details(self):
        """Test error creation with empty details."""
        error = AppError(code=ErrorCode.INTERNAL_ERROR, message="Test")

        assert error.details == {}
        assert isinstance(error.details, dict)

    def test_none_details(self):
        """Test error creation with None details."""
        error = AppError(code=ErrorCode.INTERNAL_ERROR, message="Test", details=None)

        assert error.details == {}
        assert isinstance(error.details, dict)


if __name__ == "__main__":
    pytest.main([__file__])
