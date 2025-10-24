"""
Example demonstrating translation fallback logic.
"""

from awesome_errors import ErrorTranslator

# Create translator with only English and Ukrainian
translator = ErrorTranslator()

# Add custom translations
translator.add_translations(
    "en",
    {
        "CUSTOM_ERROR_1": "This error has English translation",
        "CUSTOM_ERROR_2": "Another English error",
    },
)

translator.add_translations(
    "uk",
    {
        "CUSTOM_ERROR_1": "Ця помилка має український переклад",
        # Note: CUSTOM_ERROR_2 is not translated to Ukrainian
    },
)

# Test translation fallback logic
print("=== Translation Fallback Examples ===")

# Case 1: Ukrainian exists -> use Ukrainian
result = translator.translate("CUSTOM_ERROR_1", locale="uk")
print(f"uk -> CUSTOM_ERROR_1: {result}")
# Output: "Ця помилка має український переклад"

# Case 2: Ukrainian doesn't exist but English does -> fallback to English
result = translator.translate("CUSTOM_ERROR_2", locale="uk")
print(f"uk -> CUSTOM_ERROR_2 (fallback): {result}")
# Output: "Another English error"

# Case 3: Neither Ukrainian nor English exists -> return error code
result = translator.translate("NONEXISTENT_ERROR", locale="uk")
print(f"uk -> NONEXISTENT_ERROR (no translation): {result}")
# Output: "NONEXISTENT_ERROR"

# Case 4: Requesting English directly
result = translator.translate("CUSTOM_ERROR_1", locale="en")
print(f"en -> CUSTOM_ERROR_1: {result}")
# Output: "This error has English translation"

print("\n=== Fallback Chain ===")
print("1. Try requested locale (uk)")
print("2. If not found, try English (en)")
print("3. If still not found, return error code")
