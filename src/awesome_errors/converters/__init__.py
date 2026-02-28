from __future__ import annotations

from typing import Any

from .python_converter import PythonErrorConverter
from .sql_converter import SQLErrorConverter
from .universal_converter import UniversalErrorConverter

PydanticErrorConverter: Any
try:  # pragma: no cover - optional dependency
    from .pydantic_converter import PydanticErrorConverter as PydanticErrorConverter
except ImportError:  # pragma: no cover

    class _FallbackPydanticErrorConverter:
        """Placeholder raising a helpful message when pydantic is missing."""

        @staticmethod
        def convert(*_args: Any, **_kwargs: Any) -> Any:
            raise ImportError(
                "Install 'awesome-errors[pydantic]' to enable Pydantic error conversions."
            )

    PydanticErrorConverter = _FallbackPydanticErrorConverter


__all__ = [
    "SQLErrorConverter",
    "PythonErrorConverter",
    "PydanticErrorConverter",
    "UniversalErrorConverter",
]
