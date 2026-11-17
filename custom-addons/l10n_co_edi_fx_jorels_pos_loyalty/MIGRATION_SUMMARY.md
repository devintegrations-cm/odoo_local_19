# Quick Migration Summary: Odoo 16 → 17

## Files Changed

### Modified Files
- ✅ `__manifest__.py` - Updated assets bundle and version
- ✅ `models/account_move.py` - Fixed deprecated fields and uncommented methods
- ✅ `models/pos_order_line.py` - Updated data loading for POS
- ✅ `models/pos_payment.py` - Uncommented payment method
- ✅ `static/src/js/models.js` - Converted to ES6 modules with patch()
- ✅ `static/src/js/payment_screen.js` - NEW: Rewritten for Odoo 17

### Deleted Files (Incompatible with Odoo 17)
- ❌ `static/src/js/PaymentScreen.js`
- ❌ `static/src/js/ExtendedPartnerDetailsEdit.js`
- ❌ `static/src/js/PartnerDetailsEdit.js`
- ❌ `static/src/xml/ExtendedPartnerDetailsEdit.xml`

### New Files
- ✨ `static/src/js/payment_screen.js` - Odoo 17 compatible version
- ✨ `static/src/xml/payment_screen.xml` - Placeholder template
- ✨ `UPGRADE_TO_V17.md` - Detailed upgrade guide
- ✨ `MIGRATION_SUMMARY.md` - This file

## Critical Changes

### 1. Assets Bundle (BREAKING)
```python
# OLD (Odoo 16)
'assets': {
    'point_of_sale.assets': [...]
}

# NEW (Odoo 17)
'assets': {
    'point_of_sale._assets_pos': [...]
}
```

### 2. JavaScript Modules (BREAKING)
```javascript
// OLD (Odoo 16)
odoo.define('module.name', function(require) {
    const Registries = require('point_of_sale.Registries');
    Registries.Model.extend(Orderline, MyOrderline);
});

// NEW (Odoo 17)
/** @odoo-module */
import { Orderline } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

patch(Orderline.prototype, {
    // Your methods
});
```

### 3. Account Types (BREAKING)
```python
# OLD (Odoo 16)
line.account_id.internal_type == 'receivable'

# NEW (Odoo 17)
line.account_id.account_type == 'asset_receivable'
```

### 4. POS Data Loading (BREAKING)
```python
# OLD (Odoo 16)
def _export_for_ui(self, orderline):
    result = super()._export_for_ui(orderline)
    result['my_field'] = orderline.my_field
    return result

# NEW (Odoo 17)
def _load_pos_data_fields(self, config_id):
    fields = super()._load_pos_data_fields(config_id)
    fields.extend(['my_field'])
    return fields
```

## Installation Command

```bash
# Upgrade module
odoo-bin -u l10n_co_edi_fx_jorels_pos_loyalty -d your_database

# Or with full path
/path/to/odoo-bin -u l10n_co_edi_fx_jorels_pos_loyalty -d your_database -c /path/to/odoo.conf
```

## Quick Test

1. Install/upgrade module
2. Clear browser cache (Ctrl+Shift+R)
3. Open POS
4. Check browser console for errors
5. Create order with loyalty reward
6. Validate order
7. Check invoice creation

## If Something Breaks

1. Check browser console (F12)
2. Check Odoo logs: `tail -f /var/log/odoo/odoo-server.log`
3. Verify dependencies are Odoo 17 versions
4. Clear assets: `odoo-bin --dev=all` or delete `~/.local/share/Odoo/filestore/[db]/assets/`

## Key Odoo 17 Patterns

### Import Statements
```javascript
import { Component } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { Order } from "@point_of_sale/app/store/models";
```

### Patching Components
```javascript
patch(ComponentName.prototype, {
    setup() {
        super.setup(...arguments);
        // Your code
    },
    
    myMethod() {
        // Your code
        return super.myMethod(...arguments);
    }
});
```

### Popup API
```javascript
// OLD
await this.showPopup('PopupName', { options });

// NEW
await this.popup.add('PopupName', { options });
```

## Status: ✅ READY FOR TESTING

All critical changes implemented. Module should work in Odoo 17.
