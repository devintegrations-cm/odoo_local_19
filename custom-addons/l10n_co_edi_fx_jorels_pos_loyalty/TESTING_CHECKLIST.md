# Testing Checklist - Odoo 17 Upgrade

## Pre-Upgrade Preparation
- [ ] Backup Odoo 16 database
- [ ] Backup module files
- [ ] Document current module version
- [ ] Test in staging environment first
- [ ] Verify dependencies are Odoo 17 compatible:
  - [ ] `pos_loyalty`
  - [ ] `l10n_co_edi_jorels`
  - [ ] `l10n_co_edi_jorels_pos`

## Installation
- [ ] Copy upgraded module to addons directory
- [ ] Update apps list in Odoo
- [ ] Upgrade module via CLI or UI
- [ ] Check logs for errors during upgrade
- [ ] Restart Odoo server
- [ ] Clear browser cache (Ctrl+Shift+R)

## Basic Module Tests
- [ ] Module appears in Apps list
- [ ] Module status shows "Installed"
- [ ] No Python errors in server logs
- [ ] No JavaScript errors in browser console

## Backend Configuration Tests
- [ ] Navigate to Point of Sale > Configuration > Settings
- [ ] Verify "Enable Obligatory Invoice" option is visible
- [ ] Enable the option and save
- [ ] Disable the option and save
- [ ] Navigate to Accounting > Customers > Invoices
- [ ] Open any invoice
- [ ] Verify "Es premio" (invoice_reward_line) field is visible
- [ ] Verify "Precio Premio" (invoice_reward_price) field is visible

## POS Session Tests
- [ ] Open POS (Point of Sale > Dashboard > New Session)
- [ ] POS interface loads without errors
- [ ] Check browser console (F12) - no JavaScript errors
- [ ] Check Network tab - all assets loaded (no 404s)
- [ ] Verify payment_screen.js is loaded
- [ ] Verify models.js is loaded

## Basic POS Order Tests
- [ ] Create new order
- [ ] Add regular product to order
- [ ] Change quantity
- [ ] Change price
- [ ] Remove product
- [ ] Add product again
- [ ] Proceed to payment

## Customer Validation Tests
- [ ] Create order with products
- [ ] Click "Customer" button
- [ ] Select customer with incomplete data
- [ ] Proceed to payment
- [ ] Click "Validate"
- [ ] Verify popup shows missing fields:
  - [ ] Responsabilidad (type_liability_id)
  - [ ] Regimen (type_regime_id)
  - [ ] Número de documento (vat)
  - [ ] Nombre (name)
  - [ ] Municipalidad (municipality_id)
  - [ ] Tipo documento (l10n_latam_identification_type_id)
  - [ ] Correo Electrónico (email)
  - [ ] País (country_id)
- [ ] Complete customer data
- [ ] Retry validation - should succeed

## Loyalty Rewards Tests
- [ ] Create order with product eligible for loyalty reward
- [ ] Verify loyalty points are calculated
- [ ] Apply loyalty reward
- [ ] Verify reward line appears in order
- [ ] Check reward line has negative price
- [ ] Verify `reward_related_product_line_id` is set (check browser console logs)
- [ ] Proceed to payment
- [ ] Validate order

## Zero Quantity/Price Validation Tests
- [ ] Create order with product
- [ ] Set quantity to 0
- [ ] Try to validate
- [ ] Verify popup shows "Productos con Cantidad en Cero"
- [ ] Fix quantity
- [ ] Set price to 0
- [ ] Try to validate
- [ ] Verify popup shows "Productos con Precio en Cero"
- [ ] Fix price
- [ ] Validate successfully

## Obligatory Invoice Tests (Config Enabled)
- [ ] Enable "Enable Obligatory Invoice" in POS config
- [ ] Open new POS session
- [ ] Create order
- [ ] Proceed to payment
- [ ] Verify "Invoice" checkbox is checked and disabled
- [ ] Try to uncheck - should remain checked
- [ ] Validate order
- [ ] Verify invoice is created

## Obligatory Invoice Tests (Config Disabled)
- [ ] Disable "Enable Obligatory Invoice" in POS config
- [ ] Open new POS session
- [ ] Create order
- [ ] Proceed to payment
- [ ] Verify "Invoice" checkbox can be toggled
- [ ] Uncheck invoice
- [ ] Validate order
- [ ] Verify no invoice is created
- [ ] Create another order
- [ ] Check invoice checkbox
- [ ] Validate order
- [ ] Verify invoice is created

## Invoice Creation Tests
- [ ] Create POS order with loyalty reward
- [ ] Validate order with invoice
- [ ] Navigate to Accounting > Customers > Invoices
- [ ] Find the created invoice
- [ ] Verify invoice lines:
  - [ ] Regular product lines have normal price
  - [ ] Reward lines have `invoice_reward_line` = True
  - [ ] Reward lines have price_unit = 0
  - [ ] Reward lines have `invoice_reward_price` > 0
- [ ] Verify total amount is correct
- [ ] Post the invoice
- [ ] Verify no errors during posting

## Invoice Reward Line Processing Tests
- [ ] Create invoice with reward lines
- [ ] Verify `_prepare_invoice_lines()` logic:
  - [ ] Reward lines are split correctly
  - [ ] Target product lines are identified
  - [ ] Quantities are calculated correctly
  - [ ] Tax IDs are assigned properly
- [ ] Check server logs for warnings/errors
- [ ] Verify final invoice line structure

## Payment Processing Tests
- [ ] Create order with reward lines
- [ ] Add payment
- [ ] Validate order
- [ ] Verify payment is recorded
- [ ] Check if automatic tax payment is created (if applicable)
- [ ] Verify reconciliation works correctly

## Colombian E-Invoicing Tests
- [ ] Create order with complete customer data
- [ ] Include loyalty rewards
- [ ] Validate order with invoice
- [ ] Verify electronic invoice is generated
- [ ] Check Jorels integration processes invoice
- [ ] Verify invoice XML is correct
- [ ] Check DIAN validation (if applicable)
- [ ] Verify invoice number sequence

## Edge Cases
- [ ] Order with multiple reward lines
- [ ] Order with reward but no target product
- [ ] Order with same product multiple times + reward
- [ ] Order with mixed taxed/untaxed products + rewards
- [ ] Refund order with reward lines
- [ ] Partial payment scenarios
- [ ] Multiple payment methods

## Performance Tests
- [ ] Create order with 20+ products
- [ ] Apply multiple rewards
- [ ] Validate order - check response time
- [ ] Create 10 orders in succession
- [ ] Check memory usage in browser
- [ ] Check server load

## Browser Compatibility
- [ ] Test in Chrome/Chromium
- [ ] Test in Firefox
- [ ] Test in Safari (if applicable)
- [ ] Test in Edge
- [ ] Test on tablet (if applicable)
- [ ] Test on mobile (if applicable)

## Regression Tests
- [ ] All existing POS features still work
- [ ] Standard invoicing works
- [ ] Customer creation/editing works
- [ ] Product search works
- [ ] Discount application works
- [ ] Session closing works
- [ ] Reports generation works

## Final Checks
- [ ] No errors in Odoo logs
- [ ] No JavaScript errors in console
- [ ] No SQL errors
- [ ] No permission errors
- [ ] Module can be uninstalled (if needed)
- [ ] Module can be reinstalled
- [ ] Data integrity maintained

## Sign-off
- [ ] All critical tests passed
- [ ] All blocking issues resolved
- [ ] Documentation reviewed
- [ ] Stakeholders notified
- [ ] Ready for production deployment

---

## Notes Section
Use this space to document any issues found during testing:

### Issues Found:
1. 
2. 
3. 

### Resolutions:
1. 
2. 
3. 

### Known Limitations:
1. ExtendedPartnerDetailsEdit component removed (needs reimplementation if required)
2. 
3. 

---

**Tester Name:** ___________________
**Date:** ___________________
**Environment:** [ ] Staging [ ] Production
**Odoo Version:** 17.0
**Module Version:** 17.0.1.0.0
