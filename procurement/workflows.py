"""
Procurement-specific workflows for Odoo AI Agent
"""
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from src.utils.logging import get_logger, audit_log

logger = get_logger(__name__)


@dataclass
class PurchaseOrderInfo:
    """Information about a purchase order"""
    id: int
    name: str
    partner_id: int
    partner_name: str
    amount_total: float
    state: str
    date_order: str
    lines: List[Dict]


class ProcurementWorkflows:
    """
    Specialized workflows for procurement operations
    """

    def __init__(self, odoo_client):
        """
        Initialize procurement workflows

        Args:
            odoo_client: OdooClient instance
        """
        self.odoo = odoo_client
        logger.info("ProcurementWorkflows initialized")

    async def get_pending_purchase_orders(
        self,
        limit: int = 50,
        states: Optional[List[str]] = None,
    ) -> List[PurchaseOrderInfo]:
        """
        Get pending purchase orders

        Args:
            limit: Maximum number of orders to return
            states: List of states to filter (default: draft, sent, to approve)

        Returns:
            List of PurchaseOrderInfo
        """
        if states is None:
            states = ["draft", "sent", "to approve"]

        try:
            # Build domain filter
            domain = [["state", "in", states]]

            # Search and read POs
            results = self.odoo.search_read(
                model_name="purchase.order",
                domain=domain,
                limit=limit,
                order="date_order desc",
            )

            orders = []
            for po in results:
                order_info = PurchaseOrderInfo(
                    id=po.get("id"),
                    name=po.get("name"),
                    partner_id=po.get("partner_id", [])[0] if po.get("partner_id") else None,
                    partner_name=po.get("partner_id", [False, ""])[1] if po.get("partner_id") else "",
                    amount_total=po.get("amount_total", 0.0),
                    state=po.get("state"),
                    date_order=po.get("date_order"),
                    lines=po.get("order_line", []),
                )
                orders.append(order_info)

            logger.info(f"Found {len(orders)} pending purchase orders")
            return orders

        except Exception as e:
            logger.error(f"Error getting pending POs: {e}")
            return []

    async def approve_purchase_order(
        self,
        po_id: int,
        user: str = "system",
    ) -> Dict[str, Any]:
        """
        Approve a purchase order

        Args:
            po_id: Purchase Order ID
            user: User performing the action

        Returns:
            Dict with result
        """
        try:
            logger.info(f"Approving PO {po_id}")
            audit_log(
                action="approve_po_attempt",
                user=user,
                details={"po_id": po_id}
            )

            # Call button_approve
            result = self.odoo.execute_method(
                "purchase.order",
                "button_approve",
                [po_id]
            )

            logger.info(f"Successfully approved PO {po_id}")
            audit_log(
                action="approve_po_success",
                user=user,
                details={"po_id": po_id}
            )

            return {
                "success": True,
                "po_id": po_id,
                "result": result,
            }

        except Exception as e:
            error_msg = f"Error approving PO {po_id}: {str(e)}"
            logger.error(error_msg)
            audit_log(
                action="approve_po_error",
                user=user,
                details={"po_id": po_id, "error": str(e)}
            )

            return {
                "success": False,
                "po_id": po_id,
                "error": str(e),
            }

    async def create_rfq(
        self,
        product_id: int,
        supplier_ids: List[int],
        quantity: float,
        user: str = "system",
    ) -> Dict[str, Any]:
        """
        Create RFQs for a product to multiple suppliers

        Args:
            product_id: Product ID
            supplier_ids: List of supplier (partner) IDs
            quantity: Quantity to order
            user: User performing the action

        Returns:
            Dict with created RFQ IDs
        """
        try:
            logger.info(
                f"Creating RFQ for product {product_id} "
                f"to {len(supplier_ids)} suppliers, qty={quantity}"
            )
            audit_log(
                action="create_rfq_attempt",
                user=user,
                details={
                    "product_id": product_id,
                    "supplier_ids": supplier_ids,
                    "quantity": quantity
                }
            )

            created_rfqs = []

            for supplier_id in supplier_ids:
                # Create PO in RFQ state (draft)
                po_values = {
                    "partner_id": supplier_id,
                    "order_line": [
                        (0, 0, {
                            "product_id": product_id,
                            "product_qty": quantity,
                            "date_planned": False,  # Will use default
                        })
                    ],
                }

                po_id = self.odoo.execute_method(
                    "purchase.order",
                    "create",
                    [po_values]
                )

                if po_id:
                    created_rfqs.append(po_id)
                    logger.info(f"Created RFQ {po_id} for supplier {supplier_id}")

            logger.info(f"Successfully created {len(created_rfqs)} RFQs")
            audit_log(
                action="create_rfq_success",
                user=user,
                details={
                    "product_id": product_id,
                    "rfq_ids": created_rfqs,
                    "count": len(created_rfqs)
                }
            )

            return {
                "success": True,
                "product_id": product_id,
                "rfq_ids": created_rfqs,
                "count": len(created_rfqs),
            }

        except Exception as e:
            error_msg = f"Error creating RFQs: {str(e)}"
            logger.error(error_msg)
            audit_log(
                action="create_rfq_error",
                user=user,
                details={
                    "product_id": product_id,
                    "error": str(e)
                }
            )

            return {
                "success": False,
                "product_id": product_id,
                "error": str(e),
            }

    async def send_rfq(
        self,
        rfq_id: int,
        user: str = "system",
    ) -> Dict[str, Any]:
        """
        Send RFQ to supplier

        Args:
            rfq_id: RFQ (Purchase Order) ID
            user: User performing the action

        Returns:
            Dict with result
        """
        try:
            logger.info(f"Sending RFQ {rfq_id}")
            audit_log(
                action="send_rfq_attempt",
                user=user,
                details={"rfq_id": rfq_id}
            )

            # Call action_rfq_send
            result = self.odoo.execute_method(
                "purchase.order",
                "action_rfq_send",
                [rfq_id]
            )

            logger.info(f"Successfully sent RFQ {rfq_id}")
            audit_log(
                action="send_rfq_success",
                user=user,
                details={"rfq_id": rfq_id}
            )

            return {
                "success": True,
                "rfq_id": rfq_id,
                "result": result,
            }

        except Exception as e:
            error_msg = f"Error sending RFQ {rfq_id}: {str(e)}"
            logger.error(error_msg)
            audit_log(
                action="send_rfq_error",
                user=user,
                details={"rfq_id": rfq_id, "error": str(e)}
            )

            return {
                "success": False,
                "rfq_id": rfq_id,
                "error": str(e),
            }

    async def get_low_stock_products(
        self,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get products that are below minimum stock levels

        Args:
            limit: Maximum number of products to return

        Returns:
            List of products with stock info
        """
        try:
            # Search for products that are below reorder point
            # This query uses stock.warehouse.orderpoint model
            results = self.odoo.search_read(
                model_name="stock.warehouse.orderpoint",
                domain=[],
                limit=limit,
            )

            low_stock_products = []

            for orderpoint in results:
                # Get product details
                product_id = orderpoint.get("product_id", [False, {}])[0]
                if product_id:
                    product_data = self.odoo.read_records(
                        "product.product",
                        [product_id],
                        fields=["name", "qty_available", "virtual_available"]
                    )

                    if product_data:
                        product = product_data[0]
                        low_stock_products.append({
                            "id": product.get("id"),
                            "name": product.get("name"),
                            "qty_available": product.get("qty_available", 0),
                            "virtual_available": product.get("virtual_available", 0),
                            "min_qty": orderpoint.get("product_min_qty", 0),
                            "max_qty": orderpoint.get("product_max_qty", 0),
                        })

            logger.info(f"Found {len(low_stock_products)} low stock products")
            return low_stock_products

        except Exception as e:
            logger.error(f"Error getting low stock products: {e}")
            return []

    async def get_supplier_performance(
        self,
        supplier_id: int,
    ) -> Dict[str, Any]:
        """
        Get performance metrics for a supplier

        Args:
            supplier_id: Supplier (partner) ID

        Returns:
            Dict with performance metrics
        """
        try:
            # Get supplier info
            supplier_data = self.odoo.read_records(
                "res.partner",
                [supplier_id],
                fields=["name", "supplier_rank", "email", "phone"]
            )

            if not supplier_data:
                return {"error": "Supplier not found"}

            supplier = supplier_data[0]

            # Get PO stats
            po_results = self.odoo.search_read(
                model_name="purchase.order",
                domain=[["partner_id", "=", supplier_id]],
                fields=["state", "amount_total"],
            )

            total_orders = len(po_results)
            total_amount = sum(po.get("amount_total", 0) for po in po_results)

            # Count by state
            states_count = {}
            for po in po_results:
                state = po.get("state", "unknown")
                states_count[state] = states_count.get(state, 0) + 1

            logger.info(f"Retrieved performance for supplier {supplier_id}")

            return {
                "supplier_id": supplier_id,
                "name": supplier.get("name"),
                "email": supplier.get("email"),
                "phone": supplier.get("phone"),
                "supplier_rank": supplier.get("supplier_rank"),
                "total_orders": total_orders,
                "total_amount": total_amount,
                "orders_by_state": states_count,
            }

        except Exception as e:
            logger.error(f"Error getting supplier performance: {e}")
            return {"error": str(e)}
