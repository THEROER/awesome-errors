"""Core error response models built on msgspec."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Mapping

import msgspec

from ._utils import to_iso_z, utc_now


class ErrorDetail(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Serializable representation of an application error."""

    code: str
    message: str
    request_id: str
    details: Dict[str, Any] = msgspec.field(default_factory=dict)
    timestamp: datetime = msgspec.field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to builtin types, ensuring ISO timestamps."""
        data = msgspec.to_builtins(self, builtin_types=None)
        timestamp = data.get("timestamp")
        if isinstance(timestamp, datetime):
            data["timestamp"] = to_iso_z(timestamp)
        elif isinstance(timestamp, str):
            data["timestamp"] = timestamp
        else:
            data["timestamp"] = to_iso_z(utc_now())
        return data


class ErrorResponse(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Legacy `{"error": {...}}` envelope."""

    error: ErrorDetail

    def to_dict(self) -> Dict[str, Any]:
        return {"error": self.error.to_dict()}


def error_detail_from_mapping(data: Mapping[str, Any]) -> ErrorDetail:
    """Construct an ``ErrorDetail`` from mapping data."""
    timestamp = data.get("timestamp")
    if isinstance(timestamp, str):
        try:
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            timestamp = utc_now()

    return ErrorDetail(
        code=str(data.get("code", "UNKNOWN_ERROR")),
        message=str(data.get("message", "")),
        details=dict(data.get("details") or {}),
        timestamp=timestamp if isinstance(timestamp, datetime) else utc_now(),
        request_id=str(data.get("request_id", "")),
    )
