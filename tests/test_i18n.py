import pytest
import tempfile
import json
from pathlib import Path

from awesome_errors import ErrorTranslator


class TestErrorTranslator:
    """Test error translator functionality."""

    def test_basic_translation(self):
        """Test basic error translation."""
        translator = ErrorTranslator()

        # Should translate built-in error codes
        result = translator.translate("USER_NOT_FOUND", locale="en")
        assert result == "User not found"

        result = translator.translate("USER_NOT_FOUND", locale="uk")
        assert result == "Користувача не знайдено"

    def test_fallback_to_english(self):
        """Test fallback to English when translation not found."""
        translator = ErrorTranslator()

        # Add English translation only
        translator.add_translations("en", {"CUSTOM_ERROR": "Custom error in English"})

        # Request Ukrainian (should fallback to English)
        result = translator.translate("CUSTOM_ERROR", locale="uk")
        assert result == "Custom error in English"

    def test_fallback_to_error_code(self):
        """Test fallback to error code when no translation found."""
        translator = ErrorTranslator()

        # Request non-existent error code
        result = translator.translate("NONEXISTENT_ERROR", locale="uk")
        assert result == "NONEXISTENT_ERROR"

    def test_default_locale(self):
        """Test default locale behavior."""
        translator = ErrorTranslator(default_locale="uk")

        # Should use Ukrainian as default
        result = translator.translate("USER_NOT_FOUND")
        assert result == "Користувача не знайдено"

    def test_add_translations(self):
        """Test adding custom translations."""
        translator = ErrorTranslator()

        custom_translations = {
            "CUSTOM_ERROR_1": "First custom error",
            "CUSTOM_ERROR_2": "Second custom error",
        }

        translator.add_translations("en", custom_translations)

        assert translator.translate("CUSTOM_ERROR_1", "en") == "First custom error"
        assert translator.translate("CUSTOM_ERROR_2", "en") == "Second custom error"

    def test_message_formatting(self):
        """Test message formatting with parameters."""
        translator = ErrorTranslator()

        translator.add_translations(
            "en", {"USER_ERROR": "User {username} has {error_count} errors"}
        )

        result = translator.translate(
            "USER_ERROR", locale="en", params={"username": "john", "error_count": 5}
        )

        assert result == "User john has 5 errors"

    def test_message_formatting_error_handling(self):
        """Test message formatting with invalid parameters."""
        translator = ErrorTranslator()

        translator.add_translations(
            "en", {"TEMPLATE_ERROR": "User {username} has {missing_param} errors"}
        )

        # Should not crash with missing parameters
        result = translator.translate(
            "TEMPLATE_ERROR", locale="en", params={"username": "john"}
        )

        # Should return unformatted message
        assert "User {username} has {missing_param} errors" in result

    def test_custom_locales_directory(self):
        """Test using custom locales directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            locales_dir = Path(temp_dir) / "locales"

            # Create custom locale structure
            en_dir = locales_dir / "en"
            en_dir.mkdir(parents=True)

            custom_errors = {"CUSTOM_ERROR": "Custom error message"}

            with open(en_dir / "errors.json", "w") as f:
                json.dump(custom_errors, f)

            # Initialize translator with custom directory
            translator = ErrorTranslator(locales_dir=locales_dir)

            result = translator.translate("CUSTOM_ERROR", "en")
            assert result == "Custom error message"

    def test_get_available_locales(self):
        """Test getting available locales."""
        translator = ErrorTranslator()

        # Should have at least English and Ukrainian
        locales = translator.get_available_locales()
        assert "en" in locales
        assert "uk" in locales

    def test_add_translations_saves_to_file(self):
        """Test that add_translations saves to file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            locales_dir = Path(temp_dir) / "locales"
            translator = ErrorTranslator(locales_dir=locales_dir)

            custom_translations = {"TEST_ERROR": "Test error message"}

            translator.add_translations("test", custom_translations)

            # Check that file was created
            test_file = locales_dir / "test" / "errors.json"
            assert test_file.exists()

            # Check file contents
            with open(test_file) as f:
                saved_translations = json.load(f)

            assert saved_translations["TEST_ERROR"] == "Test error message"

    def test_invalid_locale_files_ignored(self):
        """Test that invalid locale files are ignored."""
        with tempfile.TemporaryDirectory() as temp_dir:
            locales_dir = Path(temp_dir) / "locales"

            # Create invalid JSON file
            invalid_dir = locales_dir / "invalid"
            invalid_dir.mkdir(parents=True)

            with open(invalid_dir / "errors.json", "w") as f:
                f.write("invalid json content {")

            # Should not crash
            translator = ErrorTranslator(locales_dir=locales_dir)

            # Should not have invalid locale
            locales = translator.get_available_locales()
            assert "invalid" not in locales

    def test_unicode_translations(self):
        """Test Unicode character support in translations."""
        translator = ErrorTranslator()

        unicode_translations = {
            "UNICODE_ERROR": "Помилка з україськими символами 🇺🇦",
            "EMOJI_ERROR": "Error with emojis 😊✨🚀",
        }

        translator.add_translations("test", unicode_translations)

        result1 = translator.translate("UNICODE_ERROR", "test")
        assert result1 == "Помилка з україськими символами 🇺🇦"

        result2 = translator.translate("EMOJI_ERROR", "test")
        assert result2 == "Error with emojis 😊✨🚀"

    def test_translation_caching(self):
        """Test that translations are cached properly."""
        translator = ErrorTranslator()

        # First translation
        result1 = translator.translate("USER_NOT_FOUND", "en")

        # Second identical translation (should use cache)
        result2 = translator.translate("USER_NOT_FOUND", "en")

        assert result1 == result2
        assert result1 == "User not found"

    def test_empty_translations_dict(self):
        """Test behavior with empty translations dictionary."""
        translator = ErrorTranslator()

        translator.add_translations("empty", {})

        # Should fallback to error code
        result = translator.translate("ANY_ERROR", "empty")
        assert result == "ANY_ERROR"

    def test_none_parameters(self):
        """Test translation with None parameters."""
        translator = ErrorTranslator()

        translator.add_translations("en", {"SIMPLE_ERROR": "Simple error message"})

        # Should work with None parameters
        result = translator.translate("SIMPLE_ERROR", "en", params=None)
        assert result == "Simple error message"

    def test_locale_case_sensitivity(self):
        """Test locale case sensitivity."""
        translator = ErrorTranslator()

        # Test different cases
        result_lower = translator.translate("USER_NOT_FOUND", "en")
        result_upper = translator.translate("USER_NOT_FOUND", "EN")

        # "EN" should fallback to error code since it doesn't exist
        assert result_lower == "User not found"
        assert result_upper == "USER_NOT_FOUND"


if __name__ == "__main__":
    pytest.main([__file__])
