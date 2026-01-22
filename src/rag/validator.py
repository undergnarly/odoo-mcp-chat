"""
Value Validator for Odoo operations.

Validates and converts values before sending to Odoo:
- Type conversion (string "100" -> int 100)
- Date/datetime parsing (various formats -> Odoo format)
- Selection value validation (check against allowed values)
- Required field checking
"""

import logging
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional

from src.rag.schema_cache import OdooSchemaCache, FieldSchema

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when validation fails."""
    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__(f"Validation failed: {'; '.join(errors)}")


class OdooValueValidator:
    """
    Validates and converts values before write operations.

    Usage:
        validator = OdooValueValidator(schema_cache)
        validated, errors = validator.validate_and_convert("sale.order", {"state": "done", "amount": "100"})
        if errors:
            print("Validation errors:", errors)
        else:
            # Safe to write validated values to Odoo
    """

    # Date formats to try when parsing
    DATE_FORMATS = [
        '%Y-%m-%d',           # ISO format (Odoo default)
        '%d.%m.%Y',           # European format
        '%d/%m/%Y',           # European with slash
        '%m/%d/%Y',           # US format
        '%Y-%m-%d %H:%M:%S',  # ISO with time (extract date)
    ]

    # Datetime formats to try when parsing
    DATETIME_FORMATS = [
        '%Y-%m-%d %H:%M:%S',  # ISO format (Odoo default)
        '%Y-%m-%dT%H:%M:%S',  # ISO with T separator
        '%Y-%m-%d %H:%M',     # Without seconds
        '%d.%m.%Y %H:%M:%S',  # European with time
        '%d.%m.%Y %H:%M',     # European without seconds
        '%d/%m/%Y %H:%M:%S',  # European with slash
        '%Y-%m-%d',           # Date only -> add 00:00:00
    ]

    def __init__(self, schema_cache: OdooSchemaCache):
        """
        Initialize validator.

        Args:
            schema_cache: OdooSchemaCache instance
        """
        self.schema_cache = schema_cache

    def validate_and_convert(
        self,
        model: str,
        values: Dict[str, Any],
        operation: str = "write"
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Validate and convert values for an Odoo operation.

        Args:
            model: Odoo model name
            values: Dict of field -> value to validate
            operation: "create" or "write" (affects required field checking)

        Returns:
            Tuple of (validated_values, errors)
            - validated_values: Dict with converted values (only valid fields)
            - errors: List of error messages (empty if all valid)
        """
        try:
            schema = self.schema_cache.get_model_schema(model)
        except Exception as e:
            logger.warning(f"Could not get schema for {model}, skipping validation: {e}")
            # Return original values if can't get schema
            return values, []

        validated = {}
        errors = []

        for field_name, value in values.items():
            # Check if field exists
            if field_name not in schema.fields:
                errors.append(f"Unknown field: {field_name}")
                logger.warning(f"Unknown field {field_name} in model {model}")
                continue

            field_schema = schema.fields[field_name]

            # Check readonly
            if field_schema.readonly:
                errors.append(f"Field '{field_name}' is readonly")
                continue

            # Validate and convert value
            try:
                converted = self._convert_value(value, field_schema)
                validated[field_name] = converted
            except ValueError as e:
                errors.append(f"Field '{field_name}': {e}")

        # Check required fields for create
        if operation == "create":
            required = schema.get_required_fields()
            for req_field in required:
                if req_field not in validated and req_field not in values:
                    # Don't error if it has a default or is computed
                    # Odoo will handle this
                    logger.debug(f"Required field {req_field} not provided for create")

        return validated, errors

    def _convert_value(self, value: Any, field_schema: FieldSchema) -> Any:
        """
        Convert a value to the correct type for the field.

        Args:
            value: Value to convert
            field_schema: Field schema with type info

        Returns:
            Converted value

        Raises:
            ValueError if conversion fails or value is invalid
        """
        # Handle None/null
        if value is None:
            if field_schema.required:
                raise ValueError("Required field cannot be null")
            return None

        field_type = field_schema.type

        # Integer fields
        if field_type == 'integer':
            return self._convert_integer(value)

        # Float/monetary fields
        elif field_type in ('float', 'monetary'):
            return self._convert_float(value)

        # Boolean fields
        elif field_type == 'boolean':
            return self._convert_boolean(value)

        # Date fields
        elif field_type == 'date':
            return self._convert_date(value)

        # Datetime fields
        elif field_type == 'datetime':
            return self._convert_datetime(value)

        # Selection fields - validate against allowed values
        elif field_type == 'selection':
            return self._convert_selection(value, field_schema)

        # Many2one - convert to integer ID
        elif field_type == 'many2one':
            return self._convert_many2one(value)

        # Many2many / One2many - convert to Odoo command format
        elif field_type in ('many2many', 'one2many'):
            return self._convert_x2many(value, field_schema)

        # Char, text, html - keep as string
        elif field_type in ('char', 'text', 'html'):
            return str(value) if value is not None else value

        # Binary - keep as-is (base64 encoded)
        elif field_type == 'binary':
            return value

        # Unknown type - return as-is
        else:
            return value

    def _convert_integer(self, value: Any) -> int:
        """Convert value to integer."""
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            # Remove whitespace and try to parse
            value = value.strip().replace(',', '').replace(' ', '')
            try:
                return int(float(value))  # Handle "100.0"
            except ValueError:
                raise ValueError(f"Cannot convert '{value}' to integer")
        raise ValueError(f"Cannot convert {type(value).__name__} to integer")

    def _convert_float(self, value: Any) -> float:
        """Convert value to float."""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            # Handle various number formats
            value = value.strip().replace(',', '.').replace(' ', '')
            try:
                return float(value)
            except ValueError:
                raise ValueError(f"Cannot convert '{value}' to float")
        raise ValueError(f"Cannot convert {type(value).__name__} to float")

    def _convert_boolean(self, value: Any) -> bool:
        """Convert value to boolean."""
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            lower = value.lower().strip()
            if lower in ('true', '1', 'yes', 'да', 'on'):
                return True
            if lower in ('false', '0', 'no', 'нет', 'off'):
                return False
            raise ValueError(f"Cannot convert '{value}' to boolean")
        raise ValueError(f"Cannot convert {type(value).__name__} to boolean")

    def _convert_date(self, value: Any) -> str:
        """Convert value to Odoo date format (YYYY-MM-DD)."""
        if isinstance(value, datetime):
            return value.strftime('%Y-%m-%d')

        if isinstance(value, str):
            value = value.strip()

            # Try each format
            for fmt in self.DATE_FORMATS:
                try:
                    dt = datetime.strptime(value, fmt)
                    return dt.strftime('%Y-%m-%d')
                except ValueError:
                    continue

            raise ValueError(f"Cannot parse date: '{value}'. Use YYYY-MM-DD format.")

        raise ValueError(f"Cannot convert {type(value).__name__} to date")

    def _convert_datetime(self, value: Any) -> str:
        """Convert value to Odoo datetime format (YYYY-MM-DD HH:MM:SS)."""
        if isinstance(value, datetime):
            return value.strftime('%Y-%m-%d %H:%M:%S')

        if isinstance(value, str):
            value = value.strip()

            # Try each format
            for fmt in self.DATETIME_FORMATS:
                try:
                    dt = datetime.strptime(value, fmt)
                    return dt.strftime('%Y-%m-%d %H:%M:%S')
                except ValueError:
                    continue

            raise ValueError(f"Cannot parse datetime: '{value}'. Use YYYY-MM-DD HH:MM:SS format.")

        raise ValueError(f"Cannot convert {type(value).__name__} to datetime")

    def _convert_selection(self, value: Any, field_schema: FieldSchema) -> str:
        """Validate and convert selection value."""
        value_str = str(value).strip()

        allowed = field_schema.get_selection_values()
        if not allowed:
            # No selection values known, accept as-is
            return value_str

        if value_str in allowed:
            return value_str

        # Try case-insensitive match
        value_lower = value_str.lower()
        for allowed_val in allowed:
            if allowed_val.lower() == value_lower:
                return allowed_val

        # Try to match by label
        labels = field_schema.get_selection_labels()
        for val, label in labels.items():
            if label.lower() == value_lower:
                return val

        raise ValueError(
            f"Invalid value '{value_str}'. Allowed: {', '.join(allowed)}"
        )

    def _convert_many2one(self, value: Any) -> Optional[int]:
        """Convert many2one value to integer ID."""
        if value is None or value is False:
            return False  # Odoo uses False for empty many2one

        if isinstance(value, int):
            return value

        if isinstance(value, (list, tuple)) and len(value) >= 1:
            # Handle [id, name] format from read
            return int(value[0])

        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                raise ValueError(f"Many2one field requires integer ID, got '{value}'")

        raise ValueError(f"Cannot convert {type(value).__name__} to many2one ID")

    def _convert_x2many(self, value: Any, field_schema: FieldSchema) -> List:
        """
        Convert many2many/one2many value to Odoo command format.

        Odoo x2many command format:
        - (0, 0, {values}) - create new record
        - (1, id, {values}) - update record
        - (2, id, 0) - delete record
        - (3, id, 0) - unlink record (many2many)
        - (4, id, 0) - link existing record
        - (5, 0, 0) - unlink all
        - (6, 0, [ids]) - replace all with given ids
        """
        if value is None:
            return [(5, 0, 0)]  # Clear all

        # Already in command format
        if isinstance(value, list) and value and isinstance(value[0], (list, tuple)):
            return value

        # List of IDs - use replace command
        if isinstance(value, list):
            ids = []
            for v in value:
                if isinstance(v, int):
                    ids.append(v)
                elif isinstance(v, (list, tuple)) and len(v) >= 1:
                    ids.append(int(v[0]))
                else:
                    try:
                        ids.append(int(v))
                    except (ValueError, TypeError):
                        continue
            return [(6, 0, ids)]

        raise ValueError(f"Cannot convert {type(value).__name__} to x2many format")

    def suggest_correction(self, field_name: str, invalid_value: str, model: str) -> Optional[str]:
        """
        Suggest a correction for an invalid value.

        Args:
            field_name: Field name
            invalid_value: The invalid value that was provided
            model: Model name

        Returns:
            Suggested valid value or None
        """
        try:
            schema = self.schema_cache.get_model_schema(model)
            field_schema = schema.fields.get(field_name)

            if not field_schema or not field_schema.selection:
                return None

            # Try fuzzy matching
            invalid_lower = invalid_value.lower()
            best_match = None
            best_score = 0

            for val, label in field_schema.selection:
                # Check similarity
                if invalid_lower in val.lower() or invalid_lower in label.lower():
                    score = len(invalid_value) / max(len(val), len(label))
                    if score > best_score:
                        best_score = score
                        best_match = val

            return best_match

        except Exception:
            return None
