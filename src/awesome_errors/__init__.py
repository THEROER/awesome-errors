from .core.exceptions import (
    AppError,
    ValidationError,
    AuthError,
    NotFoundError,
    DatabaseError,
    BusinessLogicError,
)
from .core.error_codes import ErrorCode
from .core.error_response import ErrorResponse, ErrorDetail
from .converters import (
    SQLErrorConverter,
    PythonErrorConverter,
    PydanticErrorConverter,
    UniversalErrorConverter,
)
from .i18n.translator import ErrorTranslator
from .middleware.fastapi import setup_error_handling

# Client utilities
from .client import (
    ErrorResponseParser,
    BackendError,
)

# Analysis utilities
from .analysis import (
    ErrorAnalyzer,
    analyze_errors,
    openapi_errors,
)

# FastAPI integrations
try:
    from .integrations.fastapi_auto_docs import (
        setup_automatic_error_docs,
        apply_auto_error_docs_to_router,
        auto_analyze_errors,
    )
except ImportError:
    # FastAPI not available
    def setup_automatic_error_docs(*args, **kwargs):
        raise ImportError("FastAPI integration requires fastapi to be installed")

    def apply_auto_error_docs_to_router(*args, **kwargs):
        raise ImportError("FastAPI integration requires fastapi to be installed")

    def auto_analyze_errors(*args, **kwargs):
        raise ImportError("FastAPI integration requires fastapi to be installed")


# WebSocket support
from .websocket import (
    WebSocketError,
    JSONRPCErrorCode,
    WebSocketAuthError,
    WebSocketTokenExpiredError,
    WebSocketRateLimitError,
    WebSocketValidationError,
    WebSocketMethodNotFoundError,
    WebSocketInternalError,
    WebSocketErrorHandler,
    setup_websocket_error_handling,
)

__version__ = "0.1.0"

__all__ = [
    # Core exceptions
    "AppError",
    "ValidationError",
    "AuthError",
    "NotFoundError",
    "DatabaseError",
    "BusinessLogicError",
    # Error codes and response models
    "ErrorCode",
    "ErrorResponse",
    "ErrorDetail",
    # Converters
    "SQLErrorConverter",
    "PythonErrorConverter",
    "PydanticErrorConverter",
    "UniversalErrorConverter",
    # i18n
    "ErrorTranslator",
    # Middleware
    "setup_error_handling",
    # Client utilities
    "ErrorResponseParser",
    "BackendError",
    # Analysis utilities
    "ErrorAnalyzer",
    "analyze_errors",
    "openapi_errors",
    # FastAPI integrations
    "setup_automatic_error_docs",
    "apply_auto_error_docs_to_router",
    "auto_analyze_errors",
    # WebSocket support
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
