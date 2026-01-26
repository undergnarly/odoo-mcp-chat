"""API authentication middleware."""
import logging
from typing import Dict, Any

from fastapi import HTTPException, Security, Request
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    request: Request,
    api_key: str = Security(api_key_header)
) -> Dict[str, Any]:
    """
    Verify API key from request header.

    Returns:
        Key metadata dict with id, name, permissions, created_by

    Raises:
        HTTPException 401 if key is missing or invalid
    """
    from src.security.api_keys import get_api_key_manager

    if not api_key:
        logger.warning("API request without X-API-Key header")
        raise HTTPException(
            status_code=401,
            detail={"code": "MISSING_API_KEY", "message": "X-API-Key header is required"}
        )

    manager = await get_api_key_manager()
    key_data = await manager.verify_key(api_key)

    if not key_data:
        logger.warning("API request with invalid API key")
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_API_KEY", "message": "Invalid API key"}
        )

    # Log usage
    try:
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("User-Agent")
        await manager.log_usage(
            key_id=key_data["id"],
            endpoint=str(request.url.path),
            method=request.method,
            ip_address=client_ip,
            user_agent=user_agent,
        )
    except Exception as e:
        logger.error(f"Failed to log API usage: {e}")

    return key_data
