# src/utils/error_sanitizer.py
"""
Error sanitization for user-friendly error messages.
Inspired by mcp-server-odoo error handling patterns.
"""
import re
from typing import Optional


class ErrorSanitizer:
    """
    Sanitizes error messages by removing internal implementation details
    while preserving useful information for the user.
    """

    # Patterns to remove from error messages
    REMOVE_PATTERNS = [
        # File paths with line numbers
        r'/[\w/.-]+\.py:\d+',
        r'/[\w/.-]+\.py',
        # Home directory paths
        r'/home/[\w/.-]+',
        r'/opt/[\w/.-]+',
        r'/usr/[\w/.-]+',
        # Stack traces
        r'Traceback \(most recent call last\):.*?(?=\w+Error:|\w+Exception:|\Z)',
        r'File ".*?", line \d+.*?\n?',
        # Python module internals
        r'xmlrpc\.client\.',
        r'odoo\.exceptions\.',
        r'psycopg2\.\w+\.',
    ]

    # Error message mappings for common errors
    ERROR_MAPPINGS = {
        "Access Denied": "Access denied. You don't have permission for this operation.",
        "ValidationError": "Validation failed. Please check your input.",
        "UserError": "Operation failed. Please check your input.",
        "MissingError": "Record not found. It may have been deleted.",
        "AccessError": "Access denied to this record or model.",
        "RedirectWarning": "Action required. Please review the details.",
        "Warning": "Warning: Please review the following information.",
        "QWebException": "Template rendering error. Please check the view configuration.",
    }

    @classmethod
    def sanitize(cls, error_message: str) -> str:
        """
        Sanitize an error message for user display.

        Args:
            error_message: Raw error message (may contain paths, traces)

        Returns:
            Clean, user-friendly error message
        """
        if not error_message:
            return "An unknown error occurred."

        result = str(error_message)

        # Extract the main error type and message
        # Pattern: "SomeError: actual message" or "SomeException: message" or "SomeWarning: message"
        error_match = re.search(r'(\w*Error|\w*Exception|\w*Warning):\s*(.+?)(?:\n|$)', result, re.DOTALL)
        if error_match:
            error_type = error_match.group(1)
            error_detail = error_match.group(2).strip()

            # Use mapped message if available
            for key, mapped_msg in cls.ERROR_MAPPINGS.items():
                if key in error_type or key in error_detail:
                    # Append specific detail if it contains useful info
                    if cls._contains_useful_info(error_detail):
                        return f"{mapped_msg} Details: {cls._clean_detail(error_detail)}"
                    return mapped_msg

            # Otherwise, clean and return the detail
            result = cls._clean_detail(error_detail)
        else:
            # No standard error format, just clean the whole message
            result = cls._clean_detail(result)

        return result if result else "An error occurred during the operation."

    @classmethod
    def _contains_useful_info(cls, message: str) -> bool:
        """Check if text contains useful info like model/field names."""
        # Check for Odoo model names
        if re.search(r'\b[a-z]+\.[a-z_]+\b', message):
            return True
        # Check for field names
        if re.search(r"field[s]?\s+['\"]?\w+['\"]?", message, re.IGNORECASE):
            return True
        return False

    @classmethod
    def _clean_detail(cls, detail: str) -> str:
        """Remove technical details while preserving useful info."""
        result = detail

        # Remove patterns
        for pattern in cls.REMOVE_PATTERNS:
            result = re.sub(pattern, '', result, flags=re.DOTALL | re.MULTILINE)

        # Clean up multiple whitespace/newlines
        result = re.sub(r'\s+', ' ', result).strip()

        # Remove leading/trailing quotes
        result = result.strip('"\'')

        return result
