"""
Write operation tools for MCP server extension
Extends mcp-odoo with create, update, delete operations
"""
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from src.utils.logging import get_logger, audit_log, audit_log_json

logger = get_logger(__name__)


def _get_record_name(odoo, model: str, record_id: int) -> str:
    """Try to get display name for a record"""
    try:
        result = odoo.search_read(model, [["id", "=", record_id]], ["display_name", "name"], limit=1)
        if result:
            return result[0].get("display_name") or result[0].get("name") or f"#{record_id}"
    except Exception:
        pass
    return f"#{record_id}"


def _get_old_values(odoo, model: str, record_id: int, fields: list) -> dict:
    """Read current values of fields before update"""
    try:
        result = odoo.search_read(model, [["id", "=", record_id]], fields, limit=1)
        if result:
            return result[0]
    except Exception:
        pass
    return {}


# ============================================
# Pydantic Models for Type Safety
# ============================================


class CreateRecordRequest(BaseModel):
    """Request to create a new record"""

    model: str = Field(description="Model name (e.g., 'purchase.order')")
    values: Dict[str, Any] = Field(description="Field values for the new record")


class CreateRecordResponse(BaseModel):
    """Response from create_record operation"""

    success: bool = Field(description="Whether the operation succeeded")
    record_id: Optional[int] = Field(default=None, description="ID of created record")
    error: Optional[str] = Field(default=None, description="Error message if failed")


class UpdateRecordRequest(BaseModel):
    """Request to update a record"""

    model: str = Field(description="Model name (e.g., 'purchase.order')")
    record_id: int = Field(description="ID of the record to update")
    values: Dict[str, Any] = Field(description="Field values to update")


class UpdateRecordResponse(BaseModel):
    """Response from update_record operation"""

    success: bool = Field(description="Whether the operation succeeded")
    error: Optional[str] = Field(default=None, description="Error message if failed")


class DeleteRecordRequest(BaseModel):
    """Request to delete a record"""

    model: str = Field(description="Model name (e.g., 'purchase.order')")
    record_id: int = Field(description="ID of the record to delete")


class DeleteRecordResponse(BaseModel):
    """Response from delete_record operation"""

    success: bool = Field(description="Whether the operation succeeded")
    error: Optional[str] = Field(default=None, description="Error message if failed")


# ============================================
# Tool Registration
# ============================================

# Global variable to store MCP server instance
# Will be set when register_tools is called
_mcp_server = None


def register_tools(mcp_server):
    """
    Register write operation tools with the MCP server

    Args:
        mcp_server: FastMCP server instance
    """
    global _mcp_server
    _mcp_server = mcp_server

    @mcp_server.tool(description="Create a new record in Odoo")
    def create_record(
        ctx: Context,
        model: str,
        values: Dict[str, Any],
    ) -> CreateRecordResponse:
        """
        Create a new record in an Odoo model

        Parameters:
            model: The model name (e.g., 'purchase.order', 'res.partner')
            values: Dictionary of field values for the new record

        Returns:
            CreateRecordResponse with created record ID or error

        Example:
            create_record(model="purchase.order", values={
                "partner_id": 1,
                "date_order": "2026-01-19",
            })
        """
        odoo = ctx.request_context.lifespan_context.odoo
        user = getattr(ctx, "user", "system")

        try:
            logger.info(f"Creating record in {model}: {values}")

            # Execute create method
            record_id = odoo.execute_method(model, "create", [values])

            if record_id:
                # Get display name for the created record
                record_name = _get_record_name(odoo, model, record_id)

                logger.info(f"Successfully created {model} record with ID: {record_id}")

                # Log to JSONL audit
                audit_log_json(
                    action="create",
                    model=model,
                    record_id=record_id,
                    record_name=record_name,
                    user=user,
                    values=values,
                )

                return CreateRecordResponse(
                    success=True,
                    record_id=record_id
                )
            else:
                error_msg = f"Failed to create {model} record: No ID returned"
                logger.error(error_msg)
                return CreateRecordResponse(
                    success=False,
                    error=error_msg
                )

        except Exception as e:
            error_msg = f"Error creating {model} record: {str(e)}"
            logger.error(error_msg)
            return CreateRecordResponse(
                success=False,
                error=str(e)
            )

    @mcp_server.tool(description="Update an existing record in Odoo")
    def update_record(
        ctx: Context,
        model: str,
        record_id: int,
        values: Dict[str, Any],
    ) -> UpdateRecordResponse:
        """
        Update an existing record in an Odoo model

        Parameters:
            model: The model name (e.g., 'purchase.order', 'res.partner')
            record_id: ID of the record to update
            values: Dictionary of field values to update

        Returns:
            UpdateRecordResponse indicating success or failure

        Example:
            update_record(
                model="purchase.order",
                record_id=123,
                values={"state": "approved", "date_approve": "2026-01-19"}
            )
        """
        odoo = ctx.request_context.lifespan_context.odoo
        user = getattr(ctx, "user", "system")

        try:
            logger.info(f"Updating {model} record {record_id}: {values}")

            # Get old values before update for audit trail
            fields_to_read = list(values.keys()) + ["display_name", "name"]
            old_data = _get_old_values(odoo, model, record_id, fields_to_read)
            record_name = old_data.get("display_name") or old_data.get("name") or f"#{record_id}"

            # Execute write method
            result = odoo.execute_method(model, "write", [[record_id], values])

            if result:
                logger.info(f"Successfully updated {model} record {record_id}")

                # Build changes dict with old/new values
                changes = {}
                for field, new_value in values.items():
                    old_value = old_data.get(field)
                    # Handle Many2one fields (tuples like (id, name))
                    if isinstance(old_value, (list, tuple)) and len(old_value) == 2:
                        old_value = old_value[1]  # Get display name
                    changes[field] = {"old": old_value, "new": new_value}

                # Log to JSONL audit
                audit_log_json(
                    action="update",
                    model=model,
                    record_id=record_id,
                    record_name=record_name,
                    user=user,
                    changes=changes,
                )

                return UpdateRecordResponse(success=True)
            else:
                error_msg = f"Failed to update {model} record {record_id}"
                logger.error(error_msg)
                return UpdateRecordResponse(
                    success=False,
                    error=error_msg
                )

        except Exception as e:
            error_msg = f"Error updating {model} record {record_id}: {str(e)}"
            logger.error(error_msg)
            return UpdateRecordResponse(
                success=False,
                error=str(e)
            )

    @mcp_server.tool(description="Delete a record from Odoo")
    def delete_record(
        ctx: Context,
        model: str,
        record_id: int,
    ) -> DeleteRecordResponse:
        """
        Delete a record from an Odoo model

        Parameters:
            model: The model name (e.g., 'purchase.order', 'res.partner')
            record_id: ID of the record to delete

        Returns:
            DeleteRecordResponse indicating success or failure

        Example:
            delete_record(model="purchase.order", record_id=123)

        Note: This is a destructive action. Consider using workflow state
        changes instead of deletion when possible.
        """
        odoo = ctx.request_context.lifespan_context.odoo
        user = getattr(ctx, "user", "system")

        try:
            logger.warning(f"Deleting {model} record {record_id}")

            # Get record data before deletion for audit trail
            old_data = _get_old_values(odoo, model, record_id, ["display_name", "name"])
            record_name = old_data.get("display_name") or old_data.get("name") or f"#{record_id}"

            # Try to get all field values for complete audit
            try:
                full_data = odoo.search_read(model, [["id", "=", record_id]], [], limit=1)
                values_before_delete = full_data[0] if full_data else old_data
            except Exception:
                values_before_delete = old_data

            # Execute unlink method
            result = odoo.execute_method(model, "unlink", [[record_id]])

            if result:
                logger.warning(f"Successfully deleted {model} record {record_id}")

                # Log to JSONL audit
                audit_log_json(
                    action="delete",
                    model=model,
                    record_id=record_id,
                    record_name=record_name,
                    user=user,
                    values=values_before_delete,
                )

                return DeleteRecordResponse(success=True)
            else:
                error_msg = f"Failed to delete {model} record {record_id}"
                logger.error(error_msg)
                return DeleteRecordResponse(
                    success=False,
                    error=error_msg
                )

        except Exception as e:
            error_msg = f"Error deleting {model} record {record_id}: {str(e)}"
            logger.error(error_msg)
            return DeleteRecordResponse(
                success=False,
                error=str(e)
            )

    logger.info("Write operation tools registered successfully")
