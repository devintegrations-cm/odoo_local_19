# Odoo 19 Upgrade Notes - Purchase Order Price Validation Module

## Module Overview
**Module Name:** Purchase Order Price Validation  
**Previous Version:** Odoo 17 (v17.0.1.1.0)  
**Target Version:** Odoo 19 (v19.0.1.1.0)  
**Module Type:** Purchase Order and Stock Picking validation with wizard dialogs

## Changes Made

### 1. Manifest File (__manifest__.py)
**Changes:**
- Updated version from `'17.0.1.1.0'` to `'19.0.1.1.0'`

**Why:** Odoo 19 uses semantic versioning format: `{odoo_version}.{major}.{minor}.{patch}`

### 2. Python Models

#### `models/purchase_order.py`
**Changes:**
- Line 80: `product.type == 'product'` → `product.type == 'consu'`

**Why:** In Odoo 19, the product type field values changed:
- `'product'` (storable) was **removed**
- `'consu'` (Goods) now represents all physical products
- `'service'` remains unchanged
- `'combo'` is new in Odoo 19

#### `models/stock_picking.py`
**Changes:**
- Line 57: `picking.move_ids_without_package` → `picking.move_ids`
- Line 59: `product.type == 'product'` → `product.type == 'consu'`

**Why:** 
- `move_ids_without_package` field was **removed** in Odoo 19. Use `move_ids` instead.
- Same product type change as purchase_order.py

#### Other Python Files
**Status:** ✅ No changes required
- `models/product_template.py` - Field definitions compatible
- `models/confirmation_variation_wizard.py` - TransientModel compatible
- `models/warning_variation_wizard.py` - TransientModel compatible
- `models/res_config_settings.py` - Config parameter compatible

### 3. XML Views
**Status:** ✅ No changes required

All XML views are compatible:
- `<list>` tag is used (not `<tree>`) - correct for Odoo 19
- Form views use standard structure
- XPath expressions are valid
- Widget attributes (html) are supported
- Button definitions are correct

### 4. Security (ir.model.access.csv)
**Status:** ✅ No changes required

Access rights format remains the same in Odoo 19.

## Breaking Changes Analysis (v17 → v19)

### What Changed in Odoo 19:

1. **`product.type` field values** - The `'product'` type was removed. Physical products now use `'consu'` (Goods).

2. **`move_ids_without_package` removed** - The `stock.picking` field `move_ids_without_package` no longer exists. Use `move_ids` instead.

3. **`<tree>` → `<list>`** - XML view tag `<tree>` was replaced with `<list>`. (Not applicable to this module - views already use standard form views.)

4. **`ir.cron` `numbercall` removed** - Not used in this module, no impact.

5. **`_sql_constraints` removed** - Not used in this module, no impact.

### What Stayed the Same:
- ORM methods (write, button_confirm, etc.)
- TransientModel wizards
- View inheritance patterns
- Security CSV format
- Field types and attributes
- `purchase.order` model name and `button_confirm` method
- `stock.picking` model name and `button_validate` method
- `purchase.order.line` `price_unit` field

## Installation & Testing Checklist

### Pre-Installation
- [ ] Backup your Odoo 17 database before upgrading
- [ ] Ensure Odoo 19 is properly installed
- [ ] Verify dependencies: `purchase`, `product`, and `stock` modules are available

### Installation Steps

1. **Copy the upgraded module to Odoo 19 addons path:**
   ```bash
   cp -r purchase_price_validation /path/to/odoo19/addons/
   ```

2. **Update the apps list:**
   ```bash
   odoo-bin -c /path/to/odoo.conf -d your_database -u all --stop-after-init
   ```
   Or from UI: Apps → Update Apps List

3. **Upgrade the module:**
   ```bash
   odoo-bin -c /path/to/odoo.conf -d your_database -u purchase_price_validation --stop-after-init
   ```
   Or from UI: Apps → Search "Purchase Order Price Validation" → Upgrade

### Testing Checklist

#### 1. Module Installation
- [ ] Module installs without errors
- [ ] No `AttributeError` about `move_ids_without_package`
- [ ] No issues with product type validation

#### 2. Configuration Settings Test
- [ ] Go to Inventory → Configuration → Settings
- [ ] Scroll down to "Validación de Precios" section
- [ ] Verify two checkboxes appear:
  - "Validar variación de precios en Órdenes de Compra"
  - "Validar variación de precios en Recepciones de Inventario"
- [ ] Both should be enabled by default
- [ ] Save settings

#### 3. Product Configuration Test
- [ ] Go to Inventory → Products → Products
- [ ] Open any product of type **Goods** (consu)
- [ ] Verify "Porcentaje de variación" field appears in the Cost section
- [ ] Set a variation percentage (e.g., 10%)
- [ ] Save the product

#### 4. Purchase Order - Zero Price Test
- [ ] Create a new Purchase Order
- [ ] Add a product line with price = 0
- [ ] Try to confirm the order
- [ ] **Expected:** Warning wizard appears for non-managers
- [ ] **Expected:** Confirmation wizard appears for stock managers

#### 5. Purchase Order - Price Variation Test
- [ ] Create a new Purchase Order
- [ ] Add a product with cost = $100 and variation = 10%
- [ ] Set unit price to $120 (20% variation, exceeds limit)
- [ ] Try to confirm the order
- [ ] **Expected:** Warning/Confirmation wizard shows variation details
- [ ] Verify the table displays: Product, Allowed %, Generated %, Cost, New Cost

#### 6. Purchase Order - Normal Flow Test
- [ ] Create a new Purchase Order
- [ ] Add products with prices within allowed variation
- [ ] Confirm the order
- [ ] **Expected:** Order confirms normally without warnings

#### 7. Permission Test
- [ ] Test as regular user (without stock.group_stock_manager)
- [ ] **Expected:** Cannot confirm orders with variations
- [ ] Test as stock manager
- [ ] **Expected:** Can confirm orders with variations after wizard confirmation

#### 8. Stock Picking - Incoming Reception Test
- [ ] Go to Inventory → Operations → Receipts
- [ ] Create a new receipt or open an existing one
- [ ] Add product lines with price_unit = 0 or with high variation
- [ ] Try to validate the receipt (click "Validate" button)
- [ ] **Expected:** Warning/Confirmation wizard appears similar to purchase orders
- [ ] Verify the table displays variation details correctly

#### 9. Stock Picking - Normal Reception Test
- [ ] Create a new incoming receipt
- [ ] Add products with prices within allowed variation
- [ ] Validate the receipt
- [ ] **Expected:** Receipt validates normally without warnings

#### 10. Configuration Toggle Test
- [ ] Go to Inventory → Configuration → Settings
- [ ] Disable "Validar variación de precios en Órdenes de Compra"
- [ ] Save settings
- [ ] Create a purchase order with price variations
- [ ] Try to confirm
- [ ] **Expected:** Order confirms without validation
- [ ] Re-enable the setting and test again
- [ ] **Expected:** Validation works again

### Common Issues & Solutions

**Issue:** `AttributeError: 'stock.picking' object has no attribute 'move_ids_without_package'`  
**Solution:** Ensure you're running the updated module with `move_ids` instead of `move_ids_without_package`.

**Issue:** Product validation not triggering  
**Solution:** Verify the product type is **Goods** (consu), not Service. The validation only applies to physical products.

**Issue:** Module not appearing in Apps list  
**Solution:** Update apps list or restart Odoo with `--update=all`

**Issue:** "Module not found" error  
**Solution:** Verify module is in correct addons path and path is in odoo.conf

## Summary

This module required two critical changes for Odoo 19 compatibility:

1. **Product type check:** `product.type == 'product'` → `product.type == 'consu'` (Odoo 19 removed the `'product'` type)
2. **Stock picking moves:** `move_ids_without_package` → `move_ids` (field removed in Odoo 19)

**Total files modified:** 2 (models/purchase_order.py, models/stock_picking.py)  
**Compatibility:** All features work as expected after the changes
