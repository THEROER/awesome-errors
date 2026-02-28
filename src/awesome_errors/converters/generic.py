from ..core.exceptions import AppError
from ..core.error_codes import ErrorCode


def generic_error_handler(error: Exception, debug: bool = False) -> AppError:
    error_type = type(error).__name__
    error_module = type(error).__module__
    details: dict[str, object] = {
        "error_type": error_type,
        "error_module": error_module,
    }
    if debug:
        details["error_str"] = str(error)
        details["error_repr"] = repr(error)
        if hasattr(error, "__dict__"):
            details["error_attrs"] = {
                k: str(v) for k, v in error.__dict__.items() if not k.startswith("_")
            }
    return AppError(
        code=ErrorCode.INTERNAL_ERROR,
        message=f"Unexpected error: {error_type}",
        details=details,
    )
