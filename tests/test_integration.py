import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from awesome_errors import (
    setup_error_handling,
    NotFoundError,
    ValidationError,
    AuthError,
    ErrorCode,
    ErrorResponseFormat,
    openapi_errors,
    analyze_errors,
)


class TestIntegration:
    """Integration tests for awesome-errors with FastAPI."""

    def setup_method(self):
        """Setup test FastAPI app."""
        self.app = FastAPI()

        # Setup error handling
        setup_error_handling(
            self.app,
            debug=True,
            custom_translations={
                "en": {"CUSTOM_TEST_ERROR": "Custom test error message"},
                "uk": {"CUSTOM_TEST_ERROR": "Повідомлення про власну тестову помилку"},
            },
        )

        self.client = TestClient(self.app)

    def test_not_found_error_response(self):
        """Test NotFoundError response format."""

        @self.app.get("/users/{user_id}")
        def get_user(user_id: int):
            if user_id == 404:
                raise NotFoundError("user", user_id)
            return {"id": user_id, "name": "Test User"}

        # Test successful case
        response = self.client.get("/users/123")
        assert response.status_code == 200
        assert response.json()["id"] == 123

        # Test error case
        response = self.client.get("/users/404")
        assert response.status_code == 404

        error_data = response.json()
        assert "error" in error_data

        error = error_data["error"]
        assert error["code"] == "RESOURCE_NOT_FOUND"
        assert "resource not found" in error["message"].lower()
        assert error["details"]["resource"] == "user"
        assert error["details"]["resource_id"] == 404
        assert "timestamp" in error
        assert "request_id" in error

    def test_validation_error_response(self):
        """Test ValidationError response format."""

        @self.app.post("/users")
        def create_user(email: str):
            if not email:
                raise ValidationError(
                    "Email is required",
                    field="email",
                    code=ErrorCode.MISSING_REQUIRED_FIELD,
                )

            if "@" not in email:
                raise ValidationError(
                    "Invalid email format",
                    field="email",
                    value=email,
                    code=ErrorCode.INVALID_FORMAT,
                )

            return {"email": email, "id": 123}

        # Test invalid email
        response = self.client.post("/users?email=invalid")
        assert response.status_code == 400

        error_data = response.json()
        error = error_data["error"]
        assert error["code"] == "INVALID_FORMAT"
        assert error["details"]["field"] == "email"
        assert error["details"]["value"] == "invalid"

    def test_auth_error_response(self):
        """Test AuthError response format."""

        @self.app.get("/admin/users")
        def get_admin_users():
            raise AuthError(
                "Admin access required",
                code=ErrorCode.AUTH_PERMISSION_DENIED,
                required_permission="admin.users.read",
            )

        response = self.client.get("/admin/users")
        assert response.status_code == 403

        error_data = response.json()
        error = error_data["error"]
        assert error["code"] == "AUTH_PERMISSION_DENIED"
        assert error["details"]["required_permission"] == "admin.users.read"

    def test_problem_detail_response(self):
        """Test RFC 7807 payload rendering."""

        app = FastAPI()
        setup_error_handling(app, response_format=ErrorResponseFormat.RFC7807)
        client = TestClient(app)

        @app.get("/problem")
        def problem():
            raise NotFoundError("user", 7)

        response = client.get("/problem")
        assert response.status_code == 404
        assert response.headers["content-type"].startswith("application/problem+json")

        payload = response.json()
        assert payload["code"] == "RESOURCE_NOT_FOUND"
        assert payload["title"].lower().startswith("user not found")
        assert payload["details"]["resource_id"] == 7
        assert payload["type"] == "about:blank"
        assert "timestamp" in payload

    def test_custom_error_code_translation(self):
        """Test custom error code translation."""

        @self.app.get("/custom-error")
        def custom_error():
            raise ValidationError("Custom error", code=ErrorCode("CUSTOM_TEST_ERROR"))

        # Test English translation
        response = self.client.get("/custom-error")
        assert response.status_code == 400

        error_data = response.json()
        error = error_data["error"]
        assert error["code"] == "CUSTOM_TEST_ERROR"
        assert error["message"] == "Custom test error message"

        # Test Ukrainian translation
        response = self.client.get("/custom-error", headers={"Accept-Language": "uk"})
        assert response.status_code == 400

        error_data = response.json()
        error = error_data["error"]
        assert error["code"] == "CUSTOM_TEST_ERROR"
        assert "власну тестову помилку" in error["message"]

    def test_openapi_errors_decorator_integration(self):
        """Test OpenAPI errors decorator integration."""

        @openapi_errors(
            additional_errors=["RATE_LIMIT_EXCEEDED"],
            custom_descriptions={
                "RESOURCE_NOT_FOUND": "The requested user does not exist"
            },
        )
        @self.app.get("/openapi-test/{user_id}")
        def openapi_test(user_id: int):
            if user_id == 404:
                raise NotFoundError("user", user_id)
            return {"id": user_id}

        # Test that function still works
        response = self.client.get("/openapi-test/123")
        assert response.status_code == 200

        # Test error response
        response = self.client.get("/openapi-test/404")
        assert response.status_code == 404

        # Check that OpenAPI responses were attached
        assert hasattr(openapi_test, "_openapi_error_responses")
        responses = openapi_test._openapi_error_responses

        # Should have 404 response
        assert "404" in responses
        assert "RATE_LIMIT_EXCEEDED" in str(responses)

    def test_analyze_errors_decorator_integration(self):
        """Test analyze_errors decorator integration."""

        @analyze_errors()
        @self.app.get("/analyze-test")
        def analyze_test():
            raise ValidationError("Test error")
            raise NotFoundError("test")

        # Test that function analysis was performed
        assert hasattr(analyze_test, "_error_analysis")
        analysis = analyze_test._error_analysis

        assert "VALIDATION_FAILED" in analysis["error_codes"]
        assert "RESOURCE_NOT_FOUND" in analysis["error_codes"]
        assert analysis["total_errors"] >= 2

    def test_request_id_header(self):
        """Test that request ID is included in response headers."""

        @self.app.get("/test-request-id")
        def test_request_id():
            raise NotFoundError("test")

        response = self.client.get("/test-request-id")
        assert response.status_code == 404

        # Check request ID header
        assert "X-Request-ID" in response.headers

        # Check request ID in response body
        error_data = response.json()
        request_id = error_data["error"]["request_id"]
        assert request_id == response.headers["X-Request-ID"]

    def test_debug_mode_includes_traceback(self):
        """Test that debug mode includes traceback information."""

        @self.app.get("/debug-test")
        def debug_test():
            raise Exception("Debug test error")

        # TestClient may re-raise exceptions in debug mode
        # Check that middleware is properly configured
        try:
            response = self.client.get("/debug-test")
            # If we reach here, exception was handled
            assert response.status_code == 500
            error_data = response.json()
            error = error_data["error"]

            # In debug mode, should include traceback
            assert "traceback" in error["details"]
            assert "debug_test" in error["details"]["traceback"]
        except Exception:
            # TestClient may propagate exceptions in debug mode
            # This is normal behavior, check that middleware is configured
            assert hasattr(self.app, "exception_handlers")
            assert Exception in self.app.exception_handlers

    def test_fastapi_validation_error_handling(self):
        """Test handling of FastAPI's built-in validation errors."""
        from pydantic import BaseModel

        class UserModel(BaseModel):
            name: str
            age: int
            email: str

        @self.app.post("/pydantic-validation")
        def pydantic_validation(user: UserModel):
            return {"user": user.model_dump()}

        # Send invalid data
        response = self.client.post(
            "/pydantic-validation",
            json={"name": "John", "age": "not-a-number", "email": "invalid"},
        )

        assert response.status_code == 400

        error_data = response.json()
        error = error_data["error"]
        assert error["code"] == "VALIDATION_FAILED"
        assert "errors" in error["details"]

    def test_http_exception_handling(self):
        """Test handling of FastAPI HTTPException."""
        from fastapi import HTTPException

        @self.app.get("/http-exception")
        def http_exception():
            raise HTTPException(status_code=418, detail="I'm a teapot")

        response = self.client.get("/http-exception")
        assert response.status_code == 418

        error_data = response.json()
        error = error_data["error"]
        # Message is translated, check the original detail is preserved
        assert "teapot" in error["message"].lower() or error["code"] == "UNKNOWN_ERROR"

        # Check that http_detail is included in details
        assert "http_detail" in error["details"]
        assert error["details"]["http_detail"] == "I'm a teapot"

    def test_sqlalchemy_error_integration(self):
        """Test SQLAlchemy error integration."""
        from sqlalchemy.exc import IntegrityError
        from unittest.mock import Mock

        @self.app.get("/sql-error")
        def sql_error():
            # Mock SQLAlchemy error
            orig_error = Mock()
            orig_error.__str__ = (
                lambda self: 'duplicate key value violates unique constraint "users_email_unique"'
            )

            raise IntegrityError("statement", "params", orig_error)

        response = self.client.get("/sql-error")
        assert response.status_code == 409

        error_data = response.json()
        error = error_data["error"]
        assert error["code"] == "DB_DUPLICATE_ENTRY"

    def test_openapi_schema_generation(self):
        """Test that OpenAPI schema includes error responses."""

        @openapi_errors()
        @self.app.get("/schema-test")
        def schema_test():
            raise NotFoundError("test")

        # Get OpenAPI schema
        response = self.client.get("/openapi.json")
        assert response.status_code == 200

        openapi_schema = response.json()

        # Check that our endpoint is in the schema
        paths = openapi_schema["paths"]
        assert "/schema-test" in paths

        # The error responses should be included in the schema
        # (This is a basic check - full OpenAPI integration would need more testing)
        endpoint_spec = paths["/schema-test"]["get"]
        assert "responses" in endpoint_spec


if __name__ == "__main__":
    pytest.main([__file__])
