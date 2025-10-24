"""
Example of using error analysis decorators for OpenAPI documentation.
"""

from fastapi import FastAPI
from awesome_errors import (
    setup_error_handling,
    NotFoundError,
    ValidationError,
    AuthError,
    ErrorCode,
    openapi_errors,
    analyze_errors,
)

app = FastAPI()
setup_error_handling(app)


def verify_user_permission(user_id: int) -> None:
    """Mock permission verification that can raise auth errors."""
    if user_id == 999:
        raise AuthError("Permission denied", code=ErrorCode.AUTH_PERMISSION_DENIED)


@openapi_errors(
    additional_errors=["RATE_LIMIT_EXCEEDED"],  # Add custom errors
    exclude_errors=["INTERNAL_ERROR"],  # Exclude some errors
    custom_descriptions={
        "USER_NOT_FOUND": "The specified user does not exist in the system",
        "RATE_LIMIT_EXCEEDED": "Too many requests, please try again later",
    },
)
@app.get("/users/{user_id}")
def get_user(user_id: int):
    """
    Get user by ID.

    This endpoint automatically documents all possible errors through AST analysis.
    """
    # This will be detected by AST analyzer
    if user_id <= 0:
        raise ValidationError(
            "User ID must be positive", field="user_id", code=ErrorCode.INVALID_INPUT
        )

    # This call will be analyzed for errors too
    verify_user_permission(user_id)

    # This will be detected
    if user_id == 404:
        raise NotFoundError("user", user_id)

    return {"id": user_id, "name": "John Doe"}


@analyze_errors()
@app.post("/users")
def create_user(email: str, name: str):
    """
    Create new user.

    Uses @analyze_errors to collect all possible errors.
    """
    if not email:
        raise ValidationError(
            "Email is required", field="email", code=ErrorCode.MISSING_REQUIRED_FIELD
        )

    if "@" not in email:
        raise ValidationError(
            "Invalid email format", field="email", code=ErrorCode.INVALID_FORMAT
        )

    # Simulate database duplicate error
    if email == "existing@example.com":
        raise ValidationError(
            "Email already exists",
            field="email",
            code=ErrorCode("EMAIL_ALREADY_EXISTS"),
        )

    return {"email": email, "name": name, "id": 123}


@app.get("/analysis-demo")
def show_analysis():
    """Demo endpoint to show error analysis results."""

    # Get analysis from decorated functions
    get_user_analysis = (
        get_user._error_analysis if hasattr(get_user, "_error_analysis") else None
    )
    create_user_analysis = (
        create_user._error_analysis if hasattr(create_user, "_error_analysis") else None
    )

    # Get OpenAPI responses
    get_user_responses = (
        get_user._openapi_error_responses
        if hasattr(get_user, "_openapi_error_responses")
        else None
    )

    return {
        "get_user_analysis": get_user_analysis,
        "create_user_analysis": create_user_analysis,
        "get_user_openapi_responses": get_user_responses,
    }


if __name__ == "__main__":
    import uvicorn  # type: ignore

    # Print analysis results before starting server
    print("=== Error Analysis Results ===")

    if hasattr(get_user, "_error_analysis"):
        print(f"get_user errors: {get_user._error_analysis['error_codes']}")

    if hasattr(create_user, "_error_analysis"):
        print(f"create_user errors: {create_user._error_analysis['error_codes']}")

    if hasattr(get_user, "_openapi_error_responses"):
        print(
            f"get_user OpenAPI responses: {list(get_user._openapi_error_responses.keys())}"
        )

    uvicorn.run(app, host="0.0.0.0", port=8000)
