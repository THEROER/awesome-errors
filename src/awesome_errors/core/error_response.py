"""Core error response models built on msgspec."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Mapping

import msgspec


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class ErrorDetail(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Serializable representation of an application error."""

    code: str
    message: str
    request_id: str
    details: Dict[str, Any] = msgspec.field(default_factory=dict)
    timestamp: datetime = msgspec.field(default_factory=_now_utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to builtin types, ensuring ISO timestamps."""
        data = msgspec.to_builtins(self, builtin_types=None)
        timestamp = data.get("timestamp")
        if isinstance(timestamp, datetime):
            data["timestamp"] = timestamp.isoformat().replace("+00:00", "Z")
        elif isinstance(timestamp, str):
            data["timestamp"] = timestamp
        else:
            data["timestamp"] = _now_utc().isoformat().replace("+00:00", "Z")
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
            timestamp = datetime.fromisoformat(
                timestamp.replace("Z", "+00:00")
            )
        except ValueError:
            timestamp = _now_utc()

    return ErrorDetail(
        code=str(data.get("code", "UNKNOWN_ERROR")),
        message=str(data.get("message", "")),
        details=dict(data.get("details") or {}),
        timestamp=timestamp if isinstance(timestamp, datetime) else _now_utc(),
        request_id=str(data.get("request_id", "")),
    )
