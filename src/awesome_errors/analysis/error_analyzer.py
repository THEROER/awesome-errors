import ast
import inspect
import textwrap
from typing import Set, List, Dict, Any, Optional, Callable


class ErrorAnalyzer(ast.NodeVisitor):
    """AST analyzer that discovers the error codes a function may raise.

    The analysis is static: it parses the function's own source (and its
    decorators) looking for ``raise`` statements and well-known library call
    patterns. It does not follow calls into other functions — resolving call
    targets reliably requires runtime introspection that isn't available from
    the AST alone.

    ``max_depth`` and ``analyze_decorators`` are accepted for backwards
    compatibility; ``max_depth`` currently has no effect since cross-function
    recursion is not performed.
    """

    def __init__(
        self, function: Callable, max_depth: int = 10, analyze_decorators: bool = True
    ):
        """
        Initialize error analyzer.

        Args:
            function: Function to analyze
            max_depth: Retained for compatibility (no cross-function recursion)
            analyze_decorators: Whether to analyze decorators
        """
        self.function = function
        self.max_depth = max_depth
        self.analyze_decorators = analyze_decorators
        self.errors: Set[str] = set()
        self.error_details: List[Dict[str, Any]] = []
        self.decorator_errors: List[Dict[str, Any]] = []

    def analyze(self) -> Dict[str, Any]:
        """
        Analyze function for all possible errors.

        Returns:
            Dictionary with error analysis results
        """
        # Reset state so an analyzer can be reused.
        self.errors.clear()
        self.error_details.clear()
        self.decorator_errors.clear()

        if self.analyze_decorators:
            self._analyze_decorators(self.function)

        self._analyze_function(self.function)

        return {
            "function_name": getattr(self.function, "__name__", "<unknown>"),
            "error_codes": sorted(self.errors),
            "error_details": self.error_details,
            "decorator_errors": self.decorator_errors,
            "total_errors": len(self.errors),
            "analysis_depth": 0,
            "max_depth_reached": False,
        }

    @staticmethod
    def _get_source(func: Callable) -> Optional[str]:
        """Return the dedented source of ``func``, or ``None`` if unavailable.

        Handles wrapped functions (``functools.wraps``) and environments where
        ``inspect.getsource`` fails because the recorded filename can't be read.
        """
        target = inspect.unwrap(func)
        for candidate in (target, func):
            try:
                return textwrap.dedent(inspect.getsource(candidate))
            except (OSError, TypeError):
                continue
        return None

    def _analyze_function(self, func: Callable) -> None:
        """Parse a function's source and visit its AST for raised errors."""
        source = self._get_source(func)
        if source is None:
            # Source unavailable (builtin/C function or unreadable file) — fall
            # back to inferring errors from the callable's identity.
            self._analyze_builtin_function(func)
            return

        try:
            tree = ast.parse(source)
        except SyntaxError:
            self._analyze_builtin_function(func)
            return

        self.visit(tree)

    def visit_Raise(self, node: ast.Raise) -> None:
        """Handle raise statements."""
        if node.exc:
            error_info = self._extract_error_info(node.exc)
            if error_info:
                self.errors.add(error_info["code"])
                self.error_details.append(error_info)

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Detect known error-producing call patterns (ORM/validation)."""
        self._analyze_call_context(node)
        self.generic_visit(node)

    def _analyze_call_context(self, node: ast.Call) -> None:
        """Analyze call context to detect common error patterns."""
        call_str = self._get_call_string(node)

        # SQLAlchemy session operations
        if any(
            pattern in call_str
            for pattern in [
                "session.",
                ".execute(",
                ".commit(",
                ".rollback(",
                ".query(",
                ".add(",
                ".delete(",
                ".merge(",
                ".flush(",
            ]
        ):
            self._add_sqlalchemy_errors()

        # Pydantic validation
        elif any(
            pattern in call_str
            for pattern in [
                ".model_validate(",
                ".parse_obj(",
                ".model_dump(",
                ".model_validate_json(",
            ]
        ):
            self.errors.add("VALIDATION_FAILED")

    def _get_call_string(self, node: ast.Call) -> str:
        """Get string representation of call for pattern matching."""
        try:
            if isinstance(node.func, ast.Attribute):
                return f"{self._get_attr_chain(node.func)}()"
            elif isinstance(node.func, ast.Name):
                return f"{node.func.id}()"
        except Exception:
            pass
        return ""

    def _get_attr_chain(self, node: ast.Attribute) -> str:
        """Get full attribute chain like 'obj.method'."""
        parts = []
        current: ast.AST = node

        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value

        if isinstance(current, ast.Name):
            parts.append(current.id)

        return ".".join(reversed(parts)) if parts else ""

    def _extract_error_info(self, node: ast.AST) -> Optional[Dict[str, Any]]:
        """Extract error information from raise statement."""
        if isinstance(node, ast.Call):
            # Handle: raise SomeError("message", code="ERROR_CODE")
            func_name = self._get_function_name(node.func)

            if func_name and self._is_app_error_class(func_name):
                if func_name == "HTTPException":
                    # Special handling for HTTPException
                    error_info = self._extract_http_exception_info(node)
                else:
                    error_info = {
                        "type": func_name,
                        "code": self._extract_error_code(node),
                        "message": self._extract_error_message(node),
                        "line": getattr(node, "lineno", None),
                    }
                return error_info

        elif isinstance(node, ast.Name):
            # Handle: raise existing_error
            return {
                "type": "unknown",
                "code": "UNKNOWN_ERROR",
                "message": "Re-raised error",
                "line": getattr(node, "lineno", None),
            }

        return None

    def _extract_error_code(self, node: ast.Call) -> str:
        """Extract error code from exception constructor."""
        # Look for code parameter
        for keyword in node.keywords:
            if keyword.arg == "code":
                # Handle string constants
                if isinstance(keyword.value, ast.Constant) and isinstance(
                    keyword.value.value, str
                ):
                    return keyword.value.value
                # Handle ErrorCode.CONSTANT_NAME
                elif isinstance(keyword.value, ast.Attribute):
                    if (
                        isinstance(keyword.value.value, ast.Name)
                        and keyword.value.value.id == "ErrorCode"
                    ):
                        return keyword.value.attr
                # Handle ErrorCode("CUSTOM_ERROR_CODE")
                elif isinstance(keyword.value, ast.Call):
                    if (
                        isinstance(keyword.value.func, ast.Name)
                        and keyword.value.func.id == "ErrorCode"
                        and keyword.value.args
                        and isinstance(keyword.value.args[0], ast.Constant)
                        and isinstance(keyword.value.args[0].value, str)
                    ):
                        return keyword.value.args[0].value
                return "UNKNOWN_ERROR"

        # Look for ErrorCode in positional args
        for arg in node.args:
            if isinstance(arg, ast.Call):
                func_name = self._get_function_name(arg.func)
                if func_name == "ErrorCode" and arg.args:
                    return self._extract_string_value(arg.args[0]) or "UNKNOWN_ERROR"

        # Default based on exception type
        func_name = self._get_function_name(node.func)
        return self._get_default_error_code(func_name or "unknown")

    def _extract_error_message(self, node: ast.Call) -> str:
        """Extract error message from exception constructor."""
        if node.args:
            message = self._extract_string_value(node.args[0])
            if message:
                return message

        # Look for message parameter
        for keyword in node.keywords:
            if keyword.arg == "message":
                return self._extract_string_value(keyword.value) or "Unknown error"

        return "Unknown error"

    def _extract_string_value(self, node: ast.AST) -> Optional[str]:
        """Extract string value from AST node."""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        return None

    def _get_function_name(self, node: ast.AST) -> Optional[str]:
        """Get function name from call node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        return None

    def _is_app_error_class(self, name: str) -> bool:
        """Check if name is an AppError class."""
        app_error_classes = {
            "AppError",
            "ValidationError",
            "AuthError",
            "NotFoundError",
            "DatabaseError",
            "BusinessLogicError",
            "HTTPException",  # Support FastAPI HTTPException
        }
        return name in app_error_classes

    def _get_default_error_code(self, class_name: str) -> str:
        """Get default error code for exception class."""
        default_codes = {
            "ValidationError": "VALIDATION_FAILED",
            "AuthError": "AUTH_REQUIRED",
            "NotFoundError": "RESOURCE_NOT_FOUND",
            "DatabaseError": "DB_QUERY_ERROR",
            "BusinessLogicError": "BUSINESS_RULE_VIOLATION",
            "AppError": "INTERNAL_ERROR",
            "HTTPException": "HTTP_EXCEPTION",
        }
        return default_codes.get(class_name, "UNKNOWN_ERROR")

    def _extract_http_exception_info(self, node: ast.Call) -> Dict[str, Any]:
        """Extract error information from HTTPException constructor."""
        status_code = 500
        message = "HTTP Error"

        # Extract status_code from kwargs or positional args
        for keyword in node.keywords:
            if keyword.arg == "status_code":
                if isinstance(keyword.value, ast.Constant) and isinstance(
                    keyword.value.value, int
                ):
                    status_code = keyword.value.value
            elif keyword.arg == "detail":
                if isinstance(keyword.value, ast.Constant) and isinstance(
                    keyword.value.value, str
                ):
                    message = keyword.value.value

        # Check positional args for status_code
        if (
            node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, int)
        ):
            status_code = node.args[0].value

        # Map status code to error code
        error_code = self._map_status_code_to_error_code(status_code)

        return {
            "type": "HTTPException",
            "code": error_code,
            "message": message,
            "status_code": status_code,
            "line": getattr(node, "lineno", None),
        }

    def _map_status_code_to_error_code(self, status_code: int) -> str:
        """Map HTTP status code to appropriate error code."""
        status_to_error = {
            400: "VALIDATION_FAILED",
            401: "AUTH_REQUIRED",
            403: "AUTH_PERMISSION_DENIED",
            404: "RESOURCE_NOT_FOUND",
            409: "RESOURCE_CONFLICT",
            422: "BUSINESS_RULE_VIOLATION",
            500: "INTERNAL_ERROR",
        }
        return status_to_error.get(status_code, "HTTP_EXCEPTION")

    def _analyze_decorators(self, func: Callable) -> None:
        """Analyze function decorators for potential errors."""
        try:
            source_lines = inspect.getsourcelines(func)[0]

            decorator_lines = []
            for line in source_lines:
                stripped = line.strip()
                if stripped.startswith("@"):
                    decorator_lines.append(stripped)
                elif stripped.startswith("def "):
                    break

            for decorator_line in decorator_lines:
                self._analyze_decorator_line(decorator_line)

        except (OSError, TypeError):
            pass

    def _analyze_decorator_line(self, decorator_line: str) -> None:
        """Analyze a single decorator line."""
        try:
            decorator_name = decorator_line.replace("@", "").strip()

            if "(" in decorator_name:
                decorator_name = decorator_name.split("(")[0]

            # Common decorator patterns
            decorator_errors = {
                "require_auth": ["AUTH_REQUIRED", "AUTH_PERMISSION_DENIED"],
                "validate_input": ["VALIDATION_FAILED", "INVALID_INPUT"],
                "rate_limit": ["RATE_LIMIT_EXCEEDED"],
                "cache": ["CACHE_ERROR"],
            }

            if decorator_name in decorator_errors:
                errors = decorator_errors[decorator_name]
                self.errors.update(errors)
                self.decorator_errors.append(
                    {
                        "decorator": decorator_name,
                        "possible_errors": errors,
                        "type": "decorator_analysis",
                    }
                )

        except Exception:
            pass

    def _analyze_builtin_function(self, func: Callable) -> None:
        """Analyze built-in functions for common error patterns using existing converters."""
        func_name = getattr(func, "__name__", str(func))
        module_name = getattr(func, "__module__", "")

        # SQLAlchemy errors - use existing SQL converter knowledge
        if "sqlalchemy" in module_name.lower():
            self._add_sqlalchemy_errors()

        # JSON errors
        elif func_name in ["loads", "dumps"] and "json" in module_name:
            self.errors.add("INVALID_FORMAT")

        # HTTP client errors
        elif "requests" in module_name or "httpx" in module_name:
            self.errors.update(["INTERNAL_ERROR", "NETWORK_ERROR"])

    def _add_sqlalchemy_errors(self) -> None:
        """Add SQLAlchemy errors using existing converter knowledge."""
        from ..converters.sql_converter import SQLErrorConverter
        from ..core.error_codes import ErrorCode

        # Get all possible error codes from SQL converter patterns
        sql_error_codes = {
            code.value for code, _message in SQLErrorConverter.SQL_PATTERNS.values()
        }

        # Add common SQLAlchemy errors based on existing converter
        sql_error_codes.update(
            [
                ErrorCode.DB_CONNECTION_ERROR.value,
                ErrorCode.DB_QUERY_ERROR.value,
                ErrorCode.DB_TRANSACTION_ERROR.value,
            ]
        )

        self.errors.update(sql_error_codes)
