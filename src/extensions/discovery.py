"""
Dynamic model and field discovery for Odoo
Automatically discovers all available models, fields, and actions
"""
import json
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

from src.utils.logging import get_logger

logger = get_logger(__name__)

# Default Odoo models - these are standard and don't change between versions
# Used as fallback when ir.model access is not available
DEFAULT_ODOO_MODELS = {
    # Core models
    "res.partner": {"name": "Contact", "description": "Contacts and addresses"},
    "res.users": {"name": "Users", "description": "System users"},
    "res.company": {"name": "Companies", "description": "Company records"},
    "res.currency": {"name": "Currencies", "description": "Currency definitions"},
    "res.country": {"name": "Countries", "description": "Country records"},
    "res.country.state": {"name": "States", "description": "Country states/provinces"},
    "res.bank": {"name": "Banks", "description": "Bank records"},
    "res.partner.bank": {"name": "Bank Accounts", "description": "Partner bank accounts"},

    # Sales
    "sale.order": {"name": "Sales Order", "description": "Sales orders and quotations"},
    "sale.order.line": {"name": "Sales Order Line", "description": "Sales order line items"},

    # Purchase
    "purchase.order": {"name": "Purchase Order", "description": "Purchase orders and RFQs"},
    "purchase.order.line": {"name": "Purchase Order Line", "description": "Purchase order line items"},

    # Inventory
    "stock.picking": {"name": "Transfer", "description": "Stock transfers/deliveries"},
    "stock.move": {"name": "Stock Move", "description": "Stock movement records"},
    "stock.warehouse": {"name": "Warehouse", "description": "Warehouse definitions"},
    "stock.location": {"name": "Location", "description": "Stock locations"},
    "stock.quant": {"name": "Quant", "description": "Stock quantities"},
    "stock.lot": {"name": "Lot/Serial", "description": "Lot and serial numbers"},

    # Products
    "product.product": {"name": "Product Variant", "description": "Product variants"},
    "product.template": {"name": "Product", "description": "Product templates"},
    "product.category": {"name": "Product Category", "description": "Product categories"},
    "product.pricelist": {"name": "Pricelist", "description": "Product pricelists"},
    "product.pricelist.item": {"name": "Pricelist Item", "description": "Pricelist rules"},
    "uom.uom": {"name": "Unit of Measure", "description": "Units of measure"},
    "uom.category": {"name": "UoM Category", "description": "UoM categories"},

    # Accounting
    "account.move": {"name": "Journal Entry", "description": "Accounting journal entries"},
    "account.move.line": {"name": "Journal Item", "description": "Journal entry lines"},
    "account.account": {"name": "Account", "description": "Chart of accounts"},
    "account.journal": {"name": "Journal", "description": "Accounting journals"},
    "account.payment": {"name": "Payment", "description": "Customer/vendor payments"},
    "account.tax": {"name": "Tax", "description": "Tax definitions"},
    "account.fiscal.position": {"name": "Fiscal Position", "description": "Tax mapping rules"},

    # CRM
    "crm.lead": {"name": "Lead/Opportunity", "description": "CRM leads and opportunities"},
    "crm.stage": {"name": "CRM Stage", "description": "CRM pipeline stages"},
    "crm.team": {"name": "Sales Team", "description": "Sales teams"},

    # HR
    "hr.employee": {"name": "Employee", "description": "Employee records"},
    "hr.department": {"name": "Department", "description": "Company departments"},
    "hr.job": {"name": "Job Position", "description": "Job positions"},
    "hr.contract": {"name": "Contract", "description": "Employee contracts"},
    "hr.leave": {"name": "Time Off", "description": "Leave requests"},
    "hr.leave.type": {"name": "Time Off Type", "description": "Leave types"},

    # Project
    "project.project": {"name": "Project", "description": "Projects"},
    "project.task": {"name": "Task", "description": "Project tasks"},

    # Manufacturing
    "mrp.production": {"name": "Manufacturing Order", "description": "Manufacturing orders"},
    "mrp.bom": {"name": "Bill of Materials", "description": "BoM definitions"},
    "mrp.bom.line": {"name": "BoM Line", "description": "BoM components"},
    "mrp.workorder": {"name": "Work Order", "description": "Work orders"},
    "mrp.workcenter": {"name": "Work Center", "description": "Work centers"},

    # Calendar & Activities
    "calendar.event": {"name": "Calendar Event", "description": "Calendar events"},
    "mail.activity": {"name": "Activity", "description": "Scheduled activities"},
    "mail.message": {"name": "Message", "description": "Messages and notes"},
}


@dataclass
class FieldMetadata:
    """Metadata about a model field"""
    name: str
    field_type: str
    string: str
    required: bool = False
    readonly: bool = False
    relation: Optional[str] = None
    help_text: Optional[str] = None
    selection: Optional[List[tuple]] = None


@dataclass
class ModelMetadata:
    """Metadata about an Odoo model"""
    name: str
    model: str
    fields: Dict[str, FieldMetadata]
    methods: List[str]
    description: Optional[str] = None


class OdooModelDiscovery:
    """
    Discovers and caches information about Odoo models and their capabilities
    """

    def __init__(self, odoo_client, cache_ttl: int = 300):
        """
        Initialize the discovery service

        Args:
            odoo_client: OdooClient instance
            cache_ttl: Cache time-to-live in seconds (default 5 minutes)
        """
        self.odoo = odoo_client
        self.cache_ttl = cache_ttl

        # Cache storage
        self._models_cache: Optional[Dict[str, ModelMetadata]] = None
        self._cache_timestamp: Optional[datetime] = None
        self._fields_cache: Dict[str, Dict[str, FieldMetadata]] = {}

        logger.info(f"OdooModelDiscovery initialized with cache_ttl={cache_ttl}s")

    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid"""
        if self._cache_timestamp is None:
            return False

        age = datetime.now() - self._cache_timestamp
        return age < timedelta(seconds=self.cache_ttl)

    def _get_default_models(self) -> Dict[str, ModelMetadata]:
        """
        Get default Odoo models as fallback when ir.model is not accessible.

        Returns:
            Dictionary mapping model names to ModelMetadata
        """
        logger.info("Using default Odoo models list (ir.model not accessible)")

        models_metadata = {}
        for model_name, model_info in DEFAULT_ODOO_MODELS.items():
            metadata = ModelMetadata(
                name=model_info["name"],
                model=model_name,
                fields={},
                methods=[],
                description=model_info.get("description")
            )
            models_metadata[model_name] = metadata

        return models_metadata

    def get_all_models(self, force_refresh: bool = False) -> Dict[str, ModelMetadata]:
        """
        Get all available models in the Odoo system.

        First tries to fetch models dynamically via ir.model.
        If that fails (no access), falls back to predefined default models list.

        Args:
            force_refresh: Force refresh of cache

        Returns:
            Dictionary mapping model names to ModelMetadata
        """
        if not force_refresh and self._is_cache_valid():
            logger.debug("Using cached models list")
            return self._models_cache

        logger.info("Discovering all Odoo models...")

        try:
            # Try to get models dynamically
            models_info = self.odoo.get_models()

            if "error" in models_info:
                error_msg = str(models_info.get('error', ''))
                # Check if it's an access rights error
                if "Access" in error_msg or "denied" in error_msg.lower() or "rights" in error_msg.lower():
                    logger.warning(f"No access to ir.model: {error_msg}")
                    # Use default models as fallback
                    self._models_cache = self._get_default_models()
                    self._cache_timestamp = datetime.now()
                    return self._models_cache
                else:
                    logger.error(f"Error discovering models: {error_msg}")
                    # Still use fallback for any error
                    self._models_cache = self._get_default_models()
                    self._cache_timestamp = datetime.now()
                    return self._models_cache

            model_names = models_info.get("model_names", [])

            # If no models returned, use fallback
            if not model_names:
                logger.warning("No models returned from Odoo, using default list")
                self._models_cache = self._get_default_models()
                self._cache_timestamp = datetime.now()
                return self._models_cache

            logger.info(f"Found {len(model_names)} models from Odoo")

            # Build metadata for each model
            models_metadata = {}
            for model_name in model_names:
                # Skip transient models and base models
                if any(model_name.startswith(prefix) for prefix in ["ir.", "base.", "web."]):
                    continue

                try:
                    model_details = models_info["models_details"].get(model_name, {})
                    metadata = ModelMetadata(
                        name=model_details.get("name", model_name),
                        model=model_name,
                        fields={},
                        methods=[],
                        description=model_details.get("description")
                    )
                    models_metadata[model_name] = metadata

                except Exception as e:
                    logger.warning(f"Error processing model {model_name}: {e}")
                    continue

            # Update cache
            self._models_cache = models_metadata
            self._cache_timestamp = datetime.now()

            logger.info(f"Successfully discovered {len(models_metadata)} models")
            return models_metadata

        except Exception as e:
            logger.error(f"Error in get_all_models: {e}, using default models")
            # Use fallback on any exception
            self._models_cache = self._get_default_models()
            self._cache_timestamp = datetime.now()
            return self._models_cache

    def get_model_fields(
        self,
        model_name: str,
        force_refresh: bool = False
    ) -> Dict[str, FieldMetadata]:
        """
        Get field definitions for a specific model

        Args:
            model_name: Name of the model (e.g., 'purchase.order')
            force_refresh: Force refresh of cache

        Returns:
            Dictionary mapping field names to FieldMetadata
        """
        # Check cache
        if not force_refresh and model_name in self._fields_cache:
            logger.debug(f"Using cached fields for {model_name}")
            return self._fields_cache[model_name]

        logger.debug(f"Discovering fields for {model_name}...")

        try:
            fields_data = self.odoo.get_model_fields(model_name)

            if "error" in fields_data:
                logger.error(f"Error getting fields for {model_name}: {fields_data['error']}")
                return {}

            # Parse field metadata
            fields_metadata = {}
            for field_name, field_info in fields_data.items():
                try:
                    metadata = FieldMetadata(
                        name=field_name,
                        field_type=field_info.get("type", "unknown"),
                        string=field_info.get("string", field_name),
                        required=field_info.get("required", False),
                        readonly=field_info.get("readonly", False),
                        relation=field_info.get("relation"),
                        help_text=field_info.get("help"),
                        selection=field_info.get("selection")
                    )
                    fields_metadata[field_name] = metadata

                except Exception as e:
                    logger.warning(f"Error processing field {field_name}: {e}")
                    continue

            # Update cache
            self._fields_cache[model_name] = fields_metadata

            logger.debug(f"Discovered {len(fields_metadata)} fields for {model_name}")
            return fields_metadata

        except Exception as e:
            logger.error(f"Error in get_model_fields for {model_name}: {e}")
            return {}

    def get_safe_fields(self, model_name: str) -> List[str]:
        """
        Get a list of "safe" fields for a model that won't trigger access errors.

        Uses predefined common fields for standard Odoo models to avoid
        permission errors on related models.

        Args:
            model_name: Name of the model

        Returns:
            List of safe field names
        """
        # Predefined safe fields for common Odoo models
        # These are standard fields that exist in most Odoo installations
        # and don't trigger permission errors on related models
        MODEL_SAFE_FIELDS = {
            "sale.order": [
                "id", "name", "display_name", "state", "date_order",
                "amount_total", "amount_untaxed", "amount_tax",
                "partner_id", "user_id", "company_id", "currency_id",
                "note", "reference", "origin", "client_order_ref",
            ],
            "purchase.order": [
                "id", "name", "display_name", "state", "date_order", "date_approve",
                "amount_total", "amount_untaxed", "amount_tax",
                "partner_id", "user_id", "company_id", "currency_id",
                "notes", "origin", "partner_ref",
            ],
            "res.partner": [
                "id", "name", "display_name", "email", "phone", "mobile",
                "street", "street2", "city", "zip", "country_id", "state_id",
                "vat", "website", "is_company", "company_type", "active",
                "commercial_company_name", "ref",
            ],
            "product.product": [
                "id", "name", "display_name", "default_code", "barcode",
                "list_price", "standard_price", "type", "categ_id",
                "active", "description", "description_sale",
            ],
            "product.template": [
                "id", "name", "display_name", "default_code", "barcode",
                "list_price", "standard_price", "type", "categ_id",
                "active", "description", "description_sale",
            ],
            "account.move": [
                "id", "name", "display_name", "state", "move_type",
                "date", "invoice_date", "invoice_date_due",
                "amount_total", "amount_untaxed", "amount_tax", "amount_residual",
                "partner_id", "company_id", "currency_id", "journal_id",
                "ref", "narration", "payment_state",
            ],
            "stock.picking": [
                "id", "name", "display_name", "state", "origin",
                "scheduled_date", "date_done", "picking_type_id",
                "partner_id", "company_id", "location_id", "location_dest_id",
                "note",
            ],
            "hr.employee": [
                "id", "name", "display_name", "job_id", "department_id",
                "work_email", "work_phone", "mobile_phone",
                "company_id", "active",
            ],
            "crm.lead": [
                "id", "name", "display_name", "type", "stage_id",
                "partner_id", "user_id", "company_id",
                "email_from", "phone", "expected_revenue",
                "probability", "date_deadline", "description", "active",
            ],
            "project.task": [
                "id", "name", "display_name", "state", "stage_id",
                "project_id", "user_ids", "partner_id", "company_id",
                "date_deadline", "description", "priority", "active",
            ],
            "project.project": [
                "id", "name", "display_name", "active", "stage_id",
                "partner_id", "user_id", "company_id",
                "date_start", "date", "description",
            ],
        }

        # Default fields for any model not in the list
        default_fields = ["id", "name", "display_name", "create_date", "write_date", "active"]

        # Return predefined fields if available
        if model_name in MODEL_SAFE_FIELDS:
            logger.debug(f"Using predefined safe fields for {model_name}")
            return MODEL_SAFE_FIELDS[model_name]

        # For unknown models, use default minimal fields
        logger.debug(f"Using default safe fields for {model_name}")
        return default_fields

    def get_model_methods(self, model_name: str) -> List[str]:
        """
        Discover available methods for a model

        This is a heuristic approach - we can't truly introspect methods
        via XML-RPC, but we can provide common Odoo methods

        Args:
            model_name: Name of the model

        Returns:
            List of method names that likely exist on this model
        """
        # Common Odoo methods that exist on most models
        common_methods = [
            "create",
            "write",
            "read",
            "unlink",
            "search",
            "search_read",
            "name_search",
            "fields_get",
            "default_get",
        ]

        # Model-specific common methods
        model_specific = {
            "purchase.order": [
                "button_approve",
                "button_cancel",
                "action_rfq_send",
                "action_create_invoice",
                "print_quotation",
            ],
            "sale.order": [
                "action_confirm",
                "action_cancel",
                "action_draft",
                "print_quotation",
            ],
            "account.move": [
                "button_post",
                "button_cancel",
                "action_draft",
            ],
            "stock.picking": [
                "button_validate",
                "action_cancel",
                "do_unreserve",
                "force_assign",
            ],
        }

        methods = common_methods + model_specific.get(model_name, [])

        logger.debug(f"Found {len(methods)} potential methods for {model_name}")
        return methods

    def search_models_by_keyword(self, keyword: str) -> List[str]:
        """
        Search for models matching a keyword

        Args:
            keyword: Keyword to search for (e.g., 'purchase', 'sale', 'stock')

        Returns:
            List of matching model names
        """
        models = self.get_all_models()
        keyword_lower = keyword.lower()

        matching = [
            model_name
            for model_name in models.keys()
            if keyword_lower in model_name.lower()
        ]

        logger.info(f"Found {len(matching)} models matching '{keyword}'")
        return matching

    def get_model_summary(self, model_name: str) -> Dict[str, Any]:
        """
        Get a summary of a model including fields and methods

        Args:
            model_name: Name of the model

        Returns:
            Dictionary with model summary
        """
        models = self.get_all_models()

        if model_name not in models:
            return {"error": f"Model {model_name} not found"}

        model_info = models[model_name]
        fields = self.get_model_fields(model_name)
        methods = self.get_model_methods(model_name)

        # Group fields by type
        fields_by_type = {}
        for field_name, field_meta in fields.items():
            field_type = field_meta.field_type
            if field_type not in fields_by_type:
                fields_by_type[field_type] = []
            fields_by_type[field_type].append({
                "name": field_name,
                "string": field_meta.string,
                "required": field_meta.required,
                "readonly": field_meta.readonly,
            })

        return {
            "model": model_name,
            "name": model_info.name,
            "total_fields": len(fields),
            "fields_by_type": fields_by_type,
            "common_methods": methods,
        }

    def refresh_cache(self):
        """Force refresh of all caches"""
        logger.info("Refreshing discovery caches...")
        self._models_cache = None
        self._cache_timestamp = None
        self._fields_cache.clear()
        logger.info("Cache refreshed")
