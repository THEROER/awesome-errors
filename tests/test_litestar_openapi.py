"""Tests for Litestar OpenAPI integration helpers."""

from __future__ import annotations

from litestar import Litestar, get
from litestar.openapi.config import OpenAPIConfig
from litestar.openapi.spec.response import OpenAPIResponse

from awesome_errors import (
    ErrorResponseFormat,
    ErrorTranslator,
    NotFoundError,
    apply_litestar_openapi_problem_details,
    create_litestar_exception_handlers,
)


def test_apply_litestar_openapi_problem_details() -> None:
    """Ensure OpenAPI responses advertise RFC 7807 payloads."""

    translator = ErrorTranslator(default_locale="en")

    @get("/boom", sync_to_thread=False)
    def boom() -> None:
        raise NotFoundError("item", 1)

    handlers = create_litestar_exception_handlers(
        translator=translator,
        response_format=ErrorResponseFormat.RFC7807,
    )

    app = Litestar(
        route_handlers=[boom],
        exception_handlers=handlers,
        openapi_config=OpenAPIConfig(title="Test", version="1.0.0"),
    )

    schema = app.openapi_schema
    schema.paths["/boom"].get.responses["404"] = OpenAPIResponse(description="Not Found")

    apply_litestar_openapi_problem_details(app, service_name="test-service")

    openapi_dict = app.openapi_schema.to_schema()
    response = openapi_dict["paths"]["/boom"]["get"]["responses"]["404"]
    problem = response["content"]["application/problem+json"]

    required = set(problem["schema"]["required"])
    assert {
        "type",
        "title",
        "status",
        "detail",
        "instance",
        "code",
        "timestamp",
        "request_id",
    }.issubset(required)

    example = problem["example"]
    assert example["status"] == 404
    assert example["code"] == "RESOURCE_NOT_FOUND"
    assert example["service"] == "test-service"
