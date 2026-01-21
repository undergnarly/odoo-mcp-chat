"""
LangChain agent for natural language interaction with Odoo
"""
import json
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser

from src.config import get_settings
from src.agent.prompts import (
    get_intent_classifier_prompt,
    get_query_generator_prompt,
    get_procurement_system_prompt,
)
from src.utils.logging import get_logger
from src.utils.error_sanitizer import ErrorSanitizer

logger = get_logger(__name__)


class IntentRouter:
    """
    Routes natural language requests to appropriate Odoo operations.
    Uses dynamic model discovery to provide context to LLM.
    """

    def __init__(self, llm: BaseChatModel, odoo_client, discovery_service=None):
        """
        Initialize the intent router

        Args:
            llm: LangChain language model
            odoo_client: OdooClient instance
            discovery_service: Optional OdooModelDiscovery for dynamic model info
        """
        self.llm = llm
        self.odoo = odoo_client
        self.discovery = discovery_service
        self._cached_models_info = None

    def _get_available_models_info(self) -> str:
        """
        Get formatted string of available models for prompt injection.
        Uses discovery service if available, otherwise fetches directly.
        Falls back to default models if ir.model access is denied.
        """
        try:
            if self._cached_models_info:
                return self._cached_models_info

            # Try to get models from Odoo, fallback to discovery service
            try:
                models_data = self.odoo.get_models()
                model_names = models_data.get("model_names", [])
                models_details = models_data.get("models_details", {})
            except Exception as e:
                # Fallback to discovery service default models
                logger.warning(f"Cannot access ir.model, using default models for prompt: {e}")
                if self.discovery:
                    default_models = self.discovery.get_all_models()
                    model_names = list(default_models.keys())
                    models_details = default_models
                else:
                    return "Model information not available. Ask user to specify the model explicitly."

            # Format top models with descriptions (limit to most common)
            common_models = [
                "res.partner", "res.users", "sale.order", "purchase.order",
                "product.product", "product.template", "account.move",
                "stock.picking", "stock.quant", "hr.employee", "crm.lead",
                "project.project", "project.task", "mail.message"
            ]

            lines = []
            for model in common_models:
                if model in model_names:
                    detail = models_details.get(model, {})
                    name = detail.get("name", model) if isinstance(detail, dict) else model
                    lines.append(f"- `{model}` ({name})")

            # Add count of other available models
            other_count = len(model_names) - len([m for m in common_models if m in model_names])
            if other_count > 0:
                lines.append(f"- ...and {other_count} other models available")

            self._cached_models_info = "\n".join(lines)
            return self._cached_models_info

        except Exception as e:
            logger.warning(f"Could not fetch models info: {e}")
            return "Model information not available. Ask user to specify the model explicitly."

    async def route(self, user_input: str) -> Dict[str, Any]:
        """
        Route user input to appropriate operation

        Args:
            user_input: Natural language request from user

        Returns:
            Dict with intent classification and parameters
        """
        logger.info(f"Routing user input: {user_input[:100]}...")

        try:
            # Get dynamic models info for prompt
            available_models = self._get_available_models_info()

            # Create chain with dynamic prompt
            prompt = get_intent_classifier_prompt()
            chain = prompt | self.llm | JsonOutputParser()

            result = await chain.ainvoke({
                "user_input": user_input,
                "available_models": available_models
            })

            logger.info(f"Intent classified: {result.get('intent')} (confidence: {result.get('confidence')})")

            return result

        except Exception as e:
            logger.error(f"Error in intent routing: {e}")
            return {
                "intent": "QUERY",
                "model": None,
                "confidence": 0.0,
                "error": str(e),
            }


class OdooAgent:
    """
    Main agent for interacting with Odoo via natural language
    """

    def __init__(self, odoo_client, discovery_service):
        """
        Initialize the Odoo agent

        Args:
            odoo_client: OdooClient instance
            discovery_service: OdooModelDiscovery instance
        """
        self.odoo = odoo_client
        self.discovery = discovery_service
        self.settings = get_settings()

        # Initialize LLM based on configuration
        self.llm = self._init_llm()

        # Initialize intent router with discovery service
        self.router = IntentRouter(self.llm, odoo_client, discovery_service)

        # Conversation history
        self.history: List[Dict] = []

        # Cache for models info
        self._models_cache = None

        logger.info("OdooAgent initialized")

    # Valid Odoo domain operators
    VALID_ODOO_OPERATORS = {
        '=', '!=', '>', '<', '>=', '<=',
        'in', 'not in',
        'like', 'ilike', 'not like', 'not ilike',
        '=like', '=ilike',
        'child_of', 'parent_of',
    }

    def _normalize_domain_filters(self, filters) -> List:
        """
        Normalize filters from LLM into valid Odoo domain format.

        LLM might return filters in various formats:
        - None or empty -> []
        - Correct format: [['field', 'op', 'value']] -> pass through
        - Incorrect nested: [[['field', 'op', 'value']]] -> flatten
        - Dict format: [{'field': 'x', 'operator': '=', 'value': 'y'}] -> convert to list
        - Single condition not in list: ['field', 'op', 'value'] -> wrap in list
        - Invalid operators like 'year' -> convert to date range

        Args:
            filters: Raw filters from LLM

        Returns:
            Valid Odoo domain list
        """
        if not filters:
            return []

        if not isinstance(filters, list):
            logger.warning(f"Filters is not a list: {type(filters).__name__}, returning empty")
            return []

        # Empty list is valid
        if len(filters) == 0:
            return []

        # Check if filters contains dicts (invalid format from LLM)
        # e.g., [{'field': 'date', 'operator': '>=', 'value': '2025-01-01'}]
        normalized = []
        for item in filters:
            if isinstance(item, dict):
                # Convert dict to tuple/list format
                field = item.get('field') or item.get('name') or item.get('column')
                operator = item.get('operator') or item.get('op') or '='
                value = item.get('value')
                if field and value is not None:
                    # Validate and fix operator
                    fixed_filters = self._fix_invalid_operator(field, operator, value)
                    normalized.extend(fixed_filters)
            elif isinstance(item, (list, tuple)):
                # Check if it's a valid condition [field, op, value]
                if len(item) == 3 and isinstance(item[0], str):
                    # Validate and fix operator
                    fixed_filters = self._fix_invalid_operator(item[0], item[1], item[2])
                    normalized.extend(fixed_filters)
                elif len(item) > 0 and isinstance(item[0], (list, tuple)):
                    # Nested list - flatten it [[['field', 'op', 'value']]] -> [['field', 'op', 'value']]
                    for sub_item in item:
                        if isinstance(sub_item, (list, tuple)) and len(sub_item) == 3:
                            fixed_filters = self._fix_invalid_operator(sub_item[0], sub_item[1], sub_item[2])
                            normalized.extend(fixed_filters)
                else:
                    # Unknown format, try to use as is
                    normalized.append(item)
            elif isinstance(item, str) and item in ('&', '|', '!'):
                # Domain operators are valid
                normalized.append(item)
            else:
                logger.warning(f"Unknown filter item format: {item}")

        return normalized

    def _fix_invalid_operator(self, field: str, operator: str, value) -> List:
        """
        Fix invalid operators from LLM.

        Args:
            field: Field name
            operator: Operator (may be invalid)
            value: Filter value

        Returns:
            List of valid filter conditions
        """
        # If operator is valid, return as-is
        if operator in self.VALID_ODOO_OPERATORS:
            logger.info(f"Valid filter: [{field}, {operator}, {value}]")
            return [[field, operator, value]]

        # Handle special invalid operators
        if operator in ('year', 'YEAR'):
            # Convert year filter to date range
            try:
                year = int(value)
                logger.info(f"Converting 'year' operator to date range: {year}")
                return [
                    '&',
                    [field, '>=', f'{year}-01-01'],
                    [field, '<', f'{year + 1}-01-01']
                ]
            except (ValueError, TypeError):
                logger.warning(f"Cannot convert year value: {value}")
                return []

        if operator in ('month', 'MONTH'):
            # Would need year+month to convert, skip for now
            logger.warning(f"'month' operator not supported, skipping filter")
            return []

        if operator in ('contains', 'CONTAINS'):
            # Convert to ilike
            logger.info(f"Converting 'contains' to 'ilike'")
            return [[field, 'ilike', value]]

        if operator in ('starts_with', 'startswith', 'STARTS_WITH'):
            # Convert to =like with %
            logger.info(f"Converting 'starts_with' to '=like'")
            return [[field, '=like', f'{value}%']]

        if operator in ('ends_with', 'endswith', 'ENDS_WITH'):
            logger.info(f"Converting 'ends_with' to '=like'")
            return [[field, '=like', f'%{value}']]

        # Unknown operator - log and skip
        logger.warning(f"Unknown operator '{operator}' for field '{field}', skipping filter")
        return []

    def _init_llm(self) -> BaseChatModel:
        """
        Initialize the language model based on settings

        Returns:
            LangChain chat model instance
        """
        if self.settings.llm_provider.lower() == "anthropic":
            if not self.settings.anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY is required for Anthropic provider")

            logger.info(f"Using Anthropic model: {self.settings.llm_model}")
            
            kwargs = {
                "model": self.settings.llm_model,
                "api_key": self.settings.anthropic_api_key,
                "temperature": self.settings.llm_temperature,
            }
            
            if self.settings.anthropic_base_url:
                kwargs["base_url"] = self.settings.anthropic_base_url
                
            return ChatAnthropic(**kwargs)

        elif self.settings.llm_provider.lower() == "openai":
            if not self.settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY is required for OpenAI provider")

            logger.info(f"Using OpenAI model: {self.settings.llm_model}")
            return ChatOpenAI(
                model=self.settings.llm_model,
                temperature=self.settings.llm_temperature,
                api_key=self.settings.openai_api_key,
            )

        elif self.settings.llm_provider.lower() == "google":
            if not self.settings.google_api_key:
                raise ValueError("GOOGLE_API_KEY is required for Google provider")

            logger.info(f"Using Google model: {self.settings.llm_model}")
            return ChatGoogleGenerativeAI(
                model=self.settings.llm_model,
                temperature=self.settings.llm_temperature,
                google_api_key=self.settings.google_api_key,
                convert_system_message_to_human=True,
            )

        else:
            raise ValueError(f"Unsupported LLM provider: {self.settings.llm_provider}")

    async def process_message(
        self,
        user_message: str,
        user_context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Process a user message and generate a response

        Args:
            user_message: Natural language message from user
            user_context: Optional context about the user

        Returns:
            Dict with response data
        """
        logger.info(f"Processing user message: {user_message[:100]}...")

        try:
            # Add to history
            self.history.append({
                "role": "user",
                "content": user_message,
            })

            # Route the intent
            intent_result = await self.router.route(user_message)
            intent = intent_result.get("intent")
            model = intent_result.get("model")
            parameters = intent_result.get("parameters", {})

            logger.info(f"Intent: {intent}, Model: {model}")

            # Execute based on intent
            if intent == "QUERY":
                response = await self._handle_query(model, parameters, user_message)

            elif intent == "CREATE":
                response = await self._handle_create(model, parameters, user_message)

            elif intent == "UPDATE":
                response = await self._handle_update(model, parameters, user_message)

            elif intent == "DELETE":
                response = await self._handle_delete(model, parameters, user_message)

            elif intent == "ACTION":
                response = await self._handle_action(model, parameters, user_message)

            elif intent == "METADATA":
                response = await self._handle_metadata()

            else:
                response = {
                    "type": "error",
                    "content": f"Unknown intent: {intent}",
                }

            # Add assistant response to history
            self.history.append({
                "role": "assistant",
                "content": response.get("content", ""),
            })

            return response

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            sanitized_error = ErrorSanitizer.sanitize(str(e))
            return {
                "type": "error",
                "content": f"Sorry, I encountered an error: {sanitized_error}",
            }

    async def _handle_query(
        self,
        model: Optional[str],
        parameters: Dict,
        original_message: str,
    ) -> Dict[str, Any]:
        """
        Handle a query intent

        Args:
            model: Target Odoo model
            parameters: Query parameters
            original_message: Original user message

        Returns:
            Response dict
        """
        if not model:
            return {
                "type": "clarification",
                "content": "Which model would you like to query? (e.g., purchase orders, suppliers, products)",
            }

        try:
            # If filters not provided, try to generate them from message
            filters = parameters.get("filters")
            logger.info(f"Raw filters from LLM: {filters} (type: {type(filters).__name__})")

            # Validate and normalize filters to Odoo domain format
            filters = self._normalize_domain_filters(filters)
            logger.info(f"Normalized filters: {filters}")

            # Get safe fields to avoid permission errors on related models
            # This prevents errors like "You are not allowed to access 'sale.order.coupon.points'"
            safe_fields = self.discovery.get_safe_fields(model)

            # Get total count first
            try:
                total_count = self.odoo.execute_method(model, "search_count", filters)
            except Exception:
                total_count = None

            # Get requested limit (default 100 for pagination support)
            limit = parameters.get("limit", 100)

            # Execute search with explicit fields
            results = self.odoo.search_read(
                model_name=model,
                domain=filters,  # Now guaranteed to be a list
                fields=safe_fields,  # Only fetch safe fields
                limit=limit,
            )

            # Format results for display
            if results:
                # Create a simple markdown list of results
                result_strings = []
                for res in results[:10]:  # Limit display to 10
                    name = res.get("name") or res.get("display_name") or f"Record {res.get('id')}"
                    result_strings.append(f"- {name}")

                formatted_results = "\n".join(result_strings)

                # Show total count if available
                if total_count and total_count > len(results):
                    content = f"### Showing {len(results)} of {total_count} total records in `{model}`:\n\n{formatted_results}"
                    content += f"\n\n*Use filters or ask for more records to see additional results.*"
                else:
                    content = f"### Found {len(results)} records in `{model}`:\n\n{formatted_results}"
            else:
                content = f"Found 0 records in `{model}` matching your criteria."

            return {
                "type": "query_result",
                "model": model,
                "count": len(results),
                "total_count": total_count,
                "results": results,
                "content": content,
            }

        except Exception as e:
            logger.error(f"Error in query: {e}")
            sanitized_error = ErrorSanitizer.sanitize(str(e))
            return {
                "type": "error",
                "content": f"Error querying {model}: {sanitized_error}",
            }

    async def _handle_create(
        self,
        model: Optional[str],
        parameters: Dict,
        original_message: str,
    ) -> Dict[str, Any]:
        """Handle a create intent"""
        if self.settings.read_only_mode:
            return {
                "type": "error",
                "content": "🚫 **Write Action Blocked**\n\nI am currently running in **Read-Only Mode**. Creating new records is disabled to protect your data."
            }
        values = parameters.get("values")

        if not model:
            return {
                "type": "clarification",
                "content": "What type of record would you like to create?",
            }

        if not values:
            return {
                "type": "clarification",
                "content": f"What values should I use for the new {model} record?",
            }

        return {
            "type": "confirmation_required",
            "content": f"⚠️ About to create {model} with values: {values}. Proceed?",
            "operation": "create",
            "model": model,
            "values": values,
        }

    async def _handle_update(
        self,
        model: Optional[str],
        parameters: Dict,
        original_message: str,
    ) -> Dict[str, Any]:
        """Handle an update intent"""
        if self.settings.read_only_mode:
            return {
                "type": "error",
                "content": "🚫 **Write Action Blocked**\n\nI am currently running in **Read-Only Mode**. Updating records is disabled to protect your data."
            }
        record_id = parameters.get("record_id")
        values = parameters.get("values")

        return {
            "type": "confirmation_required",
            "content": f"⚠️ About to update {model} record {record_id} with: {values}. Proceed?",
            "operation": "update",
            "model": model,
            "record_id": record_id,
            "values": values,
        }

    async def _handle_delete(
        self,
        model: Optional[str],
        parameters: Dict,
        original_message: str,
    ) -> Dict[str, Any]:
        """Handle a delete intent"""
        if self.settings.read_only_mode:
            return {
                "type": "error",
                "content": "🚫 **Write Action Blocked**\n\nI am currently running in **Read-Only Mode**. Deleting records is disabled to protect your data."
            }
        record_id = parameters.get("record_id")

        return {
            "type": "confirmation_required",
            "content": f"⚠️ About to delete {model} record {record_id}. This cannot be undone. Proceed?",
            "operation": "delete",
            "model": model,
            "record_id": record_id,
        }

    async def _handle_action(
        self,
        model: Optional[str],
        parameters: Dict,
        original_message: str,
    ) -> Dict[str, Any]:
        """Handle an action intent"""
        if self.settings.read_only_mode:
            return {
                "type": "error",
                "content": "🚫 **Action Blocked**\n\nI am currently running in **Read-Only Mode**. Executing actions is disabled to protect your data."
            }
        method = parameters.get("method")
        record_id = parameters.get("record_id")

        return {
            "type": "confirmation_required",
            "content": f"⚠️ About to execute {method} on {model} record {record_id}. Proceed?",
            "operation": "action",
            "model": model,
            "record_id": record_id,
            "method": method,
        }

    async def _handle_metadata(self) -> Dict[str, Any]:
        """
        Handle metadata intent - return dynamic system capabilities.
        Fetches real model information from connected Odoo instance.
        Falls back to default models if ir.model access is denied.
        """
        using_fallback = False

        try:
            models_data = self.odoo.get_models()
            model_names = models_data.get("model_names", [])
            models_details = models_data.get("models_details", {})
        except Exception as e:
            # Fallback to default models when ir.model is not accessible
            logger.warning(f"Cannot access ir.model, using default models: {e}")
            model_names = list(self.discovery.get_all_models().keys())
            models_details = self.discovery.get_all_models()
            using_fallback = True

        count = len(model_names)

        # Group models by category dynamically
        categories = {
            "Sales & CRM": ["sale.order", "sale.order.line", "crm.lead", "crm.team"],
            "Purchase": ["purchase.order", "purchase.order.line"],
            "Inventory": ["stock.picking", "stock.move", "stock.quant", "stock.warehouse"],
            "Accounting": ["account.move", "account.move.line", "account.payment"],
            "Contacts": ["res.partner", "res.users", "res.company"],
            "Products": ["product.product", "product.template", "product.category"],
            "HR": ["hr.employee", "hr.department", "hr.contract"],
            "Projects": ["project.project", "project.task"],
        }

        # Build dynamic model list
        model_sections = []
        found_models = set()

        for category, category_models in categories.items():
            available = [m for m in category_models if m in model_names]
            if available:
                model_list = ", ".join([f"`{m}`" for m in available[:3]])
                if len(available) > 3:
                    model_list += f" (+{len(available) - 3} more)"
                model_sections.append(f"- **{category}**: {model_list}")
                found_models.update(available)

        other_count = count - len(found_models)

        # Add note about fallback mode
        fallback_note = ""
        if using_fallback:
            fallback_note = "\n\n*Note: Showing standard Odoo models. Some models may not be available in your instance.*"

        content = f"""## System Capabilities

I am connected to **Odoo** and have access to **{count}** standard models.

### Available Model Categories:
{chr(10).join(model_sections)}

*Plus {other_count} other specialized models*

### What I Can Do:
- **Query data**: "Show me all contacts", "List recent orders"
- **Create records**: "Create a new contact named John"
- **Update records**: "Update order #123 status"
- **Execute actions**: "Confirm order #456", "Approve request"
- **Attach files**: "Attach invoice to order"
- **Post messages**: "Add comment to record"

### Tips:
- Be specific about which model/record you want to work with
- I'll ask for confirmation before making any changes
- You can use model names directly (e.g., `res.partner`) or natural language{fallback_note}

What would you like to do?"""

        return {
            "type": "metadata",
            "content": content,
            "data": {
                "total_models": count,
                "model_names": model_names[:50],  # Limit for response size
                "using_fallback": using_fallback,
            }
        }

    async def execute_confirmed_action(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a confirmed action (create, update, delete, or workflow action).

        Args:
            action_data: Dict containing operation details from confirmation

        Returns:
            Dict with execution result
        """
        operation = action_data.get("operation")
        model = action_data.get("model")
        record_id = action_data.get("record_id")
        values = action_data.get("values")
        method = action_data.get("method")

        logger.info(f"Executing confirmed action: {operation} on {model}")

        try:
            if operation == "create":
                if not model or not values:
                    return {
                        "success": False,
                        "content": "Missing model or values for create operation",
                    }

                new_id = self.odoo.execute_method(model, "create", [values])
                return {
                    "success": True,
                    "content": f"Successfully created new {model} record with ID: {new_id}",
                    "record_id": new_id,
                }

            elif operation == "update":
                if not model or not record_id or not values:
                    return {
                        "success": False,
                        "content": "Missing model, record_id, or values for update operation",
                    }

                self.odoo.execute_method(model, "write", [[record_id], values])
                return {
                    "success": True,
                    "content": f"Successfully updated {model} record {record_id}",
                    "record_id": record_id,
                }

            elif operation == "delete":
                if not model or not record_id:
                    return {
                        "success": False,
                        "content": "Missing model or record_id for delete operation",
                    }

                self.odoo.execute_method(model, "unlink", [[record_id]])
                return {
                    "success": True,
                    "content": f"Successfully deleted {model} record {record_id}",
                    "record_id": record_id,
                }

            elif operation == "action":
                if not model or not record_id or not method:
                    return {
                        "success": False,
                        "content": "Missing model, record_id, or method for action operation",
                    }

                result = self.odoo.execute_method(model, method, [[record_id]])
                return {
                    "success": True,
                    "content": f"Successfully executed {method} on {model} record {record_id}",
                    "record_id": record_id,
                    "result": result,
                }

            else:
                return {
                    "success": False,
                    "content": f"Unknown operation type: {operation}",
                }

        except Exception as e:
            logger.error(f"Error executing action: {e}")
            sanitized_error = ErrorSanitizer.sanitize(str(e))
            return {
                "success": False,
                "content": f"Error executing action: {sanitized_error}",
                "error": sanitized_error,
            }

    def clear_history(self):
        """Clear conversation history"""
        self.history = []
        logger.info("Conversation history cleared")

    def get_history(self) -> List[Dict]:
        """Get conversation history"""
        return self.history
