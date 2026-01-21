# tests/utils/test_error_sanitizer.py
import pytest
from src.utils.error_sanitizer import ErrorSanitizer


class TestErrorSanitizer:
    def test_removes_file_paths(self):
        raw = "Error at /home/user/project/src/module.py:123"
        result = ErrorSanitizer.sanitize(raw)
        assert "/home/user" not in result
        assert "module.py:123" not in result

    def test_removes_stack_trace(self):
        raw = """Traceback (most recent call last):
  File "/opt/odoo/server.py", line 456
    result = execute()
ValueError: Invalid field"""
        result = ErrorSanitizer.sanitize(raw)
        assert "Traceback" not in result
        assert "Invalid field" in result

    def test_preserves_field_name(self):
        raw = "Invalid field res.partner.supplier in leaf"
        result = ErrorSanitizer.sanitize(raw)
        assert "supplier" in result
        assert "res.partner" in result

    def test_preserves_model_name(self):
        raw = "Access denied to model sale.order"
        result = ErrorSanitizer.sanitize(raw)
        assert "sale.order" in result

    def test_maps_common_errors(self):
        raw = "xmlrpc.client.Fault: Access Denied"
        result = ErrorSanitizer.sanitize(raw)
        assert "Access" in result
        assert "xmlrpc" not in result

    def test_none_input(self):
        """Test handling of None input."""
        result = ErrorSanitizer.sanitize(None)
        assert result == "An unknown error occurred."

    def test_empty_string_input(self):
        """Test handling of empty string input."""
        result = ErrorSanitizer.sanitize("")
        assert result == "An unknown error occurred."

    def test_unicode_characters(self):
        """Test handling of Unicode characters in error messages."""
        raw = "ValidationError: Invalid value for field 'café' with symbol €"
        result = ErrorSanitizer.sanitize(raw)
        assert "café" in result
        assert "€" in result
        assert "Validation failed" in result

    def test_very_long_message(self):
        """Test handling of very long error messages."""
        long_detail = "x" * 1000
        raw = f"UserError: {long_detail}"
        result = ErrorSanitizer.sanitize(raw)
        assert "Operation failed" in result
        assert len(result) > 0

    def test_contains_useful_info_with_model_name(self):
        """Test _contains_useful_info detects Odoo model names."""
        error_detail = "Error with sale.order record"
        result = ErrorSanitizer.sanitize(f"ValidationError: {error_detail}")
        # Should include details because it has useful model name
        assert "Details:" in result
        assert "sale.order" in result

    def test_contains_useful_info_with_field_name(self):
        """Test _contains_useful_info detects field names."""
        error_detail = "Invalid field 'partner_id' in model"
        result = ErrorSanitizer.sanitize(f"ValidationError: {error_detail}")
        # Should include details because it has useful field name
        assert "Details:" in result
        assert "partner_id" in result

    def test_contains_useful_info_without_model_or_field(self):
        """Test _contains_useful_info returns False for generic messages."""
        error_detail = "Something went wrong"
        result = ErrorSanitizer.sanitize(f"ValidationError: {error_detail}")
        # Should not include details for generic message
        assert "Validation failed" in result
        assert "Details:" not in result

    def test_error_mapping_redirect_warning(self):
        """Test RedirectWarning mapping."""
        raw = "RedirectWarning: Please configure your settings"
        result = ErrorSanitizer.sanitize(raw)
        assert "Action required" in result
        assert "RedirectWarning" not in result

    def test_error_mapping_warning(self):
        """Test Warning mapping."""
        raw = "Warning: This operation may take time"
        result = ErrorSanitizer.sanitize(raw)
        assert "Warning:" in result
        assert "review" in result

    def test_error_mapping_qweb_exception(self):
        """Test QWebException mapping."""
        raw = "QWebException: Template not found"
        result = ErrorSanitizer.sanitize(raw)
        assert "Template rendering error" in result
        assert "QWebException" not in result

    def test_no_standard_error_format(self):
        """Test handling of messages without standard Error/Exception format."""
        raw = "Something went wrong without standard format"
        result = ErrorSanitizer.sanitize(raw)
        assert result == "Something went wrong without standard format"

    def test_error_with_no_detail_returns_fallback(self):
        """Test that cleaning removes all content returns fallback message."""
        raw = "ValueError: "
        result = ErrorSanitizer.sanitize(raw)
        # Empty detail after cleaning should return fallback
        assert result == "An error occurred during the operation."

    def test_multiple_patterns_removal(self):
        """Test removal of multiple patterns in single message."""
        raw = """Traceback (most recent call last):
  File "/home/user/odoo/addons/module.py", line 123
  File "/opt/odoo/lib/base.py", line 456
xmlrpc.client.Fault: psycopg2.errors.UniqueViolation: ValidationError: Duplicate entry"""
        result = ErrorSanitizer.sanitize(raw)
        assert "/home/user" not in result
        assert "/opt/odoo" not in result
        assert "xmlrpc.client" not in result
        assert "psycopg2" not in result
        assert "Traceback" not in result
        assert "Validation failed" in result

    def test_preserves_detail_with_model_and_field(self):
        """Test that details with model and field names are preserved."""
        raw = "AccessError: Access denied to field partner_id on model res.partner"
        result = ErrorSanitizer.sanitize(raw)
        assert "Access denied" in result
        assert "partner_id" in result
        assert "res.partner" in result
        assert "Details:" in result

    def test_clean_detail_strips_quotes(self):
        """Test that _clean_detail removes leading/trailing quotes."""
        raw = "UserError: 'This is quoted'"
        result = ErrorSanitizer.sanitize(raw)
        assert result == "Operation failed. Please check your input."

    def test_regex_pattern_last_line_without_newline(self):
        """Test that regex handles last traceback line without newline."""
        raw = 'Traceback (most recent call last):\n  File "test.py", line 1, in module'
        result = ErrorSanitizer.sanitize(raw)
        # Should not fail and should remove the file reference
        assert "File" not in result or result == "An error occurred during the operation."
