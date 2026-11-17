# Odoo 16 to 17 Upgrade Guide - Bancolombia Payment Dispersal Module

## Module Information
- **Module Name:** bancolombia_payment_dispersal
- **Purpose:** Generate Excel files for payment dispersion to suppliers through Bancolombia bank
- **Current Version:** 0.1 (Odoo 16)
- **Target Version:** 17.0.1.0.0 (Odoo 17)

## Changes Made

### 1. Manifest File (`__manifest__.py`)

**Changes:**
- Updated version from `0.1` to `17.0.1.0.0` (following Odoo 17 versioning convention: `{odoo_version}.{major}.{minor}.{patch}`)
- Uncommented and enabled `external_dependencies` for Python packages `openpyxl` and `unidecode`

**Why:** 
- Odoo 17 uses a standardized versioning format
- External dependencies should be explicitly declared for proper module installation validation

### 2. View Files - XML Updates

#### `views/bancolombia_payment_dispersal_fields_views.xml`

**Changes:**
- Removed deprecated `type` field from view records (2 occurrences)
- Updated `web_ribbon` widget:
  - Changed `bg_color="bg-danger"` to `bg_color="text-bg-danger"` (Bootstrap 5 class)
  - Replaced `attrs="{'invisible': [('active', '=', True)]}"` with `invisible="active"`

**Why:**
- The `type` field in `ir.ui.view` records is deprecated in Odoo 17 (automatically inferred from arch)
- Odoo 17 uses Bootstrap 5, which changed class naming conventions
- The `attrs` attribute is deprecated in favor of direct attribute usage with domain expressions

### 3. Python Models - No Changes Required

**Files Analyzed:**
- `models/account_payment.py`
- `models/bancolombia_payment_dispersal_field.py`
- `models/res_bank.py`
- `models/res_partner_bank.py`

**Status:** All Python code is compatible with Odoo 17
- `Command.set()` usage is correct
- `safe_eval` imports are proper
- Field definitions (Selection, Char, etc.) remain unchanged
- API decorators (`@api.depends`, `@staticmethod`) work the same way

### 4. Other Files - No Changes Required

- **Security files** (`security/ir.model.access.csv`): No changes needed
- **Data files** (`data/*.xml`): Compatible with Odoo 17
- **View inheritance**: All XPath expressions remain valid

## Breaking Changes Summary

### What Changed in Odoo 17 That Affects This Module:

1. **attrs Deprecation**
   - Old: `attrs="{'invisible': [('field', '=', value)]}"`
   - New: `invisible="field == value"` or `invisible="not field"`

2. **Bootstrap 5 Migration**
   - Old: `bg-danger`, `bg-success`, etc.
   - New: `text-bg-danger`, `text-bg-success`, etc.

3. **View Type Field**
   - The `type` field in view records is no longer needed

### What Didn't Change (Good News!):

- Python ORM API remains stable
- Field types and attributes
- Inheritance mechanisms
- Security rules format
- Data file structure
- Server actions syntax

## Installation Steps

### Prerequisites

1. **Ensure Python dependencies are installed:**
   ```bash
   pip3 install openpyxl unidecode
   ```

2. **Verify the parent module is available:**
   - Module `account_payment_dispersion` must be installed and upgraded to Odoo 17 first

### Installation Process

1. **Backup your database:**
   ```bash
   pg_dump -U odoo -d your_database > backup_before_upgrade.sql
   ```

2. **Copy the upgraded module to your Odoo 17 addons directory:**
   ```bash
   cp -r bancolombia_payment_dispersal /path/to/odoo17/addons/
   ```

3. **Update the module list:**
   - Go to Apps menu
   - Click "Update Apps List"
   - Or via command line:
     ```bash
     odoo-bin -c /path/to/odoo.conf -d your_database -u bancolombia_payment_dispersal --stop-after-init
     ```

4. **Upgrade the module:**
   - In Apps menu, search for "Bancolombia Payment Dispersal"
   - Click "Upgrade"
   - Or via command line (recommended):
     ```bash
     odoo-bin -c /path/to/odoo.conf -d your_database -u bancolombia_payment_dispersal
     ```

## Testing Checklist

### Backend Functionality

- [ ] **Module Installation**
  - Module installs without errors
  - All dependencies are satisfied
  - No missing external dependencies warnings

- [ ] **Menu Access**
  - Navigate to Accounting → Payment Dispersal → Configurations Bancolombia
  - Verify "Configuration payment dispersal fields" menu is accessible

- [ ] **Field Configuration**
  - Open the dispersal fields list view
  - Verify all 12 default fields are present
  - Test drag-and-drop sequence reordering
  - Create a new field and verify it saves correctly
  - Archive/unarchive a field

- [ ] **Bank Configuration**
  - Go to Contacts → Configuration → Bank Accounts → Banks
  - Open a bank record
  - Verify "Bancolombia Code" field is visible
  - Edit and save a bancolombia code

- [ ] **Partner Bank Account**
  - Open a partner (supplier)
  - Go to Accounting tab → Bank Accounts
  - Create/edit a bank account
  - Verify "Bancolombia" tab is present
  - Set "Type of transaction" field
  - Save and verify it persists

- [ ] **Payment Configuration**
  - Create or open a vendor payment
  - Verify "Bancolombia Fields" tab is visible
  - Check that "Type of transaction" field appears
  - Verify it auto-computes from partner bank account

### Excel Generation

- [ ] **Generate Dispersion File (Standard)**
  - Create multiple vendor payments with:
    - Same journal
    - Different partners
    - Bank accounts configured
    - Transaction types set
  - Select payments in list view
  - Click Action → "Generate Bancolombia dispersion file"
  - Verify Excel file downloads
  - Open Excel and verify:
    - Header information (NIT, account, etc.)
    - All payment rows are present
    - All 12 columns have correct data
    - Special characters (Ñ) are handled correctly
    - Amounts are formatted properly
    - Dates are in YYYYMMDD format

- [ ] **Generate Dispersion File (Payroll)**
  - Select payments
  - Click Action → "Generate Bancolombia dispersion file payroll"
  - Verify file downloads with type_of_payment='225'

- [ ] **Error Handling**
  - Try generating with payments from different journals → Should show error
  - Try with payment missing transaction type → Should show error
  - Try with payment missing bank account (for non-cash types) → Should show error
  - Try with payment missing bank code → Should show error

### Data Integrity

- [ ] **Existing Records**
  - Verify all existing payment dispersal field configurations are intact
  - Check that historical payment records still display correctly
  - Verify bank codes on existing banks are preserved

- [ ] **Multi-company**
  - If using multi-company, verify field configurations are company-specific
  - Test creating fields for different companies

### Security & Permissions

- [ ] **Account User Role**
  - Login as user with "Billing" access
  - Verify can view dispersal fields (read-only)
  - Verify can generate dispersion files

- [ ] **Account Manager Role**
  - Login as user with "Billing Administrator" access
  - Verify can create/edit/delete dispersal fields
  - Verify full access to all features

## Rollback Plan

If issues occur during upgrade:

1. **Restore database backup:**
   ```bash
   dropdb -U odoo your_database
   createdb -U odoo your_database
   psql -U odoo -d your_database < backup_before_upgrade.sql
   ```

2. **Revert to Odoo 16 module version:**
   ```bash
   git checkout odoo-16-version
   ```

3. **Restart Odoo 16 instance**

## Common Issues & Solutions

### Issue: Module won't install - missing dependency
**Solution:** Ensure `account_payment_dispersion` module is installed and upgraded to v17 first

### Issue: "openpyxl" or "unidecode" not found
**Solution:** Install Python packages:
```bash
pip3 install openpyxl unidecode
```

### Issue: Views not updating after upgrade
**Solution:** Clear browser cache and restart Odoo:
```bash
odoo-bin -c /path/to/odoo.conf -d your_database -u bancolombia_payment_dispersal --stop-after-init
```

### Issue: Excel generation fails
**Solution:** 
- Check that all required fields are configured on payments
- Verify partner bank accounts have transaction types set
- Check Odoo logs for specific error messages

## Additional Notes

- This module has no JavaScript/OWL components, so no frontend framework changes were needed
- The module uses standard Odoo patterns that remain stable across versions
- All custom business logic in Python models is compatible with Odoo 17
- The Excel generation using openpyxl library works identically in Odoo 17

## Support

For issues specific to this upgrade:
- Check Odoo logs: `/var/log/odoo/odoo-server.log`
- Enable developer mode for detailed error messages
- Contact: Firefly Software Consulting S.A.S (https://firefly-e.com/)
