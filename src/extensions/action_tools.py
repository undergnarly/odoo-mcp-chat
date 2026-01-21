"""
Action operation tools for MCP server extension
Extends mcp-odoo with action calls, messaging, and file attachments
"""
import base64
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from src.utils.logging import get_logger, audit_log

logger = get_logger(__name__)


# ============================================
# Pydantic Models for Type Safety
# ============================================


class CallActionResponse(BaseModel):
    """Response from call_action operation"""

    success: bool = Field(description="Whether the action succeeded")
    result: Optional[Any] = Field(default=None, description="Action result if successful")
    error: Optional[str] = Field(default=None, description="Error message if failed")


class PostMessageResponse(BaseModel):
    """Response from post_message operation"""

    success: bool = Field(description="Whether the message was posted")
    message_id: Optional[int] = Field(default=None, description="ID of posted message")
    error: Optional[str] = Field(default=None, description="Error message if failed")


class AttachFileResponse(BaseModel):
    """Response from attach_file operation"""

    success: bool = Field(description="Whether the file was attached")
    attachment_id: Optional[int] = Field(default=None, description="ID of attachment")
    error: Optional[str] = Field(default=None, description="Error message if failed")


# ============================================
# Tool Registration
# ============================================


def register_tools(mcp_server):
    """
    Register action operation tools with the MCP server

    Args:
        mcp_server: FastMCP server instance
    """

    @mcp_server.tool(description="Call an action method on an Odoo record")
    def call_action(
        ctx: Context,
        model: str,
        record_id: int,
        method_name: str,
        args: Optional[List[Any]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> CallActionResponse:
        """
        Call an action method on a specific Odoo record

        This is used to trigger button actions, workflow transitions,
        and other record-specific methods.

        Parameters:
            model: The model name (e.g., 'purchase.order')
            record_id: ID of the record to act on
            method_name: Name of the method to call (e.g., 'button_confirm',
                        'action_approve', 'action_rfq_send')
            args: Optional positional arguments for the method
            kwargs: Optional keyword arguments for the method

        Returns:
            CallActionResponse with result or error

        Examples:
            # Approve a purchase order
            call_action(
                model="purchase.order",
                record_id=123,
                method_name="button_approve"
            )

            # Send RFQ to suppliers
            call_action(
                model="purchase.order",
                record_id=123,
                method_name="action_rfq_send"
            )

            # Confirm a sale order
            call_action(
                model="sale.order",
                record_id=456,
                method_name="action_confirm"
            )
        """
        odoo = ctx.request_context.lifespan_context.odoo
        user = getattr(ctx, "user", "system")

        try:
            logger.info(f"Calling {method_name} on {model} record {record_id}")
            audit_log(
                action="call_action_attempt",
                user=user,
                details={
                    "model": model,
                    "record_id": record_id,
                    "method": method_name,
                    "args": str(args),
                    "kwargs": str(kwargs)
                }
            )

            # Prepare arguments
            call_args = args or []
            call_kwargs = kwargs or {}

            # Execute the method
            result = odoo.execute_method(model, method_name, [record_id] + call_args, call_kwargs)

            logger.info(f"Successfully called {method_name} on {model} record {record_id}")
            audit_log(
                action="call_action_success",
                user=user,
                details={
                    "model": model,
                    "record_id": record_id,
                    "method": method_name
                }
            )

            return CallActionResponse(
                success=True,
                result=result
            )

        except Exception as e:
            error_msg = f"Error calling {method_name} on {model} record {record_id}: {str(e)}"
            logger.error(error_msg)
            audit_log(
                action="call_action_error",
                user=user,
                details={
                    "model": model,
                    "record_id": record_id,
                    "method": method_name,
                    "error": str(e)
                }
            )

            return CallActionResponse(
                success=False,
                error=str(e)
            )

    @mcp_server.tool(description="Post a message to a record's chatter")
    def post_message(
        ctx: Context,
        model: str,
        record_id: int,
        body: str,
        subject: Optional[str] = None,
        message_type: str = "comment",
        subtype_xmlid: Optional[str] = None,
    ) -> PostMessageResponse:
        """
        Post a message to a record's chatter (discussion thread)

        Parameters:
            model: The model name (e.g., 'purchase.order', 'sale.order')
            record_id: ID of the record to post message to
            body: Message body text
            subject: Optional subject line
            message_type: Type of message ('comment', 'email', 'notification')
            subtype_xmlid: Optional subtype XML ID (e.g., 'mail.mt_comment')

        Returns:
            PostMessageResponse with message ID or error

        Examples:
            # Add a comment to a purchase order
            post_message(
                model="purchase.order",
                record_id=123,
                body="Please expedite this order"
            )

            # Send an email notification
            post_message(
                model="purchase.order",
                record_id=123,
                body="Your order has been approved",
                message_type="email"
            )
        """
        odoo = ctx.request_context.lifespan_context.odoo
        user = getattr(ctx, "user", "system")

        try:
            logger.info(f"Posting message to {model} record {record_id}")
            audit_log(
                action="post_message_attempt",
                user=user,
                details={
                    "model": model,
                    "record_id": record_id,
                    "body": body[:100] + "..." if len(body) > 100 else body
                }
            )

            # Prepare message values
            message_values = {
                "body": body,
                "model": model,
                "res_id": record_id,
                "message_type": message_type,
            }

            if subject:
                message_values["subject"] = subject

            if subtype_xmlid:
                # Get subtype ID from XML ID
                subtype_data = odoo.execute_method(
                    "ir.model.data",
                    "xmlid_to_res_id",
                    subtype_xmlid
                )
                if subtype_data:
                    message_values["subtype_id"] = subtype_data

            # Create the message
            message_id = odoo.execute_method("mail.message", "create", [message_values])

            logger.info(f"Successfully posted message to {model} record {record_id}, message_id={message_id}")
            audit_log(
                action="post_message_success",
                user=user,
                details={
                    "model": model,
                    "record_id": record_id,
                    "message_id": message_id
                }
            )

            return PostMessageResponse(
                success=True,
                message_id=message_id
            )

        except Exception as e:
            error_msg = f"Error posting message to {model} record {record_id}: {str(e)}"
            logger.error(error_msg)
            audit_log(
                action="post_message_error",
                user=user,
                details={
                    "model": model,
                    "record_id": record_id,
                    "error": str(e)
                }
            )

            return PostMessageResponse(
                success=False,
                error=str(e)
            )

    @mcp_server.tool(description="Attach a file to a record")
    def attach_file(
        ctx: Context,
        model: str,
        record_id: int,
        filename: str,
        file_content_b64: str,  # Base64 encoded file content
        mimetype: Optional[str] = None,
        name: Optional[str] = None,
    ) -> AttachFileResponse:
        """
        Attach a file to an Odoo record

        Parameters:
            model: The model name (e.g., 'purchase.order', 'hr.employee')
            record_id: ID of the record to attach file to
            filename: Name of the file (e.g., 'invoice.pdf')
            file_content_b64: Base64 encoded file content
            mimetype: Optional MIME type (e.g., 'application/pdf')
            name: Optional display name for the attachment

        Returns:
            AttachFileResponse with attachment ID or error

        Examples:
            # Attach a PDF invoice
            attach_file(
                model="purchase.order",
                record_id=123,
                filename="invoice.pdf",
                file_content_b64="JVBERi0xLjQK...",
                mimetype="application/pdf"
            )

            # Attach an image
            attach_file(
                model="hr.employee",
                record_id=456,
                filename="photo.jpg",
                file_content_b64="/9j/4AAQSkZJRg...",
                mimetype="image/jpeg"
            )
        """
        odoo = ctx.request_context.lifespan_context.odoo
        user = getattr(ctx, "user", "system")

        try:
            logger.info(f"Attaching file '{filename}' to {model} record {record_id}")
            audit_log(
                action="attach_file_attempt",
                user=user,
                details={
                    "model": model,
                    "record_id": record_id,
                    "filename": filename
                }
            )

            # Decode base64 content
            try:
                file_data = base64.b64decode(file_content_b64)
            except Exception as e:
                raise ValueError(f"Invalid base64 content: {str(e)}")

            # Prepare attachment values
            attachment_values = {
                "name": name or filename,
                "datas": base64.b64encode(file_data).decode("ascii"),
                "res_model": model,
                "res_id": record_id,
                "res_name": filename,
            }

            if mimetype:
                attachment_values["mimetype"] = mimetype

            # Create the attachment
            attachment_id = odoo.execute_method("ir.attachment", "create", [attachment_values])

            logger.info(
                f"Successfully attached '{filename}' to {model} record {record_id}, "
                f"attachment_id={attachment_id}, size={len(file_data)} bytes"
            )
            audit_log(
                action="attach_file_success",
                user=user,
                details={
                    "model": model,
                    "record_id": record_id,
                    "filename": filename,
                    "attachment_id": attachment_id,
                    "size_bytes": len(file_data)
                }
            )

            return AttachFileResponse(
                success=True,
                attachment_id=attachment_id
            )

        except Exception as e:
            error_msg = f"Error attaching file to {model} record {record_id}: {str(e)}"
            logger.error(error_msg)
            audit_log(
                action="attach_file_error",
                user=user,
                details={
                    "model": model,
                    "record_id": record_id,
                    "filename": filename,
                    "error": str(e)
                }
            )

            return AttachFileResponse(
                success=False,
                error=str(e)
            )

    logger.info("Action operation tools registered successfully")
