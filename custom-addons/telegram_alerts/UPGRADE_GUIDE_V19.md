# Odoo 17 → 19 Upgrade Guide: Telegram Alerts Module

## Summary of Changes

This module has been upgraded from Odoo 17 to Odoo 19. The module is a backend-only module (no JavaScript/POS components). The main breaking change in Odoo 19 is the replacement of `<tree>` with `<list>` in XML views and the removal of the `numbercall` field from `ir.cron`.

---

## Files Modified

### 1. `__manifest__.py`

**Changes made:**
- Updated version from `17.0.1.0.0` to `19.0.1.0.0`

**Why:** Odoo 19 uses the same semantic versioning format: `{ODOO_VERSION}.{MAJOR}.{MINOR}.{PATCH}`

---

### 2. `views/telegram_alerts_views.xml`

**Changes made:**
- `<tree>` → `<list>` (line 8)
- `</tree>` → `</list>` (line 14)
- `view_mode`: `tree,form` → `list,form` (line 43)

**Why:** In Odoo 19, the `<tree>` view type has been completely removed and replaced with `<list>`. The error message when using `<tree>` is:

```
Tipo de vista no válido: "tree".
Los tipos permitidos son: list, form, graph, pivot, calendar, kanban, search, qweb, hierarchy, activity
```

The `view_mode` field on `ir.actions.act_window` must also use `list` instead of `tree`.

---

### 3. `data/server_actions.xml`

**Changes made:**
- Removed `<field name="numbercall">-1</field>` from the cron job record

**Why:** The `numbercall` field has been removed from `ir.cron` in Odoo 19. Crons now repeat indefinitely by default. To stop a cron, set `active=False` instead of using `numbercall=0`.

---

## Files That Didn't Need Changes

### Python Files
- `models/product_template.py` ✓
- `models/telegram_alerts.py` ✓
- `models/models.py` ✓
- `models/__init__.py` ✓
- `controllers/controllers.py` ✓
- `__init__.py` ✓

**Why no changes needed:**
- Python ORM patterns are compatible across versions
- `@api.constrains` decorator unchanged
- `product.template` model and `standard_price` field unchanged
- `requests` library available (v2.31.0)
- No `_sql_constraints` used (removed in Odoo 19)

### XML View Files
- `views/product_view.xml` ✓
- `views/views.xml` ✓ (all content is commented out)
- `views/templates.xml` ✓ (all content is commented out)

**Why no changes needed:**
- `product.product_template_only_form_view` view ID exists in Odoo 19
- `//group[@name='group_standard_price']` xpath target exists in Odoo 19
- Commented-out files have no runtime impact

### Other Files
- `security/ir.model.access.csv` ✓
- `data/telegram_config.xml` ✓
- `demo/demo.xml` ✓

---

## Key Odoo 19 Changes That Affected This Module

### 1. `<tree>` → `<list>` View Tag

**Odoo 17:**
```xml
<tree string="Telegram Alerts Configuration">
    <field name="identifier"/>
    ...
</tree>
```

**Odoo 19:**
```xml
<list string="Telegram Alerts Configuration">
    <field name="identifier"/>
    ...
</list>
```

This is a mandatory change. Using `<tree>` in Odoo 19 causes a `ParseError` during module installation.

### 2. `view_mode` Values

**Odoo 17:**
```xml
<field name="view_mode">tree,form</field>
```

**Odoo 19:**
```xml
<field name="view_mode">list,form</field>
```

### 3. `ir.cron` — `numbercall` Removed

**Odoo 17:**
```xml
<record id="scheduled_action" model="ir.cron">
    <field name="interval_number">1</field>
    <field name="interval_type">days</field>
    <field name="numbercall">-1</field>
    <field name="active" eval="True"/>
</record>
```

**Odoo 19:**
```xml
<record id="scheduled_action" model="ir.cron">
    <field name="interval_number">1</field>
    <field name="interval_type">days</field>
    <field name="active" eval="True"/>
</record>
```

In Odoo 19, crons repeat by default. To stop a cron, set `active=False`.

---

## Installation & Testing Checklist

### Pre-Installation
1. Backup your Odoo 17 database before upgrading
2. Ensure Odoo 19 is installed and running
3. Python `requests` library is included in Odoo 19's environment

### Installation Steps

1. **Copy the upgraded module to Odoo 19 addons directory:**
   ```bash
   cp -r telegram_alerts /path/to/odoo19/addons/
   ```

2. **Update the addons list:**
   ```bash
   odoo-bin -c /path/to/odoo.conf -u telegram_alerts -d your_database
   ```
   Or from the UI: Apps → Update Apps List

3. **Upgrade the module:**
   - Go to Apps
   - Remove "Apps" filter
   - Search for "Telegram Alerts"
   - Click "Upgrade"

### Testing Checklist

#### 1. Module Installation
- [ ] Module installs without errors
- [ ] No `ParseError` about `<tree>` tag
- [ ] No error about `numbercall` field

#### 2. Configuration Test
- [ ] Navigate to: Telegram Alerts → Configuration
- [ ] Verify the demo configuration record "Alertas Costos" exists with identifier `cost_alert`
- [ ] Create a new Telegram configuration
- [ ] Verify all fields are editable (name, identifier, token, user_ids, msg_test)

#### 3. Product Configuration Test
- [ ] Go to: Products → Products
- [ ] Open any product (type: Goods/consu)
- [ ] Verify new fields appear in the "Cost" section:
  - [ ] Reference Cost
  - [ ] Percentage Difference Cost
- [ ] Try setting Percentage Difference Cost to 1.5 (should fail with validation error)
- [ ] Set Percentage Difference Cost to 0.15 (should succeed)

#### 4. Server Actions Test
- [ ] Go to product list view
- [ ] Select one or more products
- [ ] Click "Action" dropdown
- [ ] Verify these actions appear:
  - [ ] "Calculate Difference Percentage"
  - [ ] "Send Cost Differences"
- [ ] Execute "Calculate Difference Percentage" (should attempt to send Telegram message)

#### 5. Telegram Alert Test
- [ ] Go to: Telegram Alerts → Configuration
- [ ] Open a configuration record
- [ ] Set a valid bot token and your chat_id in user_ids
- [ ] Click "Action" → "Send Telegram Alert"
- [ ] Verify test message is received in Telegram

#### 6. Scheduled Action Test
- [ ] Go to: Settings → Technical → Automation → Scheduled Actions
- [ ] Search for "Send Cost Differences"
- [ ] Verify the cron job exists and is active
- [ ] Verify `numbercall` field is NOT present (it shouldn't appear in the form)
- [ ] Check the next execution date is set
- [ ] Optionally: Click "Run Manually" to test immediate execution

#### 7. Cost Threshold Alert Test
- [ ] Create/edit a product with:
  - Standard Price (Cost): 100
  - Reference Cost: 120
  - Percentage Difference Cost: 0.10 (10%)
- [ ] Run "Send Cost Differences" action from list view
- [ ] Verify Telegram message is received with product details
- [ ] Message should show: product name, cost, and percentage difference

---

## Troubleshooting

**Issue:** `ParseError: Tipo de vista no válido: "tree"`
**Solution:** Replace all `<tree>` with `<list>` and `</tree>` with `</list>` in XML view files. Also update `view_mode` from `tree,form` to `list,form`.

**Issue:** Error about `numbercall` field
**Solution:** Remove `<field name="numbercall">` from all `ir.cron` records in XML data files.

**Issue:** Server actions don't appear in Action menu
**Solution:** Clear browser cache and refresh. Verify `binding_view_types` is set correctly to `list` or `list,form`.

**Issue:** Telegram messages not sending
**Solution:**
- Verify bot token is valid (test with @BotFather)
- Check user IDs are correct (use @userinfobot in Telegram to get your ID)
- Check server has internet access to `api.telegram.org`
- Review Odoo logs for error messages

**Issue:** Module won't upgrade
**Solution:**
- Check Odoo logs for specific errors
- Verify all XML files are valid (no syntax errors)
- Try: `odoo-bin -c config.conf -u telegram_alerts -d database --stop-after-init`

**Issue:** Validation error on percentage field
**Solution:** This is expected behavior. Value must be between 0 and 1 (e.g., 0.15 = 15%)

---

## Security Considerations

- The demo data includes a preconfigured Telegram bot token — **UPDATE THIS** with your own bot credentials in production
- Update `data/telegram_config.xml` with your own bot token and user IDs
- Consider restricting access to `telegram.alerts.config` model to admin users only (update `security/ir.model.access.csv`)

---

## Compatibility

- **Odoo Version:** 19.0
- **Python Version:** 3.10+
- **Dependencies:** `requests` library (included in Odoo 19)
- **Database:** PostgreSQL 12+

---

## Changelog

### Version 19.0.1.0.0
- Upgraded from Odoo 17 to Odoo 19
- Replaced `<tree>` with `<list>` in XML views (breaking change in Odoo 19)
- Updated `view_mode` from `tree,form` to `list,form`
- Removed `numbercall` field from cron job (removed in Odoo 19 `ir.cron`)
- All Python code compatible without changes
- All product template views compatible (xpath targets unchanged)

### Version 17.0.1.0.0
- Upgraded from Odoo 16 to Odoo 17
- Updated manifest to Odoo 17 standards
- Added `binding_view_types` to server actions
- Simplified cron job configuration
- Removed deprecated manifest keys
