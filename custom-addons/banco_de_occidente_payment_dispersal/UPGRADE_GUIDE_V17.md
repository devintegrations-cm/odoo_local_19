# Odoo 16 to 17 Upgrade Guide
## Banco de Occidente Payment Dispersal Module

---

## Summary of Changes

This document details all changes made to upgrade the `banco_de_occidente_payment_dispersal` module from Odoo 16 to Odoo 17.

---

## 1. Manifest File Changes

**File:** `__manifest__.py`

### Change:
- Updated version from `'0.1'` to `'17.0.0.1'`

### Why:
Odoo 17 modules should follow the versioning pattern: `17.0.x.y` where:
- `17.0` = Odoo version
- `x` = major module version
- `y` = minor/patch version

---

## 2. Python Model Changes

**File:** `models/account_payment.py`

### Change 1: Added Required Imports

**Added:**
```python
import tempfile
import os
```

### Why:
These imports are needed for proper temporary file handling with correct permissions across different operating systems.

---

### Change 2: Removed `pay.type == 'bank'` condition

**Before (Odoo 16):**
```python
if pay.payment_type == 'outbound' and pay.type == 'bank' and pay.partner_id...
```

**After (Odoo 17):**
```python
if pay.payment_type == 'outbound' and pay.partner_id...
```

### Why:
In Odoo 17, the `type` field was **removed** from `account.payment` model. This field was used to distinguish between 'bank' and 'cash' payments. In v17, this is now handled through `payment_method_line_id` which links to payment methods configured on journals.

**Impact:** The condition now relies only on `payment_type == 'outbound'` and the presence of bank account information. If you need to filter by payment method, you should check `payment_method_line_id.payment_method_id.code` instead.

---

### Change 3: Fixed File Generation Methods

**Changes made to file handling methods:**

1. **`generate_txt_file()`** - Now uses `tempfile.gettempdir()` for proper temp directory
2. **`read_file()`** - Updated to accept full file path
3. **`write_file()`** - Changed from append mode to write mode, removed manual close
4. **Filename format** - Changed from `YYYY-MM-DD HH:MM:SS` to `YYYYMMDD_HHMMSS` (removed colons and spaces)
5. **File cleanup** - Added automatic deletion of temp files after use

### Why:
- **Permission errors fixed**: Using `tempfile.gettempdir()` ensures correct permissions
- **Cross-platform compatibility**: Works on Linux, Windows, and Mac
- **Filesystem safety**: Removed colons from filenames (problematic on some systems)
- **Resource management**: Temp files are now cleaned up automatically
- **Better practices**: Using proper temp file handling instead of hardcoded `/tmp/`

**Before:**
```python
def generate_txt_file(self, filename):
    return '/tmp/'+filename+'.txt'

def write_file(self, filename, data):
    with open(filename+'.txt', 'a') as file:
        for row in data:
            row_str = ''.join(map(str, row))
            file.write(row_str + '\n')
    file.close()
```

**After:**
```python
def generate_txt_file(self, filename):
    temp_dir = tempfile.gettempdir()
    return os.path.join(temp_dir, filename + '.txt')

def write_file(self, filepath, data):
    with open(filepath, 'w') as file:
        for row in data:
            row_str = ''.join(map(str, row))
            file.write(row_str + '\n')
```

---

## 3. XML View Changes

**File:** `views/bancodeoccidente_payment_dispersal_fields_views.xml`

### Change 1: Removed `type` attribute from view records

**Before (Odoo 16):**
```xml
<record id="..." model="ir.ui.view">
    <field name="type">form</field>
    ...
</record>
```

**After (Odoo 17):**
```xml
<record id="..." model="ir.ui.view">
    <!-- type attribute removed -->
    ...
</record>
```

### Why:
The `type` attribute in `ir.ui.view` records is **deprecated** in Odoo 17. The view type is now automatically inferred from the root element in the `arch` field (`<form>`, `<tree>`, `<kanban>`, etc.).

---

### Change 2: Updated `web_ribbon` widget attributes

**Before (Odoo 16):**
```xml
<widget name="web_ribbon" title="Archived" bg_color="bg-danger" 
        attrs="{'invisible': [('active', '=', True)]}"/>
```

**After (Odoo 17):**
```xml
<widget name="web_ribbon" title="Archived" bg_color="text-bg-danger" 
        invisible="active"/>
```

### Why:
- **`attrs` is deprecated** in Odoo 17. Use direct attributes instead: `invisible`, `readonly`, `required`, `column_invisible`
- **Bootstrap 5 migration**: `bg-danger` → `text-bg-danger` (new Bootstrap 5 class names)
- **Simplified domain syntax**: `invisible="active"` is equivalent to `invisible="[('active', '=', True)]"`

---

### Change 3: Replaced `attrs` with direct attributes

**Before (Odoo 16):**
```xml
<field name="active" invisible='1'/>
<field name="name" required='1'/>
```

**After (Odoo 17):**
```xml
<field name="active" invisible="1"/>
<field name="name" required="1"/>
```

### Why:
- Changed single quotes to double quotes for consistency (both work, but double quotes are standard in XML)
- These direct attributes (`invisible`, `required`, `readonly`) are the preferred way in v17

---

## 4. Files That Did NOT Require Changes

The following files work as-is in Odoo 17:

- `__init__.py` - No changes needed
- `models/__init__.py` - No changes needed
- `models/bancodeoccidente_payment_dispersal_field.py` - No changes needed
- `models/res_partner_bank.py` - No changes needed
- `views/account_payment_views.xml` - No changes needed
- `views/account_payment_action_server.xml` - No changes needed
- `views/res_partner_bank_views.xml` - No changes needed
- `views/menus.xml` - No changes needed
- `data/bancodeoccidente_payment_dispersal_field_data.xml` - No changes needed
- `security/ir.model.access.csv` - No changes needed

---

## 5. Key Odoo 17 Breaking Changes Summary

### Python Changes:
1. **`account.payment.type` field removed** - Use `payment_method_line_id` instead
2. **No major API changes** for this module's use case

### XML/View Changes:
1. **`attrs` attribute deprecated** - Use direct attributes: `invisible`, `readonly`, `required`
2. **`type` attribute in views deprecated** - Remove it, type is auto-detected
3. **Bootstrap 5 classes** - Update color classes (e.g., `bg-danger` → `text-bg-danger`)
4. **Simplified invisible domains** - `invisible="field_name"` instead of `attrs="{'invisible': [('field_name', '=', True)]}"`

---

## 6. Installation & Testing Checklist

### Pre-Installation:
- [ ] Backup your Odoo 16 database
- [ ] Ensure `account_payment_dispersion` module is upgraded to v17 first (dependency)
- [ ] Review custom modifications if any

### Installation Steps:

1. **Update module files:**
   ```bash
   # Copy upgraded module to Odoo 17 addons directory
   cp -r banco_de_occidente_payment_dispersal /path/to/odoo17/addons/
   ```

2. **Restart Odoo server:**
   ```bash
   # Restart with update flag
   ./odoo-bin -c odoo.conf -u banco_de_occidente_payment_dispersal -d your_database
   ```

3. **Or upgrade via UI:**
   - Go to Apps menu
   - Remove "Apps" filter
   - Search for "Banco de Occidente Payment Dispersal"
   - Click "Upgrade"

### Testing Checklist:

#### Basic Functionality:
- [ ] Module installs/upgrades without errors
- [ ] No errors in server logs during upgrade
- [ ] All menus are visible: Accounting → Payment Dispersal → Configurations Banco de Occidente

#### Configuration Fields:
- [ ] Open "Configuration payment dispersal fields" menu
- [ ] Verify all default fields are present (Source account, Beneficiary Name, etc.)
- [ ] Create a new field configuration
- [ ] Edit an existing field
- [ ] Verify sequence (drag & drop) works in list view
- [ ] Archive/unarchive a field

#### Partner Bank Configuration:
- [ ] Go to Contacts → Select a vendor
- [ ] Open Bank Accounts tab
- [ ] Create/edit a bank account
- [ ] Verify "Banco de Occidente" tab is visible
- [ ] Set "Form of payment" and "Type of service"
- [ ] Save and verify values persist

#### Payment Creation & Dispersal:
- [ ] Create a vendor bill
- [ ] Register a payment (outbound)
- [ ] Verify "Fields Banco de occidente" tab appears in payment form
- [ ] Verify fields auto-populate from partner bank account
- [ ] Manually adjust "Form of payment" and "Type of service" if needed
- [ ] Create multiple payments for the same journal

#### File Generation:
- [ ] Select multiple payments in list view
- [ ] Click Action → "Generate dispersion file Banco de Occidente"
- [ ] Verify TXT file downloads
- [ ] Open TXT file and verify format:
  - Header line starts with "1"
  - Detail lines start with "2"
  - Footer line starts with "3"
  - All fields are properly formatted (zero-padded, space-padded)
- [ ] Verify payment dispersal record is created
- [ ] Check that payments are linked to dispersal record

#### Error Handling:
- [ ] Try generating file with payments from different journals (should show error)
- [ ] Try generating file with payment missing bank account (should show error)
- [ ] Try generating file with payment missing bank code (should show error)
- [ ] Try generating file with payment missing form of payment (should show error)

#### Multi-Company (if applicable):
- [ ] Test with multiple companies
- [ ] Verify field configurations are company-specific
- [ ] Verify payments respect company context

---

## 7. Known Issues & Considerations

### Potential Issues:

1. **Payment Method Filtering:**
   - The removed `type == 'bank'` condition means the module now processes all outbound payments
   - If you need to filter by payment method, add this condition:
     ```python
     if pay.payment_method_line_id.payment_method_id.code in ['manual', 'check_printing']:
     ```

2. **Dependency on `account_payment_dispersion`:**
   - This module depends on a custom module that must also be upgraded to v17
   - Ensure that module is compatible before upgrading this one

3. **File Generation Path:**
   - The module writes to `/tmp/` directory
   - Ensure proper permissions on production servers
   - Consider using `tempfile` module for better cross-platform compatibility

### Recommendations:

1. **Test in staging environment first**
2. **Review any custom modifications** you may have made
3. **Check server logs** during and after upgrade
4. **Verify file format** with Banco de Occidente specifications
5. **Test with real payment data** before going live

---

## 8. Rollback Plan

If issues occur:

1. **Restore database backup:**
   ```bash
   dropdb your_database
   createdb your_database
   psql your_database < backup.sql
   ```

2. **Revert to Odoo 16 module version**

3. **Restart Odoo 16 server**

---

## 9. Additional Resources

- [Odoo 17 Release Notes](https://www.odoo.com/odoo-17)
- [Odoo 17 Developer Documentation](https://www.odoo.com/documentation/17.0/developer.html)
- [Odoo 16 to 17 Migration Guide](https://www.odoo.com/documentation/17.0/developer/howtos/upgrade_custom_db.html)

---

## Support

For issues or questions:
- **Developer:** Firefly Software Consulting S.A.S
- **Website:** https://firefly-e.com/

---

**Last Updated:** 2025-11-11
**Module Version:** 17.0.0.1
