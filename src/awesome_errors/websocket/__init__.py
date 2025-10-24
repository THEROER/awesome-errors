"""WebSocket support for awesome-errors"""

from .exceptions import (
    # Base classes
    WebSocketError,
    JSONRPCErrorCode,
    # Specific errors
    WebSocketAuthError,
    WebSocketTokenExpiredError,
    WebSocketRateLimitError,
    WebSocketValidationError,
    WebSocketMethodNotFoundError,
    WebSocketInternalError,
)

from .error_handler import (
    WebSocketErrorHandler,
    setup_websocket_error_handling,
)

__all__ = [
    # Base classes
    "WebSocketError",
    "JSONRPCErrorCode",
    # Specific errors
    "WebSocketAuthError",
    "WebSocketTokenExpiredError",
    "WebSocketRateLimitError",
    "WebSocketValidationError",
    "WebSocketMethodNotFoundError",
    "WebSocketInternalError",
    # Error handling
    "WebSocketErrorHandler",
    "setup_websocket_error_handling",
]
