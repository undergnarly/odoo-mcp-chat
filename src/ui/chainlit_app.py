"""
Chainlit web UI for Odoo AI Agent
"""
import asyncio
import sys
import os
import traceback
import uuid
from typing import Optional

import chainlit as cl

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.config import get_settings
from src.utils.logging import (
    setup_logging,
    get_logger,
    set_session_context,
    clear_session_context,
    log_chat_error,
)
from src.odoo_mcp.odoo_client import get_odoo_client
from src.agent.langchain_agent import OdooAgent
from src.extensions.discovery import OdooModelDiscovery
from src.ui.data_layer import (
    create_data_layer,
    init_database,
    register_user,
    authenticate_user,
    user_exists,
)

# Setup logging
logger_instance = setup_logging()
logger = get_logger(__name__)

# Global variables
agent: Optional[OdooAgent] = None
settings = get_settings()


async def send_assistant_message(content: str) -> cl.Message:
    """
    Send assistant message without parent_id to ensure it shows in chat history.

    Chainlit by default sets parent_id for messages sent in response context,
    which causes them to not appear when resuming chat from history.
    Setting parent_id=None makes them root messages that always show.
    """
    msg = cl.Message(content=content)
    msg.parent_id = None  # Ensure no parent - critical for history display
    await msg.send()
    return msg


@cl.data_layer
def get_data_layer():
    """Provide data layer for chat history persistence"""
    import asyncio
    # Initialize database schema synchronously at startup
    asyncio.get_event_loop().run_until_complete(init_database())
    return create_data_layer()


@cl.password_auth_callback
async def auth_callback(username: str, password: str):
    """
    Password authentication with registration support.
    - If username starts with 'new:' - register new user
    - Otherwise authenticate existing user
    """
    # Handle registration: prefix username with "new:" to register
    if username.startswith("new:"):
        actual_username = username[4:]  # Remove "new:" prefix
        if not actual_username or not password:
            return None

        # Check if user already exists
        if await user_exists(actual_username):
            logger.warning(f"Registration failed: user {actual_username} already exists")
            return None

        # Register new user
        if await register_user(actual_username, password):
            logger.info(f"New user registered: {actual_username}")
            return cl.User(
                identifier=actual_username,
                metadata={"role": "user", "provider": "credentials"}
            )
        return None

    # Normal authentication
    if await authenticate_user(username, password):
        return cl.User(
            identifier=username,
            metadata={"role": "user", "provider": "credentials"}
        )

    # Fallback to env-based admin auth for initial setup
    expected_user = os.environ.get("CHAINLIT_AUTH_USER", "admin")
    expected_pass = os.environ.get("CHAINLIT_AUTH_PASSWORD", "admin")

    if username == expected_user and password == expected_pass:
        return cl.User(
            identifier=username,
            metadata={"role": "admin", "provider": "credentials"}
        )

    return None


@cl.on_chat_start
async def on_chat_start():
    """Initialize the agent when a new chat session starts"""
    # Get or create session ID for logging
    session_id = cl.user_session.get("id") or str(uuid.uuid4())
    thread_id = cl.context.session.thread_id if cl.context.session else None

    # Set session context for logging
    set_session_context(session_id=session_id, thread_id=thread_id)

    logger.info(f"Starting new chat session. Thread: {thread_id}")

    # Show loading indicator while connecting
    loading_msg = cl.Message(content="Connecting to Odoo...")
    await loading_msg.send()

    try:
        # Get user-provided environment variables from Chainlit
        user_env = cl.user_session.get("env") or {}

        # Debug: log what we got from user_env
        logger.info(f"User env keys: {list(user_env.keys()) if user_env else 'empty'}")

        # Set environment variables from user_env for odoo_client and openai
        # This allows the existing code to work without modification
        env_vars = ["OPENAI_API_KEY", "ODOO_URL", "ODOO_DB", "ODOO_USERNAME", "ODOO_PASSWORD"]
        for var in env_vars:
            if var in user_env and user_env[var]:
                os.environ[var] = user_env[var]
                logger.info(f"Set {var} from user_env")

        # Get connection info for display
        odoo_url = user_env.get("ODOO_URL") or os.environ.get("ODOO_URL", "Not configured")
        odoo_db = user_env.get("ODOO_DB") or os.environ.get("ODOO_DB", "Not configured")

        # Update loading message with connection details
        loading_msg.content = f"Connecting to Odoo at {odoo_url}..."
        await loading_msg.update()

        # Initialize Odoo client
        odoo_client = get_odoo_client()
        logger.info("Odoo client initialized")

        # Update loading status
        loading_msg.content = "Initializing AI agent..."
        await loading_msg.update()

        # Store odoo_client in session for later use
        cl.user_session.set("odoo_client", odoo_client)

        # Initialize discovery service
        discovery = OdooModelDiscovery(odoo_client, cache_ttl=300)
        cl.user_session.set("discovery", discovery)

        # Initialize agent
        global agent
        agent = OdooAgent(odoo_client, discovery)
        cl.user_session.set("agent", agent)

        # Remove loading message and send welcome message
        await loading_msg.remove()

        # Send welcome message
        welcome_message = f"""
# Welcome to Odoo AI Agent

I'm your intelligent assistant for interacting with Odoo ERP.

## What I can do:

**Query Data**
- View any records in your Odoo system
- Generate reports and summaries
- Search and filter data

**Perform Actions**
- Create new records (with confirmation)
- Update existing records
- Execute workflows and actions
- Post messages and comments
- Attach files

## How to use me:

Simply ask questions in natural language:
- "Show me all contacts"
- "List recent orders"
- "Create a new partner"
- "What models are available?"

I'll always ask for confirmation before making changes.

---

**Connected to:** {odoo_url}
**Database:** {odoo_db}
        """

        await send_assistant_message(welcome_message)

        # Show available models (with fallback to discovery)
        try:
            models_info = odoo_client.get_models()
            model_count = len(models_info.get("model_names", []))
            if model_count > 0:
                await send_assistant_message(
                    f"Ready! I have access to **{model_count}** models in your Odoo instance."
                )
            else:
                raise ValueError("No models returned from ir.model")
        except Exception as models_err:
            # Fallback to discovery's default models when ir.model is not accessible
            logger.warning(f"Cannot access ir.model, using discovery models: {models_err}")
            model_count = len(discovery.get_all_models())
            await send_assistant_message(
                f"Ready! Using **{model_count}** standard Odoo models (limited API access)."
            )

    except Exception as e:
        logger.error(f"Error initializing chat: {e}")
        log_chat_error(
            error_type="initialization",
            error_message=str(e),
            stack_trace=traceback.format_exc(),
        )
        # Update loading message to show error
        loading_msg.content = f"Connection failed: {str(e)}\n\nPlease check your Odoo connection settings."
        await loading_msg.update()


def handle_pagination_command(user_input: str) -> Optional[int]:
    """
    Check if user input is a pagination command and return the new page number.

    Returns:
        New page number (0-indexed) or None if not a pagination command
    """
    user_input_lower = user_input.lower().strip()

    # Get query context
    query_ctx = cl.user_session.get("query_context")
    if not query_ctx:
        return None

    current_page = query_ctx.get("current_page", 0)
    total_count = query_ctx.get("total_count", 0)
    total_pages = (total_count + PAGE_SIZE - 1) // PAGE_SIZE

    if user_input_lower in ("next", "следующая", "далее", ">"):
        return min(current_page + 1, total_pages - 1)
    elif user_input_lower in ("prev", "previous", "назад", "предыдущая", "<"):
        return max(current_page - 1, 0)
    elif user_input_lower in ("first", "первая", "<<"):
        return 0
    elif user_input_lower in ("last", "последняя", ">>"):
        return total_pages - 1
    elif user_input_lower.startswith("page ") or user_input_lower.startswith("страница "):
        try:
            page_num = int(user_input_lower.split()[-1])
            return max(0, min(page_num - 1, total_pages - 1))  # Convert to 0-indexed
        except ValueError:
            return None

    return None


@cl.on_message
async def on_message(message: cl.Message):
    """
    Process incoming messages from the user

    Args:
        message: Chainlit message from user
    """
    # Update session context for this message
    session_id = cl.user_session.get("id") or "unknown"
    thread_id = cl.context.session.thread_id if cl.context.session else None
    set_session_context(session_id=session_id, thread_id=thread_id)

    if agent is None:
        logger.error("Agent not initialized when processing message")
        await send_assistant_message("❌ Agent not initialized. Please refresh the page.")
        return

    user_input = message.content
    logger.info(f"User message: {user_input[:100]}...")

    # Check for confirmation commands (for pending actions)
    pending_action = cl.user_session.get("pending_action")
    if pending_action:
        confirmation = handle_confirmation_command(user_input)
        if confirmation is True:
            await execute_pending_action()
            return
        elif confirmation is False:
            cl.user_session.set("pending_action", None)
            await send_assistant_message("Action cancelled.")
            return

    # Check for pagination commands
    new_page = handle_pagination_command(user_input)
    if new_page is not None:
        query_ctx = cl.user_session.get("query_context")
        if query_ctx and new_page != query_ctx.get("current_page"):
            query_ctx["current_page"] = new_page
            cl.user_session.set("query_context", query_ctx)

            total_pages = (query_ctx["total_count"] + PAGE_SIZE - 1) // PAGE_SIZE
            content = build_table_content(
                query_ctx["model"],
                query_ctx["results"],
                new_page,
                query_ctx["total_count"]
            )
            content += f"\n\n---\n**Page {new_page + 1} of {total_pages}** | To navigate: type `next`, `prev`, `page 5`, or `last`"
            await send_assistant_message(content)
            return
        elif query_ctx:
            await send_assistant_message(f"Already on page {new_page + 1}")
            return

    # Handle file uploads (attached to message)
    if message.elements:
        for element in message.elements:
            if isinstance(element, cl.File):
                logger.info(f"File uploaded: {element.name}")
                await send_assistant_message(f"📎 Received file: **{element.name}**")
                # Store file for later use
                cl.user_session.set("uploaded_file", element)


    # Show chain of thought with detailed steps
    try:
        # Step 1: Analyze intent (with conversation history for context)
        async with cl.Step(name="🧠 Analyzing Intent", type="llm") as intent_step:
            intent_step.input = user_input

            # Route the intent with history for context resolution
            # agent.history contains conversation history for context
            intent_result = await agent.router.route(user_input, agent.history)
            intent = intent_result.get("intent", "UNKNOWN")
            model = intent_result.get("model", "unknown")
            parameters = intent_result.get("parameters", {})
            record_id = parameters.get("record_id") if parameters else None
            reasoning = intent_result.get("reasoning", "")

            # Show context resolution if record_id was resolved from history
            context_note = ""
            if record_id and "this" in user_input.lower() or "it" in user_input.lower() or "этот" in user_input.lower() or "эту" in user_input.lower():
                context_note = f"\n**Context Resolved:** Record ID {record_id} from previous conversation"

            intent_step.output = f"""**Detected Intent:** {intent}
**Target Model:** {model or 'auto-detect'}
**Parameters:** {parameters if parameters else 'none'}{context_note}
**Reasoning:** {reasoning}"""

        # Step 2: Process with agent
        async with cl.Step(name="⚙️ Processing Request", type="tool") as process_step:
            process_step.input = f"Intent: {intent}, Model: {model}"

            # Process message with agent, passing pre-routed intent to avoid double routing
            response = await agent.process_message(user_input, pre_routed_intent=intent_result)

            response_type = response.get("type")
            process_step.output = f"Response type: {response_type}"

        # Handle response based on type
        if response_type == "query_result":
            await handle_query_result(response)

        elif response_type == "confirmation_required":
            await handle_confirmation_required(response)

        elif response_type == "error":
            await handle_error(response)

        else:
            await handle_default(response)

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        # Log detailed error for debugging
        log_chat_error(
            error_type="message_processing",
            error_message=str(e),
            user_input=user_input,
            stack_trace=traceback.format_exc(),
        )
        await send_assistant_message(f"❌ Error: {str(e)}")


def format_field_value(key: str, value) -> str:
    """Format a field value for display"""
    if value is None or value is False:
        return "-"

    # Handle many2one fields (tuple of id, name)
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return str(value[1])

    # Handle monetary/float fields
    if key in ('amount_total', 'amount_untaxed', 'amount_tax', 'amount_residual',
               'list_price', 'standard_price', 'expected_revenue', 'price_unit'):
        try:
            return f"{float(value):,.2f}"
        except (ValueError, TypeError):
            return str(value)

    # Handle date fields
    if key in ('date_order', 'date', 'create_date', 'write_date', 'date_deadline',
               'invoice_date', 'invoice_date_due', 'scheduled_date', 'date_done'):
        if isinstance(value, str) and len(value) >= 10:
            return value[:10]  # Show only date part
        return str(value)

    # Handle boolean
    if isinstance(value, bool):
        return "Yes" if value else "No"

    # Default: convert to string and truncate if too long
    str_value = str(value)
    if len(str_value) > 40:
        return str_value[:37] + "..."
    return str_value


def get_display_columns(model: str, results: list) -> list:
    """
    Dynamically determine which columns to display based on model and available data.

    Returns list of tuples: (field_name, display_header)
    """
    # Priority fields for different models
    MODEL_PRIORITY_FIELDS = {
        "sale.order": [
            ("name", "Order"),
            ("state", "Status"),
            ("partner_id", "Customer"),
            ("date_order", "Date"),
            ("amount_total", "Total"),
        ],
        "purchase.order": [
            ("name", "Order"),
            ("state", "Status"),
            ("partner_id", "Vendor"),
            ("date_order", "Date"),
            ("amount_total", "Total"),
        ],
        "res.partner": [
            ("name", "Name"),
            ("email", "Email"),
            ("phone", "Phone"),
            ("city", "City"),
            ("is_company", "Company"),
        ],
        "product.product": [
            ("default_code", "Code"),
            ("name", "Product"),
            ("list_price", "Price"),
            ("type", "Type"),
            ("categ_id", "Category"),
        ],
        "product.template": [
            ("default_code", "Code"),
            ("name", "Product"),
            ("list_price", "Price"),
            ("type", "Type"),
            ("categ_id", "Category"),
        ],
        "account.move": [
            ("name", "Number"),
            ("move_type", "Type"),
            ("partner_id", "Partner"),
            ("invoice_date", "Date"),
            ("amount_total", "Total"),
            ("payment_state", "Payment"),
        ],
        "stock.picking": [
            ("name", "Reference"),
            ("state", "Status"),
            ("partner_id", "Partner"),
            ("scheduled_date", "Date"),
            ("origin", "Source"),
        ],
        "hr.employee": [
            ("name", "Name"),
            ("job_id", "Job"),
            ("department_id", "Department"),
            ("work_email", "Email"),
            ("work_phone", "Phone"),
        ],
        "crm.lead": [
            ("name", "Name"),
            ("partner_id", "Partner"),
            ("stage_id", "Stage"),
            ("expected_revenue", "Revenue"),
            ("user_id", "Salesperson"),
        ],
        "project.task": [
            ("name", "Task"),
            ("project_id", "Project"),
            ("stage_id", "Stage"),
            ("user_ids", "Assigned"),
            ("date_deadline", "Deadline"),
        ],
    }

    # Get priority fields for this model
    if model in MODEL_PRIORITY_FIELDS:
        columns = MODEL_PRIORITY_FIELDS[model]
    else:
        # Default columns - dynamically detect from first result
        columns = [("name", "Name")]

        if results:
            first_record = results[0]
            # Add other meaningful fields
            priority_keys = ["state", "partner_id", "date", "amount_total", "email",
                           "phone", "type", "active", "user_id", "company_id"]

            for key in priority_keys:
                if key in first_record and first_record[key] not in (None, False, "", []):
                    # Generate header from field name
                    header = key.replace("_id", "").replace("_", " ").title()
                    columns.append((key, header))
                    if len(columns) >= 5:
                        break

    return columns


PAGE_SIZE = 10  # Records per page


def build_table_content(model: str, results: list, page: int, total_count: int) -> str:
    """Build table content for a specific page"""
    start_idx = page * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    page_results = results[start_idx:end_idx] if len(results) > start_idx else results

    total_pages = (total_count + PAGE_SIZE - 1) // PAGE_SIZE if total_count else 1

    # Build response content
    content = f"## 📊 Query Results: `{model}`\n\n"
    content += f"**Page {page + 1} of {total_pages}** | "
    content += f"Showing records {start_idx + 1}-{min(start_idx + len(page_results), total_count)} of {total_count} total\n\n"

    if page_results:
        # Get dynamic columns for this model
        columns = get_display_columns(model, page_results)

        # Build table header
        headers = [col[1] for col in columns]
        content += "| # | " + " | ".join(headers) + " |\n"
        content += "|---" + "|---" * len(columns) + "|\n"

        # Build table rows
        for idx, record in enumerate(page_results, start_idx + 1):
            row_values = [f"**{idx}**"]

            for field_name, _ in columns:
                value = record.get(field_name)
                formatted = format_field_value(field_name, value)
                row_values.append(formatted)

            content += "| " + " | ".join(row_values) + " |\n"

    return content


async def handle_query_result(response: dict):
    """
    Handle query result response with dynamic table formatting and pagination

    Args:
        response: Response dict from agent
    """
    model = response.get("model", "Unknown")
    count = response.get("count", 0)
    total_count = response.get("total_count") or count
    results = response.get("results", [])

    if not results:
        content = f"## 📊 Query Results: `{model}`\n\n"
        content += "❌ No records found matching your query."
        await send_assistant_message(content)
        return

    # Store query context for pagination
    query_context = {
        "model": model,
        "results": results,
        "total_count": total_count,
        "current_page": 0,
    }
    cl.user_session.set("query_context", query_context)

    # Build first page
    content = build_table_content(model, results, 0, total_count)

    # Add pagination info if there are more pages
    total_pages = (total_count + PAGE_SIZE - 1) // PAGE_SIZE

    if total_pages > 1:
        content += f"\n\n---\n**Page 1 of {total_pages}** | To navigate: type `next`, `prev`, `page 5`, or `last`"

    await send_assistant_message(content)


async def handle_confirmation_required(response: dict):
    """
    Handle confirmation required response.
    Uses text commands instead of action buttons for better compatibility.

    Args:
        response: Response dict from agent
    """
    operation = response.get("operation")
    content = response.get("content", "Please confirm this action")

    # Store response data for later confirmation
    cl.user_session.set("pending_action", response)

    # Add instructions for confirmation
    content += "\n\n---\n**Type `yes` or `confirm` to proceed, or `no` / `cancel` to abort.**"

    await send_assistant_message(content)


def handle_confirmation_command(user_input: str) -> Optional[bool]:
    """
    Check if user input is a confirmation command.

    Returns:
        True for confirm, False for cancel, None if not a confirmation command
    """
    user_input_lower = user_input.lower().strip()

    if user_input_lower in ("yes", "y", "confirm", "да", "подтвердить", "ok", "proceed"):
        return True
    elif user_input_lower in ("no", "n", "cancel", "нет", "отмена", "abort"):
        return False

    return None


async def execute_pending_action():
    """Execute the pending action stored in session."""
    pending = cl.user_session.get("pending_action")
    if not pending:
        await send_assistant_message("No pending action to execute.")
        return

    # Clear pending action
    cl.user_session.set("pending_action", None)

    await send_assistant_message("Executing action...")

    try:
        if agent is not None:
            execution_result = await agent.execute_confirmed_action(pending)

            if execution_result.get("success"):
                result_content = execution_result.get("content", "Action completed successfully")
                await send_assistant_message(f"**Success:** {result_content}")
            else:
                error_content = execution_result.get("content", "Action failed")
                await send_assistant_message(f"**Error:** {error_content}")
        else:
            await send_assistant_message("**Error:** Agent not initialized")

    except Exception as e:
        logger.error(f"Error executing confirmed action: {e}")
        await send_assistant_message(f"**Error:** {str(e)}")


async def handle_error(response: dict):
    """
    Handle error response

    Args:
        response: Response dict from agent
    """
    content = f"## ⚠️ Error\n\n{response.get('content', 'Unknown error')}"
    await send_assistant_message(content)


async def handle_default(response: dict):
    """
    Handle default response

    Args:
        response: Response dict from agent
    """
    content = response.get("content", "No content")
    await send_assistant_message(content)


@cl.on_chat_end
async def on_chat_end():
    """Cleanup when chat session ends"""
    logger.info("Chat session ended")
    if agent:
        agent.clear_history()
    # Clear session context
    clear_session_context()


@cl.on_chat_resume
async def on_chat_resume(thread=None):
    """Handle chat resume from saved thread"""
    # Set session context for resumed thread
    session_id = cl.user_session.get("id") or str(uuid.uuid4())
    thread_id = None
    if thread:
        thread_id = thread.get("id") if isinstance(thread, dict) else getattr(thread, "id", None)
    set_session_context(session_id=session_id, thread_id=thread_id)

    logger.info(f"Chat session resumed. Thread: {thread_id}")

    # Show loading indicator
    loading_msg = cl.Message(content="Reconnecting to Odoo...")
    await loading_msg.send()

    try:
        # Get user-provided environment variables from Chainlit
        user_env = cl.user_session.get("env") or {}

        # Set environment variables from user_env
        env_vars = ["OPENAI_API_KEY", "ODOO_URL", "ODOO_DB", "ODOO_USERNAME", "ODOO_PASSWORD"]
        for var in env_vars:
            if var in user_env and user_env[var]:
                os.environ[var] = user_env[var]

        # Re-initialize Odoo client and agent for resumed session
        odoo_client = get_odoo_client()
        cl.user_session.set("odoo_client", odoo_client)

        discovery = OdooModelDiscovery(odoo_client, cache_ttl=300)
        cl.user_session.set("discovery", discovery)

        global agent
        agent = OdooAgent(odoo_client, discovery)
        cl.user_session.set("agent", agent)

        logger.info("Agent re-initialized for resumed session")

        # Remove loading message - chat history will be shown automatically
        await loading_msg.remove()

    except Exception as e:
        logger.error(f"Error resuming chat: {e}")
        log_chat_error(
            error_type="session_resume",
            error_message=str(e),
            stack_trace=traceback.format_exc(),
        )
        # Update loading message with error
        loading_msg.content = f"Failed to reconnect: {str(e)}"
        await loading_msg.update()


# File upload handling

