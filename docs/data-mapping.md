# Odoo Data Mapping Document

## Overview

This document describes the field mapping for procurement-related entities in Odoo.
For each entity, we document:
- **Read fields**: Fields retrieved for display, search, and reporting
- **Write fields**: Fields that can be created/updated via API
- **Required fields**: Mandatory for record creation
- **Readonly fields**: Computed or system-managed, cannot be written
- **Actions**: Available workflow methods

---

## 1. Purchase Order (PO)

### Model: `purchase.order`

#### Read Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `id` | integer | Unique record ID | `42` |
| `name` | char | PO number (sequence) | `PO00042` |
| `state` | selection | Current status | `draft`, `sent`, `to approve`, `purchase`, `done`, `cancel` |
| `partner_id` | many2one → res.partner | Vendor reference | `[15, "Acme Corp"]` |
| `partner_ref` | char | Vendor's reference number | `VENDOR-REF-123` |
| `date_order` | datetime | Order date | `2026-01-22 10:30:00` |
| `date_approve` | date | Approval date | `2026-01-22` |
| `date_planned` | datetime | Expected delivery date | `2026-02-01 00:00:00` |
| `origin` | char | Source document | `PR00015` |
| `user_id` | many2one → res.users | Purchase representative | `[2, "John Doe"]` |
| `company_id` | many2one → res.company | Company | `[1, "My Company"]` |
| `currency_id` | many2one → res.currency | Currency | `[1, "USD"]` |
| `amount_untaxed` | monetary | Subtotal (readonly) | `1000.00` |
| `amount_tax` | monetary | Tax amount (readonly) | `100.00` |
| `amount_total` | monetary | Total (readonly) | `1100.00` |
| `order_line` | one2many → purchase.order.line | Order lines | `[1, 2, 3]` |
| `notes` | text | Terms and conditions | `Delivery within 30 days` |
| `payment_term_id` | many2one → account.payment.term | Payment terms | `[1, "30 Days"]` |
| `fiscal_position_id` | many2one → account.fiscal.position | Fiscal position | `[1, "Domestic"]` |
| `invoice_count` | integer | Number of invoices (readonly) | `2` |
| `invoice_ids` | many2many → account.move | Related invoices (readonly) | `[10, 11]` |
| `invoice_status` | selection | Invoice status (readonly) | `no`, `to invoice`, `invoiced` |
| `picking_count` | integer | Number of receipts (readonly) | `1` |
| `picking_ids` | many2many → stock.picking | Related receipts (readonly) | `[5]` |
| `create_date` | datetime | Created on (readonly) | `2026-01-20 09:00:00` |
| `write_date` | datetime | Last modified (readonly) | `2026-01-22 10:30:00` |
| `create_uid` | many2one → res.users | Created by (readonly) | `[1, "Admin"]` |
| `write_uid` | many2one → res.users | Modified by (readonly) | `[2, "John"]` |

#### Write Fields

| Field | Type | Required | Default | Validation |
|-------|------|----------|---------|------------|
| `partner_id` | integer | **Yes** | - | Must be valid res.partner with supplier_rank > 0 |
| `date_order` | datetime | No | `now()` | ISO format: `YYYY-MM-DD HH:MM:SS` |
| `date_planned` | datetime | No | - | Must be >= date_order |
| `origin` | char | No | - | Max 256 chars |
| `partner_ref` | char | No | - | Max 64 chars |
| `user_id` | integer | No | current user | Must be valid res.users |
| `currency_id` | integer | No | company currency | Must be valid res.currency |
| `payment_term_id` | integer | No | partner default | Must be valid account.payment.term |
| `fiscal_position_id` | integer | No | auto-detected | Must be valid account.fiscal.position |
| `notes` | text | No | - | Free text |
| `order_line` | list | **Yes** | - | See PO Line format below |

#### Order Line Format (for creation)

```python
"order_line": [
    (0, 0, {  # Create new line
        "product_id": 10,           # Required: product ID
        "name": "Product Name",     # Optional: description (auto-filled from product)
        "product_qty": 5.0,         # Required: quantity
        "product_uom": 1,           # Optional: UoM ID (auto-filled from product)
        "price_unit": 100.00,       # Optional: unit price (auto-filled from product/pricelist)
        "date_planned": "2026-02-01 00:00:00",  # Optional: planned date
        "taxes_id": [(6, 0, [1, 2])],  # Optional: tax IDs
    }),
    (1, 5, {  # Update existing line ID=5
        "product_qty": 10.0,
    }),
    (2, 6, 0),  # Delete line ID=6
]
```

#### State Transitions

```
draft → sent → to approve → purchase → done
         ↓         ↓            ↓
       cancel   cancel       cancel
```

| From State | To State | Method | Description |
|------------|----------|--------|-------------|
| `draft` | `sent` | `button_confirm()` | Send RFQ to vendor |
| `draft` | `cancel` | `button_cancel()` | Cancel draft |
| `sent` | `to approve` | `button_confirm()` | Request approval (if approval needed) |
| `sent` | `purchase` | `button_confirm()` | Confirm directly (if no approval needed) |
| `sent` | `cancel` | `button_cancel()` | Cancel sent RFQ |
| `to approve` | `purchase` | `button_approve()` | Approve PO |
| `to approve` | `cancel` | `button_cancel()` | Reject/Cancel |
| `purchase` | `done` | `button_done()` | Lock PO |
| `purchase` | `cancel` | `button_cancel()` | Cancel confirmed PO |

#### Actions (Methods)

| Method | Parameters | Description | Returns |
|--------|------------|-------------|---------|
| `button_confirm()` | - | Confirm RFQ → PO or request approval | `True` |
| `button_approve()` | - | Approve PO (managers only) | `True` |
| `button_cancel()` | - | Cancel PO | `True` |
| `button_draft()` | - | Reset to draft | `True` |
| `button_done()` | - | Lock PO | `True` |
| `action_rfq_send()` | - | Open email composer for RFQ | Action dict |
| `action_create_invoice()` | - | Create vendor bill | Action dict |
| `action_view_invoice()` | - | View related invoices | Action dict |
| `action_view_picking()` | - | View related receipts | Action dict |

---

### Model: `purchase.order.line`

#### Read Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `id` | integer | Line ID | `101` |
| `order_id` | many2one → purchase.order | Parent PO | `[42, "PO00042"]` |
| `name` | text | Description | `[PROD01] Widget A` |
| `sequence` | integer | Display order | `10` |
| `product_id` | many2one → product.product | Product | `[10, "Widget A"]` |
| `product_qty` | float | Ordered quantity | `5.0` |
| `qty_received` | float | Received quantity (readonly) | `3.0` |
| `qty_invoiced` | float | Invoiced quantity (readonly) | `3.0` |
| `qty_to_invoice` | float | To invoice (readonly) | `0.0` |
| `product_uom` | many2one → uom.uom | Unit of measure | `[1, "Units"]` |
| `price_unit` | float | Unit price | `100.00` |
| `price_subtotal` | monetary | Subtotal (readonly) | `500.00` |
| `price_total` | monetary | Total with tax (readonly) | `550.00` |
| `price_tax` | monetary | Tax amount (readonly) | `50.00` |
| `taxes_id` | many2many → account.tax | Taxes | `[1, 2]` |
| `date_planned` | datetime | Planned delivery | `2026-02-01 00:00:00` |
| `state` | selection | PO state (related, readonly) | `purchase` |
| `partner_id` | many2one | Vendor (related, readonly) | `[15, "Acme"]` |

#### Write Fields

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `order_id` | integer | **Yes** | Must be valid purchase.order |
| `product_id` | integer | **Yes** | Must be valid product.product |
| `name` | text | No | Auto-filled from product |
| `product_qty` | float | **Yes** | Must be > 0 |
| `product_uom` | integer | No | Must match product's UoM category |
| `price_unit` | float | No | Auto-filled from product/pricelist |
| `taxes_id` | list | No | `[(6, 0, [tax_ids])]` format |
| `date_planned` | datetime | No | ISO format |

---

## 2. Purchase Request/Requisition (PR)

### Model: `purchase.requisition`

> Note: This model requires the `purchase_requisition` module (Purchase Agreements)

#### Read Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `id` | integer | Unique ID | `15` |
| `name` | char | PR number | `PR00015` |
| `state` | selection | Status | `draft`, `ongoing`, `in_progress`, `open`, `done`, `cancel` |
| `type_id` | many2one → purchase.requisition.type | Agreement type | `[1, "Blanket Order"]` |
| `user_id` | many2one → res.users | Responsible | `[2, "John"]` |
| `vendor_id` | many2one → res.partner | Vendor (for exclusive) | `[15, "Acme"]` |
| `ordering_date` | date | Ordering date | `2026-01-22` |
| `date_end` | datetime | Agreement deadline | `2026-12-31` |
| `schedule_date` | date | Delivery date | `2026-02-01` |
| `origin` | char | Source document | `SO00123` |
| `description` | text | Description | `Q1 Office Supplies` |
| `company_id` | many2one → res.company | Company | `[1, "My Company"]` |
| `currency_id` | many2one → res.currency | Currency | `[1, "USD"]` |
| `line_ids` | one2many → purchase.requisition.line | Lines | `[1, 2]` |
| `purchase_ids` | one2many → purchase.order | Generated POs (readonly) | `[42, 43]` |

#### Write Fields

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `type_id` | integer | **Yes** | Must be valid purchase.requisition.type |
| `user_id` | integer | No | Default: current user |
| `vendor_id` | integer | No | Required if exclusive type |
| `ordering_date` | date | No | Default: today |
| `date_end` | datetime | No | Must be > ordering_date |
| `schedule_date` | date | No | Default: ordering_date |
| `origin` | char | No | Source reference |
| `description` | text | No | Free text |
| `line_ids` | list | **Yes** | See line format |

#### State Transitions

| From | To | Method | Description |
|------|-----|--------|-------------|
| `draft` | `ongoing` | `action_in_progress()` | Confirm requisition |
| `ongoing` | `in_progress` | - | When POs created |
| `in_progress` | `open` | - | When bids received |
| `in_progress` | `done` | `action_done()` | Close requisition |
| `*` | `cancel` | `action_cancel()` | Cancel |
| `cancel` | `draft` | `action_draft()` | Reset to draft |

---

### Model: `purchase.requisition.line`

#### Read Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `id` | integer | Line ID | `25` |
| `requisition_id` | many2one | Parent PR | `[15, "PR00015"]` |
| `product_id` | many2one → product.product | Product | `[10, "Widget"]` |
| `product_description_variants` | text | Description | `Widget A - Blue` |
| `product_qty` | float | Quantity | `100.0` |
| `product_uom_id` | many2one → uom.uom | UoM | `[1, "Units"]` |
| `price_unit` | float | Estimated price | `50.00` |
| `schedule_date` | date | Delivery date | `2026-02-01` |
| `qty_ordered` | float | Ordered qty (readonly) | `80.0` |

#### Write Fields

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `requisition_id` | integer | **Yes** | Valid PR |
| `product_id` | integer | **Yes** | Valid product |
| `product_qty` | float | **Yes** | > 0 |
| `product_uom_id` | integer | No | UoM category match |
| `price_unit` | float | No | >= 0 |
| `schedule_date` | date | No | ISO format |

---

## 3. Vendor (Supplier)

### Model: `res.partner`

> Filter: `supplier_rank > 0` for vendors

#### Read Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `id` | integer | Partner ID | `15` |
| `name` | char | Company/Contact name | `Acme Corporation` |
| `display_name` | char | Full display name (readonly) | `Acme Corporation` |
| `is_company` | boolean | Is a company | `True` |
| `parent_id` | many2one → res.partner | Parent company | `[10, "Acme Group"]` |
| `child_ids` | one2many → res.partner | Contacts | `[16, 17]` |
| `type` | selection | Address type | `contact`, `invoice`, `delivery`, `other`, `private` |
| `street` | char | Street line 1 | `123 Main St` |
| `street2` | char | Street line 2 | `Suite 100` |
| `city` | char | City | `New York` |
| `state_id` | many2one → res.country.state | State | `[10, "NY"]` |
| `zip` | char | ZIP code | `10001` |
| `country_id` | many2one → res.country | Country | `[233, "United States"]` |
| `email` | char | Email | `contact@acme.com` |
| `phone` | char | Phone | `+1-555-1234` |
| `mobile` | char | Mobile | `+1-555-5678` |
| `website` | char | Website | `https://acme.com` |
| `vat` | char | Tax ID / VAT | `US123456789` |
| `lang` | selection | Language | `en_US` |
| `category_id` | many2many → res.partner.category | Tags | `[1, 2]` |
| `supplier_rank` | integer | Supplier score | `1` (>0 = is supplier) |
| `customer_rank` | integer | Customer score | `0` |
| `property_payment_term_id` | many2one → account.payment.term | Payment terms | `[1, "30 Days"]` |
| `property_supplier_payment_term_id` | many2one | Vendor payment terms | `[2, "15 Days"]` |
| `property_account_payable_id` | many2one → account.account | Payable account | `[100, "211000"]` |
| `property_account_receivable_id` | many2one → account.account | Receivable account | `[50, "121000"]` |
| `property_purchase_currency_id` | many2one → res.currency | Purchase currency | `[1, "USD"]` |
| `bank_ids` | one2many → res.partner.bank | Bank accounts | `[5, 6]` |
| `comment` | text | Internal notes | `Preferred supplier` |
| `active` | boolean | Active | `True` |
| `company_id` | many2one → res.company | Company | `[1, "My Company"]` |
| `user_id` | many2one → res.users | Salesperson | `[2, "John"]` |
| `create_date` | datetime | Created on | `2025-01-01 00:00:00` |

#### Write Fields

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `name` | char | **Yes** | Max 128 chars |
| `is_company` | boolean | No | Default: False |
| `parent_id` | integer | No | Valid res.partner |
| `type` | selection | No | Default: `contact` |
| `street` | char | No | Max 128 chars |
| `street2` | char | No | Max 128 chars |
| `city` | char | No | Max 128 chars |
| `state_id` | integer | No | Must belong to country_id |
| `zip` | char | No | Max 24 chars |
| `country_id` | integer | No | Valid res.country |
| `email` | char | No | Valid email format |
| `phone` | char | No | Max 32 chars |
| `mobile` | char | No | Max 32 chars |
| `website` | char | No | Valid URL |
| `vat` | char | No | Validated per country |
| `lang` | selection | No | Installed language |
| `category_id` | list | No | `[(6, 0, [ids])]` |
| `supplier_rank` | integer | No | Set > 0 to mark as supplier |
| `property_supplier_payment_term_id` | integer | No | Valid payment term |
| `bank_ids` | list | No | Bank account format |
| `comment` | text | No | Free text |
| `active` | boolean | No | Default: True |

#### Creating a Vendor

```python
{
    "name": "New Supplier Inc.",
    "is_company": True,
    "supplier_rank": 1,  # Mark as supplier
    "street": "456 Vendor Ave",
    "city": "Chicago",
    "state_id": 14,  # Illinois
    "zip": "60601",
    "country_id": 233,  # USA
    "email": "info@newsupplier.com",
    "phone": "+1-312-555-0000",
    "vat": "US987654321",
    "property_supplier_payment_term_id": 2,
    "category_id": [(6, 0, [1, 3])],  # Tags: "Supplier", "Premium"
}
```

---

## 4. Product (Item)

### Model: `product.product` (Variants)

#### Read Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `id` | integer | Product variant ID | `10` |
| `name` | char | Product name | `Widget A` |
| `display_name` | char | Full name with variants | `Widget A (Blue, Large)` |
| `default_code` | char | Internal reference / SKU | `WIDGET-A-BL-L` |
| `barcode` | char | Barcode | `1234567890123` |
| `product_tmpl_id` | many2one → product.template | Template | `[5, "Widget A"]` |
| `type` | selection | Product type | `consu`, `service`, `product` |
| `categ_id` | many2one → product.category | Category | `[3, "Office Supplies"]` |
| `list_price` | float | Sales price | `150.00` |
| `standard_price` | float | Cost price | `100.00` |
| `uom_id` | many2one → uom.uom | Unit of measure | `[1, "Units"]` |
| `uom_po_id` | many2one → uom.uom | Purchase UoM | `[2, "Dozen"]` |
| `seller_ids` | one2many → product.supplierinfo | Vendor info | `[1, 2]` |
| `qty_available` | float | On hand (readonly) | `50.0` |
| `virtual_available` | float | Forecasted (readonly) | `45.0` |
| `incoming_qty` | float | Incoming (readonly) | `20.0` |
| `outgoing_qty` | float | Outgoing (readonly) | `25.0` |
| `active` | boolean | Active | `True` |
| `sale_ok` | boolean | Can be sold | `True` |
| `purchase_ok` | boolean | Can be purchased | `True` |
| `description` | text | Internal description | `Standard widget` |
| `description_purchase` | text | Purchase description | `Widget for office use` |
| `description_sale` | text | Sales description | `High-quality widget` |
| `image_1920` | binary | Product image (base64) | `iVBORw0KGgo...` |
| `weight` | float | Weight (kg) | `0.5` |
| `volume` | float | Volume (m³) | `0.001` |
| `product_variant_ids` | one2many | Variants (readonly) | `[10, 11, 12]` |
| `product_variant_count` | integer | Variant count (readonly) | `3` |
| `attribute_line_ids` | one2many | Attributes | `[1, 2]` |

#### Write Fields

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `name` | char | **Yes** | Max 128 chars |
| `default_code` | char | No | Unique per company |
| `barcode` | char | No | Unique globally |
| `type` | selection | No | Default: `consu` |
| `categ_id` | integer | No | Default: "All" category |
| `list_price` | float | No | Default: 0.0 |
| `standard_price` | float | No | Default: 0.0 |
| `uom_id` | integer | No | Default: Units |
| `uom_po_id` | integer | No | Must be same category as uom_id |
| `sale_ok` | boolean | No | Default: True |
| `purchase_ok` | boolean | No | Default: True |
| `description` | text | No | Free text |
| `description_purchase` | text | No | Free text |
| `weight` | float | No | In kg |
| `volume` | float | No | In m³ |
| `active` | boolean | No | Default: True |

---

### Model: `product.supplierinfo` (Vendor Pricelist)

#### Read Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `id` | integer | Record ID | `1` |
| `product_tmpl_id` | many2one → product.template | Product template | `[5, "Widget A"]` |
| `product_id` | many2one → product.product | Specific variant | `[10, "Widget A (Blue)"]` |
| `partner_id` | many2one → res.partner | Vendor | `[15, "Acme Corp"]` |
| `product_name` | char | Vendor product name | `ACM-WIDGET-01` |
| `product_code` | char | Vendor product code | `ACM001` |
| `sequence` | integer | Priority (lower = first) | `1` |
| `min_qty` | float | Minimum quantity | `10.0` |
| `price` | float | Unit price | `95.00` |
| `currency_id` | many2one → res.currency | Currency | `[1, "USD"]` |
| `date_start` | date | Start date | `2026-01-01` |
| `date_end` | date | End date | `2026-12-31` |
| `delay` | integer | Delivery lead time (days) | `7` |
| `company_id` | many2one → res.company | Company | `[1, "My Company"]` |

#### Write Fields

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `product_tmpl_id` | integer | **Yes*** | Valid product.template |
| `product_id` | integer | No | Valid product.product |
| `partner_id` | integer | **Yes** | Valid res.partner (supplier) |
| `product_name` | char | No | Vendor's name for product |
| `product_code` | char | No | Vendor's code |
| `sequence` | integer | No | Default: 1 |
| `min_qty` | float | No | Default: 0.0 |
| `price` | float | **Yes** | Must be >= 0 |
| `currency_id` | integer | No | Default: company currency |
| `date_start` | date | No | ISO format |
| `date_end` | date | No | Must be >= date_start |
| `delay` | integer | No | Default: 1 |

*Either product_tmpl_id or product_id required

---

## 5. Unit of Measure (UoM)

### Model: `uom.uom`

#### Read Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `id` | integer | UoM ID | `1` |
| `name` | char | UoM name | `Units` |
| `category_id` | many2one → uom.category | Category | `[1, "Unit"]` |
| `uom_type` | selection | Type | `bigger`, `reference`, `smaller` |
| `factor` | float | Ratio to reference | `1.0` |
| `factor_inv` | float | Inverse ratio (readonly) | `1.0` |
| `rounding` | float | Rounding precision | `0.01` |
| `active` | boolean | Active | `True` |

#### Write Fields

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `name` | char | **Yes** | Unique per category |
| `category_id` | integer | **Yes** | Valid uom.category |
| `uom_type` | selection | **Yes** | `bigger`, `reference`, `smaller` |
| `factor` | float | **Yes** | > 0, relative to reference |
| `rounding` | float | No | Default: 0.01 |
| `active` | boolean | No | Default: True |

#### Common UoM Examples

| Category | UoM | Type | Factor |
|----------|-----|------|--------|
| Unit | Units | reference | 1.0 |
| Unit | Dozen | bigger | 12.0 |
| Unit | Pair | bigger | 2.0 |
| Weight | kg | reference | 1.0 |
| Weight | g | smaller | 0.001 |
| Weight | lb | bigger | 0.45359237 |
| Volume | L | reference | 1.0 |
| Volume | m³ | bigger | 1000.0 |
| Time | Hours | reference | 1.0 |
| Time | Days | bigger | 8.0 |

### Model: `uom.category`

#### Read Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Category ID |
| `name` | char | Category name |
| `uom_ids` | one2many → uom.uom | UoMs in category |

---

## 6. Messages (Chatter)

### Model: `mail.message`

#### Read Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `id` | integer | Message ID | `1000` |
| `model` | char | Related model | `purchase.order` |
| `res_id` | integer | Related record ID | `42` |
| `body` | html | Message content | `<p>Order confirmed</p>` |
| `subject` | char | Email subject | `RE: PO00042` |
| `message_type` | selection | Type | `email`, `comment`, `notification`, `user_notification` |
| `subtype_id` | many2one → mail.message.subtype | Subtype | `[1, "Note"]` |
| `author_id` | many2one → res.partner | Author | `[3, "John Doe"]` |
| `email_from` | char | Sender email | `john@company.com` |
| `partner_ids` | many2many → res.partner | Recipients | `[15, 16]` |
| `date` | datetime | Date (readonly) | `2026-01-22 10:30:00` |
| `attachment_ids` | many2many → ir.attachment | Attachments | `[50, 51]` |
| `starred` | boolean | Starred (readonly) | `False` |
| `tracking_value_ids` | one2many | Field changes | See below |
| `parent_id` | many2one → mail.message | Parent message | `[999, "..."]` |

#### Posting a Message

Use `message_post()` method on any model with mail.thread mixin:

```python
# On purchase.order model
result = odoo.execute_method(
    'purchase.order',
    'message_post',
    [[42]],  # PO ID
    body="<p>Please expedite this order.</p>",
    message_type="comment",
    subtype_xmlid="mail.mt_comment",  # or "mail.mt_note" for internal
    partner_ids=[15, 16],  # Notify these partners
    attachment_ids=[(4, 50)],  # Link existing attachment
)
```

#### Message Types

| Type | Description | Notification |
|------|-------------|--------------|
| `comment` | User comment | Notifies followers |
| `notification` | System notification | No notification |
| `email` | Incoming email | Notifies followers |
| `user_notification` | User mention | Notifies mentioned users |

#### Subtypes (mail.message.subtype)

| XML ID | Name | Description |
|--------|------|-------------|
| `mail.mt_comment` | Discussions | Public comment, notifies all |
| `mail.mt_note` | Note | Internal note, no external notification |
| `mail.mt_activities` | Activities | Activity-related |
| `purchase.mt_rfq_sent` | RFQ Sent | RFQ was sent |
| `purchase.mt_rfq_confirmed` | RFQ Confirmed | PO was confirmed |

---

### Model: `mail.activity`

#### Read Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `id` | integer | Activity ID | `200` |
| `res_model` | char | Related model | `purchase.order` |
| `res_model_id` | many2one → ir.model | Model reference | `[100, "Purchase Order"]` |
| `res_id` | integer | Record ID | `42` |
| `res_name` | char | Record name (readonly) | `PO00042` |
| `activity_type_id` | many2one → mail.activity.type | Type | `[1, "To Do"]` |
| `summary` | char | Summary | `Review pricing` |
| `note` | html | Description | `<p>Check vendor prices</p>` |
| `date_deadline` | date | Due date | `2026-01-25` |
| `user_id` | many2one → res.users | Assigned to | `[2, "John"]` |
| `state` | selection | Status (readonly) | `today`, `planned`, `overdue` |
| `create_date` | datetime | Created on | `2026-01-22 09:00:00` |
| `create_uid` | many2one → res.users | Created by | `[1, "Admin"]` |

#### Write Fields / Create Activity

```python
# Create activity on PO
{
    "res_model": "purchase.order",
    "res_id": 42,
    "activity_type_id": 1,  # To Do
    "summary": "Follow up with vendor",
    "note": "<p>Call vendor about delivery</p>",
    "date_deadline": "2026-01-25",
    "user_id": 2,
}
```

#### Activity Actions

| Method | Description |
|--------|-------------|
| `action_feedback(feedback)` | Mark done with feedback |
| `action_done()` | Mark done |
| `action_close_dialog()` | Close without feedback |
| `unlink()` | Cancel/Delete activity |

---

## 7. Approvals

### Model: `approval.request`

> Note: Requires `approvals` module

#### Read Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `id` | integer | Request ID | `50` |
| `name` | char | Request name | `Purchase Approval - PO00042` |
| `category_id` | many2one → approval.category | Category | `[1, "Purchase"]` |
| `request_status` | selection | Status | `new`, `pending`, `approved`, `refused`, `cancel` |
| `request_owner_id` | many2one → res.users | Requester | `[2, "John"]` |
| `approver_ids` | one2many → approval.approver | Approvers | `[10, 11]` |
| `date_confirmed` | datetime | Confirmed date | `2026-01-22 10:00:00` |
| `date_start` | date | Start date | `2026-01-22` |
| `date_end` | date | End date | `2026-01-25` |
| `reason` | html | Description/Reason | `<p>Need approval for...</p>` |
| `reference` | char | Reference | `PO00042` |
| `amount` | float | Amount | `5000.00` |
| `currency_id` | many2one → res.currency | Currency | `[1, "USD"]` |
| `partner_id` | many2one → res.partner | Contact | `[15, "Acme"]` |

#### Write Fields

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `name` | char | **Yes** | Description |
| `category_id` | integer | **Yes** | Valid approval.category |
| `request_owner_id` | integer | No | Default: current user |
| `date_start` | date | No | ISO format |
| `date_end` | date | No | >= date_start |
| `reason` | html | No | Justification |
| `reference` | char | No | External reference |
| `amount` | float | No | Request amount |
| `partner_id` | integer | No | Valid res.partner |

#### State Transitions

```
new → pending → approved
        ↓         ↓
     refused    (done)
        ↓
     cancel
```

| Method | Description |
|--------|-------------|
| `action_confirm()` | Submit for approval (new → pending) |
| `action_approve()` | Approve (by approver) |
| `action_refuse()` | Refuse (by approver) |
| `action_cancel()` | Cancel request |
| `action_draft()` | Reset to draft |

---

### Model: `approval.approver`

#### Read Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `id` | integer | Approver line ID | `10` |
| `request_id` | many2one → approval.request | Request | `[50, "Purchase..."]` |
| `user_id` | many2one → res.users | Approver | `[5, "Manager"]` |
| `status` | selection | Decision | `new`, `pending`, `approved`, `refused` |
| `required` | boolean | Required approval | `True` |

---

## 8. Vendor Invoices (Bills)

### Model: `account.move`

> Filter: `move_type = 'in_invoice'` for vendor bills

#### Read Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `id` | integer | Invoice ID | `100` |
| `name` | char | Invoice number | `BILL/2026/0001` |
| `ref` | char | Vendor reference | `INV-12345` |
| `move_type` | selection | Type | `in_invoice` (vendor bill), `in_refund` (credit note) |
| `state` | selection | Status | `draft`, `posted`, `cancel` |
| `partner_id` | many2one → res.partner | Vendor | `[15, "Acme"]` |
| `invoice_date` | date | Invoice date | `2026-01-20` |
| `invoice_date_due` | date | Due date | `2026-02-20` |
| `date` | date | Accounting date | `2026-01-20` |
| `invoice_origin` | char | Source document | `PO00042` |
| `payment_reference` | char | Payment reference | `PAY-123` |
| `currency_id` | many2one → res.currency | Currency | `[1, "USD"]` |
| `company_id` | many2one → res.company | Company | `[1, "My Company"]` |
| `journal_id` | many2one → account.journal | Journal | `[2, "Vendor Bills"]` |
| `invoice_line_ids` | one2many → account.move.line | Lines | `[200, 201]` |
| `amount_untaxed` | monetary | Subtotal (readonly) | `1000.00` |
| `amount_tax` | monetary | Tax (readonly) | `100.00` |
| `amount_total` | monetary | Total (readonly) | `1100.00` |
| `amount_residual` | monetary | Amount due (readonly) | `1100.00` |
| `payment_state` | selection | Payment status (readonly) | `not_paid`, `in_payment`, `paid`, `partial`, `reversed` |
| `invoice_payment_term_id` | many2one → account.payment.term | Payment terms | `[1, "30 Days"]` |
| `fiscal_position_id` | many2one | Fiscal position | `[1, "Domestic"]` |
| `purchase_id` | many2one → purchase.order | Source PO (readonly) | `[42, "PO00042"]` |
| `narration` | html | Terms & conditions | `<p>...</p>` |

#### Write Fields

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `move_type` | selection | **Yes** | `in_invoice` or `in_refund` |
| `partner_id` | integer | **Yes** | Valid res.partner |
| `ref` | char | No | Vendor invoice number |
| `invoice_date` | date | No | Default: today |
| `invoice_date_due` | date | No | Auto from payment term |
| `date` | date | No | Default: invoice_date |
| `journal_id` | integer | No | Auto-selected |
| `currency_id` | integer | No | Default: company currency |
| `invoice_payment_term_id` | integer | No | Valid payment term |
| `fiscal_position_id` | integer | No | Auto-detected |
| `invoice_line_ids` | list | **Yes** | See line format |
| `narration` | html | No | Terms |

#### Creating a Vendor Bill

```python
{
    "move_type": "in_invoice",
    "partner_id": 15,
    "ref": "VENDOR-INV-12345",
    "invoice_date": "2026-01-20",
    "invoice_payment_term_id": 1,
    "invoice_line_ids": [
        (0, 0, {
            "product_id": 10,
            "quantity": 5.0,
            "price_unit": 100.00,
            "tax_ids": [(6, 0, [1])],
        }),
    ],
}
```

#### State Transitions

| From | To | Method | Description |
|------|-----|--------|-------------|
| `draft` | `posted` | `action_post()` | Validate/Post invoice |
| `posted` | `cancel` | `button_cancel()` | Cancel (if allowed) |
| `posted` | - | `button_draft()` | Reset to draft (if allowed) |

#### Payment Methods

| Method | Description |
|--------|-------------|
| `action_register_payment()` | Open payment wizard |
| `action_reverse()` | Create reversal/credit note |

---

### Model: `account.move.line`

#### Read Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `id` | integer | Line ID | `200` |
| `move_id` | many2one → account.move | Invoice | `[100, "BILL/2026/0001"]` |
| `name` | char | Description | `Widget A` |
| `product_id` | many2one → product.product | Product | `[10, "Widget A"]` |
| `account_id` | many2one → account.account | Account | `[500, "600000 Expenses"]` |
| `quantity` | float | Quantity | `5.0` |
| `product_uom_id` | many2one → uom.uom | UoM | `[1, "Units"]` |
| `price_unit` | float | Unit price | `100.00` |
| `discount` | float | Discount % | `0.0` |
| `price_subtotal` | monetary | Subtotal (readonly) | `500.00` |
| `price_total` | monetary | Total (readonly) | `550.00` |
| `tax_ids` | many2many → account.tax | Taxes | `[1]` |
| `tax_line_id` | many2one → account.tax | Tax line (for tax lines) | `[1, "VAT 10%"]` |
| `debit` | monetary | Debit (readonly) | `500.00` |
| `credit` | monetary | Credit (readonly) | `0.00` |
| `balance` | monetary | Balance (readonly) | `500.00` |
| `purchase_line_id` | many2one → purchase.order.line | PO Line | `[101, "..."]` |
| `analytic_distribution` | json | Analytics | `{"1": 100}` |

#### Write Fields

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `product_id` | integer | No | Valid product |
| `name` | char | **Yes** | Description |
| `account_id` | integer | **Yes** | Valid account.account |
| `quantity` | float | No | Default: 1.0 |
| `product_uom_id` | integer | No | UoM category match |
| `price_unit` | float | No | Default: 0.0 |
| `discount` | float | No | 0-100 |
| `tax_ids` | list | No | `[(6, 0, [ids])]` |
| `analytic_distribution` | json | No | `{account_id: percentage}` |

---

## Quick Reference: x2many Field Commands

When writing one2many or many2many fields, use these command tuples:

| Command | Format | Description |
|---------|--------|-------------|
| Create | `(0, 0, {values})` | Create new record with values |
| Update | `(1, id, {values})` | Update existing record |
| Delete | `(2, id, 0)` | Delete record from database |
| Unlink | `(3, id, 0)` | Remove link (m2m only) |
| Link | `(4, id, 0)` | Add link to existing record |
| Clear | `(5, 0, 0)` | Remove all links (m2m) |
| Replace | `(6, 0, [ids])` | Replace with list of IDs |

### Examples

```python
# Create new lines
"order_line": [(0, 0, {"product_id": 1, "product_qty": 5})]

# Update existing line
"order_line": [(1, 10, {"product_qty": 10})]

# Delete line
"order_line": [(2, 10, 0)]

# Replace all with new set
"partner_ids": [(6, 0, [1, 2, 3])]

# Add to existing set
"tag_ids": [(4, 5, 0)]

# Clear all
"follower_ids": [(5, 0, 0)]
```

---

## Common Search Domains

### Purchase Orders

```python
# Draft POs
[["state", "=", "draft"]]

# POs to approve
[["state", "=", "to approve"]]

# POs from specific vendor
[["partner_id", "=", 15]]

# POs this month
[["date_order", ">=", "2026-01-01"], ["date_order", "<", "2026-02-01"]]

# POs over $10,000
[["amount_total", ">", 10000]]

# POs with pending invoices
[["invoice_status", "=", "to invoice"]]
```

### Vendors

```python
# All suppliers
[["supplier_rank", ">", 0]]

# Active suppliers
[["supplier_rank", ">", 0], ["active", "=", True]]

# Suppliers in specific country
[["supplier_rank", ">", 0], ["country_id", "=", 233]]

# Suppliers with specific tag
[["supplier_rank", ">", 0], ["category_id", "in", [5]]]
```

### Products

```python
# Purchasable products
[["purchase_ok", "=", True]]

# Products from specific vendor
[["seller_ids.partner_id", "=", 15]]

# Products in category
[["categ_id", "child_of", 3]]

# Products low on stock
[["type", "=", "product"], ["qty_available", "<", 10]]
```

### Invoices

```python
# Unpaid vendor bills
[["move_type", "=", "in_invoice"], ["payment_state", "!=", "paid"]]

# Overdue bills
[["move_type", "=", "in_invoice"], ["payment_state", "!=", "paid"], ["invoice_date_due", "<", "2026-01-22"]]

# Bills from PO
[["move_type", "=", "in_invoice"], ["invoice_origin", "ilike", "PO00042"]]
```
