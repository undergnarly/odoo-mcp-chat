"""
Logging configuration for Odoo AI Agent
"""
import json
import sys
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger

from src.config import get_settings


# Context variable for session tracking
_session_id: ContextVar[Optional[str]] = ContextVar("session_id", default=None)
_thread_id: ContextVar[Optional[str]] = ContextVar("thread_id", default=None)


def set_session_context(session_id: Optional[str] = None, thread_id: Optional[str] = None):
    """Set the current session context for logging"""
    if session_id:
        _session_id.set(session_id)
    if thread_id:
        _thread_id.set(thread_id)


def get_session_context() -> Dict[str, Optional[str]]:
    """Get the current session context"""
    return {
        "session_id": _session_id.get(),
        "thread_id": _thread_id.get(),
    }


def clear_session_context():
    """Clear the session context"""
    _session_id.set(None)
    _thread_id.set(None)


def _format_with_context(record):
    """Add session context to log record"""
    session_id = _session_id.get()
    thread_id = _thread_id.get()

    # Add context to extra
    record["extra"]["session_id"] = session_id[:8] if session_id else "-"
    record["extra"]["thread_id"] = thread_id[:8] if thread_id else "-"
    return True


def setup_logging():
    """
    Configure Loguru logging for the application with session context
    """
    settings = get_settings()

    # Remove default handler
    logger.remove()

    # Console handler with colors and session context
    logger.add(
        sys.stdout,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>[{extra[session_id]}]</cyan> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        level=settings.log_level,
        colorize=True,
        filter=_format_with_context,
    )

    # File handler for all logs with session context
    logger.add(
        settings.log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | [{extra[session_id]}:{extra[thread_id]}] | {name}:{function}:{line} | {message}",
        level="DEBUG",
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        filter=_format_with_context,
    )

    # Separate audit log for actions
    audit_log_path = Path(settings.audit_log)
    if audit_log_path.parent != Path(settings.log_file).parent:
        audit_log_path.parent.mkdir(parents=True, exist_ok=True)

    def _audit_filter(record):
        _format_with_context(record)
        return record["extra"].get("audit") is True

    logger.add(
        settings.audit_log,
        format="{time:YYYY-MM-DD HH:mm:ss} | [{extra[session_id]}] | {message}",
        level="INFO",
        filter=_audit_filter,
        rotation="10 MB",
        retention="365 days",
        compression="zip",
    )

    # Chat error log - separate file for tracking chat-specific errors
    chat_error_log = Path(settings.log_file).parent / "chat_errors.jsonl"
    logger.add(
        str(chat_error_log),
        format="{message}",
        level="ERROR",
        filter=lambda record: record["extra"].get("chat_error") is True,
        rotation="10 MB",
        retention="30 days",
    )

    logger.info(f"Logging initialized. Level: {settings.log_level}")
    logger.info(f"Log file: {settings.log_file}")
    logger.info(f"Audit log: {settings.audit_log}")
    logger.info(f"Chat error log: {chat_error_log}")

    return logger


def get_logger(name: Optional[str] = None):
    """
    Get a logger instance

    Args:
        name: Optional name for the logger

    Returns:
        Logger instance
    """
    if name:
        return logger.bind(name=name)
    return logger


def audit_log(action: str, user: str, details: dict, **kwargs):
    """
    Log an audit event

    Args:
        action: Action performed (e.g., 'create_record', 'approve_po')
        user: User who performed the action
        details: Dictionary with action details
        **kwargs: Additional fields to log
    """
    log_data = {
        "action": action,
        "user": user,
        **details,
        **kwargs,
    }

    # Format as JSON-like string
    parts = [f"{k}={v}" for k, v in log_data.items()]
    logger.bind(audit=True).info(" | ".join(parts))


def log_chat_error(
    error_type: str,
    error_message: str,
    user_input: Optional[str] = None,
    model: Optional[str] = None,
    intent: Optional[str] = None,
    stack_trace: Optional[str] = None,
    **kwargs
):
    """
    Log a chat-specific error in JSON format for debugging

    Args:
        error_type: Type of error (e.g., 'intent_classification', 'query_execution', 'filter_parse')
        error_message: The error message
        user_input: The user's original input
        model: Odoo model being queried (if applicable)
        intent: Detected intent (if applicable)
        stack_trace: Full stack trace (if available)
        **kwargs: Additional context
    """
    context = get_session_context()

    error_data = {
        "timestamp": datetime.now().isoformat(),
        "session_id": context.get("session_id"),
        "thread_id": context.get("thread_id"),
        "error_type": error_type,
        "error_message": str(error_message),
        "user_input": user_input[:500] if user_input else None,
        "model": model,
        "intent": intent,
        "stack_trace": stack_trace,
        **kwargs
    }

    # Remove None values for cleaner logs
    error_data = {k: v for k, v in error_data.items() if v is not None}

    logger.bind(chat_error=True).error(json.dumps(error_data))


def get_session_logger(session_id: str, thread_id: Optional[str] = None):
    """
    Get a logger instance bound to a specific session

    Args:
        session_id: The session ID to bind
        thread_id: Optional thread ID to bind

    Returns:
        Logger instance with session context
    """
    set_session_context(session_id=session_id, thread_id=thread_id)
    return logger.bind(session_id=session_id[:8] if session_id else "-")
