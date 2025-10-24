import pytest
from unittest.mock import Mock
from sqlalchemy.exc import IntegrityError, DataError, OperationalError
from pydantic import ValidationError as PydanticValidationError

from awesome_errors import (
    SQLErrorConverter,
    PythonErrorConverter,
    PydanticErrorConverter,
    UniversalErrorConverter,
    ErrorCode,
    DatabaseError,
    ValidationError,
    NotFoundError,
)


class TestSQLErrorConverter:
    """Test SQL error converter."""

    def test_duplicate_key_error(self):
        """Test conversion of duplicate key errors."""
        # Mock PostgreSQL duplicate key error
        orig_error = Mock()
        orig_error.__str__ = (
            lambda self: 'duplicate key value violates unique constraint "users_email_unique"'
        )

        sqlalchemy_error = IntegrityError("statement", "params", orig_error)

        result = SQLErrorConverter.convert(sqlalchemy_error)

        assert isinstance(result, DatabaseError)
        assert result.code == ErrorCode.DB_DUPLICATE_ENTRY
        assert "already exists" in result.message

    def test_foreign_key_error(self):
        """Test conversion of foreign key constraint errors."""
        orig_error = Mock()
        orig_error.__str__ = (
            lambda self: 'violates foreign key constraint "fk_user_role"'
        )

        sqlalchemy_error = IntegrityError("statement", "params", orig_error)

        result = SQLErrorConverter.convert(sqlalchemy_error)

        assert isinstance(result, DatabaseError)
        assert result.code == ErrorCode.DB_INVALID_REFERENCE
        assert "Invalid reference" in result.message

    def test_not_null_constraint_error(self):
        """Test conversion of not-null constraint errors."""
        orig_error = Mock()
        orig_error.__str__ = (
            lambda self: 'null value in column "email" violates not-null constraint'
        )

        sqlalchemy_error = IntegrityError("statement", "params", orig_error)

        result = SQLErrorConverter.convert(sqlalchemy_error)

        assert isinstance(result, DatabaseError)
        assert result.code == ErrorCode.DB_MISSING_REQUIRED
        assert "Required field" in result.message

    def test_data_error_conversion(self):
        """Test conversion of data errors."""
        orig_error = Mock()
        orig_error.__str__ = lambda self: "invalid input value for enum"

        sqlalchemy_error = DataError("statement", "params", orig_error)

        result = SQLErrorConverter.convert(sqlalchemy_error)

        assert isinstance(result, DatabaseError)
        assert result.code == ErrorCode.INVALID_FORMAT

    def test_connection_error_conversion(self):
        """Test conversion of connection errors."""
        orig_error = Mock()
        orig_error.__str__ = lambda self: "connection to server failed"

        sqlalchemy_error = OperationalError("statement", "params", orig_error)

        result = SQLErrorConverter.convert(sqlalchemy_error)

        assert isinstance(result, DatabaseError)
        assert result.code == ErrorCode.DB_CONNECTION_ERROR

    def test_field_extraction(self):
        """Test extraction of field names from SQL errors."""
        orig_error = Mock()
        orig_error.__str__ = (
            lambda self: 'duplicate key value violates unique constraint "users_email_unique" DETAIL: Key (email)=(test@example.com) already exists.'
        )

        sqlalchemy_error = IntegrityError("statement", "params", orig_error)

        result = SQLErrorConverter.convert(sqlalchemy_error)

        # Should extract field and duplicate value details
        assert result.details.get("duplicate_value") == "test@example.com"
        assert "email" in result.details.get("sql_error", "")


class TestPythonErrorConverter:
    """Test Python error converter."""

    def test_value_error_conversion(self):
        """Test conversion of ValueError."""
        error = ValueError("Invalid value provided")

        result = PythonErrorConverter.convert(error)

        assert isinstance(result, ValidationError)
        assert result.code == ErrorCode.INVALID_INPUT
        assert "Invalid value provided" in result.message

    def test_key_error_conversion(self):
        """Test conversion of KeyError."""
        error = KeyError("missing_key")

        result = PythonErrorConverter.convert(error)

        assert isinstance(result, NotFoundError)
        assert result.code == ErrorCode.RESOURCE_NOT_FOUND

    def test_file_not_found_error_conversion(self):
        """Test conversion of FileNotFoundError."""
        error = FileNotFoundError("No such file: test.txt")
        error.filename = "test.txt"

        result = PythonErrorConverter.convert(error)

        assert isinstance(result, NotFoundError)
        assert result.code == ErrorCode.RESOURCE_NOT_FOUND
        assert "test.txt" in str(result.details.get("resource_id", ""))

    def test_permission_error_conversion(self):
        """Test conversion of PermissionError."""
        error = PermissionError("Access denied")

        result = PythonErrorConverter.convert(error)

        assert result.code == ErrorCode.AUTH_PERMISSION_DENIED

    def test_unknown_error_conversion(self):
        """Test conversion of unknown error types."""

        class CustomError(Exception):
            pass

        error = CustomError("Unknown error")

        result = PythonErrorConverter.convert(error)

        assert result.code == ErrorCode.INTERNAL_ERROR
        assert "CustomError" in result.details["error_type"]


class TestPydanticErrorConverter:
    """Test Pydantic error converter."""

    def test_single_validation_error(self):
        """Test conversion of single Pydantic validation error."""
        # Create a simple model to generate validation error
        from pydantic import BaseModel, EmailStr

        class TestModel(BaseModel):
            email: EmailStr
            age: int

        try:
            TestModel(email="invalid-email", age="not-a-number")
        except PydanticValidationError as e:
            result = PydanticErrorConverter.convert(e)

            assert isinstance(result, ValidationError)
            assert result.code == ErrorCode.VALIDATION_FAILED
            assert "field_errors" in result.details
            assert len(result.details["field_errors"]) >= 1

    def test_multiple_validation_errors(self):
        """Test conversion of multiple Pydantic validation errors."""
        from pydantic import BaseModel, field_validator, ValidationInfo

        class TestModel(BaseModel):
            name: str
            age: int
            email: str

            @field_validator("age")
            @classmethod
            def validate_age(cls, v: int, info: ValidationInfo):
                if v < 0:
                    raise ValueError("Age must be positive")
                return v

            @field_validator("name")
            @classmethod
            def validate_name(cls, v: str, info: ValidationInfo):
                if len(v) < 2:
                    raise ValueError("Name must be at least 2 characters")
                return v

        try:
            TestModel(name="", age=-5, email="invalid")
        except PydanticValidationError as e:
            result = PydanticErrorConverter.convert(e)

            assert len(result.details["field_errors"]) >= 2
            assert result.details["error_count"] >= 2

    def test_field_path_extraction(self):
        """Test extraction of nested field paths."""
        from pydantic import BaseModel

        class NestedModel(BaseModel):
            value: int

        class TestModel(BaseModel):
            nested: NestedModel

        try:
            TestModel(nested={"value": "not-a-number"})
        except PydanticValidationError as e:
            result = PydanticErrorConverter.convert(e)

            # Should have field path like "nested.value"
            field_errors = result.details["field_errors"]
            field_paths = [error["field"] for error in field_errors]

            assert any("nested" in path for path in field_paths)


class TestUniversalErrorConverter:
    """Test universal error converter."""

    def test_app_error_passthrough(self):
        """Test that AppErrors are passed through unchanged."""
        from awesome_errors import NotFoundError

        original_error = NotFoundError("user", 123)
        result = UniversalErrorConverter.convert(original_error)

        assert result is original_error

    def test_pydantic_error_conversion(self):
        """Test conversion of Pydantic errors."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            required_field: str

        try:
            TestModel()
        except PydanticValidationError as e:
            result = UniversalErrorConverter.convert(e)

            assert isinstance(result, ValidationError)
            assert result.code == ErrorCode.VALIDATION_FAILED

    def test_sqlalchemy_error_conversion(self):
        """Test conversion of SQLAlchemy errors."""
        orig_error = Mock()
        orig_error.__str__ = lambda self: "database error"

        sqlalchemy_error = IntegrityError("statement", "params", orig_error)
        result = UniversalErrorConverter.convert(sqlalchemy_error)

        assert isinstance(result, DatabaseError)

    def test_python_error_conversion(self):
        """Test conversion of standard Python errors."""
        error = ValueError("Invalid value")
        result = UniversalErrorConverter.convert(error)

        assert isinstance(result, ValidationError)
        assert result.code == ErrorCode.INVALID_INPUT

    def test_json_decode_error_handling(self):
        """Test handling of JSON decode errors."""
        import json

        try:
            json.loads("invalid json")
        except json.JSONDecodeError as e:
            result = UniversalErrorConverter.convert(e)

            assert result.code == ErrorCode.INVALID_FORMAT
            assert "JSON" in result.message

    def test_import_error_handling(self):
        """Test handling of import errors."""
        error = ImportError("No module named 'nonexistent'")
        error.name = "nonexistent"

        result = UniversalErrorConverter.convert(error)

        assert result.code == ErrorCode.INTERNAL_ERROR
        assert "Missing required module" in result.message
        assert "nonexistent" in result.details.get("module", "")

    def test_unknown_error_debug_mode(self):
        """Test unknown error handling in debug mode."""

        class CustomException(Exception):
            def __init__(self, message):
                super().__init__(message)
                self.custom_attr = "test_value"

        error = CustomException("Custom error message")
        result = UniversalErrorConverter.convert(error, debug=True)

        assert result.code == ErrorCode.INTERNAL_ERROR
        assert "CustomException" in result.message
        assert "error_str" in result.details
        assert "error_attrs" in result.details

    def test_unknown_error_production_mode(self):
        """Test unknown error handling in production mode."""

        class CustomException(Exception):
            pass

        error = CustomException("Custom error")
        result = UniversalErrorConverter.convert(error, debug=False)

        assert result.code == ErrorCode.INTERNAL_ERROR
        assert "error_str" not in result.details
        assert "error_attrs" not in result.details


if __name__ == "__main__":
    pytest.main([__file__])
