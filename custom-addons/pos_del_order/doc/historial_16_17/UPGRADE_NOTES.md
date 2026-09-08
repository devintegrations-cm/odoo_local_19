# Odoo 16 → 17 Upgrade Notes: pos_del_order Module

## Summary of Changes

### 1. **__manifest__.py**
**Changes:**
- Updated `version` from `'16.0'` to `'17.0.1.0.0'` (Odoo 17 standard versioning)
- Changed `'category'` from `'POS'` to `'Point of Sale'` (standard category name)
- **CRITICAL:** Changed asset bundle from `'point_of_sale.assets'` to `'point_of_sale._assets_pos'`
- Updated asset paths to match new Odoo 17 structure:
  - Old: `static/src/js/Screens/TicketScreen.js`
  - New: `static/src/app/screens/ticket_screen/ticket_screen.js`
- Cleaned up commented flags, set `installable: True` and `auto_install: False`

**Why:** Odoo 17 uses a new asset bundle system for POS. The `_assets_pos` bundle is specifically for POS frontend assets.

---

### 2. **JavaScript: ticket_screen.js**
**Location:** `static/src/app/screens/ticket_screen/ticket_screen.js`

**Major Changes:**
- **Removed:** `odoo.define()` pattern (Odoo 16 AMD modules)
- **Added:** ES6 module syntax with `/** @odoo-module */` decorator
- **Removed:** `Registries.Component.extend()` pattern
- **Added:** `patch()` utility from `@web/core/utils/patch`
- **Updated imports:**
  - Old: `require('point_of_sale.TicketScreen')`
  - New: `import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen"`
- **Updated API calls:**
  - Old: `this.env.pos.cashier`
  - New: `this.pos.get_cashier()`
  - Old: `this.env.pos.config`
  - New: `this.pos.config`

**Why:** Odoo 17 migrated from AMD modules to ES6 modules and uses the `patch()` system for extending components instead of class inheritance via Registries.

---

### 3. **XML Template: ticket_screen.xml**
**Location:** `static/src/app/screens/ticket_screen/ticket_screen.xml`

**Changes:**
- **Removed:** `owl="1"` attribute (no longer needed in Odoo 17)
- **Updated operator:** Changed `&amp;` to `and` for boolean logic
- **Updated event handler:**
  - Old: `this.trigger('delete-order', order)`
  - New: `this.onDeleteOrder(order)`
- **Updated mobile check:**
  - Old: `env.isMobile`
  - New: `ui.isSmall`

**Why:** Odoo 17 uses OWL 2.x which has cleaner syntax. Event handling changed from custom triggers to direct method calls. The UI service replaced environment flags.

---

### 4. **Python Models**
**File:** `models/pos_config.py`

**Changes:**
- Removed unused import: `from functools import partial`
- Made Many2many relation explicit with proper parameters:
  - Added `relation='pos_config_able_del_employee_rel'`
  - Added `column1='pos_config_id'`
  - Added `column2='employee_id'`
- Improved field string from "Employees able to del orders" to "Employees able to delete orders"

**Why:** Explicit relation names prevent conflicts and follow Odoo best practices. The old `relation="abl_employee_ids"` was too generic.

**File:** `models/res_config_settings.py` - No changes needed (already compatible)

---

### 5. **File Structure Changes**

**Old Structure (Odoo 16):**
```
static/src/
├── js/
│   └── Screens/
│       └── TicketScreen.js
└── xml/
    └── Screens/
        └── TicketScreen.xml
```

**New Structure (Odoo 17):**
```
static/src/
└── app/
    └── screens/
        └── ticket_screen/
            ├── ticket_screen.js
            └── ticket_screen.xml
```

**Why:** Odoo 17 POS follows a feature-based folder structure where each component has its own directory with lowercase, underscore-separated names. JS and XML files are co-located.

---

## Breaking Changes Summary

1. **Asset Bundle:** Must use `point_of_sale._assets_pos` instead of `point_of_sale.assets`
2. **Module System:** ES6 modules replace AMD (`odoo.define`)
3. **Component Extension:** `patch()` replaces `Registries.Component.extend()`
4. **POS API Changes:**
   - `env.pos.cashier` → `pos.get_cashier()`
   - `env.pos` → `pos` (direct access)
5. **OWL Template Syntax:**
   - Remove `owl="1"` attribute
   - `&amp;` → `and` for boolean operations
   - `env.isMobile` → `ui.isSmall`
6. **Event Handling:** Custom triggers replaced with direct method calls

---

## Installation & Testing Checklist

### Installation Steps:
1. ✅ Backup your Odoo 16 database before upgrading
2. ✅ Copy the upgraded module to your Odoo 17 addons directory
3. ✅ Update the module list: `Settings → Apps → Update Apps List`
4. ✅ Upgrade the module: Search for "Delete Pos Order" → Click "Upgrade"
5. ✅ Restart the Odoo server (recommended)
6. ✅ Clear browser cache and reload

### Testing Checklist:

#### Backend Configuration:
- [ ] Go to `Point of Sale → Configuration → Settings`
- [ ] Select a POS configuration
- [ ] Verify the "Able to delete Orders in POS Session" field appears
- [ ] Add/remove employees from the list
- [ ] Save and verify changes persist

#### POS Session Testing:
- [ ] Open a POS session
- [ ] Create a test order and close it
- [ ] Go to Ticket Screen (Orders button)
- [ ] **Test Case 1 - Allowed Employee:**
  - Login as an employee in the "allowed" list
  - Verify the trash icon appears on orders
  - Click trash icon and confirm deletion works
- [ ] **Test Case 2 - Restricted Employee:**
  - Login as an employee NOT in the "allowed" list
  - Verify the trash icon does NOT appear
  - Verify orders cannot be deleted
- [ ] **Test Case 3 - Empty List (All Allowed):**
  - Clear the employee list in settings
  - Login as any employee
  - Verify all employees can see and use the delete button

#### Edge Cases:
- [ ] Test with `pos_hr` module enabled/disabled
- [ ] Test with multiple POS configurations
- [ ] Test on mobile/tablet view (verify "Delete" text appears)
- [ ] Check browser console for JavaScript errors

---

## Additional Notes

- The old files in `static/src/js/` and `static/src/xml/` can be safely deleted
- If you have custom CSS/SCSS, move it to the new structure under `static/src/app/`
- The module is now fully compatible with Odoo 17's architecture
- No database migration script needed (field names unchanged)

---

## Troubleshooting

**Issue:** Delete button doesn't appear
- Check browser console for JS errors
- Verify assets are loaded: `Settings → Technical → User Interface → Assets`
- Clear browser cache and Odoo assets: `Settings → Technical → User Interface → Assets → Regenerate Assets`

**Issue:** Configuration field not showing
- Verify `pos_hr` module is installed
- Check view inheritance in `Settings → Technical → User Interface → Views`
- Search for view: `res.config.settings.view.form.inherit.pos_del_order`

**Issue:** JavaScript errors in console
- Ensure Odoo 17 is fully updated (check for point_of_sale module updates)
- Verify import paths match your Odoo 17 installation
- Check that `@odoo-module` decorator is present
