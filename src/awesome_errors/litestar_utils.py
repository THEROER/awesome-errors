"""Litestar-specific helpers for API error metadata."""

from __future__ import annotations

from typing import Any, Iterable, Tuple, Type, TypeVar, cast

from .core.exceptions import APIError

ErrorType = TypeVar("ErrorType", bound=APIError)


def _is_http_route_handler(obj: object) -> bool:
    try:  # pragma: no cover - optional dependency
        from litestar.handlers.http_handlers import HTTPRouteHandler
    except ImportError:  # pragma: no cover
        return False
    return isinstance(obj, HTTPRouteHandler)


def raises_from(*errors: Type[APIError]) -> list[Type[APIError]]:
    """Return a Litestar-compatible raises list from APIError classes."""
    return list(errors)


def errors(*errs: Type[APIError]):
    """Attach OpenAPI error responses to a Litestar handler."""

    def wrap(obj: Any) -> Any:
        if _is_http_route_handler(obj):
            current = getattr(obj, "raises", None) or []
            if isinstance(current, dict):
                current = []
            obj.raises = cast(Any, [*list(current), *errs])
            return obj
        setattr(obj, "__api_errors__", errs)
        return obj

    return wrap


def apply_api_errors(handlers: Iterable[object]) -> None:
    """Apply deferred error metadata to handlers (optional helper)."""
    for handler in handlers:
        if not _is_http_route_handler(handler):
            continue
        typed_handler = cast(Any, handler)
        errs: Tuple[Type[APIError], ...] | None = getattr(
            typed_handler.fn, "__api_errors__", None
        )
        if not errs:
            continue
        current = typed_handler.raises or []
        if isinstance(current, dict):
            current = []
        typed_handler.raises = cast(Any, [*list(current), *errs])
