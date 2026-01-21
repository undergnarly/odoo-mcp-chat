"""
Safety layer for write operations
Provides confirmation prompts, permission checks, and audit logging
"""
import json
from typing import Any, Callable, Dict, List, Optional
from enum import Enum
from dataclasses import dataclass

from src.utils.logging import get_logger, audit_log

logger = get_logger(__name__)


class DangerLevel(Enum):
    """Danger level of operations"""
    SAFE = "safe"  # No confirmation needed
    LOW = "low"  # Optional confirmation
    MEDIUM = "medium"  # Confirmation required
    HIGH = "high"  # Explicit confirmation required
    DESTRUCTIVE = "destructive"  # Strong warning + confirmation


@dataclass
class SafetyCheck:
    """Result of a safety check"""
    is_safe: bool
    danger_level: DangerLevel
    warning_message: Optional[str] = None
    requires_confirmation: bool = False
    blocked_reason: Optional[str] = None


class SafetyValidator:
    """
    Validates operations for safety before execution
    """

    # Destructive operations that require extra confirmation
    DESTRUCTIVE_OPERATIONS = {
        "unlink",
        "action_cancel",
        "button_cancel",
    }

    # Models that are extra sensitive
    SENSITIVE_MODELS = {
        "res.users": DangerLevel.HIGH,
        "res.groups": DangerLevel.HIGH,
        "ir.ui.view": DangerLevel.MEDIUM,
        "ir.model.access": DangerLevel.HIGH,
        "account.move": DangerLevel.MEDIUM,
        "hr.employee": DangerLevel.MEDIUM,
    }

    # Write operations that are generally safe
    SAFE_WRITE_MODELS = {
        "mail.message",
        "mail.compose.message",
    }

    def __init__(self):
        """Initialize the safety validator"""
        self.pending_confirmations: Dict[str, Dict] = {}
        logger.info("SafetyValidator initialized")

    def check_operation(
        self,
        operation_type: str,
        model: str,
        method: Optional[str] = None,
        values: Optional[Dict] = None,
        record_id: Optional[int] = None,
    ) -> SafetyCheck:
        """
        Check if an operation is safe to perform

        Args:
            operation_type: Type of operation ('create', 'write', 'unlink', 'action')
            model: Model name
            method: Method name (for actions)
            values: Values being written
            record_id: Record ID being affected

        Returns:
            SafetyCheck with validation result
        """
        danger_level = DangerLevel.SAFE
        warning_messages = []

        # Check operation type
        if operation_type == "unlink":
            danger_level = max(danger_level, DangerLevel.DESTRUCTIVE)
            warning_messages.append("⚠️ This will permanently delete the record")

        elif operation_type == "write" or operation_type == "action":
            # Check if it's a destructive action
            if method in self.DESTRUCTIVE_OPERATIONS:
                danger_level = max(danger_level, DangerLevel.HIGH)
                warning_messages.append(f"⚠️ Destructive action: {method}")

        # Check model sensitivity
        if model in self.SENSITIVE_MODELS:
            model_danger = self.SENSITIVE_MODELS[model]
            danger_level = max(danger_level, model_danger)
            warning_messages.append(f"⚠️ Sensitive model: {model}")

        # Check for bulk operations
        if operation_type == "write" and record_id is None:
            danger_level = max(danger_level, DangerLevel.HIGH)
            warning_messages.append("⚠️ Bulk operation - multiple records will be affected")

        # Check for critical field changes
        if values:
            critical_fields = ["state", "stage_id", "user_id", "company_id"]
            for field in critical_fields:
                if field in values:
                    danger_level = max(danger_level, DangerLevel.MEDIUM)
                    warning_messages.append(f"⚠️ Changing critical field: {field}")

        # Check if safe write model (like mail.message)
        if model in self.SAFE_WRITE_MODELS and operation_type == "create":
            danger_level = DangerLevel.SAFE
            warning_messages = []

        # Determine if confirmation is required
        requires_confirmation = danger_level in [
            DangerLevel.MEDIUM,
            DangerLevel.HIGH,
            DangerLevel.DESTRUCTIVE,
        ]

        # Check if operation is blocked
        blocked_reason = None
        is_safe = True

        # Add safety rules here if needed
        # For example, block operations on certain models in production

        return SafetyCheck(
            is_safe=is_safe,
            danger_level=danger_level,
            warning_message=" ".join(warning_messages) if warning_messages else None,
            requires_confirmation=requires_confirmation,
            blocked_reason=blocked_reason,
        )

    def require_confirmation(
        self,
        operation_id: str,
        model: str,
        operation_type: str,
        details: Dict,
    ) -> str:
        """
        Store a pending confirmation request

        Args:
            operation_id: Unique ID for this operation
            model: Model name
            operation_type: Type of operation
            details: Operation details

        Returns:
            Confirmation message for user
        """
        self.pending_confirmations[operation_id] = {
            "model": model,
            "operation_type": operation_type,
            "details": details,
            "timestamp": None,  # Will be set when needed
        }

        # Generate user-friendly confirmation message
        model_readable = model.replace(".", " ").title()

        message = f"⚠️ **Confirmation Required**\n\n"
        message += f"**Operation:** {operation_type.upper()}\n"
        message += f"**Model:** {model_readable}\n"

        if operation_type == "create":
            message += f"**Creating:** {details.get('values', {})}\n"
        elif operation_type == "write" or operation_type == "unlink":
            message += f"**Record ID:** {details.get('record_id')}\n"
            if "values" in details:
                message += f"**Changes:** {details['values']}\n"
        elif operation_type == "action":
            message += f"**Action:** {details.get('method')}\n"
            message += f"**Record ID:** {details.get('record_id')}\n"

        message += "\nDo you want to proceed? (yes/no)"

        logger.info(f"Confirmation required for operation {operation_id}")
        return message

    def confirm_operation(self, operation_id: str, confirmed: bool) -> bool:
        """
        Process user confirmation

        Args:
            operation_id: Operation ID
            confirmed: Whether user confirmed

        Returns:
            True if operation should proceed
        """
        if operation_id not in self.pending_confirmations:
            logger.warning(f"Unknown operation ID: {operation_id}")
            return False

        if not confirmed:
            logger.info(f"Operation {operation_id} cancelled by user")
            audit_log(
                action="operation_cancelled",
                user="system",
                details={"operation_id": operation_id}
            )
            # Remove from pending
            del self.pending_confirmations[operation_id]
            return False

        logger.info(f"Operation {operation_id} confirmed by user")
        audit_log(
            action="operation_confirmed",
            user="system",
            details={"operation_id": operation_id}
        )

        # Remove from pending (operation should proceed)
        del self.pending_confirmations[operation_id]
        return True

    def check_permissions(
        self,
        model: str,
        operation: str,
        user_id: Optional[int] = None,
    ) -> bool:
        """
        Check if user has permission for operation

        Args:
            model: Model name
            operation: Operation type (create, read, write, unlink)
            user_id: User ID (None for current user)

        Returns:
            True if user has permission
        """
        # This is a placeholder - in real implementation,
        # we would check Odoo access rights via IR rules
        # For now, we rely on Odoo's own permission checks

        logger.debug(f"Permission check: {operation} on {model} for user {user_id}")
        return True


class ConfirmationHandler:
    """
    Handles confirmation flow for operations
    """

    def __init__(self, safety_validator: SafetyValidator):
        """
        Initialize confirmation handler

        Args:
            safety_validator: SafetyValidator instance
        """
        self.safety = safety_validator
        self._operation_counter = 0

    def generate_operation_id(self) -> str:
        """Generate a unique operation ID"""
        self._operation_counter += 1
        return f"op_{self._operation_counter}"

    def should_proceed(
        self,
        operation_type: str,
        model: str,
        method: Optional[str] = None,
        values: Optional[Dict] = None,
        record_id: Optional[int] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if operation should proceed (with or without confirmation)

        Args:
            operation_type: Type of operation
            model: Model name
            method: Method name
            values: Values being written
            record_id: Record ID

        Returns:
            Tuple of (should_proceed, confirmation_message)
        """
        # Run safety check
        safety_check = self.safety.check_operation(
            operation_type=operation_type,
            model=model,
            method=method,
            values=values,
            record_id=record_id,
        )

        # Check if blocked
        if not safety_check.is_safe:
            return False, f"🚫 Operation blocked: {safety_check.blocked_reason}"

        # Check if confirmation needed
        if safety_check.requires_confirmation:
            operation_id = self.generate_operation_id()
            confirmation_msg = self.safety.require_confirmation(
                operation_id=operation_id,
                model=model,
                operation_type=operation_type,
                details={
                    "method": method,
                    "values": values,
                    "record_id": record_id,
                },
            )
            return False, confirmation_msg

        # Safe to proceed
        return True, None

    def execute_with_confirmation(
        self,
        operation: Callable,
        operation_type: str,
        model: str,
        **kwargs,
    ) -> Any:
        """
        Execute operation with confirmation flow

        Args:
            operation: Callable to execute
            operation_type: Type of operation
            model: Model name
            **kwargs: Arguments to pass to operation

        Returns:
            Result of operation
        """
        # Check if should proceed
        should_proceed, confirmation_msg = self.should_proceed(
            operation_type=operation_type,
            model=model,
            **kwargs
        )

        if not should_proceed:
            # Return confirmation message (operation requires confirmation)
            return {"requires_confirmation": True, "message": confirmation_msg}

        # Execute operation
        try:
            result = operation(**kwargs)

            # Log successful execution
            audit_log(
                action=f"{operation_type}_success",
                user="system",
                details={"model": model, **kwargs}
            )

            return result

        except Exception as e:
            logger.error(f"Error executing {operation_type} on {model}: {e}")

            # Log failed execution
            audit_log(
                action=f"{operation_type}_error",
                user="system",
                details={"model": model, "error": str(e)}
            )

            return {"error": str(e)}
