from .sql_converter import SQLErrorConverter
from .python_converter import PythonErrorConverter
from .universal_converter import UniversalErrorConverter

try:  # pragma: no cover - optional dependency
    from .pydantic_converter import PydanticErrorConverter
except ImportError:  # pragma: no cover
    class PydanticErrorConverter:  # type: ignore[dead-code]
        """Placeholder raising a helpful message when pydantic is missing."""

        @staticmethod
        def convert(*_args, **_kwargs):
            raise ImportError(
                "Install 'awesome-errors[pydantic]' to enable Pydantic error conversions."
            )

__all__ = [
    "SQLErrorConverter",
    "PythonErrorConverter",
    "PydanticErrorConverter",
    "UniversalErrorConverter",
]
