import json
from pathlib import Path
from typing import Dict, Optional, Any


class ErrorTranslator:
    """Translator for error messages with i18n support."""

    def __init__(self, locales_dir: Optional[Path] = None, default_locale: str = "en"):
        """
        Initialize translator.

        Args:
            locales_dir: Directory containing locale files
            default_locale: Default locale to use
        """
        self.locales_dir = locales_dir or Path(__file__).parent / "locales"
        self.default_locale = default_locale
        self._translations: Dict[str, Dict[str, str]] = {}
        self._load_translations()

    def _load_translations(self) -> None:
        """Load all translation files."""
        if not self.locales_dir.exists():
            self.locales_dir.mkdir(parents=True, exist_ok=True)
            # Create default English translations
            self._create_default_translations()

        for locale_file in self.locales_dir.glob("*/errors.json"):
            locale = locale_file.parent.name
            try:
                with open(locale_file, "r", encoding="utf-8") as f:
                    self._translations[locale] = json.load(f)
            except Exception:
                # Skip invalid files
                pass

    def _create_default_translations(self) -> None:
        """Create default English translations."""
        en_dir = self.locales_dir / "en"
        en_dir.mkdir(exist_ok=True)

        default_translations = {
            # General errors
            "UNKNOWN_ERROR": "An unknown error occurred",
            "INTERNAL_ERROR": "Internal server error",
            # Validation errors
            "VALIDATION_FAILED": "Validation failed",
            "INVALID_INPUT": "Invalid input provided",
            "MISSING_REQUIRED_FIELD": "Required field is missing",
            "INVALID_FORMAT": "Invalid format",
            # Authentication errors
            "AUTH_REQUIRED": "Authentication required",
            "AUTH_INVALID_TOKEN": "Invalid authentication token",
            "AUTH_TOKEN_EXPIRED": "Authentication token has expired",
            # Authorization errors
            "AUTH_PERMISSION_DENIED": "Permission denied",
            "AUTH_INSUFFICIENT_PRIVILEGES": "Insufficient privileges",
            # Not found errors
            "RESOURCE_NOT_FOUND": "Resource not found",
            "USER_NOT_FOUND": "User not found",
            "ENTITY_NOT_FOUND": "Entity not found",
            # Database errors
            "DB_CONNECTION_ERROR": "Database connection error",
            "DB_QUERY_ERROR": "Database query error",
            "DB_CONSTRAINT_VIOLATION": "Database constraint violated",
            "DB_DUPLICATE_ENTRY": "Duplicate entry",
            "DB_INVALID_REFERENCE": "Invalid reference",
            "DB_MISSING_REQUIRED": "Missing required field",
            # Business logic errors
            "BUSINESS_RULE_VIOLATION": "Business rule violated",
            "INSUFFICIENT_BALANCE": "Insufficient balance",
            "OPERATION_NOT_ALLOWED": "Operation not allowed",
        }

        with open(en_dir / "errors.json", "w", encoding="utf-8") as f:
            json.dump(default_translations, f, indent=2, ensure_ascii=False)

        self._translations["en"] = default_translations

    def translate(
        self,
        error_code: str,
        locale: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Translate error code to message.

        Args:
            error_code: Error code to translate
            locale: Locale to use (e.g., 'en', 'uk')
            params: Parameters for message formatting

        Returns:
            Translated message
        """
        locale = locale or self.default_locale

        # Try requested locale
        if locale in self._translations:
            message = self._translations[locale].get(error_code)
            if message:
                return self._format_message(message, params)

        # Fallback to English if available and different from requested locale (case sensitive)
        if "en" in self._translations and locale.lower() != "en":
            message = self._translations["en"].get(error_code)
            if message:
                return self._format_message(message, params)

        # Return error code if no translation found
        return error_code

    def _format_message(self, message: str, params: Optional[Dict[str, Any]]) -> str:
        """Format message with parameters."""
        if not params:
            return message

        try:
            return message.format(**params)
        except Exception:
            # Return unformatted message if formatting fails
            return message

    def add_translations(
        self, locale: str, translations: Dict[str, str], *, persist: bool = True
    ) -> None:
        """Add or update translations for a locale.

        Args:
            locale: Locale identifier
            translations: Mapping of error codes to translated messages
            persist: Persist changes to disk. Set to ``False`` for ephemeral usage.
        """
        if locale not in self._translations:
            self._translations[locale] = {}

        self._translations[locale].update(translations)

        if persist:
            locale_dir = self.locales_dir / locale
            locale_dir.mkdir(exist_ok=True)

            with open(locale_dir / "errors.json", "w", encoding="utf-8") as f:
                json.dump(self._translations[locale], f, indent=2, ensure_ascii=False)

    def get_available_locales(self) -> list[str]:
        """Get list of available locales."""
        return list(self._translations.keys())
