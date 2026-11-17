# Odoo 17 Upgrade Guide - l10n_co_edi_fx_jorels_pos_loyalty

## Module Overview
This module fixes Colombian electronic invoicing (Jorels) integration with POS loyalty/rewards programs. It handles reward line processing, tax calculations, and enforces mandatory invoice fields for Colombian compliance.

## Summary of Changes

### 1. Manifest File (__manifest__.py)
**Changes:**
- Updated version from `0.1` to `17.0.1.0.0` (Odoo 17 convention)
- Changed assets bundle from `point_of_sale.assets` to `point_of_sale._assets_pos` (CRITICAL for Odoo 17)
- Removed old JS files (ExtendedPartnerDetailsEdit.js, PartnerDetailsEdit.js)
- Updated file references to use lowercase with underscores (payment_screen.js)
- Added `license` field (LGPL-3)
- Changed `auto_install` to False (safer default)

**Why:** Odoo 17 completely restructured POS assets loading. The old bundle no longer exists.

---

### 2. JavaScript Files - Complete Rewrite

#### models.js
**Old Approach (Odoo 16):**
```javascript
odoo.define('module.name', function(require) {
    const Registries = require('point_of_sale.Registries');
    Registries.Model.extend(Orderline, UPOrderline);
});
```

**New Approach (Odoo 17):**
```javascript
/** @odoo-module */
import { Orderline } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

patch(Orderline.prototype, {
    // Your customizations
});
```

**Key Changes:**
- Removed `odoo.define()` - Odoo 17 uses ES6 modules
- Replaced `Registries.Model.extend()` with `patch()` utility
- Import statements instead of `require()`
- No more class wrapping - direct prototype patching

#### payment_screen.js (formerly PaymentScreen.js)
**Changes:**
- File renamed to lowercase with underscore
- Converted from `odoo.define` to ES6 module with `@odoo-module` directive
- Changed from `Registries.Component.extend()` to `patch()`
- Updated popup API: `this.showPopup()` → `this.popup.add()`
- Updated translation: `this.env._t()` → `_t()` (direct import)
- Removed OWL hooks imports (not needed for patches)

**Why:** Odoo 17 uses a completely new POS architecture based on OWL 2 and ES6 modules.

---

### 3. Python Model Updates

#### models/account_move.py
**Changes:**
1. Uncommented `_post()` method (was `_postxxxxx`)
2. Uncommented `action_post()` method (was `action_postxxxxx`)
3. Fixed deprecated field: `internal_type` → `account_type`
   - `'receivable'` → `'asset_receivable'`

**Why:** 
- The `internal_type` field was deprecated in Odoo 16 and removed in Odoo 17
- New `account_type` uses different values with prefixes

#### models/pos_order_line.py
**Changes:**
- Removed `_export_for_ui()` method
- Added `_load_pos_data_fields()` method for Odoo 17

**Old (Odoo 16):**
```python
def _export_for_ui(self, orderline):
    result = super()._export_for_ui(orderline)
    result['reward_related_product_line_id'] = orderline.reward_related_product_line_id
    return result
```

**New (Odoo 17):**
```python
def _load_pos_data_fields(self, config_id):
    fields = super()._load_pos_data_fields(config_id)
    fields.extend(['reward_related_product_line_id', 'reward_related_order_line_id'])
    return fields
```

**Why:** Odoo 17 changed how POS loads data from backend. The `_export_for_ui` pattern is replaced with field declarations.

#### models/pos_payment.py
**Changes:**
- Uncommented `_create_payment_moves()` method (was `_create_payment_movesxx`)

---

### 4. Removed Files
The following files were removed as they're not compatible with Odoo 17:
- `static/src/js/PaymentScreen.js` (replaced with payment_screen.js)
- `static/src/js/ExtendedPartnerDetailsEdit.js` (needs complete rewrite for OWL 2)
- `static/src/js/PartnerDetailsEdit.js` (not needed)
- `static/src/xml/ExtendedPartnerDetailsEdit.xml` (not compatible)

**Note:** The ExtendedPartnerDetailsEdit functionality would need to be reimplemented using Odoo 17's partner editing components if required.

---

## Breaking Changes Between Odoo 16 and 17

### 1. POS JavaScript Framework
- **Old:** AMD modules with `odoo.define()`
- **New:** ES6 modules with `@odoo-module` directive
- **Impact:** All JS files must be rewritten

### 2. Component Extension
- **Old:** `Registries.Component.extend()` and `Registries.Model.extend()`
- **New:** `patch()` utility from `@web/core/utils/patch`
- **Impact:** Different syntax for extending components

### 3. POS Data Loading
- **Old:** `_export_for_ui()` method
- **New:** `_load_pos_data_fields()` method
- **Impact:** Backend methods need updating

### 4. Account Types
- **Old:** `internal_type` field with values like 'receivable'
- **New:** `account_type` field with values like 'asset_receivable'
- **Impact:** All account type checks must be updated

### 5. Assets Bundle
- **Old:** `point_of_sale.assets`
- **New:** `point_of_sale._assets_pos`
- **Impact:** Manifest must be updated or assets won't load

### 6. File Naming Convention
- **Old:** CamelCase (PaymentScreen.js)
- **New:** snake_case (payment_screen.js)
- **Impact:** All POS files should follow new convention

---

## Installation & Testing Checklist

### Pre-Installation
1. ✅ Backup your Odoo 16 database
2. ✅ Upgrade Odoo to version 17
3. ✅ Ensure dependencies are upgraded:
   - `pos_loyalty` (Odoo 17 version)
   - `l10n_co_edi_jorels` (Odoo 17 version)
   - `l10n_co_edi_jorels_pos` (Odoo 17 version)

### Installation Steps
1. **Update Module Files:**
   ```bash
   # Replace old module with upgraded version
   cd /path/to/odoo/addons
   # Copy upgraded module files
   ```

2. **Update Module List:**
   ```bash
   # In Odoo shell or via UI
   # Apps > Update Apps List
   ```

3. **Upgrade Module:**
   ```bash
   # Via command line:
   odoo-bin -u l10n_co_edi_fx_jorels_pos_loyalty -d your_database
   
   # Or via UI:
   # Apps > Search "Fix EI Jorels" > Upgrade
   ```

4. **Clear Browser Cache:**
   - Clear browser cache completely
   - Or use Ctrl+Shift+R (hard refresh)
   - Assets are cached aggressively

5. **Restart Odoo Server:**
   ```bash
   sudo systemctl restart odoo
   ```

### Testing Checklist

#### Backend Tests
- [ ] Module installs without errors
- [ ] No Python errors in logs
- [ ] Account move views load correctly
- [ ] Invoice reward line field visible
- [ ] POS config settings show "Enable Obligatory Invoice" option

#### POS Tests
- [ ] POS loads without JavaScript errors (check browser console)
- [ ] Open POS session successfully
- [ ] Create order with regular products
- [ ] Add customer to order
- [ ] Verify customer validation works (missing fields popup)
- [ ] Test with loyalty rewards:
  - [ ] Add product eligible for reward
  - [ ] Apply loyalty reward
  - [ ] Verify reward line is created
  - [ ] Check `reward_related_product_line_id` is set
- [ ] Payment screen loads correctly
- [ ] Obligatory invoice checkbox behavior:
  - [ ] If config enabled: checkbox forced ON
  - [ ] If config disabled: checkbox works normally
- [ ] Validate order successfully
- [ ] Check zero quantity validation
- [ ] Check zero price validation

#### Invoice Tests
- [ ] POS order creates invoice
- [ ] Invoice contains reward lines
- [ ] Reward line has `invoice_reward_line` = True
- [ ] Reward line price is 0
- [ ] `invoice_reward_price` field stores original price
- [ ] Tax calculations are correct
- [ ] Invoice posts successfully

#### Colombian E-Invoicing Tests
- [ ] Customer fields validation works:
  - [ ] type_liability_id
  - [ ] type_regime_id
  - [ ] vat
  - [ ] name
  - [ ] municipality_id
  - [ ] l10n_latam_identification_type_id
  - [ ] email
  - [ ] country_id
- [ ] Electronic invoice generation works
- [ ] Jorels integration processes invoice
- [ ] Tax payment creation (if applicable)

---

## Common Issues & Solutions

### Issue 0: Reconciliation Error on POS Orders (FIXED)
**Symptom:** "UserError: You are trying to reconcile some entries that are already reconciled"
**Solution:** 
- This was fixed in version 17.0.1.0.1
- The custom payment move logic in `pos_payment.py` has been disabled
- Odoo 17 handles payment reconciliation automatically
- If you still see this error, ensure you're using the latest version

### Issue 1: Assets Not Loading
**Symptom:** JavaScript errors, POS doesn't load
**Solution:** 
- Verify manifest uses `point_of_sale._assets_pos`
- Clear browser cache
- Restart Odoo server
- Check browser console for 404 errors

### Issue 2: Module Won't Upgrade
**Symptom:** Upgrade fails with dependency errors
**Solution:**
- Ensure all dependencies are Odoo 17 compatible
- Check if `l10n_co_edi_jorels` and `l10n_co_edi_jorels_pos` are upgraded first
- Review Odoo logs for specific errors

### Issue 3: Payment Screen Not Working
**Symptom:** Can't validate orders, popup errors
**Solution:**
- Check browser console for JavaScript errors
- Verify `payment_screen.js` is loaded (Network tab)
- Ensure patch syntax is correct

### Issue 4: Reward Lines Not Processing
**Symptom:** Invoices don't show reward lines correctly
**Solution:**
- Check `_prepare_invoice_lines()` method in pos_order.py
- Verify `reward_related_product_line_id` is being set in JS
- Check logs for warnings during invoice creation

### Issue 5: Account Type Errors
**Symptom:** Errors about 'internal_type' not found
**Solution:**
- Search codebase for `internal_type`
- Replace with `account_type`
- Update values: 'receivable' → 'asset_receivable', 'payable' → 'liability_payable'

---

## Development Notes

### If You Need to Add More Customizations

1. **JavaScript:**
   - Use `@odoo-module` directive
   - Import with ES6 syntax
   - Use `patch()` for extensions
   - Follow snake_case naming

2. **Python:**
   - Check Odoo 17 API changes
   - Use `account_type` instead of `internal_type`
   - Test data loading methods for POS

3. **XML:**
   - Most view syntax remains the same
   - Check for deprecated attributes

### Useful Resources
- Odoo 17 POS Documentation: https://www.odoo.com/documentation/17.0/developer/reference/frontend/javascript_modules.html
- Migration Guide: https://www.odoo.com/documentation/17.0/developer/reference/upgrades.html
- OWL Framework: https://github.com/odoo/owl

---

## Rollback Plan

If upgrade fails:
1. Restore database backup
2. Revert to Odoo 16
3. Restore old module version
4. Investigate errors before retry

---

## Support

For issues specific to this module upgrade, check:
1. Odoo logs: `/var/log/odoo/odoo-server.log`
2. Browser console (F12)
3. Network tab for failed asset loads

---

## Version History

- **17.0.1.0.0** - Initial Odoo 17 upgrade
  - Converted JavaScript to ES6 modules
  - Updated Python APIs
  - Fixed deprecated fields
  - Removed incompatible components

---

**Last Updated:** 2025-11-14
**Tested On:** Odoo 17.0
**Status:** Ready for testing
