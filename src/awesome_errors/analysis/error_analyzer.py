import ast
import inspect
from typing import Set, List, Dict, Any, Optional, Callable


class ErrorAnalyzer(ast.NodeVisitor):
    """AST analyzer to find all possible errors in a function."""

    def __init__(
        self, function: Callable, max_depth: int = 10, analyze_decorators: bool = True
    ):
        """
        Initialize error analyzer.

        Args:
            function: Function to analyze
            max_depth: Maximum depth for recursive analysis
            analyze_decorators: Whether to analyze decorators
        """
        self.function = function
        self.max_depth = max_depth
        self.analyze_decorators = analyze_decorators
        self.current_depth = 0
        self.errors: Set[str] = set()
        self.error_details: List[Dict[str, Any]] = []
        self.visited_functions: Set[str] = set()
        self.decorator_errors: List[Dict[str, Any]] = []

    def analyze(self) -> Dict[str, Any]:
        """
        Analyze function for all possible errors.

        Returns:
            Dictionary with error analysis results
        """
        # Reset state
        self.errors.clear()
        self.error_details.clear()
        self.visited_functions.clear()
        self.decorator_errors.clear()
        self.current_depth = 0

        # Analyze decorators first
        if self.analyze_decorators:
            self._analyze_decorators(self.function)

        # Analyze the main function
        self._analyze_function(self.function, is_main=True)

        return {
            "function_name": self.function.__name__,
            "error_codes": sorted(list(self.errors)),
            "error_details": self.error_details,
            "decorator_errors": self.decorator_errors,
            "total_errors": len(self.errors),
            "analysis_depth": self.current_depth,
            "max_depth_reached": self.current_depth >= self.max_depth,
        }

    def _analyze_function(self, func: Callable, is_main: bool = False) -> None:
        """Analyze a specific function for errors with depth control."""
        if self.current_depth >= self.max_depth and not is_main:
            return

        func_name = f"{func.__module__}.{func.__qualname__}"

        # Avoid infinite recursion
        if func_name in self.visited_functions:
            return

        self.visited_functions.add(func_name)

        if not is_main:
            self.current_depth += 1

        try:
            # Get function source and parse AST
            source = inspect.getsource(func)
            # Remove leading indentation to avoid IndentationError
            import textwrap

            source = textwrap.dedent(source)
            tree = ast.parse(source)

            # Visit AST nodes
            self.visit(tree)

        except (OSError, TypeError):
            # Can't get source - try to infer common library errors
            self._analyze_builtin_function(func)

        if not is_main:
            self.current_depth -= 1

    def visit_Raise(self, node: ast.Raise) -> None:
        """Handle raise statements."""
        if node.exc:
            error_info = self._extract_error_info(node.exc)
            if error_info:
                self.errors.add(error_info["code"])
                self.error_details.append(error_info)

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Enhanced call analysis with context-aware error detection."""
        # Analyze call context for known error patterns
        self._analyze_call_context(node)

        # Handle method calls (obj.method())
        if isinstance(node.func, ast.Attribute):
            self._analyze_method_call(node)

        # Handle regular function calls
        else:
            called_func = self._resolve_function_call(node)
            if called_func and self.current_depth < self.max_depth:
                self._analyze_function(called_func)

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

        # Async operations
        elif "await " in call_str:
            self.errors.update(["INTERNAL_ERROR", "TIMEOUT_ERROR"])

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

    def _analyze_method_call(self, node: ast.Call) -> None:
        """Analyze method calls by trying to resolve and analyze the actual method."""
        if isinstance(node.func, ast.Attribute):
            # Try to resolve the actual method and analyze it
            resolved_method = self._resolve_method_call(node)
            if resolved_method and self.current_depth < self.max_depth:
                self._analyze_function(resolved_method)

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
        sql_error_codes = set()
        for pattern, (code, message) in SQLErrorConverter.SQL_PATTERNS.items():
            sql_error_codes.add(code.value)

        # Add common SQLAlchemy errors based on existing converter
        sql_error_codes.update(
            [
                ErrorCode.DB_CONNECTION_ERROR.value,
                ErrorCode.DB_QUERY_ERROR.value,
                ErrorCode.DB_TRANSACTION_ERROR.value,
            ]
        )

        self.errors.update(sql_error_codes)

    def _resolve_method_call(self, node: ast.Call) -> Optional[Callable]:
        """Try to resolve method call to actual method object."""
        # For now, return None but analyze based on context
        # This is complex and would require runtime introspection
        return None

    def _resolve_function_call(self, node: ast.Call) -> Optional[Callable]:
        """Try to resolve function call to actual function object."""
        # For now, return None but analyze based on context
        # This is complex and would require runtime introspection
        return None
