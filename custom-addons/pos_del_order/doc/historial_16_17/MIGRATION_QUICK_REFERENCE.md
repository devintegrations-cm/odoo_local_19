# Quick Reference: Odoo 16 → 17 POS Module Patterns

## JavaScript Module Pattern

### Odoo 16 (AMD)
```javascript
odoo.define('module.Component', function(require) {
    const Component = require('point_of_sale.Component');
    const Registries = require('point_of_sale.Registries');
    
    const ComponentExtension = Component => class extends Component {
        myMethod() { }
    };
    
    Registries.Component.extend(Component, ComponentExtension);
    return Component;
});
```

### Odoo 17 (ES6)
```javascript
/** @odoo-module */
import { Component } from "@point_of_sale/app/component";
import { patch } from "@web/core/utils/patch";

patch(Component.prototype, {
    myMethod() { }
});
```

---

## Asset Declaration

### Odoo 16
```python
'assets': {
    'point_of_sale.assets': [
        'module/static/src/js/file.js',
        'module/static/src/xml/file.xml',
    ],
}
```

### Odoo 17
```python
'assets': {
    'point_of_sale._assets_pos': [
        'module/static/src/app/component/file.js',
        'module/static/src/app/component/file.xml',
    ],
}
```

---

## OWL Template Syntax

### Odoo 16
```xml
<t t-inherit="point_of_sale.Screen" t-inherit-mode="extension" owl="1">
    <xpath expr="//div" position="replace">
        <div t-if="condition1() &amp; condition2()" 
             t-on-click.stop="() => this.trigger('event', data)">
            <t t-if="env.isMobile">Text</t>
        </div>
    </xpath>
</t>
```

### Odoo 17
```xml
<t t-inherit="point_of_sale.Screen" t-inherit-mode="extension">
    <xpath expr="//div" position="replace">
        <div t-if="condition1() and condition2()" 
             t-on-click.stop="() => this.onEvent(data)">
            <t t-if="ui.isSmall">Text</t>
        </div>
    </xpath>
</t>
```

---

## POS API Access

### Odoo 16
```javascript
this.env.pos.cashier
this.env.pos.config
this.env.pos.orders
```

### Odoo 17
```javascript
this.pos.get_cashier()
this.pos.config
this.pos.get_order_list()
```

---

## Common Import Paths (Odoo 17)

```javascript
// Screens
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";

// Core utilities
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

// POS models
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { Order } from "@point_of_sale/app/store/models";
```
