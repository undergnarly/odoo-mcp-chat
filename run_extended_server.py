#!/usr/bin/env python
"""
Run the extended Odoo MCP server with all our extensions
"""
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.utils.logging import setup_logging
from src.config import get_settings
from src.extensions.extended_server import extended_mcp

# Import run_server from mcp-odoo to use its main logic
from mcp_odoo.run_server import main as base_main, setup_logging as base_setup_logging


def main() -> int:
    """
    Run the extended Odoo MCP server
    """
    # Setup our logging first
    logger = setup_logging()

    logger.info("=== ODOO AI AGENT - EXTENDED MCP SERVER STARTING ===")

    # Show configuration
    settings = get_settings()
    logger.info(f"Odoo URL: {settings.odoo_url}")
    logger.info(f"Database: {settings.odoo_db}")
    logger.info(f"LLM Provider: {settings.llm_provider}")

    # The extended_mcp server will be used by the MCP protocol
    # For now, we need to integrate it with the stdio server

    # NOTE: The original run_server.py instantiates the base 'mcp' from odoo_mcp.server
    # We need to modify this to use our extended_mcp instead

    # For now, let's create a simple runner for our extended server
    import anyio
    from mcp.server.stdio import stdio_server

    async def arun():
        logger.info("Starting Extended Odoo MCP server with stdio transport...")
        logger.info(f"Extended MCP server type: {type(extended_mcp)}")

        async with stdio_server() as streams:
            logger.info("Stdio server initialized, running extended MCP server...")
            await extended_mcp._mcp_server.run(
                streams[0], streams[1], extended_mcp._mcp_server.create_initialization_options()
            )

    try:
        anyio.run(arun)
        logger.info("Extended MCP server stopped normally")
        return 0
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
