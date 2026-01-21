"""
Write operation tools for MCP server extension
Extends mcp-odoo with create, update, delete operations
"""
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from src.utils.logging import get_logger, audit_log

logger = get_logger(__name__)


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
            audit_log(
                action="create_record_attempt",
                user=user,
                details={"model": model, "values": str(values)}
            )

            # Execute create method
            record_id = odoo.execute_method(model, "create", [values])

            if record_id:
                logger.info(f"Successfully created {model} record with ID: {record_id}")
                audit_log(
                    action="create_record_success",
                    user=user,
                    details={"model": model, "record_id": record_id}
                )
                return CreateRecordResponse(
                    success=True,
                    record_id=record_id
                )
            else:
                error_msg = f"Failed to create {model} record: No ID returned"
                logger.error(error_msg)
                audit_log(
                    action="create_record_failed",
                    user=user,
                    details={"model": model, "error": error_msg}
                )
                return CreateRecordResponse(
                    success=False,
                    error=error_msg
                )

        except Exception as e:
            error_msg = f"Error creating {model} record: {str(e)}"
            logger.error(error_msg)
            audit_log(
                action="create_record_error",
                user=user,
                details={"model": model, "error": str(e)}
            )
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
            audit_log(
                action="update_record_attempt",
                user=user,
                details={"model": model, "record_id": record_id, "values": str(values)}
            )

            # Execute write method
            result = odoo.execute_method(model, "write", [[record_id], values])

            if result:
                logger.info(f"Successfully updated {model} record {record_id}")
                audit_log(
                    action="update_record_success",
                    user=user,
                    details={"model": model, "record_id": record_id}
                )
                return UpdateRecordResponse(success=True)
            else:
                error_msg = f"Failed to update {model} record {record_id}"
                logger.error(error_msg)
                audit_log(
                    action="update_record_failed",
                    user=user,
                    details={"model": model, "record_id": record_id, "error": error_msg}
                )
                return UpdateRecordResponse(
                    success=False,
                    error=error_msg
                )

        except Exception as e:
            error_msg = f"Error updating {model} record {record_id}: {str(e)}"
            logger.error(error_msg)
            audit_log(
                action="update_record_error",
                user=user,
                details={"model": model, "record_id": record_id, "error": str(e)}
            )
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
            audit_log(
                action="delete_record_attempt",
                user=user,
                details={"model": model, "record_id": record_id}
            )

            # Execute unlink method
            result = odoo.execute_method(model, "unlink", [[record_id]])

            if result:
                logger.warning(f"Successfully deleted {model} record {record_id}")
                audit_log(
                    action="delete_record_success",
                    user=user,
                    details={"model": model, "record_id": record_id}
                )
                return DeleteRecordResponse(success=True)
            else:
                error_msg = f"Failed to delete {model} record {record_id}"
                logger.error(error_msg)
                audit_log(
                    action="delete_record_failed",
                    user=user,
                    details={"model": model, "record_id": record_id, "error": error_msg}
                )
                return DeleteRecordResponse(
                    success=False,
                    error=error_msg
                )

        except Exception as e:
            error_msg = f"Error deleting {model} record {record_id}: {str(e)}"
            logger.error(error_msg)
            audit_log(
                action="delete_record_error",
                user=user,
                details={"model": model, "record_id": record_id, "error": str(e)}
            )
            return DeleteRecordResponse(
                success=False,
                error=str(e)
            )

    logger.info("Write operation tools registered successfully")
