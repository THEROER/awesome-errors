"""
Example showing different ways to integrate error analysis with FastAPI OpenAPI.
"""

from fastapi import FastAPI
from awesome_errors import (
    setup_error_handling,
    NotFoundError,
    ValidationError,
    ErrorCode,
    analyze_errors,
    openapi_errors,
)
from awesome_errors.integrations import (
    setup_fastapi_error_integration,
    auto_analyze_errors,
)

app = FastAPI(title="Error Analysis Integration Demo")
setup_error_handling(app)

# Setup automatic error integration
error_integration = setup_fastapi_error_integration(app)


# Method 1: @openapi_errors - full automatic integration
@openapi_errors(
    custom_descriptions={
        "USER_NOT_FOUND": "User with specified ID was not found",
        "INVALID_INPUT": "Invalid user ID provided",
    }
)
@app.get("/users/{user_id}")
def get_user_openapi(user_id: int):
    """
    Get user (with automatic OpenAPI error documentation).

    This endpoint automatically documents errors in OpenAPI.
    """
    if user_id <= 0:
        raise ValidationError("Invalid user ID", code=ErrorCode.INVALID_INPUT)

    if user_id == 404:
        raise NotFoundError("user", user_id)

    return {"id": user_id, "name": "John Doe"}


# Method 2: @auto_analyze_errors - analyze_errors + auto OpenAPI integration
@auto_analyze_errors
@app.get("/posts/{post_id}")
def get_post_auto(post_id: int):
    """
    Get post (with auto error analysis and OpenAPI integration).

    Uses @auto_analyze_errors for automatic OpenAPI integration.
    """
    if post_id <= 0:
        raise ValidationError("Invalid post ID", code=ErrorCode.INVALID_INPUT)

    if post_id == 404:
        raise NotFoundError("post", post_id)

    return {"id": post_id, "title": "Sample Post"}


# Method 3: @analyze_errors - analysis only, NO auto OpenAPI integration
@analyze_errors()
@app.get("/comments/{comment_id}")
def get_comment_manual(comment_id: int):
    """
    Get comment (manual OpenAPI integration required).

    Uses @analyze_errors - needs manual OpenAPI integration.
    """
    if comment_id <= 0:
        raise ValidationError("Invalid comment ID", code=ErrorCode.INVALID_INPUT)

    if comment_id == 404:
        raise NotFoundError("comment", comment_id)

    return {"id": comment_id, "text": "Sample comment"}


@app.get("/debug/analysis")
def show_error_analysis():
    """Show error analysis results for all endpoints."""
    results = {}

    # Check all endpoints for error analysis
    endpoints = [get_user_openapi, get_post_auto, get_comment_manual]

    for endpoint in endpoints:
        if hasattr(endpoint, "_error_analysis"):
            results[endpoint.__name__] = {
                "error_codes": endpoint._error_analysis["error_codes"],
                "has_openapi_responses": hasattr(endpoint, "_openapi_error_responses"),
                "has_auto_openapi": hasattr(endpoint, "_auto_openapi"),
            }

    return results


if __name__ == "__main__":
    import uvicorn  # type: ignore

    print("=== Integration Methods ===")
    print("1. @openapi_errors - Full automatic OpenAPI integration")
    print("2. @auto_analyze_errors - Analyze + auto OpenAPI integration")
    print("3. @analyze_errors - Analysis only, manual OpenAPI integration")
    print()

    # Show which endpoints have what features
    endpoints = [
        ("get_user_openapi", get_user_openapi),
        ("get_post_auto", get_post_auto),
        ("get_comment_manual", get_comment_manual),
    ]

    for name, endpoint in endpoints:
        features = []
        if hasattr(endpoint, "_error_analysis"):
            features.append("error_analysis")
        if hasattr(endpoint, "_openapi_error_responses"):
            features.append("openapi_responses")
        if hasattr(endpoint, "_auto_openapi"):
            features.append("auto_openapi")

        print(f"{name}: {', '.join(features) if features else 'none'}")

    print("\nStarting server...")
    print("Visit http://localhost:8000/docs to see OpenAPI documentation")

    uvicorn.run(app, host="0.0.0.0", port=8000)
