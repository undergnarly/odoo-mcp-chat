"""
RAG (Retrieval-Augmented Generation) module for Odoo AI Agent.

This module provides:
- Schema caching for Odoo models
- Value validation before write operations
- Field injection for LLM prompts
"""

from src.rag.schema_cache import OdooSchemaCache, ModelSchema, FieldSchema
from src.rag.validator import OdooValueValidator

__all__ = [
    "OdooSchemaCache",
    "ModelSchema",
    "FieldSchema",
    "OdooValueValidator",
]
