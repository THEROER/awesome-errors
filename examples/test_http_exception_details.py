"""
Test for demonstrating the handling of HTTPException with detail passed in the details field.
"""

import pytest
from fastapi.testclient import TestClient
from http_exception_details import app

client = TestClient(app)


def test_http_exception_with_details():
    """Test checks that HTTPException.detail is passed in the details field."""

    # Test 404 error
    response = client.get("/users/404")
    assert response.status_code == 404

    error_data = response.json()
    error = error_data["error"]

    # Check that http_detail is in details
    assert "http_detail" in error["details"]
    assert (
        error["details"]["http_detail"] == "Користувача з ID 404 не знайдено в системі"
    )
    assert error["code"] == "RESOURCE_NOT_FOUND"

    # Test 403 error
    response = client.get("/users/403")
    assert response.status_code == 403

    error_data = response.json()
    error = error_data["error"]

    assert "http_detail" in error["details"]
    assert (
        error["details"]["http_detail"] == "Доступ заборонено для користувача з ID 403"
    )
    assert error["code"] == "AUTH_PERMISSION_DENIED"

    # Test 400 error
    response = client.get("/users/400")
    assert response.status_code == 400

    error_data = response.json()
    error = error_data["error"]

    assert "http_detail" in error["details"]
    assert error["details"]["http_detail"] == "Невірний формат ID користувача"
    assert error["code"] == "INVALID_INPUT"

    # Test 418 error (custom code)
    response = client.get("/admin/users/999")
    assert response.status_code == 418

    error_data = response.json()
    error = error_data["error"]

    assert "http_detail" in error["details"]
    assert error["details"]["http_detail"] == "Я чайник і не можу обробити цей запит"
    assert error["code"] == "UNKNOWN_ERROR"  # Unknown status code


def test_successful_requests():
    """Test successful requests."""

    # Successful request
    response = client.get("/users/123")
    assert response.status_code == 200
    assert response.json() == {
        "id": 123,
        "name": "John Doe",
        "email": "john@example.com",
    }

    # Successful admin request
    response = client.get("/admin/users/456")
    assert response.status_code == 200
    assert response.json() == {
        "id": 456,
        "role": "admin",
        "permissions": ["read", "write"],
    }


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
