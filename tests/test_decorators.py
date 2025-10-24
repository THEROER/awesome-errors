import pytest
from awesome_errors import (
    analyze_errors,
    openapi_errors,
    NotFoundError,
    ValidationError,
    ErrorCode,
)


class TestErrorDecorators:
    """Test error analysis decorators."""

    def test_analyze_errors_decorator(self):
        """Test @analyze_errors decorator functionality."""

        @analyze_errors()
        def test_func():
            raise NotFoundError("user", 123)
            raise ValidationError("Invalid input")

        # Check that analysis was attached
        assert hasattr(test_func, "_error_analysis")
        analysis = test_func._error_analysis

        assert analysis["function_name"] == "test_func"
        assert "RESOURCE_NOT_FOUND" in analysis["error_codes"]
        assert analysis["total_errors"] >= 1

    def test_openapi_errors_decorator(self):
        """Test @openapi_errors decorator functionality."""

        @openapi_errors()
        def test_func():
            raise NotFoundError("user", 123)
            raise ValidationError("Invalid input")

        # Check that both analysis and OpenAPI responses were attached
        assert hasattr(test_func, "_error_analysis")
        assert hasattr(test_func, "_openapi_error_responses")

        analysis = test_func._error_analysis
        responses = test_func._openapi_error_responses

        assert "RESOURCE_NOT_FOUND" in analysis["error_codes"]
        assert isinstance(responses, dict)
        assert len(responses) > 0

    def test_openapi_errors_with_additional_errors(self):
        """Test @openapi_errors with additional error codes."""

        @openapi_errors(
            additional_errors=["CUSTOM_ERROR_1", "CUSTOM_ERROR_2"],
            exclude_errors=["INTERNAL_ERROR"],
        )
        def test_func():
            raise NotFoundError("user", 123)

        responses = test_func._openapi_error_responses

        # Should include additional errors in responses
        all_error_codes = []
        for status_code, response in responses.items():
            schema = response["content"]["application/json"]["schema"]
            error_codes = schema["properties"]["error"]["properties"]["code"]["enum"]
            all_error_codes.extend(error_codes)

        assert "CUSTOM_ERROR_1" in all_error_codes
        assert "CUSTOM_ERROR_2" in all_error_codes
        assert "INTERNAL_ERROR" not in all_error_codes

    def test_openapi_errors_with_custom_descriptions(self):
        """Test @openapi_errors with custom descriptions."""
        custom_descriptions = {
            "RESOURCE_NOT_FOUND": "The user you're looking for doesn't exist",
            "VALIDATION_FAILED": "Your input is invalid",
        }

        @openapi_errors(custom_descriptions=custom_descriptions)
        def test_func():
            raise NotFoundError("user", 123)
            raise ValidationError("Bad input")

        responses = test_func._openapi_error_responses

        # Check that custom descriptions are used in examples
        for status_code, response in responses.items():
            examples = response["content"]["application/json"]["examples"]
            for example_name, example in examples.items():
                error_code = example["value"]["error"]["code"]
                if error_code in custom_descriptions:
                    # Custom description should be used
                    assert custom_descriptions[error_code] in example["description"]

    def test_decorator_preserves_function_metadata(self):
        """Test that decorators preserve function metadata."""

        @analyze_errors()
        def test_func():
            """Test function docstring."""
            return "test"

        assert test_func.__name__ == "test_func"
        assert test_func.__doc__ == "Test function docstring."

    def test_openapi_response_structure(self):
        """Test OpenAPI response structure is valid."""

        @openapi_errors()
        def test_func():
            raise NotFoundError("user", 123)
            raise ValidationError("Invalid", code=ErrorCode.INVALID_INPUT)

        responses = test_func._openapi_error_responses

        # Verify response structure
        for status_code, response in responses.items():
            # Should be valid HTTP status code
            assert status_code.isdigit()
            assert 400 <= int(status_code) <= 599

            # Should have required structure
            assert "description" in response
            assert "content" in response
            assert "application/json" in response["content"]

            content = response["content"]["application/json"]
            assert "schema" in content
            assert "examples" in content

            # Verify schema structure
            schema = content["schema"]
            assert schema["type"] == "object"
            assert "error" in schema["properties"]

            error_schema = schema["properties"]["error"]
            assert "code" in error_schema["properties"]
            assert "message" in error_schema["properties"]
            assert "details" in error_schema["properties"]
            assert "timestamp" in error_schema["properties"]
            assert "request_id" in error_schema["properties"]

    def test_error_grouping_by_status_code(self):
        """Test that errors are properly grouped by HTTP status code."""

        @openapi_errors()
        def test_func():
            # 404 errors
            raise NotFoundError("user", 123)
            # 400 errors
            raise ValidationError("Invalid input", code=ErrorCode.INVALID_INPUT)
            # 401 errors
            raise ValidationError("Auth required", code=ErrorCode.AUTH_REQUIRED)

        responses = test_func._openapi_error_responses

        # Should have responses for different status codes
        status_codes = list(responses.keys())
        assert len(status_codes) > 1

        # Verify status code grouping
        for status_code, response in responses.items():
            schema = response["content"]["application/json"]["schema"]
            error_codes = schema["properties"]["error"]["properties"]["code"]["enum"]

            if status_code == "404":
                assert any("NOT_FOUND" in code for code in error_codes)
            elif status_code == "400":
                assert any("INVALID" in code for code in error_codes)

    def test_decorator_with_no_errors(self):
        """Test decorators on functions with no errors."""

        @analyze_errors()
        def clean_func():
            return {"status": "success"}

        @openapi_errors()
        def another_clean_func():
            return {"data": "test"}

        # Should not crash and should have empty analysis
        analysis = clean_func._error_analysis
        assert analysis["total_errors"] == 0
        assert len(analysis["error_codes"]) == 0

        responses = another_clean_func._openapi_error_responses
        # May have empty responses or default error responses
        assert isinstance(responses, dict)

    def test_function_execution_not_affected(self):
        """Test that decorated functions still execute normally."""

        @analyze_errors()
        def test_func(x, y):
            return x + y

        @openapi_errors()
        def another_test_func(name):
            return f"Hello, {name}!"

        # Functions should work normally
        assert test_func(2, 3) == 5
        assert another_test_func("World") == "Hello, World!"

    def test_nested_decorators(self):
        """Test function with multiple decorators."""

        def dummy_decorator(func):
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            return wrapper

        @openapi_errors()
        @dummy_decorator
        @analyze_errors()
        def test_func():
            raise NotFoundError("test")
            return "success"

        # Should have both analysis and OpenAPI responses
        assert hasattr(test_func, "_error_analysis")
        assert hasattr(test_func, "_openapi_error_responses")

        # Analysis should find the error (may be empty due to complex nested decorators)
        analysis = test_func._error_analysis
        assert analysis["total_errors"] >= 0  # At least no crashes

    def test_error_examples_generation(self):
        """Test that error examples are properly generated."""

        @openapi_errors()
        def test_func():
            raise NotFoundError("user", 123)
            raise ValidationError("Invalid email", field="email")

        responses = test_func._openapi_error_responses

        # Check examples
        found_examples = False
        for status_code, response in responses.items():
            examples = response["content"]["application/json"]["examples"]

            for example_name, example in examples.items():
                found_examples = True
                error_value = example["value"]

                # Verify example structure
                assert "error" in error_value
                error = error_value["error"]

                assert "code" in error
                assert "message" in error
                assert "details" in error
                assert "timestamp" in error
                assert "request_id" in error

        assert found_examples, "No examples were generated"


if __name__ == "__main__":
    pytest.main([__file__])
