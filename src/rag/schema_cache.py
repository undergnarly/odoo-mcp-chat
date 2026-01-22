"""
Schema Cache for Odoo models.

Caches model field definitions (from fields_get) for:
- Fast access to field types, selection values, relations
- Prompt injection to help LLM understand model structure
- Value validation before write operations
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)


@dataclass
class FieldSchema:
    """Schema definition for a single field."""
    name: str
    type: str  # char, integer, float, date, datetime, selection, many2one, one2many, many2many, etc.
    string: str  # Human-readable label
    help: Optional[str] = None
    required: bool = False
    readonly: bool = False
    selection: Optional[List[Tuple[str, str]]] = None  # [(value, label), ...] for selection fields
    relation: Optional[str] = None  # Related model name for relational fields

    def get_selection_values(self) -> List[str]:
        """Get list of allowed values for selection field."""
        if self.selection:
            return [v[0] for v in self.selection]
        return []

    def get_selection_labels(self) -> Dict[str, str]:
        """Get mapping of value -> label for selection field."""
        if self.selection:
            return {v[0]: v[1] for v in self.selection}
        return {}


@dataclass
class ModelSchema:
    """Schema definition for an Odoo model."""
    model: str
    fields: Dict[str, FieldSchema] = field(default_factory=dict)
    loaded_at: float = field(default_factory=time.time)

    def get_field(self, field_name: str) -> Optional[FieldSchema]:
        """Get field schema by name."""
        return self.fields.get(field_name)

    def get_selection_values(self, field_name: str) -> List[str]:
        """Get allowed values for a selection field."""
        field_schema = self.fields.get(field_name)
        if field_schema and field_schema.selection:
            return field_schema.get_selection_values()
        return []

    def get_required_fields(self) -> List[str]:
        """Get list of required field names."""
        return [name for name, f in self.fields.items() if f.required and not f.readonly]

    def get_writable_fields(self) -> List[str]:
        """Get list of writable (non-readonly) field names."""
        return [name for name, f in self.fields.items() if not f.readonly]

    def format_for_prompt(self, fields: List[str] = None, max_fields: int = 25) -> str:
        """
        Format schema for injection into LLM prompt.

        Args:
            fields: Specific fields to include (None = all writable fields)
            max_fields: Maximum number of fields to include (to avoid bloating prompt)

        Returns:
            Formatted string describing model schema
        """
        lines = [f"## Model: {self.model}", "### Available Fields:"]

        # Determine which fields to show
        if fields:
            target_fields = [f for f in fields if f in self.fields]
        else:
            # Prioritize important fields
            priority_fields = ['name', 'state', 'date', 'date_order', 'partner_id',
                             'amount_total', 'product_id', 'quantity', 'price_unit']
            target_fields = [f for f in priority_fields if f in self.fields]

            # Add other writable fields
            for name in self.fields:
                if name not in target_fields and not self.fields[name].readonly:
                    target_fields.append(name)

        # Limit to max_fields
        target_fields = target_fields[:max_fields]

        for name in target_fields:
            f = self.fields.get(name)
            if not f:
                continue

            # Build field description
            parts = [f"- **{name}** ({f.type})"]

            if f.required:
                parts.append("[required]")

            if f.string and f.string != name:
                parts.append(f'"{f.string}"')

            if f.selection:
                # Show selection values (limit to 10)
                values = [v[0] for v in f.selection[:10]]
                if len(f.selection) > 10:
                    values.append("...")
                parts.append(f"values: [{', '.join(values)}]")

            if f.relation:
                parts.append(f"-> {f.relation}")

            if f.help:
                # Truncate help text
                help_text = f.help[:80].replace('\n', ' ')
                if len(f.help) > 80:
                    help_text += "..."
                parts.append(f"- {help_text}")

            lines.append(" ".join(parts))

        if len(self.fields) > max_fields:
            lines.append(f"\n_... and {len(self.fields) - max_fields} more fields_")

        return "\n".join(lines)

    def format_state_info(self) -> Optional[str]:
        """Format state/status field information if available."""
        state_field = self.fields.get('state')
        if not state_field or not state_field.selection:
            return None

        lines = [f"### Statuses for {self.model}:"]
        for value, label in state_field.selection:
            lines.append(f"- `{value}`: {label}")

        return "\n".join(lines)


class OdooSchemaCache:
    """
    Caches Odoo model schemas for fast access.

    Usage:
        cache = OdooSchemaCache(odoo_client)
        schema = cache.get_model_schema("sale.order")
        print(schema.format_for_prompt())
    """

    # Common models to preload
    COMMON_MODELS = [
        'sale.order',
        'sale.order.line',
        'purchase.order',
        'purchase.order.line',
        'res.partner',
        'product.product',
        'product.template',
        'account.move',
        'account.move.line',
        'stock.picking',
        'stock.move',
        'crm.lead',
        'project.project',
        'project.task',
        'hr.employee',
    ]

    def __init__(self, odoo_client, cache_ttl: int = 3600):
        """
        Initialize schema cache.

        Args:
            odoo_client: OdooClient instance
            cache_ttl: Cache TTL in seconds (default: 1 hour)
        """
        self.odoo = odoo_client
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, ModelSchema] = {}

    def get_model_schema(self, model: str, force_reload: bool = False) -> ModelSchema:
        """
        Get schema for a model (from cache or load from Odoo).

        Args:
            model: Odoo model name (e.g., "sale.order")
            force_reload: Force reload even if cached

        Returns:
            ModelSchema instance

        Raises:
            Exception if model doesn't exist or access denied
        """
        # Check cache
        if not force_reload and self._is_cached(model):
            logger.debug(f"Schema cache hit for {model}")
            return self._cache[model]

        # Load from Odoo
        logger.info(f"Loading schema for {model} from Odoo")
        return self._load_model_schema(model)

    def _is_cached(self, model: str) -> bool:
        """Check if model is in cache and not expired."""
        if model not in self._cache:
            return False

        schema = self._cache[model]
        age = time.time() - schema.loaded_at
        return age < self.cache_ttl

    def _load_model_schema(self, model: str) -> ModelSchema:
        """Load model schema from Odoo via fields_get()."""
        try:
            fields_data = self.odoo.execute_method(
                model,
                'fields_get',
                [],
                attributes=['string', 'help', 'type', 'selection',
                           'relation', 'required', 'readonly']
            )

            schema = self._parse_fields(model, fields_data)
            self._cache[model] = schema
            logger.info(f"Cached schema for {model} with {len(schema.fields)} fields")
            return schema

        except Exception as e:
            logger.error(f"Failed to load schema for {model}: {e}")
            raise

    def _parse_fields(self, model: str, fields_data: Dict[str, Any]) -> ModelSchema:
        """Parse fields_get() response into ModelSchema."""
        fields = {}

        for field_name, field_info in fields_data.items():
            # Skip internal fields
            if field_name.startswith('__'):
                continue

            field_schema = FieldSchema(
                name=field_name,
                type=field_info.get('type', 'char'),
                string=field_info.get('string', field_name),
                help=field_info.get('help'),
                required=field_info.get('required', False),
                readonly=field_info.get('readonly', False),
                selection=field_info.get('selection'),
                relation=field_info.get('relation'),
            )
            fields[field_name] = field_schema

        return ModelSchema(model=model, fields=fields)

    def preload_common_models(self) -> Dict[str, bool]:
        """
        Preload schemas for common models.

        Returns:
            Dict mapping model name to success status
        """
        results = {}
        for model in self.COMMON_MODELS:
            try:
                self.get_model_schema(model)
                results[model] = True
                logger.debug(f"Preloaded schema for {model}")
            except Exception as e:
                results[model] = False
                logger.warning(f"Failed to preload {model}: {e}")

        loaded = sum(1 for v in results.values() if v)
        logger.info(f"Preloaded {loaded}/{len(self.COMMON_MODELS)} model schemas")
        return results

    def invalidate(self, model: str = None):
        """
        Invalidate cache.

        Args:
            model: Specific model to invalidate, or None for all
        """
        if model:
            self._cache.pop(model, None)
            logger.debug(f"Invalidated cache for {model}")
        else:
            self._cache.clear()
            logger.debug("Invalidated all schema cache")

    def get_cached_models(self) -> List[str]:
        """Get list of currently cached model names."""
        return list(self._cache.keys())

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        now = time.time()
        stats = {
            "cached_models": len(self._cache),
            "models": {}
        }
        for model, schema in self._cache.items():
            age = now - schema.loaded_at
            stats["models"][model] = {
                "fields": len(schema.fields),
                "age_seconds": int(age),
                "expires_in": int(self.cache_ttl - age)
            }
        return stats
