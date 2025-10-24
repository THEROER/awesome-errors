# Awesome Errors

A comprehensive Python library for standardized error handling, analysis, and documentation.

## Architecture Overview

### Core Components

#### 1. **Core Exceptions** (`src/awesome_errors/core/`)

- **AppError**: Base exception class for server-side error handling
- **ValidationError**: HTTP 400 errors for input validation failures
- **AuthError**: HTTP 401/403 errors for authentication/authorization
- **NotFoundError**: HTTP 404 errors for missing resources
- **DatabaseError**: HTTP 500/409/422 errors for database issues
- **BusinessLogicError**: HTTP 422 errors for business rule violations

#### 2. **Client Exceptions** (`src/awesome_errors/client/`)

- **BackendError**: Client-side exception for handling server responses
- **ErrorResponseParser**: Parser for backend error responses

**Key Difference**: Core exceptions are raised on the server, while client exceptions handle errors received from the server.

#### 3. **Error Converters** (`src/awesome_errors/converters/`)

- **UniversalErrorConverter**: Handles any type of exception
- **SQLErrorConverter**: Converts SQLAlchemy errors
- **PythonErrorConverter**: Converts standard Python exceptions
- **PydanticErrorConverter**: Converts Pydantic validation errors
- **generic_error_handler**: Shared logic for unknown errors

#### 4. **Analysis Tools** (`src/awesome_errors/analysis/`)

- **ErrorAnalyzer**: AST-based error analysis
- **analyze_errors**: Decorator for automatic error analysis
- **openapi_errors**: Decorator for OpenAPI documentation

#### 5. **FastAPI Integration** (`src/awesome_errors/integrations/`)

- **setup_automatic_error_docs**: Automatic OpenAPI documentation
- **auto_analyze_errors**: Combined analysis + OpenAPI integration
- **apply_auto_error_docs_to_router**: Router-specific documentation

#### 6. **Internationalization** (`src/awesome_errors/i18n/`)

- **ErrorTranslator**: Multi-language error message support
- Locale files in `src/awesome_errors/i18n/locales/`

#### 7. **Middleware** (`src/awesome_errors/middleware/`)

- **setup_error_handling**: FastAPI error handling middleware

## Usage Examples

### Server-Side Error Handling

```python
from awesome_errors import ValidationError, NotFoundError, ErrorCode

# Validation error
raise ValidationError("Email is required", field="email")

# Not found error
raise NotFoundError("user", user_id=123)

# Custom error code
raise ValidationError("Invalid format", code=ErrorCode("CUSTOM_ERROR"))
```

### Client-Side Error Handling

```python
from awesome_errors import BackendError

try:
    response = api_client.get_user(123)
except BackendError as e:
    if e.is_not_found_error():
        print("User not found")
    elif e.is_validation_error():
        print("Invalid input")
```

### FastAPI Integration

```python
from fastapi import FastAPI
from awesome_errors import setup_error_handling, auto_analyze_errors

app = FastAPI()
setup_error_handling(app)

@auto_analyze_errors
@app.get("/users/{user_id}")
def get_user(user_id: int):
    if user_id == 404:
        raise NotFoundError("user", user_id)
    return {"id": user_id}
```

### Error Analysis

```python
from awesome_errors import analyze_errors, openapi_errors

@analyze_errors()
def my_function():
    raise ValidationError("Test error")

@openapi_errors(additional_errors=["CUSTOM_ERROR"])
def my_api_endpoint():
    # Automatically documented in OpenAPI
    pass
```

## Key Features

### ✅ **Unified Error Models**

- Single `ErrorDetail` and `ErrorResponse` models used throughout
- No duplicate model definitions
- Consistent error structure

### ✅ **Shared Generic Error Handling**

- Common `generic_error_handler` for unknown errors
- Used by all converters to avoid code duplication
- Debug mode support for detailed error information

### ✅ **Consolidated FastAPI Integration**

- Single entry point for all FastAPI integrations
- Automatic OpenAPI documentation generation
- Combined analysis and documentation decorators

### ✅ **Clean Architecture**

- Clear separation between server and client error handling
- Modular converter system
- Comprehensive documentation

### ✅ **Internationalization Support**

- Multi-language error messages
- Locale-based translation
- Template parameter support

## Installation

```bash
pip install awesome-errors
```

## Development

```bash
# Install dependencies
poetry install

# Run tests
pytest

# Run linting
ruff check src/
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details.
