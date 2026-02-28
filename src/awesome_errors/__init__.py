from __future__ import annotations

from typing import Any, Callable, Dict

from .analysis import ErrorAnalyzer, analyze_errors, openapi_errors
from .client import BackendError, ErrorResponseParser
from .converters import (
    PydanticErrorConverter,
    PythonErrorConverter,
    SQLErrorConverter,
    UniversalErrorConverter,
)
from .core.error_codes import ErrorCode
from .core.error_response import ErrorDetail, ErrorResponse
from .core.exceptions import (
    APIError,
    AppError,
    AuthError,
    AuthInsufficientPrivilegesError,
    AuthInvalidTokenError,
    AuthPermissionDeniedError,
    AuthRequiredError,
    AuthTokenExpiredError,
    BusinessLogicError,
    DatabaseConnectionError,
    DatabaseConstraintViolationError,
    DatabaseDuplicateEntryError,
    DatabaseError,
    DatabaseInvalidReferenceError,
    DatabaseMissingRequiredError,
    DatabaseQueryError,
    DatabaseTransactionError,
    EntityNotFoundError,
    InsufficientBalanceError,
    InvalidFormatError,
    InvalidInputError,
    MissingRequiredFieldError,
    NotFoundError,
    OAuthProviderUnknownError,
    OperationNotAllowedError,
    RefreshTokenReuseDetectedError,
    ResourceNotFoundError,
    SessionExpiredError,
    UserNotFoundError,
    ValidationError,
)
from .core.renderers import ErrorResponseFormat, ErrorResponseRenderer
from .i18n.translator import ErrorTranslator
from .litestar_utils import apply_api_errors, errors, raises_from
from .middleware.litestar import (
    apply_litestar_openapi_problem_details,
    create_litestar_exception_handlers,
)

_setup_error_handling: Callable[..., Any] | None = None
try:  # pragma: no cover - optional dependency
    from .middleware.fastapi import setup_error_handling as _setup_error_handling_impl
except ImportError:  # pragma: no cover
    pass
else:
    _setup_error_handling = _setup_error_handling_impl

_setup_automatic_error_docs: Callable[..., Any] | None = None
_apply_auto_error_docs_to_router: Callable[..., Any] | None = None
_auto_analyze_errors: Callable[..., Any] | None = None
try:  # pragma: no cover - optional dependency
    from .integrations.fastapi_auto_docs import (
        apply_auto_error_docs_to_router as _apply_auto_error_docs_to_router_impl,
    )
    from .integrations.fastapi_auto_docs import (
        auto_analyze_errors as _auto_analyze_errors_impl,
    )
    from .integrations.fastapi_auto_docs import (
        setup_automatic_error_docs as _setup_automatic_error_docs_impl,
    )
except ImportError:  # pragma: no cover
    pass
else:
    _setup_automatic_error_docs = _setup_automatic_error_docs_impl
    _apply_auto_error_docs_to_router = _apply_auto_error_docs_to_router_impl
    _auto_analyze_errors = _auto_analyze_errors_impl

_websocket: Any = None
try:  # pragma: no cover - optional dependency
    from . import websocket as _websocket_module
except ImportError:  # pragma: no cover
    pass
else:
    _websocket = _websocket_module

WebSocketError = getattr(_websocket, "WebSocketError", None)
JSONRPCErrorCode = getattr(_websocket, "JSONRPCErrorCode", None)
WebSocketAuthError = getattr(_websocket, "WebSocketAuthError", None)
WebSocketTokenExpiredError = getattr(_websocket, "WebSocketTokenExpiredError", None)
WebSocketRateLimitError = getattr(_websocket, "WebSocketRateLimitError", None)
WebSocketValidationError = getattr(_websocket, "WebSocketValidationError", None)
WebSocketMethodNotFoundError = getattr(_websocket, "WebSocketMethodNotFoundError", None)
WebSocketInternalError = getattr(_websocket, "WebSocketInternalError", None)
WebSocketErrorHandler = getattr(_websocket, "WebSocketErrorHandler", None)
_setup_websocket_error_handling = getattr(
    _websocket, "setup_websocket_error_handling", None
)


def setup_error_handling(
    app: Any,
    translator: ErrorTranslator | None = None,
    debug: bool = False,
    log_errors: bool = True,
    locales_dir: str | None = None,
    default_locale: str = "en",
    custom_translations: Dict[str, Dict[str, str]] | None = None,
    response_format: ErrorResponseFormat = ErrorResponseFormat.LEGACY,
    problem_type_resolver: Callable[[AppError], str] | None = None,
    problem_extension_builder: Callable[[AppError], Dict[str, object]] | None = None,
    message_resolver: Callable[
        [AppError, str | None, ErrorTranslator | None], str
    ] | None = None,
) -> Any:
    if _setup_error_handling is None:
        raise ImportError(
            "Install 'awesome-errors[fastapi]' to enable FastAPI middleware integration."
        )
    return _setup_error_handling(
        app=app,
        translator=translator,
        debug=debug,
        log_errors=log_errors,
        locales_dir=locales_dir,
        default_locale=default_locale,
        custom_translations=custom_translations,
        response_format=response_format,
        problem_type_resolver=problem_type_resolver,
        problem_extension_builder=problem_extension_builder,
        message_resolver=message_resolver,
    )


def setup_automatic_error_docs(app: Any, **kwargs: Any) -> Any:
    if _setup_automatic_error_docs is None:
        raise ImportError("FastAPI integration requires fastapi to be installed")
    return _setup_automatic_error_docs(app, **kwargs)


def apply_auto_error_docs_to_router(router: Any, **kwargs: Any) -> Any:
    if _apply_auto_error_docs_to_router is None:
        raise ImportError("FastAPI integration requires fastapi to be installed")
    return _apply_auto_error_docs_to_router(router, **kwargs)


def auto_analyze_errors(func: Any) -> Any:
    if _auto_analyze_errors is None:
        raise ImportError("FastAPI integration requires fastapi to be installed")
    return _auto_analyze_errors(func)


def setup_websocket_error_handling(app: Any) -> Any:
    if _setup_websocket_error_handling is None:
        raise ImportError(
            "Install 'awesome-errors[fastapi]' to enable WebSocket error handling."
        )
    return _setup_websocket_error_handling(app)


__version__ = "0.1.0"

__all__ = [
    "AppError",
    "APIError",
    "ValidationError",
    "InvalidInputError",
    "MissingRequiredFieldError",
    "InvalidFormatError",
    "AuthError",
    "AuthRequiredError",
    "AuthInvalidTokenError",
    "AuthTokenExpiredError",
    "AuthPermissionDeniedError",
    "AuthInsufficientPrivilegesError",
    "SessionExpiredError",
    "RefreshTokenReuseDetectedError",
    "NotFoundError",
    "ResourceNotFoundError",
    "UserNotFoundError",
    "EntityNotFoundError",
    "OAuthProviderUnknownError",
    "DatabaseError",
    "DatabaseConnectionError",
    "DatabaseQueryError",
    "DatabaseTransactionError",
    "DatabaseConstraintViolationError",
    "DatabaseDuplicateEntryError",
    "DatabaseInvalidReferenceError",
    "DatabaseMissingRequiredError",
    "BusinessLogicError",
    "InsufficientBalanceError",
    "OperationNotAllowedError",
    "ErrorCode",
    "ErrorResponse",
    "ErrorDetail",
    "ErrorResponseFormat",
    "ErrorResponseRenderer",
    "SQLErrorConverter",
    "PythonErrorConverter",
    "PydanticErrorConverter",
    "UniversalErrorConverter",
    "ErrorTranslator",
    "setup_error_handling",
    "create_litestar_exception_handlers",
    "apply_litestar_openapi_problem_details",
    "apply_api_errors",
    "errors",
    "raises_from",
    "ErrorResponseParser",
    "BackendError",
    "ErrorAnalyzer",
    "analyze_errors",
    "openapi_errors",
    "setup_automatic_error_docs",
    "apply_auto_error_docs_to_router",
    "auto_analyze_errors",
    "WebSocketError",
    "JSONRPCErrorCode",
    "WebSocketAuthError",
    "WebSocketTokenExpiredError",
    "WebSocketRateLimitError",
    "WebSocketValidationError",
    "WebSocketMethodNotFoundError",
    "WebSocketInternalError",
    "WebSocketErrorHandler",
    "setup_websocket_error_handling",
]
