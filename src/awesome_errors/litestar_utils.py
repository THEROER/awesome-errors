"""Litestar-specific helpers for API error metadata."""

from __future__ import annotations

from typing import Iterable, Tuple, Type, TypeVar

from .core.exceptions import APIError

try:  # pragma: no cover - optional dependency
    from litestar.handlers.http_handlers import HTTPRouteHandler
    from litestar.openapi.datastructures import ResponseSpec
except ImportError:  # pragma: no cover
    HTTPRouteHandler = None  # type: ignore[assignment]
    ResponseSpec = None  # type: ignore[assignment]

ErrorType = TypeVar("ErrorType", bound=APIError)


def raises_from(*errors: Type[APIError]) -> list[Type[APIError]]:
    """Return a Litestar-compatible raises list from APIError classes."""
    return list(errors)


def errors(*errs: Type[APIError]):
    """Attach OpenAPI error responses to a Litestar handler."""

    def wrap(obj):
        if HTTPRouteHandler is not None and isinstance(obj, HTTPRouteHandler):
            current = obj.raises or []
            if isinstance(current, dict):
                current = []
            obj.raises = [*list(current), *errs]
            return obj
        setattr(obj, "__api_errors__", errs)
        return obj

    return wrap


def apply_api_errors(handlers: Iterable[object]) -> None:
    """Apply deferred error metadata to handlers (optional helper)."""
    if HTTPRouteHandler is None:
        return
    for handler in handlers:
        if isinstance(handler, HTTPRouteHandler):
            errs: Tuple[Type[APIError], ...] | None = getattr(
                handler.fn, "__api_errors__", None
            )
            if not errs:
                continue
            current = handler.raises or []
            if isinstance(current, dict):
                current = []
            handler.raises = [*list(current), *errs]
