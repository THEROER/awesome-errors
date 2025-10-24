"""
Example of using awesome-errors with FastAPI backend.
"""

from fastapi import FastAPI
from awesome_errors import (
    setup_error_handling,
    NotFoundError,
    ValidationError,
    ErrorCode,
)

app = FastAPI()

# Method 1: Simple setup with custom translations
custom_translations = {
    "en": {
        "USER_NOT_FOUND": "User could not be found",
        "EMAIL_ALREADY_EXISTS": "This email is already registered",
        "CUSTOM_BUSINESS_ERROR": "Custom business rule violated",
    },
    "uk": {
        "USER_NOT_FOUND": "Користувача не знайдено",
        "EMAIL_ALREADY_EXISTS": "Цей email вже зареєстровано",
        "CUSTOM_BUSINESS_ERROR": "Порушено користувацьке бізнес-правило",
    },
}

setup_error_handling(
    app, debug=False, custom_translations=custom_translations, default_locale="en"
)

# Method 2: Advanced setup with custom locales directory
"""
# If you have your own locales directory structure:
# locales/
#   en/errors.json
#   uk/errors.json

setup_error_handling(
    app,
    locales_dir="./locales",
    default_locale="en"
)
"""

# Method 3: Manual translator setup
"""
translator = ErrorTranslator(default_locale="en")

# Add translations programmatically
translator.add_translations("uk", {
    "CUSTOM_ERROR": "Користувацька помилка"
})

setup_error_handling(app, translator=translator)
"""


@app.get("/users/{user_id}")
def get_user(user_id: int):
    """Example endpoint that raises translated errors."""
    if user_id == 404:
        raise NotFoundError("user", user_id)

    if user_id == 999:
        # Custom error with translation
        raise ValidationError(
            "Custom validation error", code=ErrorCode("CUSTOM_BUSINESS_ERROR")
        )

    return {"id": user_id, "name": "John Doe"}


@app.post("/users")
def create_user(email: str):
    """Example endpoint with email validation."""
    if email == "existing@example.com":
        # This will be translated based on Accept-Language header
        raise ValidationError(
            "Email already exists",
            field="email",
            value=email,
            code=ErrorCode("EMAIL_ALREADY_EXISTS"),
        )

    return {"email": email, "message": "User created"}


if __name__ == "__main__":
    import uvicorn  # type: ignore

    uvicorn.run(app, host="0.0.0.0", port=8000)
