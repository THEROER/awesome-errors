"""Utilities that render ``AppError`` instances into HTTP payloads."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable, Dict, Optional

from ..core.exceptions import AppError
from .error_response import ErrorDetail, ErrorResponse


from datetime import timezone


def _isoformat(dt):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


class ErrorResponseFormat(StrEnum):
    """Supported HTTP error payload shapes."""

    LEGACY = "legacy"
    RFC7807 = "rfc7807"


@dataclass
class RenderResult:
    payload: Dict[str, Any]
    media_type: str


class ErrorResponseRenderer:
    """Render ``AppError`` objects into dictionaries ready for JSON encoding."""

    def __init__(
        self,
        format: ErrorResponseFormat = ErrorResponseFormat.LEGACY,
        *,
        problem_type_resolver: Optional[Callable[[AppError], str]] = None,
        problem_extension_builder: Optional[Callable[[AppError], Dict[str, Any]]] = None,
    ):
        self.format = format
        self._problem_type_resolver = problem_type_resolver
        self._problem_extension_builder = problem_extension_builder

    def render(
        self,
        error: AppError,
        *,
        message: str,
        request: Optional[Any] = None,
    ) -> RenderResult:
        if self.format == ErrorResponseFormat.RFC7807:
            return self._render_problem_detail(error, message=message, request=request)
        return self._render_legacy(error, message=message)

    def _render_legacy(self, error: AppError, *, message: str) -> RenderResult:
        detail = ErrorDetail(
            code=error.code.value,
            message=message,
            details=error.details,
            timestamp=error.timestamp,
            request_id=error.request_id,
        )
        envelope = ErrorResponse(error=detail)
        return RenderResult(payload=envelope.to_dict(), media_type="application/json")

    def _render_problem_detail(
        self,
        error: AppError,
        *,
        message: str,
        request: Optional[Any],
    ) -> RenderResult:
        problem_type = (
            self._problem_type_resolver(error)
            if self._problem_type_resolver
            else "about:blank"
        )
        instance: Optional[str] = None
        if request is not None:
            instance = getattr(request, "url", None)
            if instance is not None:
                instance = str(instance)

        payload: Dict[str, Any] = {
            "type": problem_type,
            "title": message,
            "status": error.status_code,
            "detail": error.message,
            "instance": instance,
            "code": error.code.value,
            "timestamp": _isoformat(error.timestamp),
            "request_id": error.request_id,
            "details": error.details,
        }
        extensions = (
            self._problem_extension_builder(error)
            if self._problem_extension_builder
            else None
        )
        if extensions:
            payload.update(extensions)

        return RenderResult(
            payload=payload,
            media_type="application/problem+json",
        )
