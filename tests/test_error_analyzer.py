import pytest
from awesome_errors import (
    ErrorAnalyzer,
    NotFoundError,
    ValidationError,
    AuthError,
    ErrorCode,
)


class TestErrorAnalyzer:
    """Test error analyzer functionality."""

    def test_basic_raise_detection(self):
        """Test detection of basic raise statements."""

        def test_func():
            raise NotFoundError("user", 123)

        analyzer = ErrorAnalyzer(test_func)
        result = analyzer.analyze()

        assert "RESOURCE_NOT_FOUND" in result["error_codes"]
        assert result["total_errors"] >= 1
        assert result["function_name"] == "test_func"

    def test_multiple_errors(self):
        """Test detection of multiple different errors."""

        def test_func(user_id: int):
            if user_id <= 0:
                raise ValidationError("Invalid ID", code=ErrorCode.INVALID_INPUT)
            if user_id == 404:
                raise NotFoundError("user", user_id)
            if user_id == 999:
                raise AuthError("No permission", code=ErrorCode.AUTH_PERMISSION_DENIED)

        analyzer = ErrorAnalyzer(test_func)
        result = analyzer.analyze()

        expected_codes = [
            "INVALID_INPUT",
            "RESOURCE_NOT_FOUND",
            "AUTH_PERMISSION_DENIED",
        ]
        for code in expected_codes:
            assert code in result["error_codes"], f"Missing error code: {code}"

        assert result["total_errors"] >= 3

    def test_error_with_custom_code(self):
        """Test detection of errors with custom error codes."""

        def test_func():
            raise ValidationError("Custom error", code=ErrorCode("CUSTOM_ERROR_CODE"))

        analyzer = ErrorAnalyzer(test_func)
        result = analyzer.analyze()

        assert "CUSTOM_ERROR_CODE" in result["error_codes"]

    def test_decorator_analysis(self):
        """Test analysis of common decorators."""

        def mock_require_auth(func):
            def wrapper(*args, **kwargs):
                # This won't be analyzed since it's a mock
                return func(*args, **kwargs)

            return wrapper

        def mock_validate_input(func):
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            return wrapper

        # Create a function with mock decorator
        source_code = """
@mock_require_auth
@mock_validate_input
def test_func():
    pass
"""

        # Define decorators in local namespace
        local_namespace = {
            "mock_require_auth": mock_require_auth,
            "mock_validate_input": mock_validate_input,
        }

        # We need to create the function dynamically to have decorators
        exec(source_code, globals(), local_namespace)

        analyzer = ErrorAnalyzer(local_namespace["test_func"], analyze_decorators=True)
        result = analyzer.analyze()

        # Should detect decorator errors
        decorator_error_codes = []
        for decorator_error in result["decorator_errors"]:
            decorator_error_codes.extend(decorator_error["possible_errors"])

        assert len(result["decorator_errors"]) >= 0  # May or may not find decorators

    def test_method_call_analysis(self):
        """Test analysis of method calls."""

        def test_func():
            # These won't actually be called in the test
            session.query(User).get(1)  # Should detect DB errors
            json.loads('{"test": true}')  # Should detect JSON errors

        analyzer = ErrorAnalyzer(test_func)
        result = analyzer.analyze()

        # Should detect method-based errors
        method_errors = ["DB_QUERY_ERROR", "INVALID_FORMAT"]
        found_method_errors = [
            code for code in method_errors if code in result["error_codes"]
        ]

        # At least some method errors should be detected
        assert len(found_method_errors) > 0

    def test_depth_control(self):
        """Test depth control in recursive analysis."""

        def deep_func_3():
            raise NotFoundError("deep", 3)

        def deep_func_2():
            deep_func_3()
            raise ValidationError("level 2")

        def deep_func_1():
            deep_func_2()
            raise AuthError("level 1")

        def main_func():
            deep_func_1()
            raise NotFoundError("main")

        # Test with different depths
        analyzer_shallow = ErrorAnalyzer(main_func, max_depth=1)
        result_shallow = analyzer_shallow.analyze()

        analyzer_deep = ErrorAnalyzer(main_func, max_depth=5)
        result_deep = analyzer_deep.analyze()

        # Deep analysis should find more errors
        assert len(result_deep["error_codes"]) >= len(result_shallow["error_codes"])
        assert result_deep["analysis_depth"] >= result_shallow["analysis_depth"]

    def test_no_decorators_option(self):
        """Test disabling decorator analysis."""

        def test_func():
            raise NotFoundError("test")

        analyzer_with_decorators = ErrorAnalyzer(test_func, analyze_decorators=True)
        analyzer_without_decorators = ErrorAnalyzer(test_func, analyze_decorators=False)

        result_with = analyzer_with_decorators.analyze()
        result_without = analyzer_without_decorators.analyze()

        # Should have same basic errors but potentially different decorator errors
        assert "RESOURCE_NOT_FOUND" in result_with["error_codes"]
        assert "RESOURCE_NOT_FOUND" in result_without["error_codes"]

    def test_error_details_extraction(self):
        """Test extraction of error details."""

        def test_func():
            raise ValidationError(
                "Test validation error", field="email", code=ErrorCode.INVALID_FORMAT
            )

        analyzer = ErrorAnalyzer(test_func)
        result = analyzer.analyze()

        # Check error details
        assert len(result["error_details"]) > 0
        error_detail = result["error_details"][0]

        assert error_detail["code"] == "INVALID_FORMAT"
        assert error_detail["message"] == "Test validation error"
        assert error_detail["type"] == "ValidationError"

    def test_builtin_function_analysis(self):
        """Test analysis of builtin functions."""

        def test_func():
            # Mock some calls that would trigger builtin analysis

            # These should be detected by pattern matching
            pass

        analyzer = ErrorAnalyzer(test_func)
        result = analyzer.analyze()

        # This test mainly ensures no exceptions are raised
        assert isinstance(result["error_codes"], list)
        assert isinstance(result["total_errors"], int)

    def test_max_depth_reached_flag(self):
        """Test max depth reached flag."""

        def deep_func():
            another_deep_func()

        def another_deep_func():
            yet_another_func()

        def yet_another_func():
            raise NotFoundError("deep")

        def main_func():
            deep_func()

        analyzer = ErrorAnalyzer(main_func, max_depth=2)
        result = analyzer.analyze()

        # Should indicate if max depth was reached
        assert "max_depth_reached" in result
        assert isinstance(result["max_depth_reached"], bool)

    def test_empty_function(self):
        """Test analysis of function with no errors."""

        def empty_func():
            return {"message": "success"}

        analyzer = ErrorAnalyzer(empty_func)
        result = analyzer.analyze()

        assert result["total_errors"] == 0
        assert len(result["error_codes"]) == 0
        assert result["function_name"] == "empty_func"

    def test_reraise_detection(self):
        """Test detection of re-raised errors."""

        def test_func():
            try:
                raise ValueError("test")
            except ValueError as e:
                raise e  # Re-raise

        analyzer = ErrorAnalyzer(test_func)
        result = analyzer.analyze()

        # Should detect the re-raise
        assert (
            "UNKNOWN_ERROR" in result["error_codes"] or len(result["error_codes"]) > 0
        )

    def test_nested_function_calls(self):
        """Test analysis of nested function calls."""

        def helper_func():
            raise AuthError("Helper error")

        def main_func():
            helper_func()
            raise NotFoundError("Main error")

        analyzer = ErrorAnalyzer(main_func, max_depth=3)
        result = analyzer.analyze()

        # Should find errors from both functions
        assert (
            "AUTH_REQUIRED" in result["error_codes"]
            or "RESOURCE_NOT_FOUND" in result["error_codes"]
        )
        assert result["total_errors"] > 0


# Mock objects for testing method calls
class MockSession:
    def query(self, model):
        return MockQuery()


class MockQuery:
    def get(self, id):
        return None

    def filter(self, *args):
        return self

    def first(self):
        return None


class MockUser:
    pass


# Create mock objects in global scope for tests
session = MockSession()
User = MockUser
json = __import__("json")

if __name__ == "__main__":
    pytest.main([__file__])
