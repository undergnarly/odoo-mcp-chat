"""
Extended MCP server that combines odoo_client with our extensions
"""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, Optional

from mcp.server.fastmcp import FastMCP

# Import odoo client
from src.odoo_mcp.odoo_client import get_odoo_client, OdooClient

# Import our extensions
from src.extensions.write_tools import register_tools as register_write_tools
from src.extensions.action_tools import register_tools as register_action_tools
from src.extensions.discovery import OdooModelDiscovery
from src.extensions.safety import SafetyValidator, ConfirmationHandler
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AppContext:
    """Application context with Odoo client"""
    odoo: OdooClient


@dataclass
class ExtendedAppContext:
    """Extended application context with our services"""

    odoo: OdooClient
    discovery: OdooModelDiscovery
    safety: SafetyValidator
    confirmation: ConfirmationHandler


@asynccontextmanager
async def extended_app_lifespan(server: FastMCP) -> AsyncIterator[ExtendedAppContext]:
    """
    Extended application lifespan with our additional services
    """
    # Initialize Odoo client
    logger.info("Initializing Odoo client...")
    odoo_client = get_odoo_client()

    logger.info("Initializing extended services...")

    # Initialize our services
    discovery = OdooModelDiscovery(
        odoo_client=odoo_client,
        cache_ttl=300  # 5 minutes
    )

    safety = SafetyValidator()
    confirmation = ConfirmationHandler(safety)

    # Perform initial model discovery
    logger.info("Performing initial model discovery...")
    try:
        models = discovery.get_all_models()
        logger.info(f"Discovered {len(models)} models")
    except Exception as e:
        logger.error(f"Error during initial discovery: {e}")

    yield ExtendedAppContext(
        odoo=odoo_client,
        discovery=discovery,
        safety=safety,
        confirmation=confirmation,
    )

    logger.info("Extended services shutdown")


# Create extended MCP server
extended_mcp = FastMCP(
    "Odoo AI Agent - Extended Server",
    dependencies=["requests", "langchain"],
    lifespan=extended_app_lifespan,
)


def register_extended_tools():
    """
    Register all our extension tools with the extended server
    """
    logger.info("Registering extension tools...")

    # Register write operation tools
    register_write_tools(extended_mcp)

    # Register action operation tools
    register_action_tools(extended_mcp)

    logger.info("All extension tools registered")


# Register tools on module import
register_extended_tools()


# Export the extended server for use in other modules
__all__ = ["extended_mcp", "ExtendedAppContext", "extended_app_lifespan", "AppContext"]
