"""WebSocket error handler for awesome-errors"""

import asyncio
import json
import logging
from typing import Dict, Any, Type, Callable, Optional
from fastapi import FastAPI, WebSocket

from awesome_errors.core.error_codes import ErrorCode
from awesome_errors.core.exceptions import AppError
from awesome_errors.websocket.exceptions import WebSocketError, WebSocketInternalError
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)


class WebSocketErrorHandler:
    """
    Centralized error handler for WebSocket connections

    Provides automatic error conversion, logging, and connection management
    similar to Anaya's approach but for WebSocket.
    """

    def __init__(self):
        self.error_mappings: Dict[Type[Exception], Dict[str, Any]] = {}
        self._setup_default_mappings()

    def _setup_default_mappings(self):
        """Setup default error mappings"""
        from .exceptions import (
            WebSocketValidationError,
            WebSocketInternalError,
            JSONRPCErrorCode,
        )

        # Map common exceptions to WebSocket errors
        self.error_mappings.update(
            {
                # Pydantic validation
                ValueError: {
                    "converter": lambda e: WebSocketValidationError(
                        message=str(e), request_id=None
                    )
                },
                # JSON parsing
                json.JSONDecodeError: {
                    "converter": lambda e: WebSocketError(
                        code=ErrorCode.INVALID_FORMAT,
                        message="Invalid JSON",
                        ws_error_code=JSONRPCErrorCode.PARSE_ERROR,
                        request_id=None,
                    )
                },
                # Generic exceptions
                Exception: {
                    "converter": lambda e: WebSocketInternalError(
                        message="Internal server error",
                        original_error=str(e),
                        request_id=None,
                    )
                },
            }
        )

    def register_error_mapping(
        self,
        error_type: Type[Exception],
        converter: Callable[[Exception], WebSocketError],
    ):
        """Register custom error mapping"""
        self.error_mappings[error_type] = {"converter": converter}

    async def handle_websocket_error(
        self, websocket: WebSocket, error: Exception, request_id: Optional[str] = None
    ) -> bool:
        """
        Handle WebSocket error

        Returns:
            bool: True if connection should be closed
        """
        try:
            # Convert to WebSocketError
            ws_error = self._convert_to_websocket_error(error, request_id)

            # Log the error
            self._log_error(ws_error)

            # Send error response
            await self._send_error_response(websocket, ws_error)

            # Handle connection closing if needed
            if ws_error.close_connection:
                await self._close_connection(websocket, ws_error)
                return True

            return False

        except Exception as handler_error:
            logger.error(f"Error in error handler: {handler_error}")
            # Try to close connection gracefully
            try:
                await websocket.close(code=1011, reason="Error handler failed")
            except Exception:
                pass
            return True

    def _convert_to_websocket_error(
        self, error: Exception, request_id: Optional[str] = None
    ) -> WebSocketError:
        """Convert any exception to WebSocketError"""

        # If already a WebSocketError, just update request_id
        if isinstance(error, WebSocketError):
            if request_id and not error.request_id:
                error.request_id = request_id
            return error

        # If it's an AppError, convert it
        if isinstance(error, AppError):
            return WebSocketError.from_app_error(error, request_id)

        # Check registered mappings
        for error_type, mapping in self.error_mappings.items():
            if isinstance(error, error_type):
                ws_error = mapping["converter"](error)
                if request_id and not ws_error.request_id:
                    ws_error.request_id = request_id
                return ws_error

        # Fallback to internal error
        return WebSocketInternalError(
            message="Unexpected error occurred",
            original_error=str(error),
            request_id=request_id,
        )

    def _log_error(self, error: WebSocketError):
        """Log error based on severity"""
        if error.ws_error_code < -32600:  # Standard JSON-RPC errors
            logger.error(
                f"WebSocket error: {error.message}",
                extra={
                    "error_code": error.code.value,
                    "ws_error_code": error.ws_error_code,
                    "request_id": error.request_id,
                },
            )
        else:  # Custom errors
            logger.warning(
                f"WebSocket error: {error.message}",
                extra={
                    "error_code": error.code.value,
                    "ws_error_code": error.ws_error_code,
                    "request_id": error.request_id,
                },
            )

    async def _send_error_response(self, websocket: WebSocket, error: WebSocketError):
        """Send error response via WebSocket"""
        try:
            if getattr(websocket, "client_state", None) not in (
                WebSocketState.CONNECTED,
            ):
                return

            error_response = json.dumps(error.to_jsonrpc_error())
            await websocket.send_text(error_response)
        except Exception as send_error:
            logger.error(f"Failed to send error response: {send_error}")

    async def _close_connection(self, websocket: WebSocket, error: WebSocketError):
        """Close WebSocket connection with proper code and reason"""
        try:
            # Wait a bit to ensure error message is delivered
            await asyncio.sleep(0.1)

            # Map error codes to WebSocket close codes
            close_code = self._get_close_code(error)
            close_reason = error.message[:123]  # Max 123 bytes for close reason

            await websocket.close(code=close_code, reason=close_reason)
            if getattr(websocket, "client_state", None) not in (
                WebSocketState.CONNECTED,
            ):
                await websocket.close(code=close_code, reason=close_reason)

        except Exception as close_error:
            logger.error(f"Failed to close WebSocket: {close_error}")

    def _get_close_code(self, error: WebSocketError) -> int:
        """Get appropriate WebSocket close code"""
        from .exceptions import JSONRPCErrorCode

        # Map error codes to WebSocket close codes
        close_code_mapping = {
            JSONRPCErrorCode.AUTH_REQUIRED: 1008,  # Policy Violation
            JSONRPCErrorCode.TOKEN_EXPIRED: 1008,  # Policy Violation
            JSONRPCErrorCode.RATE_LIMITED: 1008,  # Policy Violation
            JSONRPCErrorCode.INTERNAL_ERROR: 1011,  # Internal Error
            JSONRPCErrorCode.INVALID_REQUEST: 1003,  # Unsupported Data
            JSONRPCErrorCode.PARSE_ERROR: 1007,  # Invalid frame payload data
        }

        return close_code_mapping.get(error.ws_error_code, 1000)  # Normal closure


def setup_websocket_error_handling(app: FastAPI) -> WebSocketErrorHandler:
    """
    Setup WebSocket error handling for FastAPI app

    Usage:
        ws_error_handler = setup_websocket_error_handling(app)

        # In WebSocket endpoint:
        try:
            # ... handle message
        except Exception as e:
            should_close = await ws_error_handler.handle_websocket_error(
                websocket, e, request_id
            )
            if should_close:
                break
    """
    handler = WebSocketErrorHandler()

    # Store handler in app state for access
    app.state.ws_error_handler = handler

    return handler
