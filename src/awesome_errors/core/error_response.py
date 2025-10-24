from typing import Any, Dict
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ConfigDict


class ErrorDetail(BaseModel):
    """Error detail model."""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    details: Dict[str, Any] = Field(
        default_factory=dict, description="Additional error details"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Error timestamp",
    )
    request_id: str = Field(..., description="Request ID for tracing")


class ErrorResponse(BaseModel):
    """Standard error response model."""

    error: ErrorDetail

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": {
                    "code": "USER_NOT_FOUND",
                    "message": "User not found",
                    "details": {"user_id": 123},
                    "timestamp": "2024-01-08T12:00:00Z",
                    "request_id": "req_abc123",
                }
            }
        }
    )
