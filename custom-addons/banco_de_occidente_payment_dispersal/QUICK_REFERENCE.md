# Quick Reference - Odoo 17 Upgrade

## What Changed?

### ✅ 3 Files Modified
1. `__manifest__.py` - Version updated to 17.0.0.1
2. `models/account_payment.py` - Removed deprecated `type` field check
3. `views/bancodeoccidente_payment_dispersal_fields_views.xml` - Updated XML syntax

### ✅ 10 Files Unchanged (Compatible)
All other files work as-is in Odoo 17

---

## Key Breaking Changes in Odoo 17

| What Changed | Odoo 16 | Odoo 17 |
|--------------|---------|---------|
| **Payment type field** | `payment.type == 'bank'` | Field removed, use `payment_method_line_id` |
| **View attrs** | `attrs="{'invisible': [...]}"` | `invisible="field_name"` |
| **View type** | `<field name="type">form</field>` | Auto-detected, remove attribute |
| **Bootstrap classes** | `bg-danger` | `text-bg-danger` |

---

## Installation Command

```bash
./odoo-bin -c odoo.conf -u banco_de_occidente_payment_dispersal -d your_database
```

---

## Quick Test

1. ✅ Module upgrades without errors
2. ✅ Menu: Accounting → Payment Dispersal → Configurations Banco de Occidente
3. ✅ Create vendor payment with bank account
4. ✅ Generate dispersal file (Action menu)
5. ✅ Download and verify TXT file format

---

## If Something Breaks

**Most likely issue:** Dependency module `account_payment_dispersion` not upgraded

**Solution:** Upgrade dependency first:
```bash
./odoo-bin -c odoo.conf -u account_payment_dispersion -d your_database
```

---

## Documentation

- Full details: `UPGRADE_GUIDE_V17.md`
- Changes list: `CHANGES_SUMMARY.md`
