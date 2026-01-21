"""
FastAPI REST API for Odoo AI Agent
"""
import os
import sys
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.config import get_settings
from src.utils.logging import setup_logging, get_logger
from odoo_mcp.odoo_client import get_odoo_client

# Setup logging
logger_instance = setup_logging()
logger = get_logger(__name__)

# Initialize settings
settings = get_settings()

# Initialize FastAPI app
app = FastAPI(
    title="Odoo AI Agent API",
    description="REST API for Odoo AI Agent microservice",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================
# Request/Response Models
# ============================================


class QueryRequest(BaseModel):
    """Request model for /api/query endpoint"""

    message: str = Field(..., description="Natural language query")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")


class QueryResponse(BaseModel):
    """Response model for /api/query endpoint"""

    success: bool
    type: str
    content: str
    data: Optional[Dict[str, Any]] = None


class ActionRequest(BaseModel):
    """Request model for /api/action endpoint"""

    message: str = Field(..., description="Natural language action description")
    confirm: bool = Field(default=False, description="Whether action is confirmed")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")


class ActionResponse(BaseModel):
    """Response model for /api/action endpoint"""

    success: bool
    type: str
    content: str
    requires_confirmation: bool = False
    result: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    """Response model for /health endpoint"""

    status: str
    version: str
    odoo_connected: bool
    llm_configured: bool


# ============================================
# API Key Authentication
# ============================================


async def verify_api_key(x_api_key: Optional[str] = Header(None)) -> None:
    """
    Verify API key if enabled

    Args:
        x_api_key: API key from header

    Raises:
        HTTPException: If authentication fails
    """
    if settings.api_key_enabled:
        if not x_api_key:
            raise HTTPException(status_code=401, detail="API key required")

        if x_api_key != settings.admin_api_key:
            raise HTTPException(status_code=403, detail="Invalid API key")


# ============================================
# Endpoints
# ============================================


@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint"""
    return {
        "message": "Odoo AI Agent API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint

    Returns system status and connectivity information
    """
    odoo_connected = False
    llm_configured = False

    # Check Odoo connection
    try:
        odoo_client = get_odoo_client()
        if odoo_client.uid:
            odoo_connected = True
    except Exception as e:
        logger.warning(f"Odoo health check failed: {e}")

    # Check LLM configuration
    llm_configured = bool(settings.anthropic_api_key or settings.openai_api_key)

    return HealthResponse(
        status="healthy" if odoo_connected else "degraded",
        version="1.0.0",
        odoo_connected=odoo_connected,
        llm_configured=llm_configured,
    )


@app.post("/api/query", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    _: None = Depends(verify_api_key),
) -> QueryResponse:
    """
    Process a natural language query

    This endpoint analyzes the user's natural language request,
    determines the intent, and executes the appropriate Odoo query
    using the LangChain agent for intelligent intent routing.
    """
    try:
        logger.info(f"Query request: {request.message[:100]}...")

        # Get Odoo client and initialize agent
        odoo = get_odoo_client()

        # Import here to avoid circular imports
        from src.agent.langchain_agent import OdooAgent
        from src.extensions.discovery import OdooModelDiscovery

        # Initialize discovery and agent
        discovery = OdooModelDiscovery(odoo, cache_ttl=settings.model_cache_ttl)
        agent = OdooAgent(odoo, discovery)

        # Process message through the agent (uses LLM for intent classification)
        response = await agent.process_message(
            request.message,
            user_context=request.context
        )

        response_type = response.get("type", "default")

        if response_type == "query_result":
            return QueryResponse(
                success=True,
                type="query_result",
                content=response.get("content", ""),
                data={
                    "model": response.get("model"),
                    "count": response.get("count", 0),
                    "results": response.get("results", []),
                },
            )
        elif response_type == "error":
            return QueryResponse(
                success=False,
                type="error",
                content=response.get("content", "Unknown error"),
            )
        elif response_type == "clarification":
            return QueryResponse(
                success=True,
                type="clarification",
                content=response.get("content", ""),
            )
        else:
            return QueryResponse(
                success=True,
                type=response_type,
                content=response.get("content", ""),
                data=response,
            )

    except Exception as e:
        logger.error(f"Error in /api/query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/action", response_model=ActionResponse)
async def action(
    request: ActionRequest,
    _: None = Depends(verify_api_key),
) -> ActionResponse:
    """
    Process an action request

    This endpoint handles write operations, actions, and workflows.
    Confirmations are required for destructive actions.
    Uses LangChain agent for intelligent intent routing and safety layer.
    """
    try:
        logger.info(f"Action request: {request.message[:100]}...")

        # Get Odoo client and initialize agent
        odoo = get_odoo_client()

        # Import here to avoid circular imports
        from src.agent.langchain_agent import OdooAgent
        from src.extensions.discovery import OdooModelDiscovery

        # Initialize discovery and agent
        discovery = OdooModelDiscovery(odoo, cache_ttl=settings.model_cache_ttl)
        agent = OdooAgent(odoo, discovery)

        # Process message through the agent
        response = await agent.process_message(
            request.message,
            user_context=request.context
        )

        response_type = response.get("type", "default")

        # Handle confirmation flow
        if response_type == "confirmation_required":
            if request.confirm:
                # User confirmed - execute the action
                execution_result = await agent.execute_confirmed_action(response)
                return ActionResponse(
                    success=execution_result.get("success", False),
                    type="action_result",
                    content=execution_result.get("content", "Action executed"),
                    requires_confirmation=False,
                    result=execution_result,
                )
            else:
                # Return confirmation request
                return ActionResponse(
                    success=True,
                    type="confirmation_required",
                    content=response.get("content", "Please confirm this action"),
                    requires_confirmation=True,
                    result={
                        "operation": response.get("operation"),
                        "model": response.get("model"),
                        "record_id": response.get("record_id"),
                        "values": response.get("values"),
                        "method": response.get("method"),
                    },
                )
        elif response_type == "error":
            return ActionResponse(
                success=False,
                type="error",
                content=response.get("content", "Unknown error"),
                requires_confirmation=False,
            )
        else:
            return ActionResponse(
                success=True,
                type=response_type,
                content=response.get("content", ""),
                requires_confirmation=False,
                result=response,
            )

    except Exception as e:
        logger.error(f"Error in /api/action: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/models", response_model=Dict[str, Any])
async def list_models(
    _: None = Depends(verify_api_key),
) -> Dict[str, Any]:
    """
    List all available Odoo models

    Returns a list of models that can be queried
    """
    try:
        odoo = get_odoo_client()
        models_info = odoo.get_models()

        return {
            "success": True,
            "models": models_info.get("model_names", []),
            "total": len(models_info.get("model_names", [])),
        }

    except Exception as e:
        logger.error(f"Error in /models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/models/{model_name}", response_model=Dict[str, Any])
async def get_model_details(
    model_name: str,
    _: None = Depends(verify_api_key),
) -> Dict[str, Any]:
    """
    Get details about a specific model

    Returns field definitions and metadata
    """
    try:
        odoo = get_odoo_client()

        # Get model info
        model_info = odoo.get_model_info(model_name)

        # Get fields
        fields = odoo.get_model_fields(model_name)

        return {
            "success": True,
            "model": model_name,
            "info": model_info,
            "fields": fields,
        }

    except Exception as e:
        logger.error(f"Error in /models/{model_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Startup Event
# ============================================


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("=== Odoo AI Agent API Starting ===")
    logger.info(f"Version: 1.0.0")
    logger.info(f"Odoo URL: {settings.odoo_url}")
    logger.info(f"Database: {settings.odoo_db}")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    logger.info(f"API Key Enabled: {settings.api_key_enabled}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("=== Odoo AI Agent API Shutting Down ===")


# ============================================
# Run Server
# ============================================


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.rest:app",
        host=settings.service_host,
        port=settings.service_port,
        reload=True,
        log_level=settings.log_level.lower(),
    )
