# Odoo 17 Upgrade Checklist
## Banco de Occidente Payment Dispersal Module

---

## Pre-Upgrade Preparation

- [ ] **Backup current database**
  ```bash
  pg_dump -U odoo -d your_database > backup_$(date +%Y%m%d).sql
  ```

- [ ] **Verify Odoo 17 installation**
  ```bash
  ./odoo-bin --version
  # Should show: Odoo Server 17.0
  ```

- [ ] **Check dependency module**
  - [ ] Confirm `account_payment_dispersion` is available for Odoo 17
  - [ ] Upgrade dependency first if needed

- [ ] **Review custom modifications**
  - [ ] Document any custom changes made to the module
  - [ ] Check if custom changes are compatible with v17

---

## Upgrade Steps

### Step 1: File Preparation
- [ ] Copy upgraded module to Odoo 17 addons directory
  ```bash
  cp -r banco_de_occidente_payment_dispersal /path/to/odoo17/addons/
  ```

- [ ] Set correct permissions
  ```bash
  chown -R odoo:odoo /path/to/odoo17/addons/banco_de_occidente_payment_dispersal
  ```

- [ ] Verify all files are present
  ```bash
  ls -la /path/to/odoo17/addons/banco_de_occidente_payment_dispersal/
  ```

### Step 2: Module Upgrade
- [ ] **Option A: Command line upgrade**
  ```bash
  ./odoo-bin -c odoo.conf -u banco_de_occidente_payment_dispersal -d your_database --stop-after-init
  ```

- [ ] **Option B: UI upgrade**
  - [ ] Go to Apps menu
  - [ ] Remove "Apps" filter
  - [ ] Search for "Banco de Occidente"
  - [ ] Click "Upgrade" button

### Step 3: Verify Installation
- [ ] Check server logs for errors
  ```bash
  tail -f /var/log/odoo/odoo-server.log
  ```

- [ ] Confirm module version is 17.0.0.1
  - [ ] Apps → Search "Banco de Occidente" → Check version

- [ ] Verify no errors in log during upgrade

---

## Functional Testing

### Test 1: Menu Access
- [ ] Navigate to: **Accounting** → **Payment Dispersal** → **Configurations Banco de Occidente**
- [ ] Menu item is visible
- [ ] No access errors

### Test 2: Field Configuration
- [ ] Open "Configuration payment dispersal fields"
- [ ] Verify all default fields are present:
  - [ ] Source account
  - [ ] Beneficiary Name
  - [ ] Nit/CC
  - [ ] Bank Code
  - [ ] Date of implementation
  - [ ] Form of Payment
  - [ ] Maximum Payment Value
  - [ ] Financial Institution Destination
  - [ ] Voucher
  - [ ] Type of target accounts
  - [ ] Invoice number
  - [ ] Concept

- [ ] **Create new field:**
  - [ ] Click "Create"
  - [ ] Fill in: Name, Value (Python code), Max length
  - [ ] Select fill options (zeros/spaces)
  - [ ] Save
  - [ ] Verify field appears in list

- [ ] **Edit existing field:**
  - [ ] Open any field
  - [ ] Modify max_length
  - [ ] Save
  - [ ] Verify changes persist

- [ ] **Test sequence:**
  - [ ] Drag and drop fields in list view
  - [ ] Verify order changes

- [ ] **Archive/Unarchive:**
  - [ ] Archive a field
  - [ ] Verify "Archived" ribbon appears
  - [ ] Unarchive field
  - [ ] Verify ribbon disappears

### Test 3: Partner Bank Configuration
- [ ] Go to **Contacts**
- [ ] Select or create a vendor
- [ ] Open **Bank Accounts** tab
- [ ] Create/edit bank account
- [ ] Verify **"Banco de Occidente"** tab is visible
- [ ] Set values:
  - [ ] Form of payment: (select option)
  - [ ] Type of service: (select option)
- [ ] Save
- [ ] Reopen and verify values persist

### Test 4: Payment Creation
- [ ] Create a vendor bill
  - [ ] Vendor: (select vendor with bank account)
  - [ ] Amount: 1,000,000 COP
  - [ ] Confirm bill

- [ ] Register payment:
  - [ ] Click "Register Payment"
  - [ ] Payment Type: Outbound
  - [ ] Journal: (select bank journal)
  - [ ] Recipient Bank Account: (select configured account)
  - [ ] Verify **"Fields Banco de occidente"** tab appears
  - [ ] Check fields auto-populate from partner bank:
    - [ ] Form of payment
    - [ ] Type of service
  - [ ] Manually adjust if needed
  - [ ] Confirm payment

- [ ] Create 2-3 more payments for same journal

### Test 5: File Generation - Success Cases
- [ ] Go to **Accounting** → **Payments** → **Payments**
- [ ] Filter: Payment Type = Outbound
- [ ] Select multiple payments (same journal)
- [ ] Click **Action** → **"Generate dispersion file Banco de Occidente"**
- [ ] Verify:
  - [ ] File downloads automatically
  - [ ] Filename format: `bancodeoccidente_dispersion_YYYY-MM-DD_HH:MM:SS.txt`

- [ ] **Verify file content:**
  - [ ] Open TXT file in text editor
  - [ ] Header line (starts with "1"):
    - [ ] Contains source account (16 digits)
    - [ ] Contains date (YYYYMMDD)
    - [ ] Contains number of records
    - [ ] Contains total amount
  - [ ] Detail lines (start with "2"):
    - [ ] One line per payment
    - [ ] Sequential numbering
    - [ ] All fields properly formatted
    - [ ] Zero-padded fields are correct length
    - [ ] Space-padded fields are correct length
  - [ ] Footer line (starts with "3"):
    - [ ] Contains "9999"
    - [ ] Contains number of records
    - [ ] Contains total amount

- [ ] **Verify dispersal record:**
  - [ ] Go to **Accounting** → **Payment Dispersal** → **Payment Dispersals**
  - [ ] Find newly created record
  - [ ] Verify:
    - [ ] Name matches filename
    - [ ] File is attached
    - [ ] All payments are linked
    - [ ] Journal is correct

### Test 6: File Generation - Error Cases
- [ ] **Test: Multiple journals**
  - [ ] Select payments from different journals
  - [ ] Try to generate file
  - [ ] Verify error message: "must be for a single journal"

- [ ] **Test: Missing bank account**
  - [ ] Create payment without recipient bank account
  - [ ] Try to generate file
  - [ ] Verify error message: "has no target account"

- [ ] **Test: Missing bank code**
  - [ ] Create payment with bank account but no bank code
  - [ ] Try to generate file
  - [ ] Verify error message: "No bank or bank code configured"

- [ ] **Test: Missing form of payment**
  - [ ] Create payment without form of payment
  - [ ] Try to generate file
  - [ ] Verify error message: "No payment method configured"

- [ ] **Test: Missing account type**
  - [ ] Create payment with bank account but no account type
  - [ ] Try to generate file
  - [ ] Verify error message: "No account type configured"

### Test 7: Multi-Company (if applicable)
- [ ] Switch to different company
- [ ] Verify field configurations are company-specific
- [ ] Create payment in second company
- [ ] Generate file
- [ ] Verify correct company data

### Test 8: Permissions
- [ ] **As Account User:**
  - [ ] Can view field configurations
  - [ ] Cannot create/edit/delete fields
  - [ ] Can create payments
  - [ ] Can generate dispersal files

- [ ] **As Account Manager:**
  - [ ] Can view field configurations
  - [ ] Can create/edit/delete fields
  - [ ] Can create payments
  - [ ] Can generate dispersal files

---

## Performance Testing

- [ ] Generate file with 10 payments
  - [ ] Time: _____ seconds
  - [ ] File size: _____ KB

- [ ] Generate file with 50 payments
  - [ ] Time: _____ seconds
  - [ ] File size: _____ KB

- [ ] Generate file with 100 payments
  - [ ] Time: _____ seconds
  - [ ] File size: _____ KB

---

## Integration Testing

- [ ] **Test with real bank data:**
  - [ ] Use actual vendor information
  - [ ] Use real bank account numbers
  - [ ] Generate file
  - [ ] Validate format with Banco de Occidente specifications

- [ ] **Test special characters:**
  - [ ] Vendor name with "Ñ" (should convert to "N")
  - [ ] Vendor name > 30 characters (should truncate)
  - [ ] Special characters in concept field

- [ ] **Test edge cases:**
  - [ ] Payment amount = 0.01
  - [ ] Payment amount > 999,999,999.99
  - [ ] Date in different formats
  - [ ] Empty optional fields

---

## Regression Testing

- [ ] **Verify existing data:**
  - [ ] Old payment dispersal records still accessible
  - [ ] Old files still downloadable
  - [ ] Historical data intact

- [ ] **Verify existing configurations:**
  - [ ] Field configurations preserved
  - [ ] Partner bank configurations preserved
  - [ ] Journal configurations preserved

---

## Documentation Review

- [ ] Read `UPGRADE_GUIDE_V17.md`
- [ ] Review `CODE_CHANGES_DETAILED.md`
- [ ] Understand all breaking changes
- [ ] Note any custom modifications needed

---

## Post-Upgrade Tasks

- [ ] **Update internal documentation**
  - [ ] Note Odoo 17 specific behaviors
  - [ ] Update user guides if needed

- [ ] **Train users**
  - [ ] Inform about any UI changes
  - [ ] Demonstrate new features (if any)

- [ ] **Monitor production**
  - [ ] Watch logs for errors
  - [ ] Monitor file generation
  - [ ] Collect user feedback

- [ ] **Schedule follow-up**
  - [ ] 1 week: Check for issues
  - [ ] 1 month: Review performance
  - [ ] 3 months: Evaluate stability

---

## Rollback Plan (if needed)

- [ ] **Stop Odoo service**
  ```bash
  sudo systemctl stop odoo
  ```

- [ ] **Restore database backup**
  ```bash
  dropdb your_database
  createdb your_database
  psql your_database < backup_YYYYMMDD.sql
  ```

- [ ] **Restore Odoo 16 module**
  ```bash
  cp -r /backup/banco_de_occidente_payment_dispersal /path/to/odoo16/addons/
  ```

- [ ] **Start Odoo 16 service**
  ```bash
  sudo systemctl start odoo
  ```

- [ ] **Verify rollback successful**
  - [ ] Check module version
  - [ ] Test basic functionality
  - [ ] Verify data integrity

---

## Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Developer | | | |
| QA Tester | | | |
| System Admin | | | |
| Business Owner | | | |

---

## Notes & Issues

**Issues Found:**
1. 
2. 
3. 

**Resolutions:**
1. 
2. 
3. 

**Additional Comments:**


---

**Upgrade Completed:** ☐ Yes ☐ No  
**Date:** _______________  
**Odoo Version:** 17.0  
**Module Version:** 17.0.0.1
